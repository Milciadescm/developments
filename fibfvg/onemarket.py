"""One market at a time, every bot, $5,000 real, never skip: a trade too small for 0.01 lot opens at 0.01.

The real risk of a bumped trade is then larger than the % asked; the table shows the average and the largest
risk actually taken per trade. Period Jul 2024 -> Nov 2026 (hourly data), last 12 months shown apart.
Bots: A 24-hour prop setups, B holding (adds, chandelier, breakeven 2R), D weekly Turtle, E midnight -> 14:00.
    python -m fibfvg.onemarket -> results/onemarket.json
"""
import json

import numpy as np
import pandas as pd

from . import propsim
from .config import SYMBOLS
from .engines import load, net_r
from .plans import position_engine
from .prop24 import build as prop_build
from .propsim import Account, run
from .swaps import with_swaps
from .livefund import monthly, max_dd
from .threeway import weekly, PIP
from .midnight import days_of as mdays
from .goldsilver import trade as gtrade
from .candle10 import NOW
from . import scoreboard  # registers the BE2 holding mode
from .engines import Trade

START = pd.Timestamp("2024-07-01", tz="UTC")
Y1 = NOW - pd.Timedelta(days=365)
SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
CAP = 5_000


def midnight_trades(sym):
    out = []
    for day in mdays(sym):
        t = gtrade(day, sym, 0.75, True)
        if t is None:
            continue
        d = t["date"]; d = d.tz_convert("UTC") if d.tzinfo else d.tz_localize("UTC")
        x = Trade(sym, "position", t["dir"], d, t["entry"], t["entry"] - t["dir"] * t["stop_pips"] * PIP[sym])
        x.exits = [(d + pd.Timedelta(hours=14), t["exit"], 1.0)]; x.plan = "Plan 1"
        out.append(x)
    return out


def account(tr, risk, start):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    o = run(tr, Account("Real", CAP, 0.0, None, None, real=True, payout_days=None), "X", start=start)
    m = monthly(o["curve"], CAP) if o["curve"] else []
    rk = [f["risk_usd"] / f["equity"] * 100 for f in o["fills"] if f["equity"] > 0]
    return dict(end=round(o["end_balance"]), pct=round((o["end_balance"] / CAP - 1) * 100, 1),
                dd=round(max_dd(m) * 100, 1) if len(m) else 0.0, trades=o["trades"],
                avg_risk=round(float(np.mean(rk)), 2) if rk else 0, max_risk=round(float(np.max(rk)), 2) if rk else 0)


def main():
    propsim.BUMP_MIN_LOT = True
    a, b = prop_build()
    bots = {"A 24-hour": (lambda s: [t for t in a + b if t.symbol == s], 0.009),
            "B Holding": (lambda s: _hold(s), 0.005),
            "D Weekly Turtle": (lambda s: weekly(s, load(f"data/{s}_D1.csv"), add_only_in_profit=True, runner="trail"), 0.02),
            "E Midnight": (midnight_trades, 0.009)}
    out = {}
    for bot, (make, risk) in bots.items():
        for s in SYMBOLS:
            try:
                tr = sorted(make(s), key=lambda t: t.entry_time)
            except Exception as e:  # market without the data this bot needs
                out[f"{bot} | {s}"] = dict(error=str(e)[:80]); continue
            r = np.array([net_r(t) for t in tr if t.entry_time >= START])
            if len(r) < 5:
                out[f"{bot} | {s}"] = dict(setups=len(r)); continue
            h1 = np.array([net_r(t) for t in tr if START <= t.entry_time < SPLIT]); h2 = np.array([net_r(t) for t in tr if t.entry_time >= SPLIT])
            row = dict(setups=len(r), win=round(float((r > 0).mean() * 100)), avg_R=round(float(r.mean()), 2),
                       t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 1),
                       halves=[round(float(h1.mean()), 2) if len(h1) else None, round(float(h2.mean()), 2) if len(h2) else None],
                       risk_asked=risk * 100, full=account(tr, risk, START), last12=account(tr, risk, Y1))
            out[f"{bot} | {s}"] = row
            print(bot, s, json.dumps(row))
    json.dump(out, open("results/onemarket.json", "w"), indent=1)


def _hold(s):
    tr = with_swaps(position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= pd.Timestamp("2024-01-01", tz="UTC")], "BE2", start="2024-01-01"))
    for t in tr:
        t.plan = "Plan 1"
    return tr


if __name__ == "__main__":
    main()

"""One scoreboard: every strategy still alive, same $5,000, same period, bug-fixed code.

Period: Jul 2024 -> Nov 2026 (the hourly data), plus 2006 -> 2026 where daily data allows it.
Real money: $5,000, compounding, broker minimum 0.01 lot (a trade that would need more risk is skipped).
Prop: GFT Instant Premium $5K ($74 fee): 6% trailing, 1% floating limit (one trade at 0.9%), 5 profitable days
of +0.5% per payout, 80% split.
Strategies:
  A  24-hour prop bot (Prop24): BTC, S&P, Nasdaq; daily + 4-hour pullback setups; flat within 24 h.
  B  Holding bot, all 5 markets: daily pullback setup, adds to winners, chandelier trail, breakeven at 2R.
  C  Holding bot, gold + silver only.
  D  Weekly Turtle, silver + BTC: Monday entry, Tue/Wed adds, Friday close, runner with 20-day trail.
  E  Gold midnight -> 14:00 (stop 0.75 daily range, breakeven at half the stop).
    python -m fibfvg.scoreboard -> results/scoreboard.json
"""
import json

import numpy as np
import pandas as pd

from . import plans, propsim
from .config import SYMBOLS
from .engines import load, net_r
from .plans import position_engine
from .prop24 import build as prop_build
from .propsim import Account, run
from .swaps import with_swaps
from .longhold import load_long
from .livefund import monthly, max_dd
from .threeway import weekly
from .midnight import days_of as mdays
from .goldsilver import trade as gtrade
from .candle10 import gft, NOW

plans.POS_MODES["BE2"] = dict(tp1=False, tp2=False, trail="chand3", be_at=2.0, time_stop=(10, 0.5))
H_START = pd.Timestamp("2024-07-01", tz="UTC")
Y1 = NOW - pd.Timedelta(days=365)


def real(tr, cap, risk, start, end=None):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    o = run(tr, Account("Real", cap, 0.0, None, None, real=True, payout_days=None), "X", start=start, end=end)
    m = monthly(o["curve"], cap)
    yrs = max(len(m) / 12, 0.1)
    return dict(end=round(o["end_balance"]), total_pct=round((o["end_balance"] / cap - 1) * 100, 1),
                per_year_pct=round(((o["end_balance"] / cap) ** (1 / yrs) - 1) * 100, 1), worst_drawdown_pct=round(max_dd(m) * 100, 1),
                trades=o["trades"], skipped_min_lot=o["skipped_min_lot"])


def to_trades(sym, ts):
    """gold-midnight dicts -> Trade objects for the account simulator"""
    from .engines import Trade
    out = []
    for t in ts:
        e = t["entry"]; d = t["dir"]; stop = e - d * t["stop_pips"] * 0.1
        x = Trade(sym, "position", d, t["date"].tz_convert("UTC") if t["date"].tzinfo else t["date"].tz_localize("UTC"), e, stop)
        x.exits = [(x.entry_time + pd.Timedelta(hours=14), t["exit"], 1.0)]; x.plan = "Plan 1"
        out.append(x)
    return out


def main():
    out = {}
    a, b = prop_build()
    A = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    S0 = pd.Timestamp("2024-01-01", tz="UTC")
    B = with_swaps([t for s in SYMBOLS for t in position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= S0], "BE2", start="2024-01-01")])
    for t in B:
        t.plan = "Plan 1"
    C = [t for t in B if t.symbol in ("XAUUSD", "XAGUSD")]
    D = [t for s in ("XAGUSD", "BTCUSD") for t in weekly(s, load(f"data/{s}_D1.csv"), add_only_in_profit=True, runner="trail")]
    gd = mdays("XAUUSD")
    E = to_trades("XAUUSD", [t for day in gd if (t := gtrade(day, "XAUUSD", 0.75, True)) is not None])
    rows = {"A 24-hour prop bot": (A, (0.009,)), "B Holding bot, 5 markets": (B, (0.005, 0.01)),
            "C Holding bot, gold + silver": (C, (0.005, 0.01)), "D Weekly Turtle, silver + BTC": (D, (0.02, 0.05)),
            "E Gold midnight": (E, (0.009,))}
    for name, (tr, risks) in rows.items():
        r = np.array([net_r(t) for t in tr if t.entry_time >= H_START])
        out[name] = dict(trades_per_month=round(len(r) / 29, 1), win_rate=round(float((r > 0).mean() * 100), 1),
                         avg_R=round(float(r.mean()), 3), real={})
        for risk in risks:
            full = real(tr, 5_000, risk, H_START); last = real(tr, 5_000, risk, Y1)
            out[name]["real"][f"{risk * 100:.1f}%"] = dict(jul2024_to_now=full, last_12_months=last)
        print(name, json.dumps(out[name]))
    # prop $5K GFT for A and E (one trade at a time, 0.9%)
    for name, tr in (("A 24-hour prop bot", A), ("E Gold midnight", E)):
        ts = [dict(date=t.entry_time, R=net_r(t)) for t in tr if t.entry_time >= H_START]
        days = {}
        for t in ts:
            days.setdefault(t["date"].normalize(), []).append(t)
        one = [v[0] for v in days.values()]
        p = gft(one, risk=0.009); l = gft(one, risk=0.009, start=Y1, end=NOW)
        scale = 5_000 / 100_000
        out[name]["prop_gft_5k"] = dict(fee=74, paid_jul2024_to_now=round(p["paid"] * scale), payouts=p["payouts"], breach=p["breach"],
                                         paid_last_12_months=round(l["paid"] * scale))
        print(name, "GFT $5K prop:", out[name]["prop_gft_5k"])
    # 20 years where daily data allows
    out["20_years_real_5k"] = {}
    for name, mk in (("B Holding bot, 5 markets", SYMBOLS), ("C Holding bot, gold + silver", ("XAUUSD", "XAGUSD"))):
        tr = with_swaps([t for s in mk for t in position_engine(s, load_long(s), "BE2", start="2006-01-01")])
        for t in tr:
            t.plan = "Plan 1"
        out["20_years_real_5k"][name] = {f"{r * 100:.1f}%": real(tr, 5_000, r, pd.Timestamp("2006-01-01", tz="UTC")) for r in (0.005, 0.01)}
        print("20 years", name, out["20_years_real_5k"][name])
    json.dump(out, open("results/scoreboard.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

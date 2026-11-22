"""Wallet 2: how long may Cueto & Co. real money hold a trade? Gold and silver, 2005-2026 (futures history).

Same entries as bot v3 (position plan). Exits compared, all with swaps charged (5%/yr of the position's value
for every calendar day held):
  P2 chandelier : current bot (breakeven at +1R, trail 3 daily ranges, 10-day time stop) - holds days to weeks
  P1 run20      : breakeven at +1R, trail the 20-day low                                 - weeks to months
  P3 monthly    : half at the -0.272 extension, rest trails the 55-day low                 - months
  Y1 year       : breakeven at +1R, trail the 120-day low (about 6 months of candles)     - up to a year or more
Judged on the 4 checks (R per trade after fees, both halves positive, t >= 2, drawdown on real money).
    python -m fibfvg.longhold -> results/longhold.json
"""
import json

import numpy as np
import pandas as pd

from . import plans, propsim
from .engines import net_r
from .plans import position_engine
from .propsim import Account, run
from .swaps import with_swaps
from .livefund import monthly, max_dd, bootstrap

plans.POS_MODES["Y1 year"] = dict(tp1=False, tp2=False, trail="d120", be_at=1.0, time_stop=None)
SYMS = ("XAUUSD", "XAGUSD")
START = pd.Timestamp("2006-01-01", tz="UTC")
SPLIT = pd.Timestamp("2016-01-01", tz="UTC")


def load_long(sym):
    j = json.load(open(f"data/long/{sym}.json"))["chart"]["result"][0]
    q = j["indicators"]["quote"][0]
    df = pd.DataFrame(dict(Open=q["open"], High=q["high"], Low=q["low"], Close=q["close"]),
                      index=pd.to_datetime(j["timestamp"], unit="s", utc=True).normalize())
    df = df.dropna(); df = df[(df.High >= df.Low) & (df.Low > 0)]
    return df[~df.index.duplicated()].sort_index()


def main():
    out = {}
    for mode in ("P2 chandelier", "P1 run20", "P3 monthly", "Y1 year"):
        tr = []
        for s in SYMS:
            d = load_long(s)
            tr += position_engine(s, d, mode, start="2006-01-01")
        for t in tr:
            t.plan = "Plan 1"
        tr = with_swaps(tr)
        r = np.array([net_r(t) for t in tr])
        a = np.array([net_r(t) for t in tr if t.entry_time < SPLIT]); b = np.array([net_r(t) for t in tr if t.entry_time >= SPLIT])
        w, l = r[r > 0], r[r <= 0]
        hold = np.array([(t.exit_time - t.entry_time).days for t in tr])
        row = dict(trades=len(r), win=round(float((r > 0).mean() * 100), 1), rr=round(float(w.mean() / -l.mean()), 2),
                   net=round(float(r.mean()), 3), first=round(float(a.mean()), 3), second=round(float(b.mean()), 3),
                   t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2),
                   median_hold_days=int(np.median(hold)), max_hold_days=int(hold.max()), real={})
        for risk in (0.005, 0.01):
            propsim.MODES["X"] = dict(p1=risk, p3=risk)
            for cap in (25_000, 100_000, 250_000):
                o = run(tr, Account("Live", cap, 0.0, None, None, real=True), "X", start=START)
                m = monthly(o["curve"], cap)
                yrs = len(m) / 12
                row["real"][f"{risk * 100:.1f}% ${cap // 1000}K"] = dict(
                    cagr=round(((o["end_balance"] / cap) ** (1 / yrs) - 1) * 100, 1), max_dd=round(max_dd(m) * 100, 1),
                    skipped=o["skipped_min_lot"], taken=o["trades"],
                    worst_12m=round(float(min(np.prod(1 + m[i:i + 12]) - 1 for i in range(len(m) - 11)) * 100), 1),
                    years_down=round(float(np.mean([np.prod(1 + m[i:i + 12]) - 1 < 0 for i in range(0, len(m) - 11, 12)]) * 100), 1),
                    **{k: v for k, v in bootstrap(m).items() if k in ("p_loss_12m", "median_12m", "dd_p99")})
        out[mode] = row
        print(mode, {k: v for k, v in row.items() if k != "real"})
        for k, v in row["real"].items():
            print("   ", k, v)
    json.dump(out, open("results/longhold.json", "w"), indent=1)


if __name__ == "__main__":
    main()

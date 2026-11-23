"""When should the holding plan move its stop to breakeven? (position plan, adds to winners, chandelier exit)

Breakeven trigger as a share of the stop distance (R): 0.05R (about 10 pips on gold: the stop is ~$50-100),
0.25R, 0.5R, 1.0R (current rule), 2.0R. Daily candles, so a trigger is seen at the day's high and acted on from
the next day. Swaps charged. Two periods: 2024-2026 (recent) and 2006-2026 (20 years, futures/index history).
Real money $5,000 and $25,000 at 1% per unit: growth and worst drawdown, broker minimum lot respected.
    python -m fibfvg.betest -> results/betest.json
"""
import json

import numpy as np
import pandas as pd

from . import plans, propsim
from .config import SYMBOLS
from .engines import load, net_r
from .plans import position_engine
from .propsim import Account, run
from .swaps import with_swaps
from .longhold import load_long
from .livefund import monthly, max_dd

SPLIT_R = pd.Timestamp("2025-08-19", tz="UTC")
SPLIT_L = pd.Timestamp("2016-01-01", tz="UTC")


def main():
    out = {}
    for be in (0.05, 0.25, 0.5, 1.0, 2.0):
        name = f"BE{be}"
        plans.POS_MODES[name] = dict(tp1=False, tp2=False, trail="chand3", be_at=be, time_stop=(10, 0.5))
        for period, loader, start, split in (("2024-2026", lambda s: load(f"data/{s}_D1.csv"), "2024-01-01", SPLIT_R),
                                             ("2006-2026", load_long, "2006-01-01", SPLIT_L)):
            tr = []
            for s in SYMBOLS:
                d = loader(s); d = d[d.index >= pd.Timestamp(start, tz="UTC")]
                tr += position_engine(s, d, name, start=start)
            for t in tr:
                t.plan = "Plan 1"
            tr = with_swaps(tr)
            r = np.array([net_r(t) for t in tr])
            a = np.array([net_r(t) for t in tr if t.entry_time < split]); b = np.array([net_r(t) for t in tr if t.entry_time >= split])
            row = dict(n=len(r), win=round(float((r > 0).mean() * 100), 1), rr=round(float(r[r > 0].mean() / -r[r <= 0].mean()), 2),
                       net_R=round(float(r.mean()), 3), first=round(float(a.mean()), 3), second=round(float(b.mean()), 3),
                       t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2))
            for cap in (5_000, 25_000):
                propsim.MODES["X"] = dict(p1=0.01, p3=0.01)
                o = run(tr, Account("Real", cap, 0.0, None, None, real=True, payout_days=None), "X", start=pd.Timestamp(start, tz="UTC"))
                m = monthly(o["curve"], cap)
                yrs = max(len(m) / 12, 0.1)
                row[f"${cap // 1000}K at 1%"] = dict(end=round(o["end_balance"]), per_year=round(((o["end_balance"] / cap) ** (1 / yrs) - 1) * 100, 1),
                                                     max_dd=round(max_dd(m) * 100, 1), skipped=o["skipped_min_lot"], taken=o["trades"])
            out[f"breakeven at {be}R | {period}"] = row
            print(f"breakeven at {be}R | {period}: {row}")
    json.dump(out, open("results/betest.json", "w"), indent=1)


if __name__ == "__main__":
    main()

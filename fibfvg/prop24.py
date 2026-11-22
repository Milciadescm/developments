"""Prop plan under the 24-hour rule: both setups that passed the first-half choice, combined.
  A = daily setups, Fib 1.0 stop, TP 1R, flat within 24 h        (intraday24 choice)
  B = 4-hour setups, Fib 1.0 stop, flat 24 h after the fill        (fractal24 choice)
Runs: stats, one $100K FundedNext instant account at 0.25-1.0% risk from every start month (12 months each),
and the full period.
    python -m fibfvg.prop24 -> results/prop24.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .levels import load_sym
from . import propsim
from .propsim import run
from .intraday24 import FN100, fill, replay, setups, START
from .fractal24 import engine, stats


def build():
    data = {s: load_sym(s) for s in SYMBOLS}
    a = []
    for t in setups():
        j, e = fill(t, data[t.symbol][1])
        if j is not None and (x := replay(t, data[t.symbol][1], j, e, "S1 Fib 1.0", "E2 TP 1R")) is not None:
            a.append(x)
    b = [t for s, (d, h) in data.items() for t in engine(s, d, h, "H4", "S1 Fib 1.0", "X4 time only")]
    return a, b


def main():
    a, b = build()
    allx = sorted(a + b, key=lambda t: t.entry_time)
    out = dict(A_daily=stats(a), B_4h=stats(b), combined=stats(allx), prop_100k={})
    print("combined", out["combined"])
    starts = pd.date_range("2024-03-01", "2025-11-01", freq="MS", tz="UTC")
    for r in (0.0025, 0.005, 0.0075, 0.01):
        propsim.MODES["X"] = dict(p1=r, p3=r)
        p12, dds, br = [], [], 0
        for s0 in starts:
            o = run(allx, FN100, "X", start=s0, end=s0 + pd.Timedelta(days=365))
            p12.append(o["paid_to_trader"]); dds.append(o["worst_dd_pct"]); br += bool(o["breach"])
        full = run(allx, FN100, "X", start=START)
        months = (allx[-1].entry_time - START).days / 30.44
        out["prop_100k"][f"{r * 100:.2f}%"] = dict(
            full_paid=round(full["paid_to_trader"]), per_month=round(full["paid_to_trader"] / months), full_dd=full["worst_dd_pct"],
            breach=full["breach"], trades=full["trades"], median_12m=round(float(np.median(p12))), worst_12m=round(float(min(p12))),
            best_12m=round(float(max(p12))), zero_years=int(sum(p <= 0 for p in p12)), breaches=br, starts=len(starts),
            worst_dd=round(float(max(dds)), 2))
        print(r, out["prop_100k"][f"{r * 100:.2f}%"])
    json.dump(out, open("results/prop24.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()

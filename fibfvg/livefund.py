"""Wallet 2: Cueto & Co. real funds. When is there enough money to start the bot, and at what risk,
so the fund is very unlikely to lose and very likely to grow?

Bot : position plan (holds allowed on real money), chandelier exit, Turtle adds, swaps charged.
Test: real account sized on its own balance (compounding), capital $5K-$250K, risk 0.25-1.0% per unit.
      Minimum-lot check: trades the broker's 0.01 lot cannot size small enough are skipped (never oversized).
Risk: 20,000 one-year paths from 3-month blocks of the real monthly returns (block bootstrap).
    python -m fibfvg.livefund -> results/livefund.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import load
from .plans import position_engine
from . import propsim
from .propsim import Account, run
from .swaps import with_swaps

START = pd.Timestamp("2024-01-01", tz="UTC")
CAPS = (5_000, 10_000, 25_000, 50_000, 100_000, 250_000)
RISKS = (0.0025, 0.005, 0.0075, 0.01)


def trades():
    out = []
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv"); d = d[d.index >= START]
        out += position_engine(s, d, "P2 chandelier", start="2024-01-01")
    for t in out:
        t.plan = "Plan 1"
    return with_swaps(out)


def monthly(curve, cap):
    s = pd.Series([b for _, b in curve], index=pd.to_datetime([a for a, _ in curve], unit="s", utc=True))
    s = pd.concat([pd.Series([cap], index=[START]), s]).groupby(level=0).last()
    m = s.resample("ME").last().ffill()
    return m.pct_change().fillna(m.iloc[0] / cap - 1).values


def max_dd(path):
    eq = np.cumprod(1 + path); pk = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float(((pk - eq) / pk).max())


def bootstrap(rets, n=20_000, months=12, block=3, seed=7):
    rng = np.random.default_rng(seed)
    k = len(rets) - block + 1
    ends, dds = np.empty(n), np.empty(n)
    for i in range(n):
        p = np.concatenate([rets[j:j + block] for j in rng.integers(0, k, months // block)])
        ends[i] = np.prod(1 + p) - 1; dds[i] = max_dd(p)
    return dict(p_loss_12m=round(float((ends < 0).mean() * 100), 1), p_loss_over_10=round(float((ends < -0.10).mean() * 100), 2),
                median_12m=round(float(np.median(ends) * 100), 1), p5_12m=round(float(np.percentile(ends, 5) * 100), 1),
                p1_12m=round(float(np.percentile(ends, 1) * 100), 1), dd_p95=round(float(np.percentile(dds, 95) * 100), 1),
                dd_p99=round(float(np.percentile(dds, 99) * 100), 1))


def main():
    tr = trades()
    out = dict(grid=[], risk=[])
    for r in RISKS:
        propsim.MODES["X"] = dict(p1=r, p3=r)
        for cap in CAPS:
            o = run(tr, Account("Live", cap, 0.0, None, None, real=True), "X", start=START)
            rets = monthly(o["curve"], cap)
            yrs = len(rets) / 12
            row = dict(risk=r * 100, cap=cap, end=o["end_balance"], cagr=round(((o["end_balance"] / cap) ** (1 / yrs) - 1) * 100, 1),
                       max_dd=round(max_dd(rets) * 100, 1), taken=o["trades"], skipped_min_lot=o["skipped_min_lot"],
                       months_up=round(float((rets > 0).mean() * 100)), worst_month=round(float(rets.min() * 100), 1))
            out["grid"].append(row)
            print(row)
            if cap == 100_000:
                b = bootstrap(rets); b["risk"] = r * 100
                out["risk"].append(b); print("   bootstrap", b)
    json.dump(out, open("results/livefund.json", "w"), indent=1)


if __name__ == "__main__":
    main()

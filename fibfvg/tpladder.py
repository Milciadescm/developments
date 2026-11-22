"""TP ladder test: TP1 = 100 pips ... TP5 = 500 pips (20% closed at each), no month-long holds.
Entries: the position plan's real entries (daily) and the levels plan's (hourly). Stops as in each plan.
Variants: stop to breakeven after TP1 or not; max hold 5 or 10 days. Spread and estimated swaps charged.
    python -m fibfvg.tpladder -> results/tpladder.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .edgebook import build
from .levels import load_sym
from .swaps import RATE

PIP = {"XAUUSD": 0.1, "XAGUSD": 0.01, "BTCUSD": 1.0, "US500": 0.1, "NAS100": 0.1}
SPLIT = pd.Timestamp("2025-08-19", tz="UTC")


def replay(t, h1, be_after_tp1, max_days, ladder=(100, 200, 300, 400, 500)):
    d = t.direction; e = t.entry; s = t.stop; pip = PIP[t.symbol]
    i0 = int(h1.index.searchsorted(t.entry_time))
    H, L, C = h1.High.values, h1.Low.values, h1.Close.values
    tps = [e + d * k * pip for k in ladder]
    left, pnl, k, stop = 1.0, 0.0, 0, s
    end = h1.index[min(len(C) - 1, i0)] + pd.Timedelta(days=max_days)
    j = i0
    for j in range(i0, len(C)):
        if h1.index[j] > end:
            break
        lo, hi = (L[j], H[j]) if d == 1 else (-H[j], -L[j])
        if lo <= d * stop:                                     # stop first (conservative)
            pnl += left * (stop - e) * d; left = 0; break
        while k < len(tps) and hi >= d * tps[k]:
            pnl += 0.2 * (tps[k] - e) * d; left -= 0.2; k += 1
            if k == 1 and be_after_tp1:
                stop = e
        if left <= 1e-9:
            break
    if left > 1e-9:
        pnl += left * (C[min(j, len(C) - 1)] - e) * d
    days = (h1.index[min(j, len(C) - 1)] - t.entry_time).total_seconds() / 86400
    risk = abs(e - s)
    swap = abs(e) * RATE[t.symbol] * max(days, 0) / 365 * 0.6       # ~60% of size open on average
    return (pnl - SYMBOLS[t.symbol].spread - swap) / risk, risk / pip


def main():
    data = {s: load_sym(s) for s in SYMBOLS}
    _, P = build()
    out = {}
    for plan, tr in (("Position plan entries", [t for t in P["Plan 1 Position"] if t.engine == "position"]),
                     ("Levels plan entries", [t for t in P["Plan 3 Levels"] if t.engine == "levels"])):
        stops = {s: float(np.median([abs(t.entry - t.stop) / PIP[s] for t in tr if t.symbol == s])) for s in SYMBOLS}
        print(plan, "median stop in pips:", {k: round(v) for k, v in stops.items()})
        for be in (False, True):
            for md in (5, 10):
                rs = []; rows = []
                for t in tr:
                    r, sp = replay(t, data[t.symbol][1], be, md)
                    rs.append(r); rows.append((t.symbol, t.entry_time, r))
                rs = np.array(rs)
                a = np.array([r for s_, tt, r in rows if tt < SPLIT]); b = np.array([r for s_, tt, r in rows if tt >= SPLIT])
                key = f"{plan} | BE after TP1={be} | max {md} days"
                out[key] = dict(n=len(rs), mean=round(float(rs.mean()), 3), first=round(float(a.mean()), 3), second=round(float(b.mean()), 3),
                                win=round(float((rs > 0).mean() * 100), 1),
                                by_sym={s: round(float(np.mean([r for s_, tt, r in rows if s_ == s])), 3) for s in SYMBOLS},
                                median_stop_pips={k: round(v) for k, v in stops.items()})
                print(" ", key, out[key]["mean"], out[key]["first"], out[key]["second"], "win", out[key]["win"], out[key]["by_sym"])
    json.dump(out, open("results/tpladder.json", "w"), indent=1)


if __name__ == "__main__":
    main()

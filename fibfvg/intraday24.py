"""Prop rule: no trade held longer than 24 hours (and none over the weekend).

Entries : the position plan's real setups (monthly + weekly bias, 20-day breakout leg with a daily FVG,
          limit at the 0.705 Fibonacci level). The fill hour is found on the 1-hour chart.
Stops   : S0 = plan stop (leg origin - 0.25N), S1 = Fib 1.0 (leg origin), S2 = Fib 0.886.
Exits   : all closed at 24 h after the fill or at the Friday 16:00 New York close, whichever is first.
          E1 time only | E2 TP 1R | E3 TP 2R | E4 breakeven at +1R, then time
          E5 TP at the leg extreme (Fib 0) | E6 pip ladder 100..500 (20% each)
Choice  : best mean R on the first half (before 2025-08-19); judged on the second half.
Then    : the chosen version on one $100K instant account (6% trailing max loss, guard 5%) at 0.25-1.0% risk.
    python -m fibfvg.intraday24 -> results/intraday24.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import Trade, load
from .levels import load_sym
from .plans import position_engine
from . import propsim
from .propsim import Account, run
from .swaps import RATE

START = pd.Timestamp("2024-01-01", tz="UTC")
SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
PIP = {"XAUUSD": 0.1, "XAGUSD": 0.01, "BTCUSD": 1.0, "US500": 0.1, "NAS100": 0.1}
STOPS = ("S0 plan stop", "S1 Fib 1.0", "S2 Fib 0.886")
EXITS = ("E1 time only", "E2 TP 1R", "E3 TP 2R", "E4 BE at +1R", "E5 TP leg extreme", "E6 pip ladder")
FN100 = Account("FundedNext instant", 100_000, 740.0, None, 0.06)


def setups():
    out = []
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv"); d = d[d.index >= START]
        out += [t for t in position_engine(s, d, "P2 chandelier", start="2024-01-01") if t.engine == "position"]
    return out


def friday_close(ts):
    ny = ts.tz_convert("America/New_York")
    fri = (ny + pd.Timedelta(days=(4 - ny.dayofweek) % 7)).normalize() + pd.Timedelta(hours=16)
    if fri <= ny:
        fri += pd.Timedelta(days=7)
    return fri.tz_convert("UTC")


def fill(t, h1):
    """first 1-hour bar on the setup's fill day that trades through the limit."""
    day0 = (t.entry_time - pd.Timedelta(hours=12)).normalize()
    m = (h1.index >= day0) & (h1.index < day0 + pd.Timedelta(hours=30))
    idx = np.flatnonzero(m)
    d, e = t.direction, t.entry
    for j in idx:
        lo = h1.Low.values[j] if d == 1 else -h1.High.values[j]
        if lo <= d * e:
            o = h1.Open.values[j]
            return j, (min(o, e) if d == 1 else max(o, e))
    return None, None


def replay(t, h1, j0, e, stop_kind, exit_kind):
    d = t.direction; spec = SYMBOLS[t.symbol]
    lo_, hi_ = t.leg["lo"], t.leg["hi"]; rng = hi_ - lo_
    ext = hi_ if d == 1 else lo_
    if stop_kind == "S0 plan stop":
        s = t.stop
    elif stop_kind == "S1 Fib 1.0":
        s = ext - d * rng
    else:
        s = ext - d * 0.886 * rng
    risk = (e - s) * d
    if risk <= 3 * spec.spread:
        return None
    t0 = h1.index[j0]
    end = min(t0 + pd.Timedelta(hours=24), friday_close(t0))
    H, L, C, T = h1.High.values, h1.Low.values, h1.Close.values, h1.index
    if exit_kind == "E6 pip ladder":
        tps = [e + d * k * PIP[t.symbol] for k in (100, 200, 300, 400, 500)]
    elif exit_kind == "E2 TP 1R":
        tps = [e + d * risk]
    elif exit_kind == "E3 TP 2R":
        tps = [e + d * 2 * risk]
    elif exit_kind == "E5 TP leg extreme":
        tps = [ext]
    else:
        tps = []
    part = 1.0 / len(tps) if tps else 0
    left, pnl, k, stop = 1.0, 0.0, 0, s
    j = j0; last = j0
    for j in range(j0, len(C)):
        if T[j] >= end:
            break
        last = j
        lo, hi = (L[j], H[j]) if d == 1 else (-H[j], -L[j])
        if j > j0 or True:
            if lo <= d * stop:
                pnl += left * (stop - e) * d; left = 0; break
        while j > j0 and k < len(tps) and hi >= d * tps[k]:   # fill candle: only the stop counts
            pnl += part * (tps[k] - e) * d; left -= part; k += 1
        if exit_kind == "E4 BE at +1R" and j > j0 and hi >= d * (e + d * risk):
            stop = e
        if left <= 1e-9:
            break
    xt = T[last] + pd.Timedelta(hours=1)
    if left > 1e-9:
        pnl += left * (C[last] - e) * d
    hours = (xt - t0).total_seconds() / 3600
    swap = abs(e) * RATE[t.symbol] * (1 if hours > 6 else 0) / 365     # at most one rollover
    net_px = pnl - spec.spread - swap
    x = Trade(t.symbol, "position", d, t0, e, s, pos_id=f"{t.pos_id}-24")
    x.exits = [(xt, e + d * net_px + spec.spread * d, 1.0)]   # propsim charges the spread itself
    x.plan = "Plan 1"; x.net = net_px / risk; x.hours = hours
    return x


def stats(xs):
    r = np.array([x.net for x in xs]); a = np.array([x.net for x in xs if x.entry_time < SPLIT]); b = np.array([x.net for x in xs if x.entry_time >= SPLIT])
    tval = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 else 0
    return dict(n=len(r), mean=round(float(r.mean()), 3), first=round(float(a.mean()), 3), second=round(float(b.mean()), 3),
                t=round(float(tval), 2), win=round(float((r > 0).mean() * 100), 1), hold_h=round(float(np.median([x.hours for x in xs])), 1),
                by_sym={s: round(float(np.mean([x.net for x in xs if x.symbol == s])), 3) for s in SYMBOLS if any(x.symbol == s for x in xs)})


def main():
    h1 = {s: load_sym(s)[1] for s in SYMBOLS}
    base = setups()
    fills = []
    for t in base:
        j, e = fill(t, h1[t.symbol])
        if j is not None:
            fills.append((t, j, e))
    print(f"setups {len(base)}, filled on the 1-hour chart {len(fills)}")
    res, sets = {}, {}
    for sk in STOPS:
        for ek in EXITS:
            xs = [x for (t, j, e) in fills if (x := replay(t, h1[t.symbol], j, e, sk, ek)) is not None]
            key = f"{sk} | {ek}"
            res[key] = stats(xs); sets[key] = xs
            print(f"{key:40s} n {res[key]['n']:3d} mean {res[key]['mean']:+.3f} 1st {res[key]['first']:+.3f} 2nd {res[key]['second']:+.3f} t {res[key]['t']:+.2f} win {res[key]['win']}")
    best = max(res, key=lambda k: res[k]["first"])
    print("chosen on first half:", best, res[best])
    prop = {}
    for r in (0.0025, 0.005, 0.0075, 0.01):
        propsim.MODES["X"] = dict(p1=r, p3=r)
        starts = pd.date_range("2024-03-01", "2025-11-01", freq="MS", tz="UTC")
        paid12, breaches, dds = [], 0, []
        for s0 in starts:
            o = run(sets[best], FN100, "X", start=s0, end=s0 + pd.Timedelta(days=365))
            paid12.append(o["paid_to_trader"]); dds.append(o["worst_dd_pct"]); breaches += bool(o["breach"])
        full = run(sets[best], FN100, "X", start=START)
        prop[f"{r * 100:.2f}%"] = dict(full_paid=full["paid_to_trader"], full_dd=full["worst_dd_pct"], full_breach=full["breach"],
                                     trades=full["trades"], median_12m=round(float(np.median(paid12))), worst_12m=round(float(min(paid12))),
                                     best_12m=round(float(max(paid12))), zero_years=int(sum(p <= 0 for p in paid12)),
                                     breaches=breaches, starts=len(starts), worst_dd=round(float(max(dds)), 2))
        print(r, prop[f"{r * 100:.2f}%"])
    json.dump(dict(variants=res, chosen=best, chosen_stats=res[best], prop_100k=prop,
                   reference_hold=dict(mean=0.714, first=0.874, second=0.501, t=4.03)), open("results/intraday24.json", "w"), indent=1)


if __name__ == "__main__":
    main()

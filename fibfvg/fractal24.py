"""Same setup, smaller chart, every trade closed within 24 hours (prop rule).

Setup   : monthly + weekly bias agree (from completed daily bars); on the 1-hour or 4-hour chart price makes
          a 20-bar high (low for shorts), the leg from the 20-bar low is >= 1.5 x ATR(20) and holds a
          fair value gap. Limit at the 0.705 Fibonacci level; the order lives 24 hours.
Stop    : S0 = leg origin - 0.25 ATR | S1 = leg origin (Fib 1.0)
Exit    : X1 TP 1R | X2 TP 2R | X3 TP leg extreme (Fib 0) | X4 time only; always flat 24 h after the fill
          or at the Friday 16:00 New York close. Stop checked first in every bar; on the fill bar only
          the stop counts (conservative).
Choice  : best mean R on the first half (before 2025-08-19); judged on the second half.
    python -m fibfvg.fractal24 -> results/fractal24.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import Trade, atr, htf_bias
from .levels import load_sym

ENTRY_HOURS_NY = None   # (desde, hasta) hora NY: la orden límite solo está activa en ese horario (None = siempre)


def _active(t):
    if ENTRY_HOURS_NY is None:
        return True
    h = t.tz_convert("America/New_York").hour
    return ENTRY_HOURS_NY[0] <= h < ENTRY_HOURS_NY[1]
from . import propsim
from .propsim import Account, run
from .swaps import RATE
from .intraday24 import friday_close

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
FN100 = Account("FundedNext instant", 100_000, 740.0, None, 0.06)
TFS = {"H1": "1h", "H4": "4h"}
STOPS = ("S0 origin-0.25ATR", "S1 Fib 1.0")
EXITS = ("X1 TP 1R", "X2 TP 2R", "X3 TP leg extreme", "X4 time only")


def bars(h1, tf):
    if tf == "H1":
        return h1
    return h1.resample(TFS[tf], origin="epoch").agg(dict(Open="first", High="max", Low="min", Close="last")).dropna()


def engine(sym, daily, h1, tf, stop_kind, exit_kind, L=20):
    spec = SYMBOLS[sym]
    b = bars(h1, tf)
    hb = htf_bias(daily)
    bias = pd.DataFrame(dict(w=hb.w.values, m=hb.m.values), index=hb.index.normalize())
    bb = bias.reindex(b.index.normalize(), method="ffill").fillna(0)
    ok_dir = np.where((bb.w.values == bb.m.values), bb.w.values, 0)
    A = atr(b, 20).values
    T = b.index
    out = []
    life = pd.Timedelta(hours=24)
    for d in (1, -1):
        O, H, Lo, C = (b.Open.values, b.High.values, b.Low.values, b.Close.values)
        o, h, l, c = (O, H, Lo, C) if d == 1 else (-O, -Lo, -H, -C)
        setup = None; busy_until = T[0]
        for i in range(L + 2, len(c)):
            if setup is not None and T[i] >= busy_until:
                if T[i] - setup["t"] > life or o[i] <= setup["stop"]:
                    setup = None
                elif l[i] <= setup["entry"] and _active(T[i]):
                    e = min(o[i], setup["entry"]); s = setup["stop"]; risk = e - s
                    setup_ = setup; setup = None
                    if risk <= 3 * spec.spread:
                        continue
                    t0 = T[i]; end = min(t0 + life, friday_close(t0))
                    tp = {"X1 TP 1R": e + risk, "X2 TP 2R": e + 2 * risk, "X3 TP leg extreme": setup_["ext"]}.get(exit_kind)
                    px = None; j = i
                    if l[i] <= s:
                        px = s; j = i
                    else:
                        for j in range(i + 1, len(c)):
                            if T[j] >= end:
                                j -= 1; px = c[j]; break
                            if l[j] <= s:
                                px = min(o[j], s); break
                            if tp is not None and h[j] >= tp:
                                px = max(o[j], tp); break
                        if px is None:
                            px = c[j]
                    xt = T[j] + (T[1] - T[0])
                    hours = (xt - t0).total_seconds() / 3600
                    swap = abs(e) * RATE[sym] / 365 if (xt.normalize() > t0.normalize()) else 0.0
                    net = (px - e) - swap
                    t = Trade(sym, "position", d, t0, d * e, d * s, pos_id=f"F-{sym}-{tf}-{d}-{i}")
                    t.exits = [(xt, d * (e + net), 1.0)]
                    t.plan = "Plan 1"; t.net = (net - spec.spread) / risk; t.hours = hours; t.tf = tf
                    out.append(t); busy_until = xt
                    continue
            if ok_dir[i] != d or np.isnan(A[i - 1]) or T[i] < busy_until:
                continue
            if h[i] >= h[i - L:i].max():
                seg = l[i - L + 1:i + 1]
                j0 = i - L + 1 + int(np.argmin(seg))
                lo, hi = seg.min(), h[i]; rng = hi - lo
                if rng < 1.5 * A[i - 1] or not any(l[j] > h[j - 2] for j in range(max(j0 + 2, 2), i + 1)):
                    continue
                stop = lo - 0.25 * A[i - 1] if stop_kind.startswith("S0") else lo
                setup = dict(entry=hi - 0.705 * rng, stop=stop, ext=hi, t=T[i])
    return out


def stats(xs):
    r = np.array([x.net for x in xs]); a = np.array([x.net for x in xs if x.entry_time < SPLIT]); b = np.array([x.net for x in xs if x.entry_time >= SPLIT])
    tval = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 else 0
    return dict(n=len(r), per_month=round(len(r) / 34.5, 1), mean=round(float(r.mean()), 3), first=round(float(a.mean()), 3),
                second=round(float(b.mean()), 3), t=round(float(tval), 2), win=round(float((r > 0).mean() * 100), 1),
                hold_h=round(float(np.median([x.hours for x in xs])), 1),
                by_sym={s: round(float(np.mean([x.net for x in xs if x.symbol == s])), 3) for s in SYMBOLS if any(x.symbol == s for x in xs)})


def main():
    data = {s: load_sym(s) for s in SYMBOLS}
    res, sets = {}, {}
    for tf in TFS:
        for sk in STOPS:
            for ek in EXITS:
                xs = [t for s, (d, h) in data.items() for t in engine(s, d, h, tf, sk, ek)]
                k = f"{tf} | {sk} | {ek}"
                res[k] = stats(xs); sets[k] = xs
                print(f"{k:42s} n {res[k]['n']:4d} mean {res[k]['mean']:+.3f} 1st {res[k]['first']:+.3f} 2nd {res[k]['second']:+.3f} t {res[k]['t']:+.2f} win {res[k]['win']}")
    best = max(res, key=lambda k: res[k]["first"])
    print("chosen on first half:", best, res[best])
    prop = {}
    for r in (0.0025, 0.005):
        propsim.MODES["X"] = dict(p1=r, p3=r)
        full = run(sets[best], FN100, "X", start=pd.Timestamp("2024-01-01", tz="UTC"))
        prop[f"{r * 100:.2f}%"] = dict(paid=full["paid_to_trader"], dd=full["worst_dd_pct"], breach=full["breach"], trades=full["trades"])
        print(r, prop[f"{r * 100:.2f}%"])
    json.dump(dict(variants=res, chosen=best, chosen_stats=res[best], prop_100k=prop), open("results/fractal24.json", "w"), indent=1)


if __name__ == "__main__":
    main()

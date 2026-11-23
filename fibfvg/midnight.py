"""Enter at the midnight New York open (00:00), hold until 14:00 NY. All 5 markets, hourly data Jul 2024 -> Nov 2026.

Direction (pre-registered):
  D1 bias       : monthly + weekly ranges agree (the bots' direction)
  D2 daily      : yesterday's close vs the midpoint of the prior 5 days
  D3 yesterday  : same direction as yesterday's (NY) candle
  D4 fade       : opposite of yesterday's candle
  D5 bias+yest  : D1 and yesterday's candle agree
Risk unit R = 0.5 x daily ATR(14) (yesterday's).  Exits:
  X0 time only   : out at the 14:00 open (an emergency stop at 2R)
  X1 stop 1R     : stop 1R, else out at 14:00
  X2 stop 1R + BE: stop 1R, to breakeven once +0.5R (from the next hour), else out at 14:00
  X3 stop 1R + target 2R, else out at 14:00
Same hour touches stop and target -> stop first. Spread charged. Days Monday-Friday.
Choice on the first half (before 2025-08-19); judged on the second half; t-statistic; profit factor in R and pips.
The chosen version and the best single market go through GFT Instant Premium rules ($100K, 0.6% and 0.9%).
    python -m fibfvg.midnight -> results/midnight.json
"""
import json
from itertools import product

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import atr, htf_bias
from .levels import load_sym
from .threeway import PIP
from .candle10 import gft, NOW

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")


def days_of(sym):
    d, h = load_sym(sym)
    ny = h.index.tz_convert("America/New_York")
    df = h.copy(); df["hr"] = ny.hour; df["date"] = ny.normalize()
    hb = htf_bias(d)
    wm = pd.Series(np.where(hb.w.values == hb.m.values, hb.w.values, 0), index=hb.index.normalize().tz_localize(None))
    dc = d.Close; mid5 = (d.High.rolling(5).max() + d.Low.rolling(5).min()) / 2
    db = pd.Series(np.sign(dc.shift(1) - mid5.shift(2)).values, index=d.index.normalize().tz_localize(None))
    a14 = atr(d, 14); a14.index = a14.index.normalize().tz_localize(None)
    groups = {k: g for k, g in df.groupby("date")}
    keys = sorted(groups); out = []
    for i, k in enumerate(keys):
        if k.dayofweek > 4 or i == 0:
            continue
        g, prev = groups[k], groups[keys[i - 1]]
        w = g[g.hr < 15]
        if len(w) < 12 or w.hr.iloc[0] != 0 or 14 not in w.hr.values:
            continue
        key = k.tz_localize(None)
        pa = a14[a14.index < key]
        if len(pa) == 0:
            continue
        ydir = np.sign(prev.Close.iloc[-1] - prev.Open.iloc[0])
        out.append(dict(date=k, bias=int(wm.asof(key)) if key >= wm.index[0] else 0,
                        daily=int(db.asof(key)) if key >= db.index[0] and not np.isnan(db.asof(key)) else 0,
                        yest=int(ydir), atr=float(pa.iloc[-1]), bars=w[["hr", "Open", "High", "Low", "Close"]].values))
    return out


def direction(day, kind):
    if kind == "D1 bias":
        return day["bias"]
    if kind == "D2 daily":
        return day["daily"]
    if kind == "D3 yesterday":
        return day["yest"]
    if kind == "D4 fade":
        return -day["yest"]
    return day["bias"] if day["bias"] == day["yest"] else 0


def trade(day, sym, dkind, xkind):
    d = direction(day, dkind)
    if d == 0 or day["atr"] <= 0:
        return None
    bars = day["bars"]; e = bars[0][1]; r = 0.5 * day["atr"]; sp = SYMBOLS[sym].spread
    if r <= 3 * sp:
        return None
    stop = e - d * (2 * r if xkind == "X0 time only" else r)
    tp = e + d * 2 * r if xkind == "X3 stop + 2R target" else None
    px = None; be = False
    for j, (hr, O, H, L, C) in enumerate(bars):
        if hr >= 14:
            px = O; break
        hi, lo = (H, L) if d == 1 else (-L, -H)
        if lo <= d * stop:
            px = stop; break
        if tp is not None and hi >= d * tp:
            px = tp; break
        if xkind == "X2 stop + breakeven" and not be and (hi - d * e) / r >= 0.5:
            be = True; stop = e
    if px is None:
        px = bars[-1][4]
    pnl = (px - e) * d - sp
    return dict(date=day["date"], sym=sym, R=pnl / r, pips=pnl / PIP[sym])


def stats(ts):
    if len(ts) < 20:
        return dict(n=len(ts))
    R = np.array([t["R"] for t in ts]); P = np.array([t["pips"] for t in ts])
    a = np.array([t["R"] for t in ts if t["date"] < SPLIT]); b = np.array([t["R"] for t in ts if t["date"] >= SPLIT])
    pf = lambda x: round(float(x[x > 0].sum() / -x[x < 0].sum()), 2) if (x < 0).any() else None
    w, l = R[R > 0], R[R <= 0]
    return dict(n=len(R), win=round(float((R > 0).mean() * 100), 1), rr=round(float(w.mean() / -l.mean()), 2), pf_R=pf(R), pf_pips=pf(P),
                net_R=round(float(R.mean()), 3), avg_pips=round(float(P.mean()), 1), first=round(float(a.mean()), 3), second=round(float(b.mean()), 3),
                t=round(float(R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))), 2))


def main():
    data = {s: days_of(s) for s in SYMBOLS}
    combos = list(product(("D1 bias", "D2 daily", "D3 yesterday", "D4 fade", "D5 bias+yesterday"),
                          ("X0 time only", "X1 stop 1R", "X2 stop + breakeven", "X3 stop + 2R target")))
    out = dict(all_markets={}, by_market={})
    res = {}
    for c in combos:
        ts = [t for s in SYMBOLS for day in data[s] if (t := trade(day, s, *c)) is not None]
        res[c] = ts
        out["all_markets"][" | ".join(c)] = stats(ts)
    best = max(res, key=lambda c: out["all_markets"][" | ".join(c)]["first"])
    print("ALL 5 MARKETS, top 6 by first half:")
    for c in sorted(res, key=lambda c: -out["all_markets"][" | ".join(c)]["first"])[:6]:
        print("  ", c, out["all_markets"][" | ".join(c)])
    # per market: the best version chosen on that market's first half, judged on its second half
    for s in SYMBOLS:
        per = {c: stats([t for t in res[c] if t["sym"] == s]) for c in combos}
        bc = max(per, key=lambda c: per[c]["first"])
        out["by_market"][s] = dict(rule=" | ".join(bc), **per[bc])
        print(f"{s:7s} best on first half: {bc} -> {per[bc]}")
    # GFT for markets whose chosen version is positive in both halves
    out["gft"] = {}
    y1 = NOW - pd.Timedelta(days=365)
    for s, v in out["by_market"].items():
        if not (v["first"] > 0 and v["second"] > 0):
            continue
        c = tuple(v["rule"].split(" | "))
        tt = [t for t in res[c] if t["sym"] == s]
        for risk in (0.006, 0.009):
            g = gft(tt, risk=risk); l = gft(tt, risk=risk, start=y1, end=NOW)
            out["gft"][f"{s} {risk * 100:.1f}%"] = dict(paid=g["paid"], payouts=g["payouts"], breach=g["breach"], last12=l["paid"], profitable_days=g["profitable_days"])
            print("GFT Instant Premium $100K", s, risk, out["gft"][f"{s} {risk * 100:.1f}%"])
    json.dump(out, open("results/midnight.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

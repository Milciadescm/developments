"""The 10am New York 4-hour candle: one trade a day, 2024 -> now (1-hour candles; BTC hourly from Nov 2024).

Trading day: 8:00 PM New York to 6:00 PM next day. The trade lives only inside the 10:00-14:00 NY 4-hour candle:
entry 9:00-11:30 (at 1-hour resolution: the 10:00 candle), out by 14:00 or 16:00, never overnight.
Direction (pre-registered, choice on the first half, before 2025-08-19):
  D1 bias    : monthly + weekly ranges agree (the bots' direction)
  D2 daily   : yesterday's close vs the midpoint of the prior 5 days
  D3 PO3     : D1, and only when the 10:00 open is on the "discount" side of the 8 PM open (below it for buys,
               above it for sells) - accumulation overnight, manipulation early, distribution 10-2 (ICT power of three)
Entry: E1 market at the 10:00 open | E2 limit 0.25 x (average 10-2 candle range) back from the 10:00 open,
       live during the 10:00 hour only.
Stop : S1 beyond the overnight (8 PM - 10 AM) low/high | S2 half the average 10-2 candle range.
Target: T1 1R | T2 2R | T3 the projected candle extreme: entry +/- the average 10-2 candle range.
Manage: stop to breakeven at +0.5R (from the next hour); flat at 14:00 (X2) or 16:00 (X4).
Costs: spread on every trade. Profit factor = gross profit / gross loss, in R and in pips.
Then: the chosen version on GFT Instant Premium $100K (1% floating limit -> one trade at 0.9%; 5 profitable days of
+0.5% per payout; 3% daily; 6% trailing; 80%), single market or best markets, and 2,000-path 2027 / 2028 projections.
    python -m fibfvg.candle10 -> results/candle10.json
"""
import json
from itertools import product

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import htf_bias
from .levels import load_sym
from .threeway import PIP

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
NOW = pd.Timestamp("2026-11-22", tz="UTC")
SIZE = 100_000.0


def days_of(sym):
    d, h = load_sym(sym)
    ny = h.index.tz_convert("America/New_York")
    df = h.copy(); df["ny"] = ny; df["hr"] = ny.hour; df["date"] = ny.normalize()
    hb = htf_bias(d)
    wm = pd.Series(np.where(hb.w.values == hb.m.values, hb.w.values, 0), index=hb.index.normalize().tz_localize(None))
    dc = d.Close; mid5 = (d.High.rolling(5).max() + d.Low.rolling(5).min()) / 2
    db = pd.Series(np.sign(dc.shift(1) - mid5.shift(2)).values, index=d.index.normalize().tz_localize(None))
    out = []
    groups = {k: g for k, g in df.groupby("date")}
    keys = sorted(groups)
    ranges = []
    for i, k in enumerate(keys):
        g = groups[k]
        if k.dayofweek > 4:
            continue
        prev = groups.get(keys[i - 1]) if i > 0 else None
        if prev is None:
            continue
        on = pd.concat([prev[prev.hr >= 20], g[g.hr < 10]])
        win = g[(g.hr >= 10) & (g.hr <= 15)]
        if len(on) < 6 or len(win) < 4 or 10 not in win.hr.values:
            continue
        c4 = win[win.hr <= 13]
        rng = c4.High.max() - c4.Low.min()
        avg = np.mean(ranges[-20:]) if len(ranges) >= 10 else np.nan
        ranges.append(rng)
        key = k.tz_localize(None)
        out.append(dict(date=k, o20=on.Open.iloc[0], on_hi=on.High.max(), on_lo=on.Low.min(), bars=win[["hr", "Open", "High", "Low", "Close"]].values,
                        avg=avg, b_wm=int(wm.asof(key)) if key >= wm.index[0] else 0, b_d=int(db.asof(key)) if key >= db.index[0] and not np.isnan(db.asof(key)) else 0))
    return out


def trade(day, sym, dkind, ekind, skind, tkind, exit_hr):
    avg = day["avg"]
    if np.isnan(avg) or avg <= 0:
        return None
    bars = day["bars"]; o10 = bars[0][1]
    d = day["b_wm"] if dkind in ("D1 bias", "D3 PO3") else day["b_d"]
    if d == 0:
        return None
    if dkind == "D3 PO3" and not ((o10 < day["o20"]) if d == 1 else (o10 > day["o20"])):
        return None
    sp = SYMBOLS[sym].spread
    if ekind == "E1 market":
        e = o10; jf = 0
    else:
        e = o10 - d * 0.25 * avg
        b0 = bars[0]
        if not ((b0[3] <= e) if d == 1 else (b0[2] >= e)):
            return None
        jf = 0
    if skind == "S1 overnight":
        s = day["on_lo"] - sp if d == 1 else day["on_hi"] + sp
    else:
        s = e - d * 0.5 * avg
    r = (e - s) * d
    if r <= 3 * sp or r > 1.5 * avg:
        return None
    tp = e + d * (1 if tkind == "T1 1R" else 2) * r if tkind != "T3 candle extreme" else e + d * avg
    stop, be, px = s, False, None
    for j, (hr, O, H, L, C) in enumerate(bars):
        if hr >= exit_hr:
            px = O; break
        hi, lo = (H, L) if d == 1 else (-L, -H)
        if lo <= d * stop:
            px = stop; break
        if j > jf or ekind == "E1 market":
            if hi >= d * tp and not (j == jf and ekind != "E1 market"):
                px = tp; break
        if not be and (j > jf or ekind == "E1 market") and (hi - d * e) / r >= 0.5:   # fill candle: its high may predate the fill
            be = True; stop_next = e
        if be:
            stop = e if d == 1 and e > stop or d == -1 and e < stop else stop
    if px is None:
        px = bars[-1][4]
    pnl = (px - e) * d - sp
    return dict(date=day["date"], sym=sym, R=pnl / r, pips=pnl / PIP[sym], dir=d)


def stats(ts):
    if len(ts) < 10:
        return dict(n=len(ts))
    R = np.array([t["R"] for t in ts]); P = np.array([t["pips"] for t in ts])
    a = np.array([t["R"] for t in ts if t["date"] < SPLIT]); b = np.array([t["R"] for t in ts if t["date"] >= SPLIT])
    pf = lambda x: round(float(x[x > 0].sum() / -x[x < 0].sum()), 2) if (x < 0).any() else None
    return dict(n=len(R), win=round(float((R > 0).mean() * 100), 1), pf_R=pf(R), pf_pips=pf(P), net_R=round(float(R.mean()), 3),
                avg_pips=round(float(P.mean()), 1), total_pips=round(float(P.sum())), first=round(float(a.mean()), 3) if len(a) else None,
                second=round(float(b.mean()), 3) if len(b) else None, t=round(float(R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))), 2))


def gft(ts, risk=0.009, split=0.8, need=5, start=None, end=None):
    """one trade a day at 0.9% (1% floating limit), GFT Instant Premium rules"""
    days = {}
    for t in ts:
        if start is not None and not (start <= t["date"] < end):
            continue
        k = t["date"]
        days[k] = days.get(k, 0.0) + t["R"] * risk * SIZE
    s = pd.Series(days).sort_index()
    bal = peak = 0.0; paid = 0.0; pdays = 0; last = None; breach = None; pays = []
    for d, p in s.items():
        p = max(p, -0.03 * SIZE)
        bal += p; pdays += p >= 0.005 * SIZE; peak = max(peak, bal)
        if bal <= min(peak - 0.06 * SIZE, 0.0) if peak < 0.06 * SIZE else bal <= 0.0:
            breach = str(d.date()); break
        last = last or d
        if (d - last).days >= 14 and pdays >= need and bal > 0:
            paid += split * bal; pays.append((str(d.date()), round(split * bal))); bal = peak = 0.0; pdays = 0; last = d
    return dict(paid=round(paid), payouts=len(pays), breach=breach, list=pays, profitable_days=int((s >= 0.005 * SIZE).sum()), days=len(s))


def main():
    data = {s: days_of(s) for s in SYMBOLS}
    combos = list(product(("D1 bias", "D2 daily", "D3 PO3"), ("E1 market", "E2 limit"), ("S1 overnight", "S2 half range"),
                          ("T1 1R", "T2 2R", "T3 candle extreme"), (14, 16)))
    res = {}
    for c in combos:
        ts = [t for s in SYMBOLS for day in data[s] if (t := trade(day, s, *c)) is not None]
        res[c] = (stats(ts), ts)
    best = max(res, key=lambda c: (res[c][0].get("first") or -9) if res[c][0].get("n", 0) >= 200 else -9)
    out = dict(all={" | ".join(map(str, c)): v[0] for c, v in res.items()})
    top = sorted(res, key=lambda c: -(res[c][0].get("first") or -9))[:8]
    print("top 8 by first half:")
    for c in top:
        print("  ", c, res[c][0])
    st, ts = res[best]
    out["chosen"] = dict(rule=" | ".join(map(str, best)), **st)
    print("CHOSEN on first half:", best, st)
    by = {s: stats([t for t in ts if t["sym"] == s]) for s in SYMBOLS}
    out["chosen_by_market"] = by
    for s, v in by.items():
        print("   ", s, v)
    # GFT Instant Premium: whole basket (one trade a day = first market by signal order is not defined -> per market accounts)
    out["gft"] = {}
    y1 = NOW - pd.Timedelta(days=365)
    for s in SYMBOLS:
        tt = [t for t in ts if t["sym"] == s]
        if len(tt) < 20:
            continue
        g = gft(tt); l = gft(tt, start=y1, end=NOW)
        out["gft"][s] = dict(paid=g["paid"], payouts=g["payouts"], breach=g["breach"], profitable_days=g["profitable_days"], trade_days=g["days"],
                             last12=l["paid"], last12_payouts=l["payouts"])
        print("GFT Instant Premium $100K, one market at 0.9%:", s, out["gft"][s])
    # projection 2027 / 2028 for the best single market by GFT payout
    bestm = max(out["gft"], key=lambda k: out["gft"][k]["paid"])
    tt = [t for t in ts if t["sym"] == bestm]
    months = sorted({(t["date"].year, t["date"].month) for t in tt})
    rng = np.random.default_rng(10)
    by_m = {m: [t for t in tt if (t["date"].year, t["date"].month) == m] for m in months}
    yrs = []
    for _ in range(2000):
        seq = []
        base = pd.Timestamp("2027-01-04", tz="America/New_York")
        k = 0
        for mm in range(24):
            m = months[rng.integers(len(months))]
            for t in by_m[m]:
                nt = dict(t); nt["date"] = base + pd.Timedelta(days=30.44 * mm + (t["date"].day - 1)); seq.append(nt)
        g27 = gft(seq, start=base, end=base + pd.Timedelta(days=365)); g28 = gft(seq, start=base + pd.Timedelta(days=365), end=base + pd.Timedelta(days=730))
        yrs.append((g27["paid"], g28["paid"], bool(g27["breach"] or g28["breach"])))
    y27 = np.array([y[0] for y in yrs]); y28 = np.array([y[1] for y in yrs])
    q = lambda x: dict(median=round(float(np.median(x))), p10=round(float(np.percentile(x, 10))), p90=round(float(np.percentile(x, 90))))
    out["projection"] = dict(market=bestm, y2027=q(y27), y2028=q(y28), breach_pct=round(float(np.mean([y[2] for y in yrs]) * 100), 1))
    print("projection, one $100K GFT Instant Premium,", bestm, out["projection"])
    json.dump(out, open("results/candle10.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

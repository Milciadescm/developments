"""Nasdaq 100 only: the 6 AM New York 4-hour candle (06:00-10:00) as the signal, trade from 10:00 into the 4 PM candle.
Hourly futures data (24 h), Jul 2024 -> Nov 2026. 1 pip = 1 index point (as most MT5 brokers quote NAS100);
a second run uses 1 pip = 0.1 point.

Setups (pre-registered; choice on the first half, before 2025-08-19):
  C  continuation : trade in the direction the 6 AM candle closed (close > open -> buy).
  CB continuation + bias : C, only when the monthly + weekly bias agrees.
  P  pivot (reversal) : the 6 AM candle takes the overnight (20:00-06:00) high or low and closes back inside the
                        overnight range -> trade the other way (Judas swing).
  PB pivot + bias : P, only when the bias agrees with the new direction.
Entry: market at the 10:00 open.  Stop: X1 fixed 160 points (1.25R at TP2 = 200, as asked) | X2 beyond the 6 AM
candle's far end + spread.  Ladder: 20% at TP1 100, TP2 200, TP3 300, TP4 400, TP5 500 pips.
Breakeven: B0 none | B1 stop to entry after TP1.  Flat at 16:00 (F16) or 18:00 (end of the 4 PM candle, F18).
Same hour touches both stop and a target -> stop first. Spread charged.
Accounts: $100K at 0.75% and 0.25% risk per trade (fixed on the start balance), whole period and every calendar year.
    python -m fibfvg.nas6am -> results/nas6am.json
"""
import json
from itertools import product

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import htf_bias
from .levels import load_sym

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
SP = SYMBOLS["NAS100"].spread


def build_days():
    d, h = load_sym("NAS100")
    ny = h.index.tz_convert("America/New_York")
    df = h.copy(); df["hr"] = ny.hour; df["date"] = ny.normalize()
    hb = htf_bias(d)
    wm = pd.Series(np.where(hb.w.values == hb.m.values, hb.w.values, 0), index=hb.index.normalize().tz_localize(None))
    groups = {k: g for k, g in df.groupby("date")}
    keys = sorted(groups); out = []
    for i, k in enumerate(keys):
        if k.dayofweek > 4 or i == 0:
            continue
        g, prev = groups[k], groups[keys[i - 1]]
        on = pd.concat([prev[prev.hr >= 20], g[g.hr < 6]])
        c6 = g[(g.hr >= 6) & (g.hr < 10)]
        tr = g[(g.hr >= 10) & (g.hr < 18)]
        if len(on) < 6 or len(c6) < 4 or len(tr) < 6 or tr.hr.iloc[0] != 10:
            continue
        key = k.tz_localize(None)
        out.append(dict(date=k, on_hi=on.High.max(), on_lo=on.Low.min(), o6=c6.Open.iloc[0], c6=c6.Close.iloc[-1],
                        h6=c6.High.max(), l6=c6.Low.min(), bias=int(wm.asof(key)) if key >= wm.index[0] else 0,
                        bars=tr[["hr", "Open", "High", "Low", "Close"]].values))
    return out


def direction(day, setup):
    cont = 1 if day["c6"] > day["o6"] else -1 if day["c6"] < day["o6"] else 0
    piv = 0
    if day["h6"] > day["on_hi"] and day["c6"] < day["on_hi"]:
        piv = -1
    elif day["l6"] < day["on_lo"] and day["c6"] > day["on_lo"]:
        piv = 1
    d = cont if setup in ("C", "CB") else piv
    if setup in ("CB", "PB") and d != day["bias"]:
        return 0
    return d


def replay(day, setup, stop_kind, be, flat, pip):
    d = direction(day, setup)
    if d == 0:
        return None
    bars = day["bars"]; e = bars[0][1]
    s = e - d * 160 * pip if stop_kind == "X1 fixed 160" else (day["l6"] - SP if d == 1 else day["h6"] + SP)
    r = (e - s) * d
    if r <= 3 * SP:
        return None
    tps = [e + d * k * 100 * pip for k in range(1, 6)]
    stop, left, k, pnl, hit = s, 1.0, 0, 0.0, 0
    for hr, O, H, L, C in bars:
        if hr >= flat:
            pnl += left * (O - e) * d; left = 0; break
        hi, lo = (H, L) if d == 1 else (-L, -H)
        if lo <= d * stop:
            pnl += left * (stop - e) * d; left = 0; break
        while k < 5 and hi >= d * tps[k]:
            pnl += 0.2 * (tps[k] - e) * d; left -= 0.2; k += 1
            if k == 1 and be == "B1 BE after TP1":
                stop = e
        if left <= 1e-9:
            break
    if left > 1e-9:
        pnl += left * (bars[-1][4] - e) * d
    pnl -= SP
    return dict(date=day["date"], R=pnl / r, pts=pnl, tps=k, risk_pts=r, dir=d)


def stats(ts):
    if len(ts) < 20:
        return dict(n=len(ts))
    R = np.array([t["R"] for t in ts]); P = np.array([t["pts"] for t in ts])
    a = np.array([t["R"] for t in ts if t["date"] < SPLIT]); b = np.array([t["R"] for t in ts if t["date"] >= SPLIT])
    pf = lambda x: round(float(x[x > 0].sum() / -x[x < 0].sum()), 2) if (x < 0).any() else None
    w, l = R[R > 0], R[R <= 0]
    tpc = np.bincount([t["tps"] for t in ts], minlength=6)
    return dict(n=len(R), win=round(float((R > 0).mean() * 100), 1), avg_win_R=round(float(w.mean()), 2), avg_loss_R=round(float(l.mean()), 2),
                rr=round(float(w.mean() / -l.mean()), 2), pf_R=pf(R), pf_pips=pf(P), net_R=round(float(R.mean()), 3), avg_pips=round(float(P.mean()), 1),
                first=round(float(a.mean()), 3), second=round(float(b.mean()), 3), t=round(float(R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))), 2),
                reached_tp=dict(TP1=int(tpc[1:].sum()), TP2=int(tpc[2:].sum()), TP3=int(tpc[3:].sum()), TP4=int(tpc[4:].sum()), TP5=int(tpc[5])),
                avg_stop_pips=round(float(np.mean([t["risk_pts"] for t in ts])), 1))


def account(ts, risk, size=100_000.0):
    bal, peak, dd = size, size, 0.0
    by_year, by_month = {}, {}
    for t in sorted(ts, key=lambda x: x["date"]):
        p = t["R"] * risk * size
        bal += p; peak = max(peak, bal); dd = max(dd, (peak - bal) / size)
        y = t["date"].year; m = t["date"].strftime("%Y-%m")
        by_year[y] = by_year.get(y, 0.0) + p; by_month[m] = by_month.get(m, 0.0) + p
    mv = np.array(list(by_month.values()))
    return dict(end=round(bal), profit=round(bal - size), max_dd_pct=round(dd * 100, 2), by_year={k: round(v) for k, v in by_year.items()},
                months_up=int((mv > 0).sum()), months=len(mv), worst_month=round(float(mv.min())), best_month=round(float(mv.max())))


def main():
    days = build_days()
    out = {}
    for pip_name, pip in (("1 pip = 1 point", 1.0), ("1 pip = 0.1 point", 0.1)):
        res = {}
        for c in product(("C", "CB", "P", "PB"), ("X1 fixed 160", "X2 beyond 6AM candle"), ("B0 none", "B1 BE after TP1"), (16, 18)):
            ts = [t for day in days if (t := replay(day, *c, pip)) is not None]
            res[c] = (stats(ts), ts)
        ok = {c: v for c, v in res.items() if v[0].get("n", 0) >= 40}
        best = max(ok, key=lambda c: ok[c][0]["first"])
        top = sorted(ok, key=lambda c: -ok[c][0]["first"])[:6]
        print(f"\n=== {pip_name}")
        for c in top:
            print("  ", c, ok[c][0])
        st, ts = res[best]
        acc = {f"{r * 100:.2f}%": account(ts, r) for r in (0.0075, 0.0025)}
        out[pip_name] = dict(chosen=" | ".join(map(str, best)), stats=st, accounts=acc,
                             all={" | ".join(map(str, c)): v[0] for c, v in res.items()})
        print("CHOSEN:", best, st)
        for k, v in acc.items():
            print("   account", k, v)
    json.dump(out, open("results/nas6am.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

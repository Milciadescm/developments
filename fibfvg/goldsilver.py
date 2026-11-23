"""Gold and silver, midnight New York -> 14:00 NY, one pair at a time on a GFT Instant Premium $100K.
Hourly data Jul 2024 -> Nov 2026 (the oldest hourly history reachable here). Pips: gold 1 pip = $0.10, silver $0.01.

1. Reality check: how far does price really move from 00:00 to 14:00 in pips, versus the daily range?
2. The rule: trade at 00:00 when the monthly + weekly bias and yesterday's NY candle agree; out at 14:00.
   Stop sizes: 0.25 / 0.5 / 0.75 / 1.0 x daily ATR(14), with and without breakeven at +0.5 x stop.
   R = the stop distance, so "risk %" is exactly what a full stop costs (GFT floating-loss limit 1% -> max 0.9%).
3. GFT Instant Premium $100K rules: 6% trailing (locks at start), 3% daily, 1% floating, 5 profitable days of +0.5%
   per payout, every 14 days, 80% split. Risk 0.3% / 0.45% / 0.6% / 0.9% per trade.
    python -m fibfvg.goldsilver -> results/goldsilver.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .threeway import PIP
from .midnight import days_of
from .candle10 import gft, NOW

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")


def moves(sym, days):
    m = []
    for day in days:
        b = day["bars"]; o = b[0][1]
        c14 = next((x[1] for x in b if x[0] >= 14), b[-1][4])
        hi = max(x[2] for x in b if x[0] < 14); lo = min(x[3] for x in b if x[0] < 14)
        m.append(dict(net=abs(c14 - o) / PIP[sym], range=(hi - lo) / PIP[sym], atr=day["atr"] / PIP[sym]))
    q = lambda k: dict(median=round(float(np.median([x[k] for x in m]))), p25=round(float(np.percentile([x[k] for x in m], 25))),
                       p75=round(float(np.percentile([x[k] for x in m], 75))))
    return dict(days=len(m), net_move_00_to_14_pips=q("net"), range_00_to_14_pips=q("range"), daily_atr_pips=q("atr"),
                share_net_over_100_pips=round(float(np.mean([x["net"] >= 100 for x in m]) * 100)))


def trade(day, sym, k, be):
    d = day["bias"] if day["bias"] == day["yest"] else 0
    if d == 0 or day["atr"] <= 0:
        return None
    b = day["bars"]; e = b[0][1]; r = k * day["atr"]; sp = SYMBOLS[sym].spread
    if r <= 3 * sp:
        return None
    stop = e - d * r; px = None; moved = False
    for hr, O, H, L, C in b:
        if hr >= 14:
            px = O; break
        hi, lo = (H, L) if d == 1 else (-L, -H)
        if lo <= d * stop:
            px = stop; break
        if be and not moved and (hi - d * e) / r >= 0.5:
            moved = True; stop = e
    if px is None:
        px = b[-1][4]
    pnl = (px - e) * d - sp
    return dict(date=day["date"], sym=sym, R=pnl / r, pips=pnl / PIP[sym], stop_pips=r / PIP[sym], dir=d, entry=e, exit=px)


def stats(ts):
    R = np.array([t["R"] for t in ts]); P = np.array([t["pips"] for t in ts])
    a = np.array([t["R"] for t in ts if t["date"] < SPLIT]); b = np.array([t["R"] for t in ts if t["date"] >= SPLIT])
    pf = lambda x: round(float(x[x > 0].sum() / -x[x < 0].sum()), 2) if (x < 0).any() else None
    return dict(n=len(R), win=round(float((R > 0).mean() * 100), 1), pf_R=pf(R), pf_pips=pf(P), net_R=round(float(R.mean()), 3),
                avg_pips=round(float(P.mean()), 1), avg_win_pips=round(float(P[P > 0].mean()), 1), avg_loss_pips=round(float(P[P <= 0].mean()), 1),
                avg_stop_pips=round(float(np.mean([t["stop_pips"] for t in ts]))), first=round(float(a.mean()), 3), second=round(float(b.mean()), 3),
                t=round(float(R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))), 2))


def main():
    out = {}
    y1 = NOW - pd.Timedelta(days=365)
    for sym in ("XAUUSD", "XAGUSD"):
        days = days_of(sym)
        out[sym] = dict(reality=moves(sym, days), versions={}, gft={})
        print(sym, "reality check:", out[sym]["reality"])
        for k in (0.25, 0.5, 0.75, 1.0):
            for be in (False, True):
                ts = [t for day in days if (t := trade(day, sym, k, be)) is not None]
                key = f"stop {k} ATR{' + breakeven' if be else ''}"
                st = stats(ts); out[sym]["versions"][key] = st
                print(f"  {key:26s} {st}")
                for risk in (0.003, 0.0045, 0.006, 0.009):
                    g = gft(ts, risk=risk); l = gft(ts, risk=risk, start=y1, end=NOW)
                    out[sym]["gft"][f"{key} | {risk * 100:.2f}%"] = dict(paid=g["paid"], payouts=g["payouts"], breach=g["breach"], last12=l["paid"],
                                                                        profitable_days=g["profitable_days"])
        best = max(out[sym]["gft"], key=lambda x: out[sym]["gft"][x]["paid"] if not out[sym]["gft"][x]["breach"] else -1)
        print("  best GFT without breach:", best, out[sym]["gft"][best])
        out[sym]["gft_best"] = best
        # example trades: the last 8 of the 1-ATR version
        ts = [t for day in days if (t := trade(day, sym, 1.0, False)) is not None]
        out[sym]["examples"] = [dict(date=str(t["date"].date()), dir="buy" if t["dir"] == 1 else "sell", entry=round(t["entry"], 3), exit=round(t["exit"], 3),
                                     pips=round(t["pips"]), stop_pips=round(t["stop_pips"])) for t in ts[-8:]]
        for e in out[sym]["examples"]:
            print("   example", e)
    json.dump(out, open("results/goldsilver.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

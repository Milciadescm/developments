"""Toward 3-4 RR with a 40%+ win rate.

A. Baseline check: the lab's "Plan 1 by starting balance, 2005-2026, 0.5% per unit, $50,000 -> $456,392".
   Re-run on today's 20-year files (Yahoo: gold and silver futures, S&P 500 and Nasdaq 100 indices, BTC from 2014),
   all 5 markets, exits v1 / run20 / chandelier / monthly / year, $50K real money at 0.5% per unit, swaps charged.
B. Fixed R (user's definition): 1R = 100 pips = $10 on gold. Other markets use the same share of their daily range
   (R = 100 gold pips / gold's median daily ATR x that market's ATR). Stop 1R, take profit 3R / 4R / 5R,
   max hold 1 / 5 / 20 days. Entries: the prop bot's (daily + 4-hour at 0.705) and the position plan's (daily).
   2024 -> now, 1-hour candles (stop first when a candle touches both; on the fill candle only the stop counts).
   Choice on the first half (before 2025-08-19), judged on the second half.
C. Prop $100K whose loss limit does not trail (static), so holds and wider stops survive:
   position plan (holds) at 0.5% / 1% per unit, static limit 10% and none.
    python -m fibfvg.rr34 -> results/rr34.json
"""
import json

import numpy as np
import pandas as pd

from . import plans, propsim
from .config import SYMBOLS
from .engines import Trade, atr, load, net_r
from .levels import load_sym
from .plans import position_engine
from .prop24 import build as prop_build
from .propsim import Account, run
from .swaps import RATE, with_swaps
from .longhold import load_long
from .livefund import monthly, max_dd
from .threeway import PIP, stats, Y1, NOW

plans.POS_MODES["Y1 year"] = dict(tp1=False, tp2=False, trail="d120", be_at=1.0, time_stop=None)
SPLIT = pd.Timestamp("2025-08-19", tz="UTC")


def baseline():
    out = {}
    for mode in ("P0 v1", "P1 run20", "P2 chandelier", "P3 monthly", "Y1 year"):
        tr = []
        for s in SYMBOLS:
            tr += position_engine(s, load_long(s), mode, start="2005-01-01")
        for t in tr:
            t.plan = "Plan 1"
        tr = with_swaps(tr)
        propsim.MODES["X"] = dict(p1=0.005, p3=0.005)
        o = run(tr, Account("Live", 50_000, 0.0, None, None, real=True, payout_days=None), "X", start=pd.Timestamp("2005-01-01", tz="UTC"))
        m = monthly(o["curve"], 50_000)
        r = np.array([net_r(t) for t in tr])
        out[mode] = dict(trades=o["trades"], skipped=o["skipped_min_lot"], end=round(o["end_balance"]), max_dd=round(max_dd(m) * 100, 1),
                         cagr=round(((o["end_balance"] / 5e4) ** (12 / len(m)) - 1) * 100, 1), win=round(float((r > 0).mean() * 100), 1),
                         rr=round(float(r[r > 0].mean() / -r[r <= 0].mean()), 2), net=round(float(r.mean()), 3),
                         since2024=round(float(np.mean([net_r(t) for t in tr if t.entry_time.year >= 2024])), 3))
        print("A", mode, out[mode])
    return out


def replay_fixed(sym, d, e, t0, bars, r_dist, tp_mult, max_days):
    """stop 1R, target tp_mult R, flat after max_days. Returns (exit_time, exit_price) or None."""
    i0 = int(bars.index.searchsorted(t0))
    H, L, C, T = bars.High.values, bars.Low.values, bars.Close.values, bars.index
    jf = None
    for j in range(i0, min(len(C), i0 + 400)):
        if (L[j] <= e) if d == 1 else (H[j] >= e):
            jf = j; break
    if jf is None:
        return None
    sl, tp = e - d * r_dist, e + d * tp_mult * r_dist
    end = T[jf] + pd.Timedelta(days=max_days)
    for j in range(jf, len(C)):
        if T[j] >= end:
            return T[j], C[j - 1], T[jf]
        hi, lo = (H[j], L[j]) if d == 1 else (-L[j], -H[j])
        if lo <= d * sl:
            return T[j], sl, T[jf]
        if j > jf and hi >= d * tp:
            return T[j], tp, T[jf]
    return None


def fixed_r():
    data = {s: load_sym(s) for s in SYMBOLS}
    datr = {s: atr(data[s][0], 14) for s in SYMBOLS}
    gold_med = float(datr["XAUUSD"][datr["XAUUSD"].index >= pd.Timestamp("2024-01-01", tz="UTC")].median())
    k = 100 * PIP["XAUUSD"] / gold_med                 # 100 gold pips as a share of gold's daily range
    print(f"B: 1R = 100 gold pips = $10 = {k:.2f} x gold's median daily range (${gold_med:.1f})")
    a, b = prop_build()
    prop_entries = [(t.symbol, t.direction, t.entry, t.entry_time) for t in a + b]
    pos = [t for s in SYMBOLS for t in position_engine(s, data[s][0], "P2 chandelier", start="2024-01-01") if t.engine == "position"]
    pos_entries = [(t.symbol, t.direction, t.entry, t.entry_time - pd.Timedelta(hours=12)) for t in pos]
    res, sets = {}, {}
    for ename, entries in (("prop entries (daily + 4-hour)", prop_entries), ("position entries (daily)", pos_entries)):
        for tpm in (3, 4, 5):
            for md in (1, 5, 20):
                tr = []
                for (s, d, e, t0) in entries:
                    a_ = datr[s].asof(t0.normalize()) if t0.normalize() >= datr[s].index[0] else np.nan
                    if np.isnan(a_):
                        continue
                    r_dist = k * a_
                    if s == "XAUUSD":
                        r_dist = 100 * PIP[s]                  # gold: exactly 100 pips, as defined
                    x = replay_fixed(s, d, e, t0, data[s][1], r_dist, tpm, md)
                    if x is None:
                        continue
                    xt, px, ft = x
                    days = (xt - ft).total_seconds() / 86400
                    t = Trade(s, "position", d, ft, e, e - d * r_dist, pos_id=f"F{len(tr)}")
                    t.exits = [(xt, px - d * abs(e) * RATE[s] * days / 365, 1.0)]; t.plan = "Plan 1"
                    tr.append(t)
                key = f"{ename} | TP {tpm}R | max {md} d"
                st = stats(tr); st["by_market"] = {s: stats([t for t in tr if t.symbol == s]) for s in SYMBOLS}
                res[key] = st; sets[key] = tr
                print(f"B {key:52s} n {st.get('n'):4d} win {st.get('win')}% RR {st.get('rr')} net {st.get('net')} halves {st.get('first')}/{st.get('second')} t {st.get('t')}")
    best = max(res, key=lambda k_: res[k_].get("first") or -9)
    print("B chosen on first half:", best, res[best])
    return res, best, k


def static_prop():
    tr = with_swaps([t for s in SYMBOLS for t in position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= pd.Timestamp("2024-01-01", tz="UTC")], "P2 chandelier", start="2024-01-01")])
    for t in tr:
        t.plan = "Plan 1"
    out = {}
    for lim in (0.10, None):
        for risk in (0.005, 0.01):
            propsim.MODES["X"] = dict(p1=risk, p3=risk)
            acct = Account("Static-limit prop", 100_000, 740.0, None, lim, trailing=False)
            o = run(tr, acct, "X", start=pd.Timestamp("2024-01-01", tz="UTC"))
            by = {}
            for d, v in o["payout_list"]:
                by[d[:4]] = by.get(d[:4], 0) + v
            l = run(tr, acct, "X", start=Y1, end=NOW)
            key = f"static limit {'none' if lim is None else f'{lim * 100:.0f}%'} | {risk * 100:.1f}% per unit"
            out[key] = dict(by_year={k: round(v) for k, v in by.items()}, total=round(o["paid_to_trader"]), dd=o["worst_dd_pct"], breach=o["breach"],
                            last12=round(l["paid_to_trader"]))
            print("C", key, out[key])
    return out


def main():
    out = dict(A=baseline())
    out["B"], out["B_best"], out["k"] = fixed_r()
    out["C"] = static_prop()
    json.dump(out, open("results/rr34.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

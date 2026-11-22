"""Prop $100K: fixed take profit 30 pips, stop 20 pips, bigger lots (2024 -> now only).

Entries: the prop bot's real entries (daily + 4-hour setups at 0.705), all 5 markets, fill hour found on the 1-hour
chart (BTC also on the 5-minute chart). Each trade: stop 20 pips, target 30 pips, flat after 24 h.
When a 1-hour candle touches both the stop and the target we cannot know which came first:
  conservative = stop first, optimistic = target first. Spread charged on every trade.
Account: FundedNext instant $100K, 6% trailing line, 5% guard, risk 0.5% / 1% / 2% per trade.
    python -m fibfvg.scalp3020 -> results/scalp3020.json
"""
import json

import numpy as np
import pandas as pd

from . import propsim
from .config import SYMBOLS
from .engines import Trade, load, net_r
from .levels import load_sym
from .prop24 import build
from .propsim import run
from .intraday24 import FN100
from .threeway import PIP, stats, windows, prop_account, Y1, NOW

TP_PIPS, SL_PIPS = 30, 20


def replay(t, bars, optimistic):
    d, e, sym = t.direction, t.entry, t.symbol
    pip = PIP[sym]; tp = e + d * TP_PIPS * pip; sl = e - d * SL_PIPS * pip
    i0 = int(bars.index.searchsorted(t.entry_time))
    H, L, C, T = bars.High.values, bars.Low.values, bars.Close.values, bars.index
    jf = None
    for j in range(i0, min(len(C), i0 + 300)):
        if (L[j] <= e) if d == 1 else (H[j] >= e):
            jf = j; break
    if jf is None:
        return None
    end = T[jf] + pd.Timedelta(hours=24); px = None; xt = None
    for j in range(jf, len(C)):
        if T[j] >= end:
            px, xt = C[j - 1], T[j]; break
        hi, lo = (H[j], L[j]) if d == 1 else (-L[j], -H[j])
        hit_sl, hit_tp = lo <= d * sl, hi >= d * tp
        if j == jf:
            hit_tp = False                      # fill candle: the high may have come before the fill
        if hit_sl and hit_tp:
            px = tp if optimistic else sl
        elif hit_sl:
            px = sl
        elif hit_tp:
            px = tp
        if px is not None:
            xt = T[j] + (T[1] - T[0]); break
    if px is None:
        return None
    x = Trade(sym, "position", d, T[jf], e, sl, pos_id=t.pos_id + "-s")
    x.exits = [(xt, px, 1.0)]; x.plan = "Plan 1"
    return x


def main():
    data = {s: load_sym(s) for s in SYMBOLS}
    a, b = build()
    entries = sorted(a + b, key=lambda t: t.entry_time)
    m5 = load("data/BTCUSD_M5.csv")
    out = dict(by_case={}, prop={}, cost={})
    for s in SYMBOLS:
        sp = SYMBOLS[s].spread / PIP[s]
        out["cost"][s] = dict(spread_pips=round(sp, 1), breakeven_win_rate=round((SL_PIPS + sp) / (TP_PIPS + SL_PIPS) * 100, 1))
    print("spread in pips and the win rate needed to break even:", out["cost"])
    sets = {}
    for case in ("conservative", "optimistic"):
        tr = [x for t in entries if (x := replay(t, data[t.symbol][1], case == "optimistic")) is not None]
        sets[case] = tr
        st = stats(tr); st["by_market"] = {s: stats([t for t in tr if t.symbol == s]) for s in SYMBOLS}
        out["by_case"][case] = st
        print(case, {k: v for k, v in st.items() if k != "by_market"})
        for s, v in st["by_market"].items():
            print("   ", s, v.get("n"), "win", v.get("win"), "net", v.get("net"))
    btc = [x for t in entries if t.symbol == "BTCUSD" and (x := replay(t, m5, False)) is not None]
    out["btc_5min"] = stats(btc); print("BTC on 5-minute candles:", out["btc_5min"])
    for case, tr in sets.items():
        out["prop"][case] = {}
        for risk in (0.005, 0.01, 0.02):
            last = prop_account(tr, risk, Y1, NOW)
            ws = windows(tr, lambda tr_, start, end, risk=risk: prop_account(tr_, risk, start, end))
            last["windows"] = dict(median=round(float(np.median([w["paid"] for w in ws]))), worst=min(w["paid"] for w in ws),
                                   breaches=sum(bool(w["breach"]) for w in ws), n=len(ws), worst_dd=max(w["dd"] for w in ws))
            out["prop"][case][f"{risk * 100:.1f}%"] = last
            print(f"PROP {case:12s} {risk * 100:.1f}%  last 12 months paid {last['paid']:6d} breach {last['breach']} | windows median {last['windows']['median']} worst {last['windows']['worst']} breaches {last['windows']['breaches']}/{last['windows']['n']}")
    json.dump(out, open("results/scalp3020.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

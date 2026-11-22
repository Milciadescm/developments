"""Recent data only (2024-2026): can the setup be proven on 10,000+ trades?

The same entry as the bots (monthly + weekly bias, 20-bar breakout leg >= 1.5 ATR with a fair value gap, limit at
0.705, stop at the leg origin) run on every chart the recent data allows:
  BTC 5-minute and 15-minute (Binance, 2024-2026), all 5 markets 1-hour and 4-hour.
Exits: TP 1R / TP 2R / TP leg extreme / time only; always flat within 24 h (prop rule). Spread charged per trade
(config spread; BTC also at a tighter $15 to show cost sensitivity).
    python -m fibfvg.recent10k -> results/recent10k.json
"""
import json

import numpy as np
import pandas as pd

from . import config
from .config import SYMBOLS
from .engines import load
from .levels import load_sym
from .fractal24 import engine, stats, EXITS

STOP = "S1 Fib 1.0"


def run_set(label, sym, daily, bars, tf_tag):
    res = {}
    for ek in EXITS:
        xs = engine(sym, daily, bars, "H1", STOP, ek)          # "H1" = use the bars as given (no resampling)
        res[ek] = xs
    return res


def main():
    out = {}
    daily = {s: load_sym(s)[0] for s in SYMBOLS}
    sets = {}
    for tf, f in (("M5", "data/BTCUSD_M5.csv"), ("M15", "data/BTCUSD_M15.csv")):
        b = load(f)
        sets[f"BTC {tf}"] = [("BTCUSD", b)]
    sets["5 markets H1"] = [(s, load_sym(s)[1]) for s in SYMBOLS]
    sets["5 markets H4"] = [(s, load_sym(s)[1].resample("4h", origin="epoch").agg(dict(Open="first", High="max", Low="min", Close="last")).dropna()) for s in SYMBOLS]
    pool = {ek: [] for ek in EXITS}
    for name, items in sets.items():
        for ek in EXITS:
            xs = [t for s, b in items for t in engine(s, daily[s], b, "H1", STOP, ek)]
            out[f"{name} | {ek}"] = stats(xs) if xs else dict(n=0)
            pool[ek] += xs
            v = out[f"{name} | {ek}"]
            print(f"{name:14s} {ek:18s} n {v['n']:6d} mean {v.get('mean', 0):+.3f} 1st {v.get('first', 0):+.3f} 2nd {v.get('second', 0):+.3f} t {v.get('t', 0):+.2f} win {v.get('win', 0)}")
    for ek in EXITS:
        v = stats(pool[ek]); out[f"ALL charts | {ek}"] = v
        print(f"ALL charts     {ek:18s} n {v['n']:6d} mean {v['mean']:+.3f} 1st {v['first']:+.3f} 2nd {v['second']:+.3f} t {v['t']:+.2f} win {v['win']}")
    # cost sensitivity: BTC at a $15 spread
    old = SYMBOLS["BTCUSD"].spread
    SYMBOLS["BTCUSD"].spread = 15.0
    for tf, f in (("M5", "data/BTCUSD_M5.csv"), ("M15", "data/BTCUSD_M15.csv")):
        b = load(f)
        for ek in EXITS:
            v = stats(engine("BTCUSD", daily["BTCUSD"], b, "H1", STOP, ek)); out[f"BTC {tf} spread $15 | {ek}"] = v
            print(f"BTC {tf} $15     {ek:18s} n {v['n']:6d} mean {v['mean']:+.3f} 1st {v['first']:+.3f} 2nd {v['second']:+.3f} t {v['t']:+.2f} win {v['win']}")
    SYMBOLS["BTCUSD"].spread = old
    json.dump(out, open("results/recent10k.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()

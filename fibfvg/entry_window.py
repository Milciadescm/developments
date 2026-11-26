"""Prop24 con horario de entrada (re-simulación fiel): la orden límite solo está activa entre las horas dadas de Nueva York;
fuera de ese horario el precio puede tocar el nivel sin llenar, y la orden sigue viva hasta que vence.
Nació del análisis de pérdidas (fibfvg/loss_anatomy.py, 26 nov 2026): las entradas de Asia y Londres perdían.
    python -m fibfvg.entry_window -> results/entry_window.json
"""
import json

import numpy as np
import pandas as pd

from . import fractal24
from .engines import net_r
from .prop24 import build

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")


def stats(tr, risk_pct=0.75):
    tr = sorted(tr, key=lambda t: t.entry_time)
    r = np.array([net_r(t) for t in tr])
    m1 = np.array([net_r(t) for t in tr if t.entry_time < SPLIT]); m2 = np.array([net_r(t) for t in tr if t.entry_time >= SPLIT])
    eq = np.cumsum(np.r_[0, r]) * risk_pct
    return dict(n=len(r), R=round(float(r.mean()), 3), t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2),
                mitad1=round(float(m1.mean()), 3), mitad2=round(float(m2.mean()), 3),
                peor_caida_pct_075=round(float(np.max(np.maximum.accumulate(eq) - eq)), 2), suma_R=round(float(r.sum()), 1))


def main():
    out = {}
    for win in (None, (8, 18), (8, 17), (9, 18), (7, 18), (10, 18)):
        fractal24.ENTRY_HOURS_NY = win
        a, b = build()
        key = "siempre" if win is None else f"{win[0]:02d}-{win[1]:02d} NY"
        out[key] = {"3 mercados (BTC, S&P, Nasdaq)": stats([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")]),
                    "5 mercados": stats(a + b)}
        print(key, out[key])
    fractal24.ENTRY_HOURS_NY = None
    json.dump(out, open("results/entry_window.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()

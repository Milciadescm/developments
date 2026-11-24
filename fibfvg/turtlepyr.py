"""Turtle clásico con añadidos, un mercado a la vez, cuenta real de $1,000, posiciones de semanas o meses.

Reglas (velas diarias, decisión al cierre, ejecución en la apertura siguiente; sin mirar el futuro):
  Dirección: rangos mensual y semanal de acuerdo (htf_bias).  Entrada: cierre por encima del máximo de 20 días (o por debajo del mínimo).
  N = ATR de 20 días.  Añadidos: cada +0.5 N a favor, hasta 4 unidades.  Stop común: 2 N desde la última entrada.
  Salida: cierre por debajo del mínimo de 10 días (compras) o por encima del máximo de 10 días (ventas).
  Costos: spread de config.py en cada unidad y swaps de swaps.py por cada día abierto.
Lotes: "fijo 0.01" (todas las unidades 0.01), "doble" (0.01, 0.02, 0.04, 0.08), "fijo 0.02", y "riesgo X %" (la primera unidad
arriesga X % del saldo con el stop de 2 N, mínimo 0.01; cada añadido igual que la primera).
"Quemada" = el saldo baja de $100 (el bot se detiene).
    python -m fibfvg.turtlepyr -> results/turtlepyr.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import load, htf_bias
from .longhold import load_long
from .swaps import RATE


def atr(d, n=20):
    h, l, c = d.High, d.Low, d.Close
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def run(sym, d, sizing, cap=1_000.0, start=None, end=None, units_max=4):
    spec = SYMBOLS[sym]
    b = htf_bias(d)
    N = atr(d).values
    O, H, L, C = (d[k].values for k in ("Open", "High", "Low", "Close"))
    hi20 = d.High.rolling(20).max().shift(1).values; lo20 = d.Low.rolling(20).min().shift(1).values
    hi10 = d.High.rolling(10).max().shift(1).values; lo10 = d.Low.rolling(10).min().shift(1).values
    T = d.index
    bal, peak, low, mdd = cap, cap, cap, 0.0
    pos = []            # list of (entry, lots)
    dirn, stop, lastN, pend = 0, 0.0, 0.0, None
    trades, curve, burned = [], [], None
    i0 = 25
    for i in range(i0, len(T)):
        if start is not None and T[i] < start:
            continue
        if end is not None and T[i] >= end:
            break
        o, h, l, c = O[i], H[i], L[i], C[i]
        # 1) pending order from yesterday's close
        if pend is not None and not burned:
            kind = pend; pend = None
            if kind in ("enter", "add"):
                lots = size_for(sizing, len(pos), bal, lastN if kind == "add" else N[i - 1], spec)
                if lots > 0:
                    px = o
                    bal -= spec.spread * lots * spec.contract
                    pos.append((px, lots))
                    if kind == "enter":
                        lastN = N[i - 1]
                    stop = px - dirn * 2 * lastN
            elif kind == "exit" and pos:
                bal += close_all(pos, o, dirn, spec); trades.append(bal); pos = []
        # 2) stop hit during the day
        if pos and ((dirn > 0 and l <= stop) or (dirn < 0 and h >= stop)):
            px = o if ((dirn > 0 and o <= stop) or (dirn < 0 and o >= stop)) else stop
            bal += close_all(pos, px, dirn, spec); trades.append(bal); pos = []
        # 3) swaps for positions held overnight
        if pos:
            bal -= sum(lots * spec.contract * abs(e) for e, lots in pos) * RATE[sym] / 365
        # mark to market
        eq = bal + (sum((c - e) * dirn * lots * spec.contract for e, lots in pos) if pos else 0.0)
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak); low = min(low, eq)
        curve.append((T[i], eq))
        if eq < 100 and not burned:
            burned = str(T[i].date())
            if pos:
                bal += close_all(pos, c, dirn, spec); pos = []
        if burned:
            continue
        # 4) decisions at the close for tomorrow's open
        if pos:
            if (dirn > 0 and c < lo10[i]) or (dirn < 0 and c > hi10[i]):
                pend = "exit"
            elif len(pos) < units_max and (c - pos[-1][0]) * dirn >= 0.5 * lastN:
                pend = "add"
        else:
            bias = int(b.w.values[i]) if b.w.values[i] == b.m.values[i] else 0
            if np.isnan(N[i]) or np.isnan(hi20[i]):
                continue
            if bias > 0 and c > hi20[i]:
                dirn, pend = 1, "enter"
            elif bias < 0 and c < lo20[i]:
                dirn, pend = -1, "enter"
    if pos:
        bal += close_all(pos, C[min(i, len(C) - 1)], dirn, spec)
    return dict(end=round(bal), worst_dd=round(mdd * 100, 1), low=round(low), burned=burned, positions=len(trades)), curve


def close_all(pos, px, dirn, spec):
    return sum((px - e) * dirn * lots * spec.contract - spec.spread * 0 for e, lots in pos)


def size_for(sizing, k, bal, n, spec):
    kind, v = sizing
    if kind == "fijo":
        return v
    if kind == "doble":
        return round(v * 2 ** k, 2)
    if kind == "riesgo":
        lots = np.floor(bal * v / (2 * n * spec.contract) / spec.lot_step) * spec.lot_step
        return max(round(lots, 2), spec.min_lot)
    return 0


def windows(sym, d, sizing, first, last):
    res = []
    s = first
    while s + pd.DateOffset(months=24) <= last:
        r, _ = run(sym, d, sizing, start=s, end=s + pd.DateOffset(months=24))
        res.append(r)
        s += pd.DateOffset(months=3)
    e = np.array([r["end"] for r in res])
    return dict(n=len(res), median_end=int(np.median(e)), worst_end=int(e.min()), best_end=int(e.max()),
                share_burned=round(float(np.mean([bool(r["burned"]) for r in res]) * 100)),
                share_below_500=round(float(np.mean([r["low"] < 500 for r in res]) * 100)),
                share_losing=round(float(np.mean(e < 1000) * 100)))


def main():
    sizings = [("fijo", 0.01), ("fijo", 0.02), ("doble", 0.01), ("riesgo", 0.01), ("riesgo", 0.02)]
    H0 = pd.Timestamp("2024-07-01", tz="UTC"); L0 = pd.Timestamp("2006-01-01", tz="UTC"); NOW = pd.Timestamp("2026-11-23", tz="UTC")
    out = {}
    for sym in SYMBOLS:
        d = load(f"data/{sym}_D1.csv"); dl = load_long(sym)
        for sz in sizings:
            k = f"{sym} | {sz[0]} {sz[1]}"
            rec, _ = run(sym, d, sz, start=H0)
            full, _ = run(sym, dl, sz, start=L0)
            out[k] = dict(jul2024_hoy=rec, desde_2006=full, ventanas_24m_desde_2006=windows(sym, dl, sz, L0, NOW))
            print(k, json.dumps(out[k]))
    json.dump(out, open("results/turtlepyr.json", "w"), indent=1)


if __name__ == "__main__":
    main()

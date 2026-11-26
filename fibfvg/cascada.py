"""Cascada de riesgo para cuentas pequeñas: el lotaje de CADA operación sale del saldo de ese momento (interés compuesto).

Bot: 24 horas (BTC, S&P 500, Nasdaq), sus 81 operaciones reales jul 2024 - nov 2026, con el riesgo real en dólares de
0.01 lote de cada operación (lote mínimo). Si el % pedido da menos que 0.01 lote, abre 0.01 solo si eso arriesga como máximo
el "tope del lote mínimo" (3 %, o 1.5 veces el riesgo de la cascada si es mayor); si no, la salta.
Meta: $500 -> $710 (+42 %) lo antes posible, sin quemar la cuenta.
Dos pruebas:
  1. Historia real: se repiten las operaciones en su orden, empezando cada mes desde jul 2024 (todas las fechas de inicio posibles).
  2. Simulación: 5,000 caminos de 3 años remuestreando las operaciones (2.8 al mes), con la ventaja completa y sin la mejor operación.
"Caída fuerte" = el saldo cae 50 % desde su máximo en algún momento.  Sin aportes.
    python -m fibfvg.cascada -> results/cascada.json
"""
import json

import numpy as np
import pandas as pd

from .prop24 import build
from .engines import net_r
from .config import SYMBOLS

START, GOAL = 500.0, 710.0

PLANS = {
    "Fijo 0.9 % (el actual)": lambda b, s: 0.009,
    "Fijo 2 %": lambda b, s: 0.02,
    "Fijo 3 %": lambda b, s: 0.03,
    "Fijo 5 %": lambda b, s: 0.05,
    "Fijo 10 %": lambda b, s: 0.10,
    "Cascada que baja al crecer (5 % -> 3 % -> 2 % -> 1.5 %)":
        lambda b, s: 0.05 if b < 700 else 0.03 if b < 1_000 else 0.02 if b < 2_500 else 0.015,
    "Cascada que sube al crecer (1 % -> 2 % -> 3 %)":
        lambda b, s: 0.01 if b < 700 else 0.02 if b < 1_500 else 0.03,
    "3 % con freno (mitad tras 2 pérdidas seguidas)": lambda b, s: 0.015 if s["losses"] >= 2 else 0.03,
    "5 % con freno (mitad tras 2 pérdidas, 1 % si cae 20 %)":
        lambda b, s: 0.01 if b < 0.8 * s["peak"] else 0.025 if s["losses"] >= 2 else 0.05,
}


def trades():
    a, b = build()
    t = sorted([x for x in a + b if x.symbol in ("BTCUSD", "US500", "NAS100") and x.entry_time >= pd.Timestamp("2024-07-01", tz="UTC")],
               key=lambda x: x.entry_time)
    r = np.array([net_r(x) for x in t])
    mr = np.array([abs(x.entry - x.stop) * SYMBOLS[x.symbol].contract * 0.01 for x in t])   # $ de 0.01 lote
    times = [x.entry_time for x in t]
    return r, mr, times


def step(b, r, mr, f, s):
    want = f * b
    cap = max(0.03, 1.5 * f)
    lots = np.floor(want / mr) if mr > 0 else 0          # en pasos de 0.01 lote (el riesgo real se redondea hacia abajo)
    risk = lots * mr if lots >= 1 else (mr if mr <= cap * b else 0.0)
    nb = b + risk * r
    if risk > 0:
        s["losses"] = s["losses"] + 1 if r < 0 else 0
    s["peak"] = max(s["peak"], nb)
    return nb


def history(plan, r, mr, times):
    """empezar en cada mes desde jul 2024 con $500; meses hasta $710 y peor caída"""
    starts = pd.date_range("2024-07-01", "2026-05-01", freq="MS", tz="UTC")
    out = []
    for st in starts:
        b, s, peak, dd, hit = START, dict(losses=0, peak=START), START, 0.0, None
        for x, m, t in zip(r, mr, times):
            if t < st:
                continue
            b = step(b, x, m, PLANS[plan](b, s), s)
            peak = max(peak, b); dd = max(dd, 1 - b / peak)
            if hit is None and b >= GOAL:
                hit = (t - st).days / 30.4
        out.append(dict(inicio=str(st.date()), meses=round(hit, 1) if hit is not None else None, final=round(b), peor_caida=round(dd * 100, 1)))
    reached = [o["meses"] for o in out if o["meses"] is not None]
    return dict(inicios=len(out), llegaron=len(reached), meses_mediana=round(float(np.median(reached)), 1) if reached else None,
                meses_mas_rapido=min(reached) if reached else None, meses_mas_lento=max(reached) if reached else None,
                peor_caida_max=max(o["peor_caida"] for o in out), detalle=out)


def simulate(plan, r, mr, n=5_000, months=36, seed=13):
    rng = np.random.default_rng(seed)
    hit = np.full(n, np.nan); dd50 = np.zeros(n, bool); end = np.zeros(n); ruin = np.zeros(n, bool)
    for p in range(n):
        b, s, peak = START, dict(losses=0, peak=START), START
        for m in range(months):
            for _ in range(rng.poisson(2.8)):
                i = rng.integers(len(r))
                b = step(b, r[i], mr[i], PLANS[plan](b, s), s)
                peak = max(peak, b)
                if b < 0.5 * peak:
                    dd50[p] = True
                if b < 100:
                    ruin[p] = True
            if np.isnan(hit[p]) and b >= GOAL:
                hit[p] = m + 1
        end[p] = b
    ok = ~np.isnan(hit)
    q = lambda x: round(float(np.nanpercentile(hit, x)), 1) if ok.mean() * 100 > x else None
    return dict(llega_en_3_años=round(float(ok.mean() * 100), 1), meses_mediana=q(50), meses_10pct_rapido=q(10),
                meses_90pct=q(90), saldo_3_años_mediana=int(np.median(end)), saldo_3_años_peor_10pct=int(np.percentile(end, 10)),
                caida_50=round(float(dd50.mean() * 100), 1), cae_bajo_100=round(float(ruin.mean() * 100), 1))


def main():
    r, mr, times = trades()
    r_sin = r.copy(); r_sin[np.argmax(r_sin)] = np.median(r)          # sin la mejor operación (+9.8R)
    out = {}
    for plan in PLANS:
        h = history(plan, r, mr, times)
        s1 = simulate(plan, r, mr)
        s2 = simulate(plan, r_sin, mr)
        out[plan] = dict(historia=h, simulacion=s1, simulacion_sin_mejor=s2)
        print(f"{plan:55s} | historia: llegaron {h['llegaron']}/{h['inicios']}, mediana {h['meses_mediana']} meses "
              f"(rápido {h['meses_mas_rapido']}), peor caída {h['peor_caida_max']} % | sim: {s1['llega_en_3_años']} % llega, "
              f"mediana {s1['meses_mediana']} m, caída50 {s1['caida_50']} %, <$100 {s1['cae_bajo_100']} % | "
              f"sin mejor op: {s2['llega_en_3_años']} %, mediana {s2['meses_mediana']} m, caída50 {s2['caida_50']} %")
    json.dump(out, open("results/cascada.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

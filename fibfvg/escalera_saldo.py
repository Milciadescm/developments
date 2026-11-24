"""Riesgo conectado al tamaño de la cuenta (en vez de al calendario).

Mismas operaciones remuestreadas que fibfvg/escalera.py ($1,000 + $200 al mes, 10 años, 24 h siempre, oro desde $5,000).
El riesgo por operación depende del saldo en ese momento (si el saldo baja, el escalón baja solo).
  "Sube con el saldo": más riesgo a medida que la cuenta crece.
  "Baja con el saldo": más riesgo cuando la cuenta es pequeña (lo que se puede perder son pocos dólares y los aportes lo reponen),
                       menos riesgo cuando ya hay mucho dinero que proteger.
    python -m fibfvg.escalera_saldo -> results/escalera_saldo.json
"""
import json

import numpy as np
import pandas as pd

from .escalera import summary, MONTHS
from .prop24 import build
from .engines import net_r
from .plans import position_engine
from .longhold import load_long
from .swaps import with_swaps
from . import scoreboard  # noqa: F401

PLANS = {
    "Fijo 0.9 % (actual)": [(0, 0.009)],
    "Sube con el saldo hasta 5 %": [(0, 0.009), (2_500, 0.015), (5_000, 0.025), (10_000, 0.035), (20_000, 0.05)],
    "Sube con el saldo hasta 10 %": [(0, 0.009), (2_500, 0.015), (5_000, 0.025), (10_000, 0.04), (25_000, 0.06), (50_000, 0.08), (100_000, 0.10)],
    "Baja con el saldo (5 % → 1 %)": [(0, 0.05), (10_000, 0.035), (50_000, 0.025), (250_000, 0.015), (1_000_000, 0.01)],
    "Baja con el saldo (8 % → 1 %)": [(0, 0.08), (10_000, 0.05), (50_000, 0.03), (250_000, 0.02), (1_000_000, 0.01)],
    "Saldo + confirmación trimestral hasta 5 %": [(0, 0.009), (2_500, 0.015), (5_000, 0.025), (10_000, 0.035), (20_000, 0.05)],
}
GATED = {"Saldo + confirmación trimestral hasta 5 %"}
STEPS = [0.009, 0.015, 0.025, 0.035, 0.05]


def risk_for(tiers, b):
    f = tiers[0][1]
    for th, r in tiers:
        if b >= th:
            f = r
    return f


def sim(p24, gold, tiers, dep=200, n=4_000, seed=5, haircut=1.0, gated=False):
    rng = np.random.default_rng(seed)
    p24 = np.array(p24); gold = np.array(gold)
    p24 = p24 - (1 - haircut) * p24.mean(); gold = gold - (1 - haircut) * gold.mean()
    bal = np.zeros((n, MONTHS + 1)); bal[:, 0] = 1_000
    dd50 = np.zeros(n, bool); burned = np.zeros(n, bool)
    for p in range(n):
        b, peak, st, q0 = 1_000.0, 1_000.0, 0, 1_000.0
        rf = (lambda x: min(risk_for(tiers, x), STEPS[st])) if gated else (lambda x: risk_for(tiers, x))
        for m in range(MONTHS):
            if b >= 100:
                for r in rng.choice(p24, rng.poisson(2.8)):
                    b *= 1 + rf(b) * r
                if b >= 5_000:
                    for r in rng.choice(gold, rng.poisson(0.8)):
                        b *= 1 + rf(b) * r
            b += dep
            peak = max(peak, b)
            dd50[p] |= b < 0.5 * peak
            burned[p] |= b < 100
            if gated and (m + 1) % 3 == 0:
                g = b - q0 - 3 * dep
                if g > 0 and b >= 0.85 * peak and st < len(STEPS) - 1:
                    st += 1
                elif g < 0 and st > 0:
                    st -= 1
                q0 = b
                rf = lambda x: min(risk_for(tiers, x), STEPS[st])
            bal[p, m + 1] = b
    return bal, dd50, burned


def main():
    a, b = build()
    p24 = [net_r(t) for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100") and t.entry_time >= pd.Timestamp("2024-07-01", tz="UTC")]
    gold = [net_r(t) for t in with_swaps(position_engine("XAUUSD", load_long("XAUUSD"), "BE2", start="2006-01-01"))]
    out = {}
    for label, pp, hc in (("ventaja completa", p24, 1.0), ("sin la mejor operación", sorted(p24)[:-1], 1.0), ("ventaja a la mitad", p24, 0.5)):
        for name, tiers in PLANS.items():
            k = f"{name} | {label}"
            s = out[k] = summary(*sim(pp, gold, tiers, haircut=hc, gated=name in GATED))
            m = s["metas"]
            print(f"{k:60s} año5 {s['por_año']['año 5']['mediana']:>9} año10 {s['por_año']['año 10']['mediana']:>11} "
                  f"caída50 {s['prob_caida_50']:>5} | 100K años {m['$100,000']['años_mediana']} p5 {m['$100,000']['prob_5_años']} "
                  f"| 1M p10 {m['$1,000,000']['prob_10_años']} años {m['$1,000,000']['años_mediana']}")
    json.dump(out, open("results/escalera_saldo.json", "w"), indent=1)


if __name__ == "__main__":
    main()

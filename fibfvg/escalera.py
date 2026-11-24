"""Subir el riesgo cada 3 meses: cuánto se acortan los años y cuánto riesgo de quemar la cuenta trae.

Base: $1,000 real + $200 al mes, 10 años. Operaciones remuestreadas de los backtests reales:
  bot de 24 horas (BTC, S&P, Nasdaq; 81 operaciones jul 2024-nov 2026, ~2.8 al mes) siempre;
  bot Hold en oro (186 operaciones 2006-2026, ~0.8 al mes) cuando el saldo pasa de $5,000.
Escalera: cada 3 meses, si el trimestre ganó y la cuenta está a menos del 15 % de su máximo, el riesgo sube un escalón;
si el trimestre perdió, baja un escalón. Kelly (el riesgo que maximiza el crecimiento) = 20 % (24 h) y 14 % (oro):
con incertidumbre en la ventaja, lo prudente es un cuarto de Kelly (~5 %).
"Quemada" = el saldo baja de $100.
    python -m fibfvg.escalera -> results/escalera.json
"""
import json

import numpy as np
import pandas as pd

from .prop24 import build
from .engines import net_r
from .plans import position_engine
from .longhold import load_long
from .swaps import with_swaps
from . import scoreboard  # noqa: F401

TARGETS = [10_000, 20_000, 50_000, 100_000, 200_000, 500_000, 1_000_000, 5_000_000, 10_000_000]
MONTHS = 120
START = pd.Timestamp("2026-12-01")
PLANS = {
    "Fijo 0.9 % (actual)": [0.009],
    "Escalera hasta 2 %": [0.009, 0.0125, 0.015, 0.02],
    "Escalera hasta 5 % (1/4 Kelly)": [0.009, 0.015, 0.025, 0.035, 0.05],
    "Escalera hasta 10 % (1/2 Kelly)": [0.009, 0.015, 0.025, 0.04, 0.06, 0.08, 0.10],
    "Fijo 20 % (Kelly completo)": [0.20],
}


def sim(p24, gold, steps, dep=200, n=4_000, seed=5, haircut=1.0):
    rng = np.random.default_rng(seed)
    p24 = np.array(p24); gold = np.array(gold)
    p24 = p24 - (1 - haircut) * p24.mean(); gold = gold - (1 - haircut) * gold.mean()   # menos ventaja, misma volatilidad
    bal = np.zeros((n, MONTHS + 1)); bal[:, 0] = 1_000
    dd50 = np.zeros(n, bool); burned = np.zeros(n, bool); maxstep = np.zeros(n, int)
    for p in range(n):
        b, peak, s, qstart = 1_000.0, 1_000.0, 0, 1_000.0
        for m in range(MONTHS):
            if b >= 100:
                f = steps[s]
                for r in rng.choice(p24, rng.poisson(2.8)):
                    b *= 1 + f * r
                if b >= 5_000:
                    for r in rng.choice(gold, rng.poisson(0.8)):
                        b *= 1 + f * r
            b += dep
            peak = max(peak, b)
            if b < 0.5 * peak:
                dd50[p] = True
            if b < 100:
                burned[p] = True
            if (m + 1) % 3 == 0:
                gain = b - qstart - 3 * dep
                if gain > 0 and b >= 0.85 * peak and s < len(steps) - 1:
                    s += 1
                elif gain < 0 and s > 0:
                    s -= 1
                maxstep[p] = max(maxstep[p], s)
                qstart = b
            bal[p, m + 1] = b
    return bal, dd50, burned


def summary(bal, dd50, burned):
    q = lambda a, x: int(np.percentile(a, x))
    yrs = {f"año {y}": dict(p10=q(bal[:, 12 * y], 10), mediana=q(bal[:, 12 * y], 50), p90=q(bal[:, 12 * y], 90)) for y in (1, 2, 3, 5, 7, 10)}
    tg = {}
    for t in TARGETS:
        ok = (bal >= t).any(axis=1); hit = np.argmax(bal >= t, axis=1)
        tg[f"${t:,}"] = dict(prob_5_años=round(float((ok & (hit <= 60)).mean() * 100), 1), prob_10_años=round(float(ok.mean() * 100), 1),
                             años_mediana=round(float(np.median(hit[ok])) / 12, 1) if ok.mean() >= 0.5 else None,
                             años_10pct_rapido=round(float(np.percentile(hit[ok], 10)) / 12, 1) if ok.any() else None)
    return dict(por_año=yrs, metas=tg, prob_caida_50=round(float(dd50.mean() * 100), 1), prob_quemada=round(float(burned.mean() * 100), 1),
                prob_bajo_aportes_año5=round(float((bal[:, 60] < 1_000 + 60 * 200).mean() * 100), 1))


def main():
    a, b = build()
    p24 = [net_r(t) for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100") and t.entry_time >= pd.Timestamp("2024-07-01", tz="UTC")]
    gold = [net_r(t) for t in with_swaps(position_engine("XAUUSD", load_long("XAUUSD"), "BE2", start="2006-01-01"))]
    out = {}
    p24_sin = sorted(p24)[:-1]   # sin la mejor operación (+9.8R)
    for label, pp, hc in (("ventaja completa", p24, 1.0), ("sin la mejor operación", p24_sin, 1.0), ("ventaja a la mitad", p24, 0.5)):
        for name, steps in PLANS.items():
            k = f"{name} | {label}"
            out[k] = summary(*sim(pp, gold, steps, haircut=hc))
            s = out[k]
            print(k, "| año5", s["por_año"]["año 5"], "| año10", s["por_año"]["año 10"], "| caída50", s["prob_caida_50"], "quemada", s["prob_quemada"],
                  "| 1M", s["metas"]["$1,000,000"], "| 100K", s["metas"]["$100,000"])
    json.dump(out, open("results/escalera.json", "w"), indent=1)


if __name__ == "__main__":
    main()

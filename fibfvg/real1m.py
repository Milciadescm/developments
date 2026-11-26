"""Prop24 V2 en una cuenta REAL de $1,000,000, sin retiros ni aportes, 5 años.  10,000 simulaciones por plan
(remuestreo de las operaciones reales de V2 al ritmo real).  Planes: 1 %, 2 % fijo; 5 % y 10 % con freno.
Con $1M el lote mínimo no limita.  No incluye deslizamiento extra por tamaño (a 5-10 % se arriesgan $50-100K por operación).
    python -m fibfvg.real1m -> results/real1m.json
"""
import json

import numpy as np

from .forecast_v2 import base_trades

START, MONTHS, N = 1_000_000.0, 60, 10_000
PLANS = {"1 % fijo": (0.01, 0.01, False), "2 % fijo": (0.02, 0.02, False), "5 % con freno": (0.05, 0.01, True), "10 % con freno": (0.10, 0.02, True)}


def main():
    tr, r, cost, half, lam = base_trades()
    out = {}
    for name, (risk, low, brake) in PLANS.items():
        rng = np.random.default_rng(21)
        B = np.zeros((N, MONTHS + 1)); B[:, 0] = START; mdd = np.zeros(N)
        for p in range(N):
            b, peak, losses = START, START, 0
            for m in range(MONTHS):
                for _ in range(rng.poisson(lam)):
                    x = r[rng.integers(len(r))]
                    f = (low if b < 0.8 * peak else risk / 2 if losses >= 2 else risk) if brake else risk
                    b += f * b * x; losses = losses + 1 if x < 0 else 0
                    peak = max(peak, b); mdd[p] = max(mdd[p], 1 - b / peak)
                B[p, m + 1] = b
        yrs = [dict(año=y, mediana=int(np.median(B[:, 12 * y])), p10=int(np.percentile(B[:, 12 * y], 10)), p90=int(np.percentile(B[:, 12 * y], 90)),
                    pierde_pct=round(float((B[:, 12 * y] < START).mean() * 100), 1)) for y in range(1, 6)]
        monthly = np.diff(B, axis=1)
        out[name] = dict(años=yrs, caida_mediana_pct=round(float(np.median(mdd) * 100), 1), caida_p95_pct=round(float(np.percentile(mdd, 95) * 100), 1),
                         meses_en_perdida_pct=round(float((monthly < 0).mean() * 100)), anual_mediano_pct=round(float(((np.median(B[:, -1]) / START) ** 0.2 - 1) * 100), 1),
                         pnl_mes_año1_mediana=int(np.median(B[:, 12] - START) / 12))
        print(name, json.dumps(out[name], ensure_ascii=False))
    json.dump(out, open("results/real1m.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()

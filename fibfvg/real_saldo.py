"""Prop24 V2 en una cuenta REAL con cualquier saldo inicial, sin retiros ni aportes, 5 años (lote mínimo 0.01 real).
10,000 simulaciones por plan (fijo 2 %, fijo 3 %, 5 % con freno, 10 % con freno).
    python -m fibfvg.real_saldo 5000 -> results/real_saldo_5000.json
"""
import json
import sys

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import net_r
from .v2_eval import PLANS, P3, step, trades

MONTHS, N = 60, 10_000


def main(start):
    tr = [t for t in trades((8, 18)) if t.symbol in P3 and t.entry_time >= pd.Timestamp("2024-07-01", tz="UTC")]
    r = np.array([net_r(t) for t in tr]); mr = np.array([abs(t.entry - t.stop) * SYMBOLS[t.symbol].contract * 0.01 for t in tr])
    lam = len(tr) / ((tr[-1].entry_time - tr[0].entry_time).days / 30.44)
    out = {}
    for plan in PLANS:
        rng = np.random.default_rng(11)
        B = np.zeros((N, MONTHS + 1)); B[:, 0] = start
        for p in range(N):
            b, s = start, dict(losses=0, peak=start)
            for m in range(MONTHS):
                for _ in range(rng.poisson(lam)):
                    i = rng.integers(len(r)); b = step(b, r[i], mr[i], PLANS[plan](b, s), s)
                B[p, m + 1] = b
        dd = np.max(1 - B / np.maximum.accumulate(B, axis=1), axis=1) * 100
        out[plan] = dict(años=[dict(año=y, mediana=int(np.median(B[:, 12 * y])), p10=int(np.percentile(B[:, 12 * y], 10)), p90=int(np.percentile(B[:, 12 * y], 90)),
                                    pierde_pct=round(float((B[:, 12 * y] < start).mean() * 100), 1)) for y in range(1, 6)],
                         caida_mediana_pct=round(float(np.median(dd)), 1), caida_p95_pct=round(float(np.percentile(dd, 95)), 1),
                         llega_a={f"${g:,}": round(float((B.max(axis=1) >= g).mean() * 100)) for g in (10_000, 50_000, 100_000, 1_000_000)},
                         pnl_mes_año1=int((np.median(B[:, 12]) - start) / 12))
        print(plan, json.dumps(out[plan], ensure_ascii=False))
    json.dump(out, open(f"results/real_saldo_{int(start)}.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 5_000.0)

"""Prop24 V2 en una cuenta REAL de $500, sin retiros ni aportes, 5 años: P&L mes a mes.

Lotaje desde el saldo de cada momento en pasos de 0.01 lote (como el EA con MinLotIfBelow): si el % pide menos de 0.01 lote,
abre 0.01 solo si eso arriesga como máximo 1.5 x el % del plan; si no, salta la operación.  Solo BTC, S&P, Nasdaq.
Planes: 5 % con freno (recomendado) y 10 % con freno.  10,000 caminos remuestreando las operaciones reales de V2 al ritmo real;
por mes: saldo mediano, 10 % peor y 10 % mejor, y P&L del mes del camino mediano.  Además, la historia real jul 2024 - nov 2026.
    python -m fibfvg.real500 -> results/real500.json y results/real500_mes_a_mes.md
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import net_r
from .v2_eval import PLANS, P3, step, trades

START = 500.0
MONTHS = 60
N = 10_000


def main():
    tr = [t for t in trades((8, 18)) if t.symbol in P3 and t.entry_time >= pd.Timestamp("2024-07-01", tz="UTC")]
    r = np.array([net_r(t) for t in tr]); mr = np.array([abs(t.entry - t.stop) * SYMBOLS[t.symbol].contract * 0.01 for t in tr])
    lam = len(tr) / ((tr[-1].entry_time - tr[0].entry_time).days / 30.44)
    out, md = {}, []
    for plan in ("5 % con freno", "10 % con freno"):
        rng = np.random.default_rng(11)
        B = np.zeros((N, MONTHS + 1)); B[:, 0] = START; skipped = np.zeros(N); taken = np.zeros(N)
        for p in range(N):
            b, s = START, dict(losses=0, peak=START)
            for m in range(MONTHS):
                for _ in range(rng.poisson(lam)):
                    i = rng.integers(len(r))
                    nb = step(b, r[i], mr[i], PLANS[plan](b, s), s)
                    skipped[p] += nb == b; taken[p] += nb != b
                    b = nb
                B[p, m + 1] = b
        med, p10, p90 = np.median(B, axis=0), np.percentile(B, 10, axis=0), np.percentile(B, 90, axis=0)
        # P&L mensual mediano: mediana entre caminos del cambio de cada mes
        pnl = np.median(np.diff(B, axis=1), axis=0)
        loss_month = (np.diff(B, axis=1) < 0).mean(axis=0) * 100
        rows = [dict(mes=m + 1, saldo_mediana=round(float(med[m + 1])), saldo_p10=round(float(p10[m + 1])), saldo_p90=round(float(p90[m + 1])),
                     pnl_mes_mediana=round(float(pnl[m]), 2), meses_en_perdida_pct=round(float(loss_month[m]))) for m in range(MONTHS)]
        yearly = [dict(año=y, saldo_mediana=round(float(med[12 * y])), p10=round(float(p10[12 * y])), p90=round(float(p90[12 * y])),
                       ganancia_del_año_mediana=round(float(med[12 * y] - med[12 * (y - 1)]))) for y in range(1, 6)]
        dd = np.max(1 - B / np.maximum.accumulate(B, axis=1), axis=1) * 100
        out[plan] = dict(meses=rows, años=yearly, operaciones_saltadas_por_lote_minimo_pct=round(float(skipped.sum() / (skipped.sum() + taken.sum()) * 100), 1),
                         caida_max_mediana_pct=round(float(np.median(dd)), 1), caida_max_p95_pct=round(float(np.percentile(dd, 95)), 1),
                         termina_en_perdida_pct=round(float((B[:, -1] < START).mean() * 100), 1),
                         llega_a={f"${g:,}": round(float((B.max(axis=1) >= g).mean() * 100)) for g in (1_000, 5_000, 10_000, 50_000, 100_000)})
        print(plan, {k: v for k, v in out[plan].items() if k != "meses"})
        md.append(f"\n## {plan} — $500 inicial, sin retiros ni aportes\n\n| Mes | Saldo mediano | 10 % peor | 10 % mejor | P&L del mes (mediana) | Prob. mes en pérdida |\n|---|---|---|---|---|---|")
        for x in rows:
            md.append(f"| {x['mes']} | ${x['saldo_mediana']:,} | ${x['saldo_p10']:,} | ${x['saldo_p90']:,} | ${x['pnl_mes_mediana']:+,.2f} | {x['meses_en_perdida_pct']} % |")
    # historia real con $500
    hist = {}
    for plan in ("5 % con freno", "10 % con freno"):
        b, s, rows = START, dict(losses=0, peak=START), []
        for t, x, m_ in sorted(zip([t.exit_time for t in tr], r, mr), key=lambda z: z[0]):
            b = step(b, x, m_, PLANS[plan](b, s), s); rows.append((t, b))
        ser = pd.Series([b for _, b in rows], index=pd.DatetimeIndex([t for t, _ in rows])).resample("ME").last().ffill()
        hist[plan] = {k.strftime("%Y-%m"): round(float(v), 2) for k, v in ser.items()}
    out["historia_real"] = hist
    md.insert(0, "# Prop24 V2 con $500 reales: P&L mes a mes, 5 años (10,000 simulaciones, backtest)\n\nHistoria real jul 2024 - nov 2026 (saldo a fin de mes):\n\n| Mes | 5 % con freno | 10 % con freno |\n|---|---|---|\n"
              + "\n".join(f"| {k} | ${hist['5 % con freno'][k]:,.2f} | ${hist['10 % con freno'][k]:,.2f} |" for k in hist["5 % con freno"]))
    open("results/real500_mes_a_mes.md", "w").write("\n".join(md) + "\n")
    json.dump(out, open("results/real500.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(hist, ensure_ascii=False))


if __name__ == "__main__":
    main()

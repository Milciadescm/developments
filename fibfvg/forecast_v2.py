"""Pronóstico de Prop24 V2: KPI esperados con miles de simulaciones y escenarios adversos ("¿y si el mercado juega en contra?").

Base: las operaciones reales de V2 (entradas 08-18 NY) en BTC, S&P 500 y Nasdaq, jul 2024 - nov 2026, R neto de spread.
Configuraciones:
  GFT  : Instant Premium $100K, 0.9 % fijo, 6 % trailing (se fija en el saldo inicial), pagos cada 14 días con 5 días
         rentables (>= +0.5 %), reparto 80 %; tope de $2,000 por pago (lo que dijo el usuario) y sin tope.
  REAL : cuenta de $100K "real", riesgo 10 % (y 5 %) del saldo actual con freno: mitad tras 2 pérdidas seguidas,
         2 % (1 % en el plan de 5 %) si el saldo cae 20 % desde su máximo; el bot se detiene si vuelve a $50K.
Escenarios (2,000 simulaciones cada uno, 12 y 24 meses):
  base                 remuestreo de las operaciones, ritmo real (Poisson)
  rachas               remuestreo en bloques de 5 operaciones seguidas (conserva rachas reales)
  ventaja -50 %        cada operación pierde la mitad de la ventaja media
  sin ventaja          ventaja media = 0 (el mercado cambió y el bot ya no tiene ventaja)
  costos x3            spread tres veces mayor
  menos operaciones    40 % menos señales
  más operaciones      40 % más señales
  peor racha primero   cada simulación empieza con la peor racha histórica (8 pérdidas)
  sin las 3 mejores    se quitan las 3 mejores operaciones
  solo mitad 1 / 2     solo las operaciones antes / después del 19 ago 2025
  historia real        el orden real empezando cada mes (no remuestreado)
    python -m fibfvg.forecast_v2 -> results/forecast_v2.json
"""
import json

import numpy as np
import pandas as pd

from . import fractal24
from .config import SYMBOLS
from .engines import net_r
from .prop24 import build

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
N = 2_000


def base_trades():
    fractal24.ENTRY_HOURS_NY = (8, 18)
    a, b = build()
    fractal24.ENTRY_HOURS_NY = None
    tr = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    r = np.array([net_r(t) for t in tr])
    cost = np.array([SYMBOLS[t.symbol].spread / abs(t.entry - t.stop) for t in tr])
    half = np.array([1 if t.entry_time < SPLIT else 2 for t in tr])
    months = (tr[-1].entry_time - tr[0].entry_time).days / 30.44
    return tr, r, cost, half, len(tr) / months


def scenarios(r, cost, half):
    m = r.mean()
    worst = np.sort(r)[:8]
    return {
        "base": dict(r=r),
        "rachas": dict(r=r, block=5),
        "ventaja -50 %": dict(r=r - 0.5 * m),
        "sin ventaja": dict(r=r - m),
        "costos x3": dict(r=r - 2 * cost),
        "menos operaciones (-40 %)": dict(r=r, freq=0.6),
        "más operaciones (+40 %)": dict(r=r, freq=1.4),
        "peor racha primero": dict(r=r, prefix=worst),
        "sin las 3 mejores": dict(r=np.sort(r)[:-3]),
        "solo mitad 1": dict(r=r[half == 1]),
        "solo mitad 2": dict(r=r[half == 2]),
    }


def draw(rng, sc, lam, days):
    """devuelve lista de (día, R) para una simulación"""
    r = sc["r"]; f = sc.get("freq", 1.0)
    n = rng.poisson(lam * f * days / 30.44)
    if sc.get("block"):
        out = []
        while len(out) < n:
            s = rng.integers(0, len(r)); out += list(r[s:s + sc["block"]])
        R = np.array(out[:n])
    else:
        R = r[rng.integers(0, len(r), n)]
    if "prefix" in sc:
        R = np.concatenate([sc["prefix"], R])[:max(n, len(sc["prefix"]))]
    d = np.sort(rng.integers(0, days, len(R)))
    return d, R


def gft_path(d, R, days, risk=0.009, cap=2_000.0, size=100_000.0):
    bal, peak, paid, pdays, last, pays, first, mdd = 0.0, 0.0, 0.0, 0, 0, 0, None, 0.0
    floor = -0.06 * size
    j = 0
    for day in range(days):
        p = 0.0
        while j < len(d) and d[j] == day:
            p += R[j] * risk * size; j += 1
        bal += p
        if p >= 0.005 * size:
            pdays += 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - 0.06 * size), 0.0)
        mdd = max(mdd, (peak - bal) / size)
        if bal <= floor:
            return dict(paid=paid, burned=True, payouts=pays, first=first, mdd=mdd)
        if day - last >= 14 and pdays >= 5 and bal > 0:
            w = 0.8 * bal if cap is None else min(0.8 * bal, cap)
            paid += w; bal -= w / 0.8; pays += 1; pdays = 0; last = day
            first = first if first is not None else day
            peak = bal; floor = min(max(-0.06 * size, peak - 0.06 * size), 0.0)
    return dict(paid=paid, burned=False, payouts=pays, first=first, mdd=mdd)


def real_path(d, R, risk, low, start=100_000.0):
    b, peak, losses, mdd, stopped = start, start, 0, 0.0, False
    curve = []
    for x in R:
        if stopped:
            break
        f = low if b < 0.8 * peak else (risk / 2 if losses >= 2 else risk)
        b += f * b * x
        losses = losses + 1 if x < 0 else 0
        peak = max(peak, b); mdd = max(mdd, 1 - b / peak)
        if b <= 0.5 * start:
            stopped = True
        curve.append(b)
    return b, mdd, stopped


def summarize_gft(res, months):
    paid = np.array([x["paid"] for x in res]); burned = np.array([x["burned"] for x in res])
    first = np.array([x["first"] for x in res if x["first"] is not None])
    mdd = np.array([x["mdd"] for x in res]) * 100
    return dict(cobrado_mediana=int(np.median(paid)), cobrado_p10=int(np.percentile(paid, 10)), cobrado_p90=int(np.percentile(paid, 90)),
                por_mes_mediana=int(np.median(paid) / months), sin_cobrar_nada_pct=round(float((paid == 0).mean() * 100), 1),
                quema_cuenta_pct=round(float(burned.mean() * 100), 1), recupera_760_pct=round(float((paid >= 760).mean() * 100), 1),
                dias_al_primer_pago_mediana=float(np.median(first)) if len(first) else None,
                caida_max_mediana_pct=round(float(np.median(mdd)), 2), caida_max_p95_pct=round(float(np.percentile(mdd, 95)), 2))


def summarize_real(res, start=100_000.0):
    end = np.array([x[0] for x in res]); mdd = np.array([x[1] for x in res]) * 100; st = np.array([x[2] for x in res])
    return dict(saldo_mediana=int(np.median(end)), saldo_p10=int(np.percentile(end, 10)), saldo_p90=int(np.percentile(end, 90)),
                ganancia_mediana_pct=round(float((np.median(end) / start - 1) * 100), 1), pierde_dinero_pct=round(float((end < start).mean() * 100), 1),
                caida_max_mediana_pct=round(float(np.median(mdd)), 1), caida_max_p95_pct=round(float(np.percentile(mdd, 95)), 1),
                caida_30_pct=round(float((mdd >= 30).mean() * 100), 1), bot_detenido_en_50k_pct=round(float(st.mean() * 100), 1))


def history_starts(tr, r):
    """el orden real empezando el día 1 de cada mes, 12 meses"""
    out = dict(gft=[], real10=[], real5=[])
    for s0 in pd.date_range("2024-08-01", "2025-11-01", freq="MS", tz="UTC"):
        idx = [i for i, t in enumerate(tr) if s0 <= t.entry_time < s0 + pd.Timedelta(days=365)]
        d = np.array([(tr[i].exit_time - s0).days for i in idx]); R = r[idx]
        out["gft"].append(gft_path(d, R, 365)); out["real10"].append(real_path(d, R, 0.10, 0.02)); out["real5"].append(real_path(d, R, 0.05, 0.01))
    return out


def kpis(tr, r, lam):
    wins, loss = r[r > 0], r[r <= 0]
    return dict(operaciones=len(r), por_mes=round(lam, 2), por_semana=round(lam / 4.35, 2), R_por_operacion=round(float(r.mean()), 3),
                aciertos_pct=round(float((r > 0).mean() * 100), 1), ganancia_media_R=round(float(wins.mean()), 2), perdida_media_R=round(float(loss.mean()), 2),
                RR=round(float(wins.mean() / -loss.mean()), 2), profit_factor=round(float(wins.sum() / -loss.sum()), 2),
                t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2),
                mitad1_R=round(float(r[[t.entry_time < SPLIT for t in tr]].mean()), 3), mitad2_R=round(float(r[[t.entry_time >= SPLIT for t in tr]].mean()), 3),
                horas_abierta_mediana=float(np.median([(t.exit_time - t.entry_time).total_seconds() / 3600 for t in tr])),
                peor_racha=int(max(sum(1 for _ in g) for k, g in __import__("itertools").groupby(r <= 0) if k)))


def main():
    tr, r, cost, half, lam = base_trades()
    out = dict(kpi=kpis(tr, r, lam), escenarios={}, simulaciones_totales=0)
    print("KPI", out["kpi"])
    for name, sc in scenarios(r, cost, half).items():
        rng = np.random.default_rng(abs(hash(name)) % 2**32)
        row = {}
        for months in (12, 24):
            days = int(months * 30.44)
            g_cap, g_nocap, r10, r5 = [], [], [], []
            for _ in range(N):
                d, R = draw(rng, sc, lam, days)
                g_cap.append(gft_path(d, R, days)); g_nocap.append(gft_path(d, R, days, cap=None))
                r10.append(real_path(d, R, 0.10, 0.02)); r5.append(real_path(d, R, 0.05, 0.01))
            out["simulaciones_totales"] += N
            row[f"{months} meses"] = {"GFT $100K 0.9 % (tope $2K por pago)": summarize_gft(g_cap, months),
                                       "GFT $100K 0.9 % (sin tope)": summarize_gft(g_nocap, months),
                                       "Real $100K 10 % con freno": summarize_real(r10), "Real $100K 5 % con freno": summarize_real(r5)}
        out["escenarios"][name] = row
        a, b, c = row["12 meses"]["GFT $100K 0.9 % (tope $2K por pago)"], row["12 meses"]["Real $100K 10 % con freno"], row["12 meses"]["Real $100K 5 % con freno"]
        print(f"{name:28s} GFT 12m: cobra {a['cobrado_mediana']} (p10 {a['cobrado_p10']}, p90 {a['cobrado_p90']}), quema {a['quema_cuenta_pct']} %, recupera $760 {a['recupera_760_pct']} % | "
              f"Real 10 %: {b['saldo_mediana']} (p10 {b['saldo_p10']}, p90 {b['saldo_p90']}), pierde {b['pierde_dinero_pct']} %, caída p95 {b['caida_max_p95_pct']} %, se detiene {b['bot_detenido_en_50k_pct']} % | "
              f"Real 5 %: {c['saldo_mediana']} (p10 {c['saldo_p10']}), pierde {c['pierde_dinero_pct']} %")
    h = history_starts(tr, r)
    out["escenarios"]["historia real (16 inicios, 12 meses)"] = {"12 meses": {"GFT $100K 0.9 % (tope $2K por pago)": summarize_gft(h["gft"], 12),
                                                                             "Real $100K 10 % con freno": summarize_real(h["real10"]),
                                                                             "Real $100K 5 % con freno": summarize_real(h["real5"])}}
    print("historia real", out["escenarios"]["historia real (16 inicios, 12 meses)"])
    print("simulaciones totales", out["simulaciones_totales"] * 4, "(4 cuentas por simulación)")
    json.dump(out, open("results/forecast_v2.json", "w"), indent=1, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()

"""Años hasta $1M desde cada saldo inicial real ($100 ... $100,000), con $200 al mes de aporte.

Calendario: diciembre 2026 = 1 mes de prueba en demo; la cuenta real empieza en enero 2027.
Bots (los mejores que pasaron las pruebas):
  - Bot de 24 horas (BTC, S&P 500, Nasdaq), las 81 operaciones reales jul 2024-nov 2026 (~2.8 al mes).
  - Bot Hold solo en oro, las 186 operaciones 2006-2026 (~0.8 al mes; versión de 20 años, no la de la subida reciente).
Lote mínimo real: cada operación tiene su stop en dólares para 0.01 lote. Si el % pedido da menos que eso, abre 0.01 lote
solo si ese 0.01 arriesga como máximo 3 % del saldo; si no, la operación se salta. Así una cuenta pequeña solo puede operar
los mercados "baratos" (S&P, Nasdaq) y el oro entra solo cuando el saldo lo permite.
Riesgo:
  "Fijo 0.9 %": todo el tiempo.
  "Ascenso en el mes 6 por desviación estándar": empieza en 0.9 %. En el mes 6 se compara el resultado real de los 6 meses
  con lo esperado (media y desviación estándar de 6 meses al 0.9 %). Si quedó por encima de media - 1 desviación, el riesgo
  sube al techo calculado: el mayor riesgo cuyo peor caso de 6 meses (percentil 5) no pierde más de 15 %. Después, cada
  trimestre por debajo de media - 2 desviaciones, o una caída de 20 % desde el máximo, devuelve el riesgo a 0.9 %;
  un trimestre por encima de media - 1 desviación (con la cuenta a menos de 15 % de su máximo) lo vuelve a subir.
    python -m fibfvg.plan_saldos -> results/plan_saldos.json
"""
import json

import numpy as np
import pandas as pd

from .prop24 import build
from .engines import net_r
from .plans import position_engine
from .longhold import load_long
from .swaps import with_swaps
from .config import SYMBOLS
from . import scoreboard  # noqa: F401

BALANCES = [100, 500, 1_000, 2_000, 5_000, 10_000, 50_000, 100_000]
MONTHS = 300
DEP = 200
GOLD_NOW = 4_000.0
SLOTS_24, SLOTS_G = 9, 5


def trade_tables():
    a, b = build()
    t24 = [t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100") and t.entry_time >= pd.Timestamp("2024-07-01", tz="UTC")]
    r24 = np.array([net_r(t) for t in t24])
    m24 = np.array([abs(t.entry - t.stop) * SYMBOLS[t.symbol].contract * 0.01 for t in t24])          # $ risk of 0.01 lot
    tg = with_swaps(position_engine("XAUUSD", load_long("XAUUSD"), "BE2", start="2006-01-01"))
    rg = np.array([net_r(t) for t in tg])
    mg = np.array([abs(t.entry - t.stop) / t.entry * GOLD_NOW * SYMBOLS["XAUUSD"].contract * 0.01 for t in tg])  # at today's gold price
    return r24, m24, rg, mg


def six_month_bands(r24, rg, f, n=20_000, seed=3):
    """distribución del rendimiento de 6 meses con riesgo f (cuenta grande, sin lote mínimo)"""
    rng = np.random.default_rng(seed)
    out = np.ones(n)
    for _ in range(6):
        k = rng.poisson(2.8, n); kg = rng.poisson(0.8, n)
        for j in range(k.max()):
            out *= np.where(j < k, 1 + f * rng.choice(r24, n), 1)
        for j in range(kg.max()):
            out *= np.where(j < kg, 1 + f * rng.choice(rg, n), 1)
    x = out - 1
    return dict(media=float(x.mean()), sd=float(x.std()), p5=float(np.percentile(x, 5)), p50=float(np.median(x)), p95=float(np.percentile(x, 95)))


def simulate(start, r24, m24, rg, mg, plan, f_cap, band, n=1_000, seed=9):
    rng = np.random.default_rng(seed)
    b = np.full(n, float(start)); peak = b.copy(); f = np.full(n, 0.009)
    hit = np.full(n, -1); dd50 = np.zeros(n, bool); b6 = b.copy(); bq = b.copy()
    deps6 = 0.0
    for m in range(MONTHS):
        for r, mr, lam, slots in ((r24, m24, 2.8, SLOTS_24), (rg, mg, 0.8, SLOTS_G)):
            k = rng.poisson(lam, n)
            for j in range(slots):
                idx = rng.integers(0, len(r), n)
                want = f * b                                    # $ que el % pide arriesgar
                minr = mr[idx]                                  # $ que arriesga 0.01 lote
                risk = np.where(want >= minr, want, np.where(minr <= 0.03 * b, minr, 0.0))
                b = np.where(j < k, b + risk * r[idx], b)
        b = np.maximum(b, 0) + DEP
        peak = np.maximum(peak, b); dd50 |= b < 0.5 * peak
        newly = (hit < 0) & (b >= 1_000_000); hit[newly] = m + 1
        if plan == "sigma":
            if m + 1 == 6:
                ret6 = (b - 6 * DEP) / b6 - 1
                f = np.where(ret6 >= band["media"] - band["sd"], f_cap, 0.009)
                bq = b.copy()
            elif m + 1 > 6 and (m + 1) % 3 == 0:
                retq = (b - 3 * DEP) / bq - 1
                good = (retq >= band["q_media"] - band["q_sd"]) & (b >= 0.85 * peak)
                bad = (retq < band["q_media"] - 2 * band["q_sd"]) | (b < 0.8 * peak)
                f = np.where(bad, 0.009, np.where(good, f_cap, f))
                bq = b.copy()
            if m + 1 > 6:
                f = np.where(b < 0.8 * peak, 0.009, f)          # freno: caída de 20 % desde el máximo -> 0.9 %
    yrs = np.where(hit > 0, hit / 12, np.nan)
    ok = ~np.isnan(yrs)
    q = lambda p: round(float(np.nanpercentile(yrs, p)), 1) if ok.mean() * 100 > p else None
    return dict(años_a_1M_mediana=q(50), años_rapido_10pct=q(10), años_lento_90pct=q(90),
                prob_1M_10_años=round(float(((hit > 0) & (hit <= 120)).mean() * 100), 1),
                prob_1M_20_años=round(float(((hit > 0) & (hit <= 240)).mean() * 100), 1),
                prob_caida_50=round(float(dd50.mean() * 100), 1))


def main():
    r24, m24, rg, mg = trade_tables()
    out = {"bandas_6_meses": {}, "resultados": {}}
    grid = [0.009, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.08]
    for f in grid:
        bnd = six_month_bands(r24, rg, f)
        out["bandas_6_meses"][f"{f * 100:.1f} %"] = {k: round(v * 100, 1) for k, v in bnd.items()}
        print("6 meses al", f, out["bandas_6_meses"][f"{f * 100:.1f} %"])
    f_cap = max(f for f in grid if out["bandas_6_meses"][f"{f * 100:.1f} %"]["p5"] >= -15)
    base = six_month_bands(r24, rg, 0.009)
    qb = six_month_bands(r24, rg, f_cap)
    band = dict(media=base["media"], sd=base["sd"], q_media=qb["media"] / 2, q_sd=qb["sd"] / np.sqrt(2))
    out["techo_de_riesgo"] = f_cap
    print("techo de riesgo (peor caso de 6 meses >= -15 %):", f_cap)
    for label, rr, gg in (("ventaja completa", r24, rg), ("ventaja a la mitad", r24 - r24.mean() / 2, rg - rg.mean() / 2)):
        for start in BALANCES:
            for plan in ("fijo", "sigma"):
                k = f"${start:,} | {'Fijo 0.9 %' if plan == 'fijo' else 'Ascenso mes 6 por σ'} | {label}"
                out["resultados"][k] = simulate(start, rr, m24, gg, mg, plan, f_cap, band)
                print(k, out["resultados"][k])
    json.dump(out, open("results/plan_saldos.json", "w"), indent=1)


if __name__ == "__main__":
    main()

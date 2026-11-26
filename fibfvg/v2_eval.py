"""Prop24 V2 (entradas 08:00-18:00 NY) contra V1 (lo que corre en la demo): para las dos carteras.

Cueto & Co. Prop (GFT Instant Premium $100K, $760, 6 % trailing, 3 % diario, 0.9 % fijo por operación):
  historia real jul 2024 - nov 2026 empezando cada mes (12 meses cada una): cobrado, quemadas, peor caída, primer pago.
  Mercados: los 3 de siempre, y la prueba de añadir oro y plata (solo si ganan en ambas mitades con V2).
Cueto & Co. Real (saldos $100, $200, $500, $1,000, con y sin aportes de $200 al mes):
  lotaje desde el saldo de cada momento en pasos de 0.01 lote (cuentas < $5K: solo BTC, S&P, Nasdaq), 5,000 caminos
  remuestreando las operaciones reales de V2 al ritmo real (operaciones por mes), 5 años.  Planes: fijo 2 %, 3 %,
  "5 % con freno" (mitad tras 2 pérdidas seguidas, 1 % si cae 20 % desde el máximo) y 10 % con freno.
  Se mide: meses medianos para $1K, $10K, $100K, $1M; probabilidad de una caída del 50 %; saldo a 5 años.
Pregunta del usuario: ¿se puede llevar $100 a $1,000,000 en 120 días?  Se calcula qué haría falta.
    python -m fibfvg.v2_eval -> results/v2_eval.json
"""
import json

import numpy as np
import pandas as pd

from . import fractal24, propsim
from .config import SYMBOLS
from .engines import net_r
from .prop24 import build
from .propsim import Account, run

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
GFT = Account("Goat Funded Trader Instant Premium", 100_000, 760, 0.03, 0.06, refundable=False, payout_days=14)
P3 = ("BTCUSD", "US500", "NAS100")


def trades(win):
    fractal24.ENTRY_HOURS_NY = win
    a, b = build()
    fractal24.ENTRY_HOURS_NY = None
    return sorted(a + b, key=lambda t: t.entry_time)


def per_market(tr):
    out = {}
    for s in SYMBOLS:
        x = [t for t in tr if t.symbol == s]
        r = np.array([net_r(t) for t in x]); m1 = [net_r(t) for t in x if t.entry_time < SPLIT]; m2 = [net_r(t) for t in x if t.entry_time >= SPLIT]
        out[s] = dict(n=len(r), R=round(float(r.mean()), 2), mitad1=round(float(np.mean(m1)), 2) if m1 else None,
                      mitad2=round(float(np.mean(m2)), 2) if m2 else None)
    return out


def gft(tr, risk=0.009):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    propsim.BUMP_MIN_LOT = False; propsim.FIXED_LOT = None; propsim.OPEN_CAP = None
    starts = pd.date_range("2024-08-01", "2025-11-01", freq="MS", tz="UTC")
    paid, burn, dd, first = [], 0, [], []
    for s0 in starts:
        o = run(tr, GFT, "X", start=s0, end=s0 + pd.Timedelta(days=365))
        paid.append(o["paid_to_trader"]); burn += bool(o["breach"]); dd.append(o["worst_dd_pct"])
        if o["payout_list"]:
            first.append((pd.Timestamp(o["payout_list"][0][0], tz="UTC") - s0).days)
    full = run(tr, GFT, "X", start=pd.Timestamp("2024-07-01", tz="UTC"))
    months = (pd.Timestamp("2026-11-23", tz="UTC") - pd.Timestamp("2024-07-01", tz="UTC")).days / 30.44
    return dict(cobrado_12m_mediana=round(float(np.median(paid))), cobrado_12m_peor=round(float(min(paid))), cobrado_12m_mejor=round(float(max(paid))),
                quemadas=f"{burn}/{len(starts)}", peor_caida=round(float(max(dd)), 2), dias_al_primer_pago_mediana=float(np.median(first)) if first else None,
                todo_el_periodo_cobrado=round(full["paid_to_trader"]), por_mes=round(full["paid_to_trader"] / months), quemada_todo=bool(full["breach"]),
                operaciones=full["trades"])


PLANS = {
    "fijo 2 %": lambda b, s: 0.02,
    "fijo 3 %": lambda b, s: 0.03,
    "5 % con freno": lambda b, s: 0.01 if b < 0.8 * s["peak"] else 0.025 if s["losses"] >= 2 else 0.05,
    "10 % con freno": lambda b, s: 0.02 if b < 0.8 * s["peak"] else 0.05 if s["losses"] >= 2 else 0.10,
}
GOALS = (1_000, 10_000, 100_000, 1_000_000)


def step(b, r, mr, f, s):
    lots = np.floor(f * b / mr) if mr > 0 else 0
    cap = max(0.03, 1.5 * f)
    risk = lots * mr if lots >= 1 else (mr if mr <= cap * b else 0.0)
    nb = b + risk * r
    if risk > 0:
        s["losses"] = s["losses"] + 1 if r < 0 else 0
    s["peak"] = max(s["peak"], nb)
    return nb


def real(tr, start, plan, add=0.0, months=60, n=5_000, seed=5):
    x = [t for t in tr if t.symbol in P3 and t.entry_time >= pd.Timestamp("2024-07-01", tz="UTC")]
    r = np.array([net_r(t) for t in x]); mr = np.array([abs(t.entry - t.stop) * SYMBOLS[t.symbol].contract * 0.01 for t in x])
    span = (x[-1].entry_time - x[0].entry_time).days / 30.44
    lam = len(x) / span
    rng = np.random.default_rng(seed)
    hit = {g: np.full(n, np.nan) for g in GOALS}; dd50 = np.zeros(n, bool); end = np.zeros(n)
    for p in range(n):
        b, s = start, dict(losses=0, peak=start)
        for m in range(months):
            b += add; s["peak"] = max(s["peak"], b)
            for _ in range(rng.poisson(lam)):
                i = rng.integers(len(r))
                b = step(b, r[i], mr[i], PLANS[plan](b, s), s)
                if b < 0.5 * s["peak"]:
                    dd50[p] = True
            for g in GOALS:
                if np.isnan(hit[g][p]) and b >= g:
                    hit[g][p] = m + 1
        end[p] = b
    med = lambda g: (round(float(np.nanmedian(hit[g])), 1) if np.mean(~np.isnan(hit[g])) >= 0.5 else None)
    return dict(operaciones_por_mes=round(lam, 2), **{f"meses_a_${g:,}": med(g) for g in GOALS},
                **{f"llega_a_${g:,}_en_5_años_pct": round(float(np.mean(~np.isnan(hit[g])) * 100)) for g in GOALS},
                caida_50_pct=round(float(dd50.mean() * 100), 1), saldo_5_años_mediana=int(np.median(end)), saldo_5_años_peor_10pct=int(np.percentile(end, 10)))


def million_in_120_days(tr):
    x = [t for t in tr if t.symbol in P3]
    r = np.array([net_r(t) for t in x])
    span = (x[-1].entry_time - x[0].entry_time).days
    n120 = len(x) / span * 120
    best = max(((f, np.mean(np.log1p(np.clip(f * r, -0.999, None)))) for f in np.linspace(0.01, 0.6, 60)), key=lambda z: z[1])
    need = np.log(10_000) / n120                       # $100 -> $1M = x10,000
    return dict(operaciones_en_120_dias=round(n120, 1), multiplicar_por=10_000, crecimiento_necesario_por_operacion_pct=round(float(np.expm1(need) * 100)),
                mejor_riesgo_kelly_pct=round(best[0] * 100), crecimiento_medio_por_operacion_a_kelly_pct=round(float(np.expm1(best[1]) * 100), 1),
                multiplo_esperado_120_dias_a_kelly=round(float(np.exp(best[1] * n120)), 2))


def main():
    v1, v2 = trades(None), trades((8, 18))
    out = dict(por_mercado_v2=per_market(v2), por_mercado_v1=per_market(v1))
    ok_extra = [s for s, v in out["por_mercado_v2"].items() if s not in P3 and v["mitad1"] and v["mitad2"] and v["mitad1"] > 0 and v["mitad2"] > 0]
    out["mercados_extra_que_pasan"] = ok_extra
    out["gft"] = {"V1 3 mercados (lo que corre)": gft([t for t in v1 if t.symbol in P3]),
                  "V2 3 mercados": gft([t for t in v2 if t.symbol in P3])}
    if ok_extra:
        out["gft"][f"V2 3 mercados + {' + '.join(ok_extra)}"] = gft([t for t in v2 if t.symbol in P3 + tuple(ok_extra)])
    for k, v in out["gft"].items():
        print("GFT", k, v)
    out["real"] = {}
    for ver, tr in (("V1", v1), ("V2", v2)):
        for start in (100, 200, 500, 1_000):
            for plan in PLANS:
                for add in (0.0, 200.0):
                    if ver == "V1" and (add or plan not in ("5 % con freno",)):
                        continue
                    key = f"{ver} | ${start} | {plan} | aporte ${add:.0f}/mes"
                    out["real"][key] = real(tr, start, plan, add)
                    print("REAL", key, out["real"][key])
    out["un_millon_en_120_dias"] = million_in_120_days(v2)
    print("120 días", out["un_millon_en_120_dias"])
    print("por mercado V2", out["por_mercado_v2"])
    json.dump(out, open("results/v2_eval.json", "w"), indent=1, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()

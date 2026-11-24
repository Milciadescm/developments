"""Tres caminos con el mismo dinero: $1,000 cada 2 meses durante 5 años ($30,000 invertidos en total).

  A. Cuentas reales separadas: cada 2 meses se abre una cuenta real nueva de $1,000; el bot la opera 24 meses y luego
     se cierra (el saldo vuelve a ti).
  B. Una sola cuenta real: los mismos $1,000 cada 2 meses se depositan en la misma cuenta (nunca se cierra).
  C. Cuentas de fondeo GFT Instant Premium $100K: con cada $1,000 se compra una cuenta (cuota supuesta $1,000; confirmar
     el precio real). Además el 50 % de cada pago compra más cuentas, hasta 50 por persona. Si una cuenta incumple, se pierde.
     Pagos cada 14 días con 5 días rentables de +0.5 %, reparto 80 %. Tope de pago: $2,000 cada 14 días, probado de dos
     formas: por cuenta, o por persona (todas las cuentas juntas).
Mercado común: todas las cuentas toman las mismas operaciones el mismo día (si el mercado va mal, va mal para todas).
Bots: 24 horas (BTC, S&P, Nasdaq; 81 operaciones reales) + Hold en oro (186 operaciones 2006-2026) en las cuentas reales
cuando el 0.01 lote de oro arriesga como máximo 3 % del saldo. En fondeo solo el bot de 24 horas (regla de 24 h), una
operación al día al 0.9 %.
Riesgo de las cuentas reales: "fijo 0.9 %" o "ascenso": 0.9 % los primeros 6 meses de cada cuenta; luego 3 % si el semestre
quedó sobre media - 1 desviación; freno a 0.9 % con caída del 20 %.
También: punto óptimo del saldo real (una cuenta sin aportes, 24 meses).
    python -m fibfvg.caminos -> results/caminos.json
"""
import json

import numpy as np
import pandas as pd

from .plan_saldos import trade_tables

MONTHS = 60
N = 1_000
FEE = 1_000.0          # cuota supuesta de una cuenta GFT de $100K (confirmar)
SIZE = 100_000.0


def market(r24, rg, n=N, months=MONTHS, seed=21, slots24=9, slotsg=5):
    rng = np.random.default_rng(seed)
    k24 = rng.poisson(2.8, (n, months)); kg = rng.poisson(0.8, (n, months))
    i24 = rng.integers(0, len(r24), (n, months, slots24)); ig = rng.integers(0, len(rg), (n, months, slotsg))
    return k24, kg, i24, ig


def run_account(start_m, cap0, mk, r24, m24, rg, mg, plan, life=None, deposit_every=None, dep=0.0):
    """saldo de una cuenta real por mes (n caminos) desde el mes start_m"""
    k24, kg, i24, ig = mk
    n, months = k24.shape
    b = np.full(n, cap0); peak = b.copy(); f = np.full(n, 0.009); b6 = b.copy(); bq = b.copy(); dd50 = np.zeros(n, bool)
    path = np.full((n, months + 1), np.nan)
    end = months if life is None else min(months, start_m + life)
    for m in range(start_m, end):
        age = m - start_m + 1
        for r, mr, k, idx in ((r24, m24, k24, i24), (rg, mg, kg, ig)):
            for j in range(idx.shape[2]):
                x = idx[:, m, j]
                want = f * b; minr = mr[x]
                risk = np.where(want >= minr, want, np.where(minr <= 0.03 * b, minr, 0.0))
                b = np.where(j < k[:, m], b + risk * r[x], b)
        b = np.maximum(b, 0)
        if deposit_every and age % deposit_every == 0 and m < months - 1:
            b = b + dep
        peak = np.maximum(peak, b); dd50 |= b < 0.5 * peak
        if plan == "ascenso":
            if age == 6:
                f = np.where((b - b6) / np.maximum(b6, 1) >= 0.069 - 0.082, 0.03, 0.009); bq = b.copy()
            elif age > 6 and age % 3 == 0:
                q = (b - bq) / np.maximum(bq, 1)
                f = np.where((q < 0.09 - 2 * 0.23) | (b < 0.8 * peak), 0.009, np.where((q >= 0.09 - 0.23) & (b >= 0.85 * peak), 0.03, f)); bq = b.copy()
            if age > 6:
                f = np.where(b < 0.8 * peak, 0.009, f)
        path[:, m + 1] = b
    return path, dd50


def camino_real_separadas(mk, tabs, plan):
    n = mk[0].shape[0]
    open_val = np.zeros((n, MONTHS + 1)); returned = np.zeros((n, MONTHS + 1)); invested = np.zeros(MONTHS + 1)
    for s in range(0, MONTHS, 2):
        path, _ = run_account(s, 1_000.0, mk, *tabs, plan, life=24)
        invested[s:] += 1_000
        end = min(MONTHS, s + 24)
        for m in range(s, end + 1):
            open_val[:, m] += np.nan_to_num(path[:, m]) if m > s else 1_000
        if s + 24 <= MONTHS:
            returned[:, s + 24:] += path[:, s + 24][:, None]
            open_val[:, s + 24] -= path[:, s + 24]
    return open_val + returned, invested


def camino_real_unica(mk, tabs, plan):
    path, dd50 = run_account(0, 1_000.0, mk, *tabs, plan, deposit_every=2, dep=1_000.0)
    path[:, 0] = 1_000
    invested = np.array([1_000 + 1_000 * (m // 2) for m in range(MONTHS + 1)], float)
    return path, invested, dd50


def camino_fondeo(r24, cap_mode, n=N, seed=21, haircut=1.0):
    """simulación diaria de cuentas GFT; 21 días de trading por mes; operación un día de cada ~7.5"""
    rng = np.random.default_rng(seed)
    r = r24 - (1 - haircut) * r24.mean()
    days = MONTHS * 21
    trade = rng.random((n, days)) < 2.8 / 21
    R = r[rng.integers(0, len(r), (n, days))]
    pnl_day = np.where(trade, np.maximum(R * 0.009, -0.03), 0.0)             # fracción del tamaño de la cuenta
    A = 50
    active = np.zeros((n, A), bool); bal = np.zeros((n, A)); peak = np.zeros((n, A)); pd_ = np.zeros((n, A)); last = np.zeros((n, A))
    cash_buy = np.zeros(n); profit = np.zeros(n); bought = np.zeros(n); lost = np.zeros(n); invested = 0.0
    out_profit = np.zeros((n, MONTHS + 1)); out_acc = np.zeros((n, MONTHS + 1)); inv = np.zeros(MONTHS + 1)

    def buy(mask):
        nonlocal active
        free = ~active
        slot = np.argmax(free, axis=1); can = mask & free.any(axis=1)
        rows = np.where(can)[0]
        active[rows, slot[rows]] = True; bal[rows, slot[rows]] = 0; peak[rows, slot[rows]] = 0; pd_[rows, slot[rows]] = 0
        last[rows, slot[rows]] = d
        return can

    for d in range(days):
        m = d // 21
        if d % 42 == 0:                                   # $1,000 de tu dinero cada 2 meses
            invested += 1_000; cash_buy += 1_000
        while True:
            can = buy(cash_buy >= FEE)
            if not can.any():
                break
            cash_buy -= np.where(can, FEE, 0); bought += can
            if not (cash_buy >= FEE).any():
                break
        p = pnl_day[:, d][:, None] * SIZE * active
        bal += p; pd_ += (p >= 0.005 * SIZE) & active; peak = np.maximum(peak, bal)
        floor = np.where(peak < 0.06 * SIZE, peak - 0.06 * SIZE, 0.0)
        br = active & (bal <= floor)
        lost += br.sum(axis=1); active &= ~br
        due = active & ((d - last) >= 10) & (pd_ >= 5) & (bal > 0)       # 14 días naturales ≈ 10 de trading
        want = np.where(due, 0.8 * bal, 0.0)
        if cap_mode == "por cuenta":
            pay = np.minimum(want, 2_000)
        else:
            if d % 10 == 0:
                person_left = np.full(n, 2_000.0)
            tot = want.sum(axis=1); scale = np.where(tot > 0, np.minimum(1, person_left / np.maximum(tot, 1e-9)), 0)
            pay = want * scale[:, None]; person_left = person_left - pay.sum(axis=1)
        bal -= pay / 0.8
        paid_any = pay > 0
        peak = np.where(paid_any, bal, peak); pd_ = np.where(paid_any, 0, pd_); last = np.where(paid_any, d, last)
        total = pay.sum(axis=1)
        cash_buy += np.where(active.sum(axis=1) < A, 0.5 * total, 0.0)
        profit += np.where(active.sum(axis=1) < A, 0.5 * total, total)
        if (d + 1) % 21 == 0:
            out_profit[:, m + 1] = profit + cash_buy; out_acc[:, m + 1] = active.sum(axis=1); inv[m + 1] = invested
    return out_profit, out_acc, inv, lost


def pct(a, q):
    return int(np.percentile(a, q))


def main():
    r24, m24, rg, mg = trade_tables()
    out = {}
    for label, hc in (("ventaja completa", 1.0), ("ventaja a la mitad", 0.5)):
        rr = r24 - (1 - hc) * r24.mean(); gg = rg - (1 - hc) * rg.mean()
        tabs = (rr, m24, gg, mg)
        mk = market(rr, gg)
        res = {}
        for plan in ("fijo", "ascenso"):
            val, inv = camino_real_separadas(mk, tabs, plan)
            res[f"A. Cuentas reales separadas de $1,000 | {plan}"] = {f"año {y}": dict(invertido=int(inv[12 * y]), valor_mediana=pct(val[:, 12 * y], 50),
                                                                                    p10=pct(val[:, 12 * y], 10), p90=pct(val[:, 12 * y], 90),
                                                                                    ganancia_mediana=pct(val[:, 12 * y] - inv[12 * y], 50)) for y in (1, 2, 3, 5)}
            path, inv, dd = camino_real_unica(mk, tabs, plan)
            res[f"B. Una sola cuenta real | {plan}"] = {f"año {y}": dict(invertido=int(inv[12 * y]), valor_mediana=pct(path[:, 12 * y], 50),
                                                                        p10=pct(path[:, 12 * y], 10), p90=pct(path[:, 12 * y], 90),
                                                                        ganancia_mediana=pct(path[:, 12 * y] - inv[12 * y], 50)) for y in (1, 2, 3, 5)}
        for cap in ("por cuenta", "por persona"):
            prof, acc, inv, lost = camino_fondeo(r24, cap, haircut=hc)
            res[f"C. Fondeo GFT $100K, tope $2K/14 días {cap}"] = {f"año {y}": dict(invertido=int(inv[12 * y]), cobrado_mediana=pct(prof[:, 12 * y], 50),
                                                                                   p10=pct(prof[:, 12 * y], 10), p90=pct(prof[:, 12 * y], 90),
                                                                                   ganancia_mediana=pct(prof[:, 12 * y] - inv[12 * y], 50),
                                                                                   cuentas_mediana=pct(acc[:, 12 * y], 50)) for y in (1, 2, 3, 5)}
            res[f"C. Fondeo GFT $100K, tope $2K/14 días {cap}"]["cuentas_perdidas_mediana"] = pct(lost, 50)
        out[label] = res
        for k, v in res.items():
            print(label, "|", k, json.dumps(v.get("año 5")), json.dumps(v.get("año 2")))
    # punto óptimo del saldo real: una cuenta, sin aportes, 24 meses
    rr, gg = r24, rg
    mk = market(rr, gg, months=24)
    sweet = {}
    for cap0 in (100, 500, 1_000, 2_000, 3_500, 5_000, 10_000, 25_000, 50_000, 100_000):
        for plan in ("fijo", "ascenso"):
            path, dd = run_account(0, float(cap0), mk, rr, m24, gg, mg, plan)
            ret = path[:, 24] / cap0 - 1
            sweet[f"${cap0:,} | {plan}"] = dict(rend_2_años_mediana=round(float(np.median(ret)) * 100, 1),
                                                peor_10pct=round(float(np.percentile(ret, 10)) * 100, 1), caida50=round(float(dd.mean()) * 100, 1))
            print("óptimo", cap0, plan, sweet[f"${cap0:,} | {plan}"])
    out["punto_optimo_24m"] = sweet
    json.dump(out, open("results/caminos.json", "w"), indent=1)


if __name__ == "__main__":
    main()

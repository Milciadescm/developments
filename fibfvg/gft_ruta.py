"""Ruta GFT: una cuenta Instant Premium de $100K cada 2 meses a $760, bot de 24 horas con riesgo fijo 0.9 %.

Escenarios de financiamiento de la cuenta nueva (cada 2 meses):
  1. "Fondos propios": siempre pagas tú los $760; todo lo cobrado queda como ganancia.
  2. "Capital generado": la cuenta nueva se paga con lo cobrado; si todavía no alcanza, ese mes no se compra
     (la primera cuenta la pagas tú).
  3. "Mixto": se paga con lo cobrado si alcanza; si no, con fondos propios (nunca se salta una compra).
Máximo 50 cuentas activas (regla de GFT por persona). Una cuenta que toca la línea del 6 % se pierde y no se repone
fuera del calendario. Tope de pago $2,000 cada 14 días, probado por cuenta y por persona.
Simulación diaria (21 días de trading al mes), operaciones remuestreadas de las 81 reales del bot de 24 horas, un día con
operación de cada ~7.5, mismo mercado para todas las cuentas. Horizontes: 5 años y 100 meses (hasta 50 cuentas).
    python -m fibfvg.gft_ruta -> results/gft_ruta.json
"""
import json

import numpy as np

from .plan_saldos import trade_tables

FEE = 760.0
SIZE = 100_000.0
N = 2_000


def simulate(r24, funding, cap_mode, months, haircut=1.0, seed=31, n=N):
    rng = np.random.default_rng(seed)
    r = r24 - (1 - haircut) * r24.mean()
    days = months * 21
    trade = rng.random((n, days)) < 2.8 / 21
    R = r[rng.integers(0, len(r), (n, days))]
    pnl = np.where(trade, np.maximum(R * 0.009, -0.03), 0.0) * SIZE
    A = 50
    active = np.zeros((n, A), bool); bal = np.zeros((n, A)); peak = np.zeros((n, A)); pdays = np.zeros((n, A)); last = np.zeros((n, A))
    own = np.zeros(n); collected = np.zeros(n); cash = np.zeros(n); lost = np.zeros(n); bought = np.zeros(n)
    monthly = dict(own=np.zeros((n, months + 1)), collected=np.zeros((n, months + 1)), cash=np.zeros((n, months + 1)),
                   accounts=np.zeros((n, months + 1)))
    person_left = np.full(n, 2_000.0)
    for d in range(days):
        if d % 42 == 0:                                       # día de compra (cada 2 meses)
            room = active.sum(axis=1) < A
            if funding == "Fondos propios" or d == 0:
                pay_own = room; pay_cash = np.zeros(n, bool)
            elif funding == "Capital generado":
                pay_cash = room & (cash >= FEE); pay_own = np.zeros(n, bool)
            else:
                pay_cash = room & (cash >= FEE); pay_own = room & ~pay_cash
            buy = pay_own | pay_cash
            own += np.where(pay_own, FEE, 0); cash -= np.where(pay_cash, FEE, 0); bought += buy
            slot = np.argmax(~active, axis=1); rows = np.where(buy)[0]
            active[rows, slot[rows]] = True; bal[rows, slot[rows]] = 0; peak[rows, slot[rows]] = 0
            pdays[rows, slot[rows]] = 0; last[rows, slot[rows]] = d
        p = pnl[:, d][:, None] * active
        bal += p; pdays += (p >= 0.005 * SIZE) & active; peak = np.maximum(peak, bal)
        floor = np.where(peak < 0.06 * SIZE, peak - 0.06 * SIZE, 0.0)
        br = active & (bal <= floor)
        lost += br.sum(axis=1); active &= ~br
        due = active & ((d - last) >= 10) & (pdays >= 5) & (bal > 0)
        want = np.where(due, 0.8 * bal, 0.0)
        if cap_mode == "por cuenta":
            pay = np.minimum(want, 2_000.0)
        else:
            if d % 10 == 0:
                person_left = np.full(n, 2_000.0)
            tot = want.sum(axis=1)
            scale = np.where(tot > 0, np.minimum(1.0, person_left / np.maximum(tot, 1e-9)), 0.0)
            pay = want * scale[:, None]; person_left = person_left - pay.sum(axis=1)
        bal -= pay / 0.8
        got = pay > 0
        peak = np.where(got, bal, peak); pdays = np.where(got, 0, pdays); last = np.where(got, d, last)
        t = pay.sum(axis=1); collected += t; cash += t
        if (d + 1) % 21 == 0:
            m = (d + 1) // 21
            monthly["own"][:, m] = own; monthly["collected"][:, m] = collected; monthly["cash"][:, m] = cash
            monthly["accounts"][:, m] = active.sum(axis=1)
    return monthly, lost, bought


def table(monthly, lost, bought, months):
    q = lambda a, p: int(np.percentile(a, p))
    rows = {}
    for y in [1, 2, 3, 4, 5] + ([8] if months >= 96 else []):
        m = 12 * y
        if m > months:
            continue
        own = monthly["own"][:, m]; col = monthly["collected"][:, m]; net = col - own
        mon = (monthly["collected"][:, m] - monthly["collected"][:, m - 12]) / 12
        rows[f"año {y}"] = dict(fondos_propios=q(own, 50), cobrado_mediana=q(col, 50), cobrado_p10=q(col, 10), cobrado_p90=q(col, 90),
                                ganancia_neta_mediana=q(net, 50), ganancia_neta_p10=q(net, 10), cuentas_activas=q(monthly["accounts"][:, m], 50),
                                cobro_mensual_promedio_ese_año=q(mon, 50))
    first_payback = np.argmax(monthly["collected"] - monthly["own"] > 0, axis=1)
    ok = (monthly["collected"] - monthly["own"] > 0).any(axis=1)
    rows["mes_en_que_lo_cobrado_supera_lo_invertido_mediana"] = int(np.median(first_payback[ok])) if ok.mean() > 0.5 else None
    rows["prob_recuperar_inversion"] = round(float(ok.mean() * 100), 1)
    rows["cuentas_perdidas_mediana"] = q(lost, 50); rows["cuentas_compradas_mediana"] = q(bought, 50)
    return rows


def main():
    r24, _, _, _ = trade_tables()
    out = {}
    for months in (60, 100):
        for label, hc in (("ventaja completa", 1.0), ("ventaja a la mitad", 0.5)):
            for cap in ("por cuenta", "por persona"):
                for funding in ("Fondos propios", "Capital generado", "Mixto"):
                    k = f"{months} meses | {label} | tope {cap} | {funding}"
                    out[k] = table(*simulate(r24, funding, cap, months, haircut=hc), months)
                    y = out[k].get("año 5"); y8 = out[k].get("año 8")
                    print(k, "| a5", y, "| a8", y8, "| recupera mes", out[k]["mes_en_que_lo_cobrado_supera_lo_invertido_mediana"],
                          out[k]["prob_recuperar_inversion"], "| perdidas", out[k]["cuentas_perdidas_mediana"])
    json.dump(out, open("results/gft_ruta.json", "w"), indent=1)


if __name__ == "__main__":
    main()

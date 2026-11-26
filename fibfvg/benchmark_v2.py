"""V1 contra V2 mes a mes (jul 2024 - nov 2026), con la regla de retiro del usuario (26 nov 2026) para GFT.

GFT Instant Premium $100K, 0.9 % fijo, una operación abierta a la vez (1 % flotante), 6 % trailing que se fija en el saldo
inicial, 80 % para el trader.  Regla de retiro:
  - solo cada 14 días o más desde el último retiro, con 5 días rentables (>= +0.5 %) desde el último (regla GFT);
  - solo si la ganancia acumulada en la cuenta es >= $3,000;
  - se retira siempre lo máximo: $2,000 para el trader = $2,500 que salen de la cuenta, y quedan >= $500 de colchón.
Real $100K: V1 y V2 al 10 % y al 5 % del saldo actual con freno (mitad tras 2 pérdidas, 2 %/1 % si cae 20 %).
Además: 2,000 simulaciones por versión con la misma regla (12 y 24 meses) para comparar V1 y V2 con la misma vara.
    python -m fibfvg.benchmark_v2 -> results/benchmark_v2.json y results/benchmark_v2_mes_a_mes.md
"""
import json

import numpy as np
import pandas as pd

from . import fractal24, gft
from .engines import net_r
from .prop24 import build

SIZE = 100_000.0
START = pd.Timestamp("2024-07-01", tz="UTC")


def trades(win):
    fractal24.ENTRY_HOURS_NY = win
    a, b = build()
    fractal24.ENTRY_HOURS_NY = None
    return sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)


def gft_days(tr):
    days, skipped, taken = gft.daily_pnl(tr, 0.009, 0.01)
    return days[days.index >= START]


def payout_rule(days_iter, need=5, every=14, threshold=3_000.0, take=2_500.0, split=0.8):
    """days_iter: iterable de (día, pnl$).  Devuelve lista de eventos por día."""
    bal, peak, pdays, last, ev = 0.0, 0.0, 0, None, []
    burned = False
    for d, p in days_iter:
        bal += p
        if p >= 0.005 * SIZE:
            pdays += 1
        peak = max(peak, bal)
        floor = min(peak - 0.06 * SIZE, 0.0)
        paid = 0.0
        if bal <= floor:
            burned = True; ev.append((d, p, bal, 0.0, True)); break
        if last is None:
            last = d
        gap = (d - last).days if hasattr(d - last, 'days') else (d - last)
        if gap >= every and pdays >= need and bal >= threshold:
            paid = take * split; bal -= take; peak = bal; pdays = 0; last = d
        ev.append((d, p, bal, paid, False))
    return ev, burned


def real_monthly(tr, risk, low):
    b, peak, losses, rows = SIZE, SIZE, 0, []
    for t in sorted(tr, key=lambda t: t.exit_time):
        x = net_r(t)
        f = low if b < 0.8 * peak else (risk / 2 if losses >= 2 else risk)
        b += f * b * x
        losses = losses + 1 if x < 0 else 0
        peak = max(peak, b)
        rows.append((t.exit_time, b, 1 - b / peak))
    s = pd.DataFrame(rows, columns=["t", "b", "dd"]).set_index("t")
    return s.b.resample("ME").last().ffill(), s.dd.resample("ME").max().fillna(0)


def simulate(tr, months, n=2_000, seed=3):
    r = np.array([net_r(t) for t in tr]); lam = len(r) / ((tr[-1].entry_time - tr[0].entry_time).days / 30.44)
    rng = np.random.default_rng(seed)
    days = int(months * 30.44)
    paid, burned, npay, first = [], 0, [], []
    for _ in range(n):
        k = rng.poisson(lam * months)
        dd = np.sort(rng.integers(0, days, k)); R = r[rng.integers(0, len(r), k)]
        pnl = {}
        for d_, x in zip(dd, R):
            pnl[d_] = pnl.get(d_, 0.0) + x * 0.009 * SIZE
        ev, b = payout_rule(sorted(pnl.items()))
        p = [e for e in ev if e[3] > 0]
        paid.append(sum(e[3] for e in p)); burned += b; npay.append(len(p))
        if p:
            first.append(p[0][0])
    paid = np.array(paid)
    return dict(cobrado_mediana=int(np.median(paid)), cobrado_p10=int(np.percentile(paid, 10)), cobrado_p90=int(np.percentile(paid, 90)),
                retiros_mediana=float(np.median(npay)), quema_pct=round(burned / n * 100, 1), recupera_760_pct=round(float((paid >= 760).mean() * 100), 1),
                dias_al_primer_retiro_mediana=float(np.median(first)) if first else None)


def main():
    out = {"meses": {}, "simulacion": {}}
    versions = {"V1": trades(None), "V2": trades((8, 18))}
    monthly = {}
    for v, tr in versions.items():
        days = gft_days(tr)
        ev, burned = payout_rule([(d, p) for d, p in days.items()])
        e = pd.DataFrame(ev, columns=["d", "pnl", "bal", "paid", "burn"]).set_index("d")
        g = pd.DataFrame(dict(pnl=e.pnl.resample("ME").sum(), cuenta=e.bal.resample("ME").last(), retiro=e.paid.resample("ME").sum()))
        g["cuenta"] = g.cuenta.ffill().fillna(0)
        ops = pd.Series(1, index=pd.DatetimeIndex([t.entry_time for t in tr])).resample("ME").sum()
        R = pd.Series([net_r(t) for t in tr], index=pd.DatetimeIndex([t.exit_time for t in tr])).resample("ME").sum()
        b10, dd10 = real_monthly(tr, 0.10, 0.02)
        b5, dd5 = real_monthly(tr, 0.05, 0.01)
        monthly[v] = dict(ops=ops, R=R, g=g, b10=b10, b5=b5, dd10=dd10)
        out["simulacion"][v] = {f"{m} meses": simulate(tr, m) for m in (12, 24)}
        out[v] = dict(quemada=burned, retiros=int((e.paid > 0).sum()), cobrado=float(e.paid.sum()), real10_final=float(b10.iloc[-1]), real5_final=float(b5.iloc[-1]),
                      real10_peor_caida=float(dd10.max() * 100))
        print(v, out[v], out["simulacion"][v])
    idx = pd.date_range("2024-07-31", "2026-11-30", freq="ME", tz="UTC")
    lines = ["| Mes | Ops V1 | Ops V2 | R V1 | R V2 | GFT P&L V1 | GFT P&L V2 | Retiro V1 | Retiro V2 | Cobrado acum. V1 | Cobrado acum. V2 | Real 10 % V1 | Real 10 % V2 | Real 5 % V2 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    acc = {"V1": 0.0, "V2": 0.0}
    for m in idx:
        row, vals = [m.strftime("%Y-%m")], {}
        for v in ("V1", "V2"):
            M = monthly[v]
            vals[v] = dict(ops=int(M["ops"].get(m, 0)), R=float(M["R"].get(m, 0.0)), pnl=float(M["g"].pnl.get(m, 0.0)), ret=float(M["g"].retiro.get(m, 0.0)),
                           b10=float(M["b10"].reindex(idx).ffill().fillna(SIZE).get(m)), b5=float(M["b5"].reindex(idx).ffill().fillna(SIZE).get(m)))
            acc[v] += vals[v]["ret"]; vals[v]["acc"] = acc[v]
        a, b = vals["V1"], vals["V2"]
        lines.append(f"| {row[0]} | {a['ops']} | {b['ops']} | {a['R']:+.1f} | {b['R']:+.1f} | {a['pnl']:+,.0f} | {b['pnl']:+,.0f} | {a['ret']:,.0f} | {b['ret']:,.0f} | "
                     f"{a['acc']:,.0f} | {b['acc']:,.0f} | {a['b10']:,.0f} | {b['b10']:,.0f} | {b['b5']:,.0f} |")
        out["meses"][row[0]] = vals
    md = "# V1 contra V2 mes a mes (backtest jul 2024 - nov 2026)\n\nGFT $100K al 0.9 %; retiro de $2,000 (sale $2,500 de la cuenta) solo con >= $3,000 de ganancia, 14 días y 5 días rentables.\nReal $100K con freno, saldo al cierre de cada mes.\n\n" + "\n".join(lines) + "\n"
    open("results/benchmark_v2_mes_a_mes.md", "w").write(md)
    print(md)
    json.dump(out, open("results/benchmark_v2.json", "w"), indent=1, default=str, ensure_ascii=False)


if __name__ == "__main__":
    main()

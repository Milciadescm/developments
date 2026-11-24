"""Plan de $1,000 reales + aportes de $100 o $200 al mes, 5 años (dic 2026 -> nov 2031), sin retiros.

Configuración según el capital (lo que dicen las pruebas del 23-24 nov):
  Fase 1, saldo < $5,000: bot de 24 horas en BTC, S&P 500 y Nasdaq, 0.9 % por operación (0.01 lote mínimo).
  Fase 2, saldo >= $5,000: lo mismo + bot Hold solo en oro (añade a ganadoras, chandelier, breakeven 2R), 1 % por unidad.
  Protección: si el saldo cae 12 % desde su máximo, los bots se pausan un mes y vuelven a la mitad del riesgo.
Rendimientos mensuales (%) sacados de los backtests y remuestreados en bloques de 3 meses (5,000 trayectorias):
  Escenario "como 2024-26": oro con su subida reciente.  Escenario "20 años": oro 2006-2026 (mucho más débil).
  Escenario "ventaja a la mitad": los dos bots ganan la mitad de lo que ganaron.
    python -m fibfvg.plan1k -> results/plan1k.json
"""
import json

import numpy as np
import pandas as pd

from . import propsim, scoreboard  # noqa: F401
from .engines import load
from .plans import position_engine
from .prop24 import build as prop_build
from .propsim import Account, run
from .swaps import with_swaps
from .longhold import load_long

TARGETS = [10_000, 20_000, 50_000, 100_000, 200_000, 500_000, 1_000_000, 5_000_000, 10_000_000]
START = pd.Timestamp("2026-12-01")
MONTHS = 60


def month_returns(tr, cap, risk, start, bump=True):
    propsim.BUMP_MIN_LOT = bump; propsim.FIXED_LOT = None
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    o = run(tr, Account("Real", cap, 0.0, None, None, real=True, payout_days=None), "X", start=start, guard=False)
    s = pd.Series([b for _, b in o["curve"]], index=pd.to_datetime([a for a, _ in o["curve"]], unit="s", utc=True))
    s = pd.concat([pd.Series([cap], index=[start]), s]).groupby(level=0).last()
    m = s.resample("ME").last().ffill()
    r = m.pct_change().fillna(m.iloc[0] / cap - 1)
    return r, o


def hold_gold(d, start):
    tr = with_swaps(position_engine("XAUUSD", d, "BE2", start=start))
    for t in tr:
        t.plan = "Plan 1"
    return tr


def simulate(r1, r2, dep, n=5_000, seed=11, block=3, scale=1.0):
    rng = np.random.default_rng(seed)
    r1, r2 = np.asarray(r1) * scale, np.asarray(r2) * scale
    bal = np.zeros((n, MONTHS + 1)); bal[:, 0] = 1_000
    for p in range(n):
        b, peak, pause, half = 1_000.0, 1_000.0, 0, False
        i1 = rng.integers(0, len(r1) - block); i2 = rng.integers(0, len(r2) - block)
        for m in range(MONTHS):
            if m % block == 0:
                i1 = rng.integers(0, len(r1) - block); i2 = rng.integers(0, len(r2) - block)
            k = m % block
            ret = 0.0
            if pause:
                pause -= 1
            else:
                ret = r1[i1 + k] + (r2[i2 + k] if b >= 5_000 else 0.0)
                if half:
                    ret *= 0.5
            b = b * (1 + ret) + dep
            peak = max(peak, b)
            if b < peak * 0.88 and not pause:
                pause, half, peak = 1, True, b
            elif half and b >= peak:
                half = False
            bal[p, m + 1] = b
    return bal


def summary(bal, dep):
    q = lambda a, x: float(np.percentile(a, x))
    years = {f"año {y}": dict(p10=round(q(bal[:, 12 * y], 10)), mediana=round(q(bal[:, 12 * y], 50)), p90=round(q(bal[:, 12 * y], 90)),
                              aportado=1_000 + dep * 12 * y) for y in range(1, 6)}
    months = [dict(mes=str((START + pd.DateOffset(months=m)).date())[:7], mediana=round(q(bal[:, m + 1], 50)),
                   p10=round(q(bal[:, m + 1], 10)), p90=round(q(bal[:, m + 1], 90))) for m in range(MONTHS)]
    tg = {}
    for t in TARGETS:
        hit = np.argmax(bal >= t, axis=1); ok = (bal >= t).any(axis=1)
        tg[f"${t:,}"] = dict(prob_5_años=round(float(ok.mean() * 100), 1),
                            fecha_mediana=str((START + pd.DateOffset(months=int(np.median(hit[ok])) - 1)).date())[:7] if ok.mean() >= 0.5 else None,
                            fecha_10pct_mas_rapido=str((START + pd.DateOffset(months=int(np.percentile(hit[ok], 10)) - 1)).date())[:7] if ok.any() else None)
    return dict(por_año=years, por_mes=months, metas=tg)


def main():
    a, b = prop_build()
    p24 = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    H0 = pd.Timestamp("2024-07-01", tz="UTC")
    r1, o1 = month_returns(p24, 1_000, 0.009, H0)
    d = load("data/XAUUSD_D1.csv")
    r2_recent, _ = month_returns(hold_gold(d[d.index >= pd.Timestamp("2024-01-01", tz="UTC")], "2024-01-01"), 10_000, 0.01, H0)
    r2_long, _ = month_returns(hold_gold(load_long("XAUUSD"), "2006-01-01"), 10_000, 0.01, pd.Timestamp("2006-01-01", tz="UTC"))
    out = {"backtest_1000": {}}
    # backtest real mes a mes con $1,000 (sin aportes y con $200/mes), bot de 24 horas
    rr = r1[r1.index >= H0]
    for dep in (0, 200):
        b, rows = 1_000.0, []
        for ts, x in rr.items():
            gain = b * x; b = b + gain + dep
            rows.append(dict(mes=str(ts.date())[:7], ganancia=round(gain), saldo=round(b)))
        out["backtest_1000"][f"aporte {dep}"] = rows
    yearly = {}
    for r in out["backtest_1000"]["aporte 0"]:
        yearly.setdefault(r["mes"][:4], 0); yearly[r["mes"][:4]] += r["ganancia"]
    out["backtest_1000"]["por_año_sin_aportes"] = yearly
    out["mensual_promedio"] = dict(bot24=round(float(r1.mean() * 100), 2), hold_oro_2024_26=round(float(r2_recent.mean() * 100), 2),
                                   hold_oro_20_años=round(float(r2_long.mean() * 100), 2))
    print("promedio mensual %", out["mensual_promedio"])
    scen = {"como 2024-26": (r1, r2_recent, 1.0), "20 años": (r1, r2_long, 1.0), "ventaja a la mitad": (r1, r2_long, 0.5)}
    out["escenarios"] = {}
    for dep in (100, 200):
        for name, (x1, x2, sc) in scen.items():
            bal = simulate(x1.values, x2.values, dep, scale=sc)
            s = summary(bal, dep)
            out["escenarios"][f"{name} | ${dep}/mes"] = s
            print(name, dep, json.dumps(s["por_año"]), json.dumps({k: v for k, v in s["metas"].items()}))
    json.dump(out, open("results/plan1k.json", "w"), indent=1)


if __name__ == "__main__":
    main()

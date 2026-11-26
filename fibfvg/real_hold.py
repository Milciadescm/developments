"""Cartera Cueto & Co. Real (live funds): estrategias de holding para cuentas de $100, $200, $500 y $1,000, con más riesgo.

Bot de posiciones (dirección mensual + semanal, ruptura de 20 días con fair value gap, entrada en 0.705, añade hasta 3
unidades a favor). Salidas probadas:
  "run20"      trailing del mínimo/máximo de 20 días, breakeven en +1R
  "chandelier" trailing de 3 rangos diarios, breakeven en +1R, corta en 10 días si no llegó a +0.5R
  "BE2"        igual que chandelier pero breakeven en +2R
  "mensual"    toma media posición en +1R y el resto sigue el mínimo/máximo de 55 días (cierres de semanas a meses)
  "anual"      trailing del mínimo/máximo de 120 días, breakeven en +1R (posiciones de meses a un año)
Riesgo por unidad: 2 %, 5 % y 10 % del saldo ACTUAL (interés compuesto). Lote mínimo 0.01: si el % no alcanza, abre 0.01
solo si arriesga como máximo max(3 %, 1.5 x riesgo); si no, salta. Swaps y spreads incluidos.
Periodos: 2006-2026 (velas diarias largas, mitades antes/después de 2016) y 2024-2026 (reciente).
    python -m fibfvg.real_hold -> results/real_hold.json
"""
import itertools
import json

import numpy as np
import pandas as pd

from . import plans, propsim, scoreboard  # noqa: F401
from .config import SYMBOLS
from .engines import load, net_r
from .plans import position_engine
from .propsim import Account, run
from .swaps import with_swaps
from .longhold import load_long

MODES = {"run20": "P1 run20", "chandelier": "P2 chandelier", "BE2": "BE2", "mensual": "P3 monthly", "anual": "Y1 year"}
SETS = {"S&P": ["US500"], "Nasdaq": ["NAS100"], "BTC": ["BTCUSD"], "Oro": ["XAUUSD"], "Plata": ["XAGUSD"],
        "S&P + Nasdaq": ["US500", "NAS100"], "S&P + Nasdaq + BTC": ["US500", "NAS100", "BTCUSD"],
        "Oro + Plata": ["XAUUSD", "XAGUSD"], "Los 5": list(SYMBOLS)}
SIZES = [100, 200, 500, 1_000]
RISKS = [0.02, 0.05, 0.10]
L0, LS = pd.Timestamp("2006-01-01", tz="UTC"), pd.Timestamp("2016-01-01", tz="UTC")
R0, RS = pd.Timestamp("2024-07-01", tz="UTC"), pd.Timestamp("2025-08-19", tz="UTC")


def trades_for(sym, mode, long):
    d = load_long(sym) if long else load(f"data/{sym}_D1.csv")
    if not long:
        d = d[d.index >= pd.Timestamp("2024-01-01", tz="UTC")]
    tr = with_swaps(position_engine(sym, d, MODES[mode], start="2006-01-01" if long else "2024-01-01"))
    for t in tr:
        t.plan = "Plan 1"
    return tr


def account(tr, cap, risk, start, end=None):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    propsim.BUMP_MIN_LOT = True; propsim.BUMP_CAP = max(0.03, 1.5 * risk); propsim.FIXED_LOT = None
    o = run(tr, Account("Real", cap, 0.0, None, None, real=True, payout_days=None), "X", start=start, end=end, guard=False)
    bal = [cap] + [b for _, b in o["curve"]]
    peak, dd = cap, 0.0
    for b in bal:
        peak = max(peak, b); dd = max(dd, 1 - b / peak if peak > 0 else 1)
    span = ((end or pd.Timestamp("2026-11-23", tz="UTC")) - start).days / 365.25
    endb = o["end_balance"]
    return dict(final=round(endb), multiplo=round(endb / cap, 2), anual=round(((max(endb, 1) / cap) ** (1 / span) - 1) * 100, 1),
                peor_caida=round(dd * 100, 1), operaciones=o["trades"], saltadas=o["skipped_min_lot"], quemada=bool(min(bal) < 0.1 * cap))


def main():
    cache = {}
    out = []
    for (sname, syms), mode in itertools.product(SETS.items(), MODES):
        for long in (True, False):
            key = (tuple(syms), mode, long)
            if key not in cache:
                cache[key] = sorted([t for s in syms for t in trades_for(s, mode, long)], key=lambda t: t.entry_time)
        tl, tr = cache[(tuple(syms), mode, True)], cache[(tuple(syms), mode, False)]
        rl = np.array([net_r(t) for t in tl]); rr = np.array([net_r(t) for t in tr if t.entry_time >= R0])
        h1 = np.array([net_r(t) for t in tl if t.entry_time < LS]); h2 = np.array([net_r(t) for t in tl if t.entry_time >= LS])
        stats = dict(R_20_años=round(float(rl.mean()), 2), t_20_años=round(float(rl.mean() / (rl.std(ddof=1) / np.sqrt(len(rl)))), 1),
                     mitades=[round(float(h1.mean()), 2), round(float(h2.mean()), 2)], R_2024_26=round(float(rr.mean()), 2) if len(rr) else None,
                     aciertos=round(float((rl > 0).mean() * 100)), operaciones_20_años=len(rl))
        for cap, risk in itertools.product(SIZES, RISKS):
            row = dict(mercados=sname, salida=mode, saldo=cap, riesgo=risk, **stats,
                       largo=account(tl, cap, risk, L0), reciente=account(tr, cap, risk, R0))
            out.append(row)
        print(sname, mode, stats)
    json.dump(out, open("results/real_hold.json", "w"), indent=1, default=str)
    # resumen: por saldo, las mejores combinaciones que ganan en ambas mitades, sin quemarse, con caída <= 50 %
    print()
    for cap in SIZES:
        ok = [r for r in out if r["saldo"] == cap and min(r["mitades"]) > 0 and not r["largo"]["quemada"] and not r["reciente"]["quemada"]
              and r["largo"]["peor_caida"] <= 50 and r["reciente"]["operaciones"] > 0]
        ok.sort(key=lambda r: -r["largo"]["anual"])
        print(f"== ${cap}: {len(ok)} combinaciones válidas")
        for r in ok[:6]:
            print(f"   {r['mercados']:20s} {r['salida']:10s} riesgo {r['riesgo']*100:.0f} % | R {r['R_20_años']} t {r['t_20_años']} mitades {r['mitades']} | "
                  f"2006-26: x{r['largo']['multiplo']} ({r['largo']['anual']} %/año, caída {r['largo']['peor_caida']} %, saltadas {r['largo']['saltadas']}) | "
                  f"2024-26: x{r['reciente']['multiplo']} (caída {r['reciente']['peor_caida']} %)")


if __name__ == "__main__" and "tope" not in __import__("sys").argv:
    main()


def capped():
    """las estrategias de mayor R con tope de riesgo abierto total (6 %, 10 %, 15 % del saldo)"""
    pick = [("Los 5", "anual"), ("Los 5", "mensual"), ("S&P + Nasdaq + BTC", "anual"), ("Oro + Plata", "anual"),
            ("BTC", "anual"), ("S&P", "BE2"), ("S&P + Nasdaq", "anual")]
    out = []
    for sname, mode in pick:
        syms = SETS[sname]
        tl = sorted([t for s in syms for t in trades_for(s, mode, True)], key=lambda t: t.entry_time)
        tr = sorted([t for s in syms for t in trades_for(s, mode, False)], key=lambda t: t.entry_time)
        for cap, risk, oc in itertools.product((100, 500, 1_000), (0.01, 0.02, 0.03, 0.05), (0.06, 0.10, 0.15)):
            if oc < risk * 2:
                continue
            propsim.OPEN_CAP = oc
            a = account(tl, cap, risk, L0, LS); b = account(tl, cap, risk, LS); f = account(tl, cap, risk, L0); r = account(tr, cap, risk, R0)
            propsim.OPEN_CAP = None
            out.append(dict(mercados=sname, salida=mode, saldo=cap, riesgo=risk, tope_abierto=oc, mitad1=a, mitad2=b, largo=f, reciente=r))
    json.dump(out, open("results/real_hold_tope.json", "w"), indent=1, default=str)
    for cap in (100, 500, 1_000):
        ok = [x for x in out if x["saldo"] == cap and x["mitad1"]["multiplo"] > 1 and x["mitad2"]["multiplo"] > 1
              and x["largo"]["peor_caida"] <= 40 and not x["largo"]["quemada"]]
        ok.sort(key=lambda x: -x["largo"]["anual"])
        print(f"== ${cap}: {len(ok)} combinaciones con ambas mitades positivas y caída <= 40 %")
        for x in ok[:6]:
            L, R = x["largo"], x["reciente"]
            print(f"   {x['mercados']:20s} {x['salida']:8s} riesgo {x['riesgo']*100:.0f} % tope {x['tope_abierto']*100:.0f} % | "
                  f"2006-26: x{L['multiplo']} ({L['anual']} %/año, caída {L['peor_caida']} %) mitades x{x['mitad1']['multiplo']} / x{x['mitad2']['multiplo']} | "
                  f"2024-26: x{R['multiplo']} (caída {R['peor_caida']} %)")


if __name__ == "__main__" and "tope" in __import__("sys").argv:
    capped()

"""Recolector de centavos con MÁS datos: oro (PAXG, token 1:1 de oro físico) y BTC, velas de 5 minutos, ene 2024 - nov 2026,
con flujo de órdenes REAL (volumen comprado a mercado menos vendido a mercado, de Binance).

Mismas reglas que fibfvg/penny.py. Se prueban las dos direcciones: "sigue" (con el primer impulso de la kill zone) e
"invertido" (contra el impulso: el barrido). Mitades: antes y después del 19 ago 2025 (regla del proyecto).
Oro: solo lunes-viernes (el oro de MT5 no abre el fin de semana); costo $0.45 por onza por entrada.
BTC: 24/7; costo $45 por BTC por entrada (spread típico de CFD).
Cuentas:
  $100,000: oro 0.13 lote por entrada (objetivos $300-700, tope $900 = 1 % flotante GFT, o $2,000);
            BTC 0.25 lote por entrada (mismo riesgo en dólares aprox.).
  $100: 0.01 lote por entrada, hasta 5 entradas (0.05 lote total); objetivos y topes pequeños; se mide si la cuenta se quema.
    python -m fibfvg.penny_long -> results/penny_long.json
"""
import itertools
import json
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

from . import penny
from .penny import run

SPLIT = pd.Timestamp("2025-08-19", tz="America/New_York")


def load_flow(path, weekdays_only):
    d = pd.read_csv(path, parse_dates=["t"]).set_index("t")
    d.index = d.index.tz_convert("America/New_York")
    d = d.astype(float)
    if weekdays_only:
        wd = d.index.dayofweek; h = d.index.hour
        d = d[~((wd == 5) | ((wd == 6) & (h < 18)) | ((wd == 4) & (h >= 17)))]
    return d


_D = None
WORKERS = 2


def _one(args):
    g, flip = args
    a = run(_D, g["target"], g["maxloss"], g["step"], g["maxn"], g["mode"], g["flown"], 1.0, g["zones"], end=SPLIT, flip=flip)
    b = run(_D, g["target"], g["maxloss"], g["step"], g["maxn"], g["mode"], g["flown"], 1.0, g["zones"], start=SPLIT, flip=flip)
    return (g, flip, a, b)


def _pmap(tasks):
    with Pool(WORKERS) as p:
        return p.map(_one, tasks, chunksize=4)


def evaluate(d, grid, flip):
    global _D
    _D = d
    return [dict(g, mitad1=a, mitad2=b, total=a["total"] + b["total"]) for g, _, a, b in _pmap([(g, flip) for g in grid]) if a and b]


def summary(rows):
    tot = np.array([r["total"] for r in rows])
    both = [r for r in rows if r["mitad1"]["total"] > 0 and r["mitad2"]["total"] > 0]
    best = sorted(both, key=lambda r: -min(r["mitad1"]["t"], r["mitad2"]["t"]))[:5]
    return dict(versiones=len(rows), positivas=int((tot > 0).sum()), positivas_ambas=len(both),
                mediana=int(np.median(tot)) if len(tot) else None, mejores=best)


def big_grid(steps, targets=(300, 500, 700), losses=(900, 2_000)):
    out = []
    for t, ml, st, n, mo, fn, z in itertools.product(targets, losses, steps, (1, 3, 5), ("a favor", "en contra"), (6, 12),
                                                     ("kill zones", "todo el día")):
        if n == 1 and (st != steps[0] or mo != "a favor"):
            continue
        out.append(dict(target=t, maxloss=ml, step=st, maxn=n, mode=mo, flown=fn, zones=z))
    return out


def small_account(d, contract, cost, steps, zones_list):
    """cuenta de $100 con 0.01 lote por entrada; se quema si la caída llega a $100"""
    global _D
    penny.configure(contract, 0.01, cost)
    _D = d
    tasks = []
    for flip in (False, True):
        for t, ml, st, n, mo, z in itertools.product((3, 5, 10, 20), (10, 20, 40), steps, (1, 3, 5), ("a favor", "en contra"), zones_list):
            if n == 1 and (st != steps[0] or mo != "a favor"):
                continue
            tasks.append((dict(target=t, maxloss=ml, step=st, maxn=n, mode=mo, flown=12, zones=z), flip))
    rows = []
    for g, flip, a, b in _pmap(tasks):
        t, ml, st, n, mo, z = g["target"], g["maxloss"], g["step"], g["maxn"], g["mode"], g["zones"]
        if True:
            if a and b:
                full_dd = max(a["peor_caida"], b["peor_caida"])
                rows.append(dict(direccion="invertido" if flip else "sigue", objetivo=t, tope=ml, paso=st, entradas=n, modo=mo, horario=z,
                                 mitad1=a["total"], mitad2=b["total"], total=a["total"] + b["total"],
                                 peor_caida=full_dd, quemada=bool(full_dd >= 100 or a["total"] <= -100),
                                 t_min=min(a["t"], b["t"]), canastas=a["canastas"] + b["canastas"]))
    ok = [r for r in rows if r["mitad1"] > 0 and r["mitad2"] > 0 and not r["quemada"]]
    return dict(versiones=len(rows), quemadas=sum(r["quemada"] for r in rows), positivas_ambas_sin_quemar=len(ok),
                mejores=sorted(ok, key=lambda r: -r["t_min"])[:5],
                mejor_total=max(rows, key=lambda r: r["total"]) if rows else None)


def main():
    which = sys.argv[1:] or ["oro", "btc"]
    out = {}
    if "oro" in which:
        d = load_flow("data/PAXGUSD_M5.csv", True)
        penny.configure(100, 0.13, 0.45)
        g = big_grid((1.0, 2.0, 4.0))
        out["oro $100K sigue"] = summary(evaluate(d, g, False))
        out["oro $100K invertido"] = summary(evaluate(d, g, True))
        out["oro $100"] = small_account(d, 100, 0.45, (1.0, 2.0, 4.0), ("kill zones", "todo el día"))
        for k in ("oro $100K sigue", "oro $100K invertido", "oro $100"):
            print(k, json.dumps({x: y for x, y in out[k].items() if x not in ("mejores", "mejor_total")}))
    if "btc" in which:
        d = load_flow("data/BTCUSDT_M5_flow.csv", False)
        penny.configure(1, 0.25, 45.0)
        g = big_grid((100.0, 200.0, 400.0))
        g = [x for x in g if x["zones"] != "todo el día"] + [dict(x, zones="24/7") for x in g if x["zones"] == "todo el día"]
        out["btc $100K sigue"] = summary(evaluate(d, g, False))
        out["btc $100K invertido"] = summary(evaluate(d, g, True))
        out["btc $100"] = small_account(d, 1, 45.0, (100.0, 200.0, 400.0), ("kill zones", "24/7"))
        for k in ("btc $100K sigue", "btc $100K invertido", "btc $100"):
            print(k, json.dumps({x: y for x, y in out[k].items() if x not in ("mejores", "mejor_total")}))
    name = "results/penny_long_" + "_".join(which) + ".json"
    json.dump(out, open(name, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

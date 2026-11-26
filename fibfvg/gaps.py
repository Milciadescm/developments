"""Recolector de gaps: modelo binario condicionado sobre el hueco entre el CIERRE de una vela y la APERTURA de la siguiente.

Pregunta binaria: ¿el precio vuelve a cerrar el gap (toca el cierre anterior) antes de tocar el stop / antes del límite
de tiempo?  Se condiciona por: tamaño del gap en ATR, tipo (fin de semana / reapertura diaria), si el gap va a favor o en
contra del sesgo semanal, y día de la semana.  Dos formas de operarlo:
  "llenar"  (fade)        : entrar contra el gap en la apertura, objetivo = cierre anterior (100 %) o la mitad (50 %)
  "seguir"  (gap and go)  : entrar a favor del gap, objetivo = 1 o 2 veces el gap
Stop: 1 o 2 veces el tamaño del gap, o 1 ATR.  Límite de tiempo: 4, 8 o 24 velas (H1) / cierre del día (D1).
Costo: 2 x spread (en la reapertura el spread es más ancho).  Si stop y objetivo caen en la misma vela, cuenta el stop.
Muestras:
  H1 : US500, NAS100, XAUUSD, XAGUSD, jul 2024 - nov 2026 (gaps en reaperturas: 17-18 h NY y fin de semana); mitades 2025-08-19
  D1 : S&P, Nasdaq, oro, plata 2006-2026 (gap de la apertura diaria contra el cierre anterior); mitades 2016
Regla de elección (para no engañarnos): la celda (forma x stop x objetivo x tiempo x condición) se elige SOLO en la primera
mitad con n >= 20, R >= 0.10 y t >= 2; luego debe ser positiva en la segunda mitad.
    python -m fibfvg.gaps -> results/gaps.json
"""
import itertools
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import atr, htf_bias
from .levels import load_sym
from .longhold import load_long

MKT = ["US500", "NAS100", "XAUUSD", "XAGUSD"]


def events_h1(sym):
    d, h = load_sym(sym)
    a = atr(h, 14).values
    bias = htf_bias(d)
    O, H, L, C = (h[c].values for c in ("Open", "High", "Low", "Close"))
    gapt = h.index.to_series().diff().dt.total_seconds().values / 3600
    out = []
    for i in range(20, len(h) - 25):
        if not gapt[i] > 1.01 or np.isnan(a[i - 1]) or a[i - 1] <= 0:
            continue
        g = O[i] - C[i - 1]
        if abs(g) < 0.1 * a[i - 1]:
            continue
        bi = bias[bias.index <= h.index[i]]
        wb = bi.w.iloc[-1] if len(bi) else 0
        ny = h.index[i].tz_convert("America/New_York")
        out.append(dict(i=i, t=h.index[i], gap=g, gap_atr=abs(g) / a[i - 1], atr=a[i - 1], tipo="fin de semana" if gapt[i] > 30 else "diario",
                        con_sesgo=bool(np.sign(g) == wb), dia=ny.dayofweek))
    return h, out


def trade(O, H, L, C, i, dr, entry, tgt, stop, nmax, cost):
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    for t in range(i, min(len(O), i + nmax)):
        if (L[t] <= stop) if dr > 0 else (H[t] >= stop):
            return -1.0 - cost / risk
        if (H[t] >= tgt) if dr > 0 else (L[t] <= tgt):
            return abs(tgt - entry) / risk - cost / risk
    last = min(len(O), i + nmax) - 1
    return (C[last] - entry) * dr / risk - cost / risk


def size_bin(x):
    return "0.1-0.5 ATR" if x < 0.5 else "0.5-1 ATR" if x < 1 else "1-2 ATR" if x < 2 else ">2 ATR"


CONDS = {
    "todos": lambda e: True,
    **{f"tamaño {b}": (lambda b: lambda e: size_bin(e["gap_atr"]) == b)(b) for b in ("0.1-0.5 ATR", "0.5-1 ATR", "1-2 ATR", ">2 ATR")},
    "fin de semana": lambda e: e["tipo"] == "fin de semana",
    "diario": lambda e: e["tipo"] == "diario",
    "gap a favor del sesgo": lambda e: e["con_sesgo"],
    "gap contra el sesgo": lambda e: not e["con_sesgo"],
    "lunes": lambda e: e["dia"] == 0,
}


def grid_rows(sym, bars, evs, split, nlist, half_of):
    O, H, L, C = bars
    cost = 2 * SYMBOLS[sym].spread
    rows = []
    for form, tgt_k, stop_k, nmax in itertools.product(("llenar", "seguir"), (0.5, 1.0, 2.0), ("1 gap", "2 gaps", "1 ATR"), nlist):
        if form == "llenar" and tgt_k > 1:
            continue
        if form == "seguir" and tgt_k < 1:
            continue
        res = []
        for e in evs:
            i, g = e["i"], e["gap"]
            dr = -np.sign(g) if form == "llenar" else np.sign(g)
            entry = O[i]
            tgt = entry + dr * tgt_k * abs(g)
            sd = abs(g) if stop_k == "1 gap" else 2 * abs(g) if stop_k == "2 gaps" else e["atr"]
            r = trade(O, H, L, C, i, dr, entry, tgt, entry - dr * sd, nmax, cost)
            if r is not None:
                res.append((e, r))
        for cname, cf in CONDS.items():
            rr = [(e, r) for e, r in res if cf(e)]
            h1 = np.array([r for e, r in rr if half_of(e) == 1]); h2 = np.array([r for e, r in rr if half_of(e) == 2])
            if len(h1) < 20 or len(h2) < 10:
                continue
            st = lambda x: dict(n=len(x), R=round(float(x.mean()), 3), aciertos=round(float((x > 0).mean() * 100)),
                                t=round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2) if x.std() > 0 else 0)
            rows.append(dict(mercado=sym, forma=form, objetivo=f"{tgt_k:g} x gap", stop=stop_k, velas=nmax, condicion=cname,
                             mitad1=st(h1), mitad2=st(h2)))
    return rows


def h1_study():
    rows, fills = [], {}
    split = pd.Timestamp("2025-08-19", tz="UTC")
    for s in MKT:
        h, evs = events_h1(s)
        O, H, L, C = (h[c].values for c in ("Open", "High", "Low", "Close"))
        # probabilidad binaria de llenado (toca el cierre anterior) en 4/8/24 velas, por tamaño
        tab = {}
        for e in evs:
            prev = O[e["i"]] - e["gap"]
            k = size_bin(e["gap_atr"])
            for n in (1, 4, 8, 24):
                seg = slice(e["i"], e["i"] + n)
                hit = (L[seg].min() <= prev) if e["gap"] > 0 else (H[seg].max() >= prev)
                tab.setdefault(k, {}).setdefault(n, []).append(hit)
        fills[s] = dict(gaps=len(evs), por_tamaño={k: {f"{n} velas": round(float(np.mean(v)) * 100) for n, v in d.items()} | {"n": len(d[1])}
                                                   for k, d in sorted(tab.items())})
        rows += grid_rows(s, (O, H, L, C), evs, split, (4, 8, 24), lambda e: 1 if e["t"] < split else 2)
    return rows, fills


def d1_study():
    rows, fills = [], {}
    split = pd.Timestamp("2016-01-01", tz="UTC")
    for s in MKT:
        d = load_long(s)
        d = d[d.index >= pd.Timestamp("2006-01-01", tz="UTC")]
        a = atr(d, 14).values
        bias = htf_bias(d)
        O, H, L, C = (d[c].values for c in ("Open", "High", "Low", "Close"))
        evs = []
        for i in range(20, len(d)):
            g = O[i] - C[i - 1]
            if np.isnan(a[i - 1]) or abs(g) < 0.1 * a[i - 1]:
                continue
            evs.append(dict(i=i, t=d.index[i], gap=g, gap_atr=abs(g) / a[i - 1], atr=a[i - 1],
                            tipo="fin de semana" if d.index[i].dayofweek == 0 else "diario", con_sesgo=bool(np.sign(g) == bias.w.iloc[i]),
                            dia=d.index[i].dayofweek))
        tab = {}
        for e in evs:
            prev = O[e["i"]] - e["gap"]
            hit = (L[e["i"]] <= prev) if e["gap"] > 0 else (H[e["i"]] >= prev)
            tab.setdefault(size_bin(e["gap_atr"]), []).append(hit)
        fills[s] = dict(gaps=len(evs), llena_el_mismo_dia={k: dict(pct=round(float(np.mean(v)) * 100), n=len(v)) for k, v in sorted(tab.items())})
        rows += grid_rows(s, (O, H, L, C), evs, split, (1,), lambda e: 1 if e["t"] < split else 2)
    return rows, fills


def pick(rows):
    chosen = [r for r in rows if r["mitad1"]["R"] >= 0.10 and r["mitad1"]["t"] >= 2]
    surv = [r for r in chosen if r["mitad2"]["R"] > 0]
    return chosen, surv


def main():
    out = {}
    for name, fn in (("H1 2024-2026", h1_study), ("D1 2006-2026", d1_study)):
        rows, fills = fn()
        chosen, surv = pick(rows)
        out[name] = dict(celdas=len(rows), elegidas_mitad1=len(chosen), sobreviven_mitad2=len(surv),
                         sobrevivientes=sorted(surv, key=lambda r: -min(r["mitad1"]["t"], r["mitad2"]["t"])),
                         probabilidad_de_llenado=fills,
                         mejores_por_aciertos=sorted([r for r in rows if r["condicion"] == "todos"], key=lambda r: -r["mitad1"]["aciertos"])[:6])
        print(f"== {name}: celdas {len(rows)} | elegidas en mitad 1: {len(chosen)} | positivas en mitad 2: {len(surv)}")
        for s, f in fills.items():
            print("   llenado", s, f)
        for r in out[name]["sobrevivientes"][:12]:
            print("   ", r["mercado"], r["forma"], r["objetivo"], "stop", r["stop"], "velas", r["velas"], "|", r["condicion"], "| m1", r["mitad1"], "| m2", r["mitad2"])
        print("   -- más aciertos (todos los gaps):")
        for r in out[name]["mejores_por_aciertos"]:
            print("     ", r["mercado"], r["forma"], r["objetivo"], "stop", r["stop"], "velas", r["velas"], "| m1", r["mitad1"], "| m2", r["mitad2"])
    json.dump(out, open("results/gaps.json", "w"), indent=1, default=str, ensure_ascii=False)


if __name__ == "__main__":
    main()

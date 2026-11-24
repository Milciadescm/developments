"""Cuenta real de $1,000, solo XAUUSD, caída máxima 12 %, sin retiros por 2 años.

Bots probados solo en oro: Hold (mantener, añade a ganadoras, chandelier, breakeven 2R), Turtle semanal,
24 horas (Prop24) y medianoche. Tamaños: lote fijo 0.01 / 0.02 / 0.05 / 0.08, y riesgo % del saldo.
Dos formas de control:
  "sin protección": cada señal abre con el lote pedido; si el saldo cae 12 % desde su máximo, el bot se apaga.
  "con protección": antes de abrir, el bot achica o salta la operación si su stop + lo abierto pasaría la línea del 12 %.
Períodos: jul 2024 -> nov 2026 (todos los bots) y 2006 -> 2026 (Hold y Turtle, datos diarios), más todas las ventanas de 24 meses.
    python -m fibfvg.gold1k -> results/gold1k.json
"""
import json

import numpy as np
import pandas as pd

from . import propsim, scoreboard  # noqa: F401  (scoreboard registra el modo BE2)
from .engines import load, net_r
from .plans import position_engine
from .prop24 import build as prop_build
from .propsim import Account, run
from .swaps import with_swaps
from .longhold import load_long
from .threeway import weekly
from .onemarket import midnight_trades

CAP = 1_000
S = "XAUUSD"
H0 = pd.Timestamp("2024-07-01", tz="UTC")
L0 = pd.Timestamp("2006-01-01", tz="UTC")


def hold(d, start):
    tr = with_swaps(position_engine(S, d, "BE2", start=start))
    for t in tr:
        t.plan = "Plan 1"
    return tr


def sim(tr, size, protect, start, end=None):
    """size: ('lot', 0.05) or ('risk', 0.01)"""
    kind, v = size
    propsim.FIXED_LOT = v if kind == "lot" else None
    propsim.BUMP_MIN_LOT = True
    r = v if kind == "risk" else 0.01
    propsim.MODES["X"] = dict(p1=r, p3=r)
    acct = Account("Real", CAP, 0.0, None, 0.12, trailing=True, real=True, payout_days=None)
    o = run(tr, acct, "X", start=start, end=end, guard=protect)
    propsim.FIXED_LOT = None
    bal = [CAP] + [b for _, b in o["curve"]]
    peak, dd = CAP, 0.0
    for b in bal:
        peak = max(peak, b); dd = max(dd, (peak - b) / peak)
    rk = [f["risk_usd"] / f["equity"] * 100 for f in o["fills"] if f["equity"] > 0]
    return dict(end=round(o["end_balance"]), pct=round((o["end_balance"] / CAP - 1) * 100, 1), worst_dd=round(dd * 100, 1),
                stopped_at_12pct=o["breach"], low=round(min(bal)), trades=o["trades"],
                avg_risk=round(float(np.mean(rk)), 1) if rk else 0, max_risk=round(float(np.max(rk)), 1) if rk else 0)


def windows(tr, size, protect, first, last):
    """every 24-month window starting on the 1st of each month"""
    out = []
    s = first
    while s + pd.DateOffset(months=24) <= last:
        out.append(sim(tr, size, protect, s, s + pd.DateOffset(months=24)))
        s += pd.DateOffset(months=1)
    e = np.array([w["end"] for w in out])
    return dict(n=len(out), median_end=int(np.median(e)), worst_end=int(e.min()), best_end=int(e.max()),
                share_stopped=round(float(np.mean([bool(w["stopped_at_12pct"]) for w in out])) * 100),
                share_losing=round(float(np.mean(e < CAP)) * 100))


def stats(tr, start):
    r = np.array([net_r(t) for t in tr if t.entry_time >= start])
    sp = pd.Timestamp("2025-08-19", tz="UTC") if start == H0 else pd.Timestamp("2016-01-01", tz="UTC")
    a = np.array([net_r(t) for t in tr if start <= t.entry_time < sp]); b = np.array([net_r(t) for t in tr if t.entry_time >= sp])
    return dict(trades=len(r), win=round(float((r > 0).mean() * 100)), avg_R=round(float(r.mean()), 2),
                t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 1),
                halves=[round(float(a.mean()), 2), round(float(b.mean()), 2)])


def main():
    a, b = prop_build()
    d24 = load(f"data/{S}_D1.csv")
    recent = {"Hold (mantener)": hold(d24[d24.index >= pd.Timestamp("2024-01-01", tz="UTC")], "2024-01-01"),
              "Turtle semanal": weekly(S, d24, add_only_in_profit=True, runner="trail"),
              "24 horas": sorted([t for t in a + b if t.symbol == S], key=lambda t: t.entry_time),
              "Medianoche": midnight_trades(S)}
    dl = load_long(S)
    long = {"Hold (mantener)": hold(dl, "2006-01-01"), "Turtle semanal": weekly(S, dl, add_only_in_profit=True, runner="trail")}
    sizes = [("lot", 0.01), ("lot", 0.02), ("lot", 0.05), ("lot", 0.08), ("risk", 0.005), ("risk", 0.01), ("risk", 0.02)]
    now = pd.Timestamp("2026-11-23", tz="UTC")
    out = {"recent": {}, "20y": {}}
    for name, tr in recent.items():
        out["recent"][name] = dict(stats=stats(tr, H0), runs={})
        for sz in sizes:
            for prot in (False, True):
                k = f"{sz[0]} {sz[1]} {'con' if prot else 'sin'} proteccion"
                out["recent"][name]["runs"][k] = sim(tr, sz, prot, H0)
        print(name, json.dumps(out["recent"][name]["stats"]))
        for k, v in out["recent"][name]["runs"].items():
            print("   ", k, v)
    for name, tr in long.items():
        out["20y"][name] = dict(stats=stats(tr, L0), runs={})
        for sz in sizes:
            for prot in (False, True):
                k = f"{sz[0]} {sz[1]} {'con' if prot else 'sin'} proteccion"
                out["20y"][name]["runs"][k] = dict(full=sim(tr, sz, prot, L0), windows_24m=windows(tr, sz, prot, L0, now))
        print("20y", name, json.dumps(out["20y"][name]["stats"]))
        for k, v in out["20y"][name]["runs"].items():
            print("   ", k, v)
    json.dump(out, open("results/gold1k.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

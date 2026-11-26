"""Recolector de centavos en oro (XAUUSD), cuenta de $100,000, 0.13 lote por entrada.

Datos: futuros de oro GC=F de Yahoo, velas de 5 minutos del 17 sep al 25 nov 2026 (~50 días de trading) y de 1 minuto
de la última semana (data/XAUUSD_M5_GC.csv, data/XAUUSD_M1_GC.csv, hora de Nueva York). No hay datos de libro de órdenes:
el "order flow" se aproxima con el volumen de cada vela firmado por su dirección (delta = volumen si cerró arriba,
-volumen si cerró abajo), sumado en las últimas N velas: es la lectura de cinta posible con datos de velas.

Reglas (decisión al cierre de la vela, ejecución al precio de apertura de la siguiente):
  Kill zones (hora NY): Londres 02:00-05:00 y Nueva York 07:00-10:00 (o todo el día, como variante).
  Punto de origen: el precio de apertura de la kill zone.  Impulso: el precio se aleja del origen al menos k x ATR(14) de 5 min.
  Entrada: en la dirección del impulso solo si el delta de volumen de las últimas N velas va en la misma dirección.
  Entradas múltiples: hasta M entradas de 0.13 lote; cada nueva entrada cuando el precio se mueve `paso` dólares
      "a favor" (piramidar) o "en contra" (promediar).
  Cierre de la canasta: cuando la ganancia flotante de TODAS las entradas llega al objetivo ($300 / $500 / $700) se cierra todo;
      si la pérdida flotante llega al tope ($1,000 = límite flotante de GFT, o $2,000) se cierra todo;
      2 horas después de terminar la kill zone se cierra todo.
  Reentrada: después de cerrar, vuelve a entrar en la dirección que diga el delta (misma u opuesta) si sigue en la kill zone.
  Costos: spread + deslizamiento $0.45 por onza por entrada (ida y vuelta): $5.85 por entrada de 0.13 lote.
  Si en una misma vela se tocan el objetivo y el tope, se cuenta el tope (conservador).
Prueba: 432 combinaciones. Se eligen con la primera mitad (17 sep - 20 oct) y se juzgan en la segunda (21 oct - 25 nov).
    python -m fibfvg.penny -> results/penny.json
"""
import itertools
import json

import numpy as np
import pandas as pd

LOT = 0.13
OZ = 100 * LOT                 # dólares por cada $1 de movimiento del oro
COST = 0.45 * OZ               # por entrada
SPLIT = pd.Timestamp("2026-10-21", tz="America/New_York")


def load(path):
    d = pd.read_csv(path, skiprows=3, header=None, names=["t", "adj", "Close", "High", "Low", "Open", "Volume"])
    d["t"] = pd.to_datetime(d["t"], utc=True).dt.tz_convert("America/New_York")
    d = d.set_index("t")[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    return d[(d.High > 0) & (d.Low > 0)]


def run(d, target, maxloss, step, maxn, mode, flown, k, zones, start=None, end=None):
    O, H, L, C, V = (d[c].values for c in ("Open", "High", "Low", "Close", "Volume"))
    T = d.index
    tr = np.maximum(H - L, np.maximum(np.abs(H - np.roll(C, 1)), np.abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().values
    delta = pd.Series(np.sign(C - O) * V).rolling(flown).sum().values
    hour = T.hour + T.minute / 60
    if zones == "kill zones":
        inz = ((hour >= 2) & (hour < 5)) | ((hour >= 7) & (hour < 10))
        zone_id = np.where((hour >= 2) & (hour < 7), 1, np.where((hour >= 7) & (hour < 12), 2, 0))
        close_at = ((hour >= 7) & (hour < 7.01)) | ((hour >= 12) & (hour < 12.01))
    elif zones == "24/7":
        inz = np.ones(len(T), bool)
        days = (T - pd.Timedelta(hours=17)).normalize()
        zone_id = np.asarray(pd.factorize(days)[0] % 1000 + 1)
        close_at = (hour >= 16.9) & (hour < 17.0)
    else:
        inz = (hour >= 2) & (hour < 16)
        zone_id = np.where((hour >= 2) & (hour < 17), 1, 0)
        close_at = (hour >= 17) & (hour < 17.01)
    pos = []                    # (precio, dirección)
    origin, zone_prev = np.nan, 0
    baskets = []                # resultado en $ de cada canasta
    eq_day = {}
    worst_float = 0.0
    pend = None
    for i in range(20, len(T)):
        if start is not None and T[i] < start:
            continue
        if end is not None and T[i] >= end:
            break
        day = T[i].date()
        if zone_id[i] != zone_prev:
            origin = O[i]; zone_prev = zone_id[i]
        if pend is not None:
            pos.append((O[i], pend)); pend = None
        if pos:
            dr = pos[0][1]
            worst = sum((L[i] - p) * dr * OZ if dr > 0 else (H[i] - p) * dr * OZ for p, _ in pos)
            best = sum((H[i] - p) * dr * OZ if dr > 0 else (L[i] - p) * dr * OZ for p, _ in pos)
            worst_float = min(worst_float, worst)
            cost = COST * len(pos)
            res = None
            if worst <= -maxloss:
                res = -maxloss
            elif best >= target:
                res = target
            elif close_at[i] or zone_id[i] == 0:
                res = sum((O[i] - p) * dr * OZ for p, _ in pos)
            if res is not None:
                baskets.append((T[i], res - cost, len(pos)))
                eq_day[day] = eq_day.get(day, 0) + res - cost
                pos = []
                continue
            last = pos[-1][0]
            if len(pos) < maxn:
                move = (C[i] - last) * dr
                if (mode == "a favor" and move >= step) or (mode == "en contra" and move <= -step):
                    pend = dr
            continue
        if not inz[i] or np.isnan(atr[i]) or np.isnan(origin):
            continue
        imp = C[i] - origin
        if abs(imp) >= k * atr[i] and np.sign(delta[i]) == np.sign(imp) and delta[i] != 0:
            pend = int(np.sign(imp))
    r = np.array([b[1] for b in baskets])
    if len(r) == 0:
        return None
    days = np.array(list(eq_day.values()))
    eq = np.cumsum(r); peak = np.maximum.accumulate(np.concatenate([[0], eq]))[1:]
    return dict(canastas=len(r), aciertos=round(float((r > 0).mean() * 100), 1), total=round(float(r.sum())),
                promedio=round(float(r.mean()), 1), t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2) if len(r) > 2 else 0,
                ganancia_prom=round(float(r[r > 0].mean()), 1) if (r > 0).any() else 0,
                perdida_prom=round(float(r[r <= 0].mean()), 1) if (r <= 0).any() else 0,
                peor_dia=round(float(days.min())), peor_caida=round(float((peak - eq).max())),
                peor_flotante=round(worst_float), entradas_prom=round(float(np.mean([b[2] for b in baskets])), 1))


def main():
    d5 = load("data/XAUUSD_M5_GC.csv")
    grid = list(itertools.product((300, 500, 700), (1_000, 2_000), (1.0, 2.0, 4.0), (1, 3, 5), ("a favor", "en contra"),
                                  (6, 12), ("kill zones", "todo el día")))
    rows = []
    for target, ml, step, mn, mode, fn, zones in grid:
        if mn == 1 and (step != 1.0 or mode != "a favor"):
            continue
        a = run(d5, target, ml, step, mn, mode, fn, 1.0, zones, end=SPLIT)
        b = run(d5, target, ml, step, mn, mode, fn, 1.0, zones, start=SPLIT)
        full = run(d5, target, ml, step, mn, mode, fn, 1.0, zones)
        if a and b and full:
            rows.append(dict(objetivo=target, tope=ml, paso=step, entradas=mn, modo=mode, flujo_velas=fn, horario=zones,
                             primera=a, segunda=b, completo=full))
    rows.sort(key=lambda x: -x["primera"]["total"])
    both = [x for x in rows if x["primera"]["total"] > 0 and x["segunda"]["total"] > 0]
    out = dict(versiones=len(rows), positivas_ambas_mitades=len(both),
               positivas_completo=sum(x["completo"]["total"] > 0 for x in rows),
               mejores_primera_mitad=rows[:10], mejores_ambas=sorted(both, key=lambda x: -x["completo"]["t"])[:10])
    # la mejor elegida con la primera mitad, revisada con velas de 1 minuto (última semana)
    best = rows[0]
    d1 = load("data/XAUUSD_M1_GC.csv")
    out["mejor_en_1_minuto"] = run(d1, best["objetivo"], best["tope"], best["paso"], best["entradas"], best["modo"],
                                   best["flujo_velas"] * 5, 1.0, best["horario"])
    out["misma_en_5_minutos_misma_semana"] = run(d5, best["objetivo"], best["tope"], best["paso"], best["entradas"], best["modo"],
                                                best["flujo_velas"], 1.0, best["horario"], start=d1.index[0])
    print("versiones", out["versiones"], "| positivas en ambas mitades", out["positivas_ambas_mitades"],
          "| positivas en total", out["positivas_completo"])
    for x in rows[:5]:
        print("TOP 1a mitad", {k: x[k] for k in ("objetivo", "tope", "paso", "entradas", "modo", "flujo_velas", "horario")},
              "1a", x["primera"]["total"], "2a", x["segunda"]["total"], "| completo", x["completo"])
    for x in out["mejores_ambas"][:5]:
        print("AMBAS", {k: x[k] for k in ("objetivo", "tope", "paso", "entradas", "modo", "flujo_velas", "horario")},
              "1a", x["primera"]["total"], "2a", x["segunda"]["total"], "| completo", x["completo"])
    print("1 minuto:", out["mejor_en_1_minuto"], "| 5 min misma semana:", out["misma_en_5_minutos_misma_semana"])
    json.dump(out, open("results/penny.json", "w"), indent=1, default=str)


def configure(contract, lot, cost_per_unit):
    global LOT, OZ, COST
    LOT = lot; OZ = contract * lot; COST = cost_per_unit * OZ


def load_btc(path="data/BTCUSD_M5.csv"):
    d = pd.read_csv(path, parse_dates=["t"]).set_index("t")
    d.index = d.index.tz_convert("America/New_York")
    d["Volume"] = 1.0                      # sin volumen: el "flujo" cuenta velas alcistas menos bajistas
    return d


def main_small():
    """cuenta de $100: oro con 0.01 lote ($1 por cada $1 de movimiento) y BTC con 0.01 lote ($0.01 por cada $1)"""
    out = {}
    gold = load("data/XAUUSD_M5_GC.csv")
    btc = load_btc(); btc = btc[btc.index >= gold.index[0]]
    for name, d, contract, cost, steps, zones_list in (
            ("XAUUSD 0.01 lote", gold, 100, 0.45, (1.0, 2.0, 4.0), ("kill zones", "todo el día")),
            ("BTCUSD 0.01 lote", btc, 1, 45.0, (100.0, 200.0, 400.0), ("kill zones", "todo el día", "24/7"))):
        configure(contract, 0.01, cost)
        split = d.index[0] + (d.index[-1] - d.index[0]) / 2
        rows = []
        for target, ml, step, mn, mode, fn, zones in itertools.product((3, 5, 7), (10, 20), steps, (1, 3, 5),
                                                                        ("a favor", "en contra"), (6, 12), zones_list):
            if mn == 1 and (step != steps[0] or mode != "a favor"):
                continue
            a = run(d, target, ml, step, mn, mode, fn, 1.0, zones, end=split)
            b = run(d, target, ml, step, mn, mode, fn, 1.0, zones, start=split)
            f = run(d, target, ml, step, mn, mode, fn, 1.0, zones)
            if a and b and f:
                rows.append(dict(objetivo=target, tope=ml, paso=step, entradas=mn, modo=mode, flujo_velas=fn, horario=zones,
                                 primera=a["total"], segunda=b["total"], completo=f, quemada=f["peor_caida"] >= 100))
        rows.sort(key=lambda x: -x["primera"])
        both = [x for x in rows if x["primera"] > 0 and x["segunda"] > 0]
        out[name] = dict(versiones=len(rows), positivas_ambas=len(both), positivas_total=sum(x["completo"]["total"] > 0 for x in rows),
                         quemadas=sum(x["quemada"] for x in rows), mejor_primera=rows[0],
                         mejores_ambas=sorted(both, key=lambda x: -x["completo"]["t"])[:5])
        print(name, "| versiones", len(rows), "| positivas ambas mitades", len(both), "| positivas total",
              out[name]["positivas_total"], "| cuentas de $100 que caen $100 o más", out[name]["quemadas"])
        print("   mejor 1a mitad:", {k: rows[0][k] for k in ("objetivo", "tope", "paso", "entradas", "modo", "horario")},
              "2a mitad", rows[0]["segunda"], rows[0]["completo"])
        for x in out[name]["mejores_ambas"][:3]:
            print("   ambas:", {k: x[k] for k in ("objetivo", "tope", "paso", "entradas", "modo", "horario")}, x["completo"])
    json.dump(out, open("results/penny_100.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    import sys
    main_small() if "100" in sys.argv[1:] else main()

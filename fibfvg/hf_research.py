"""Fase 1 - investigación de alta frecuencia (meta: ~10-20 operaciones por semana con >= 0.3-0.7R después de costos).

Datos: oro (PAXG) y BTC en velas de 5 minutos, ene 2024 - nov 2026, con flujo de órdenes real (compras - ventas a mercado).
Para no elegir por suerte, tres tramos:
  elección   : 2024-01-01 a 2025-03-31  (aquí se eligen los parámetros)
  validación : 2025-04-01 a 2025-12-31  (debe seguir positivo)
  prueba     : 2026-01-01 a hoy         (no se mira hasta el final; debe seguir positivo)
Cada señal se decide al cierre de una vela y entra en la apertura de la siguiente; stop = k x ATR(14, 5 min),
objetivo = m x stop, cierre por tiempo a las N velas; una posición a la vez por mercado; costos en R (spread + deslizamiento).
Si stop y objetivo se tocan en la misma vela, cuenta el stop.
Familias de señales:
  ORB      ruptura del rango de los primeros 30 min de Londres (03:00 NY) o Nueva York (09:30) a favor del sesgo diario
  BARRIDO  el precio toma el máximo/mínimo de la sesión anterior y cierra de vuelta adentro, con el flujo girando: entrar en contra
  FVG5     hueco de valor justo de 5 min a favor de la tendencia de 1 hora (EMA 50), entrada a mercado cuando el precio vuelve al hueco
  FLUJO    oleada de flujo (z del delta de 12 velas > umbral) que rompe el máximo/mínimo de la última hora: a favor
    python -m fibfvg.hf_research -> results/hf_research.json
"""
import itertools
import json
from multiprocessing import Pool

import numpy as np
import pandas as pd

SEL_END = pd.Timestamp("2025-04-01", tz="America/New_York")
VAL_END = pd.Timestamp("2026-01-01", tz="America/New_York")
MARKETS = {"oro": ("data/PAXGUSD_M5.csv", 0.45, True), "btc": ("data/BTCUSDT_M5_flow.csv", 45.0, False)}


def load(path, weekdays):
    d = pd.read_csv(path, parse_dates=["t"]).set_index("t")
    d.index = d.index.tz_convert("America/New_York")
    d = d.astype(float)
    if weekdays:
        wd, h = d.index.dayofweek, d.index.hour
        d = d[~((wd == 5) | ((wd == 6) & (h < 18)) | ((wd == 4) & (h >= 17)))]
    return d


def features(d):
    O, H, L, C, V, TB = (d[c].values for c in ("Open", "High", "Low", "Close", "Volume", "TakerBuy"))
    tr = np.maximum(H - L, np.maximum(np.abs(H - np.roll(C, 1)), np.abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().values
    delta = 2 * TB - V
    d12 = pd.Series(delta).rolling(12).sum()
    z = ((d12 - d12.rolling(288).mean()) / d12.rolling(288).std()).values
    h1 = d["Close"].resample("1h").last().ffill()
    ema = h1.ewm(span=50).mean()
    trend = np.sign(ema.diff()).reindex(d.index, method="ffill").shift(12).fillna(0).values      # solo horas cerradas
    day = (d.index - pd.Timedelta(hours=17)).normalize()
    daily = d.groupby(day).agg(High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
    bias_d = np.sign(daily["Close"] - (daily["High"] + daily["Low"]) / 2).shift(1)
    prevH, prevL = daily["High"].shift(1), daily["Low"].shift(1)
    bias = bias_d.reindex(day).values; pH = prevH.reindex(day).values; pL = prevL.reindex(day).values
    hh12 = pd.Series(H).rolling(12).max().shift(1).values; ll12 = pd.Series(L).rolling(12).min().shift(1).values
    hour = d.index.hour + d.index.minute / 60
    return dict(O=O, H=H, L=L, C=C, atr=atr, delta=delta, z=z, trend=trend, bias=bias, pH=pH, pL=pL, hh12=hh12, ll12=ll12, hour=hour,
                d12=d12.values, T=d.index)


def signals(F, fam, p):
    n = len(F["C"]); s = np.zeros(n, int)
    C, H, L, O, hour = F["C"], F["H"], F["L"], F["O"], F["hour"]
    if fam == "ORB":
        start = p["sesion"]; end = start + 0.5
        inrange = (hour >= start) & (hour < end)
        key = pd.Series((F["T"] - pd.Timedelta(hours=17)).normalize())
        hi = pd.Series(np.where(inrange, H, np.nan)).groupby(key.values).cummax().ffill().values
        lo = pd.Series(np.where(inrange, L, np.nan)).groupby(key.values).cummin().ffill().values
        window = (hour >= end) & (hour < end + p["ventana"])
        up = window & (C > hi) & (F["bias"] > 0); dn = window & (C < lo) & (F["bias"] < 0)
        s[up] = 1; s[dn] = -1
    elif fam == "BARRIDO":
        swept_hi = (H > F["pH"]) & (C < F["pH"]) & (F["d12"] < 0)
        swept_lo = (L < F["pL"]) & (C > F["pL"]) & (F["d12"] > 0)
        act = (hour >= 2) & (hour < 12) if p["horas"] == "kz" else np.ones(n, bool)
        s[swept_hi & act] = -1; s[swept_lo & act] = 1
    elif fam == "FVG5":
        bull = np.roll(L, 0) > np.roll(H, 2); bear = np.roll(H, 0) < np.roll(L, 2)
        gap_mid_b = (np.roll(H, 2) + L) / 2; gap_mid_s = (np.roll(L, 2) + H) / 2
        last_b = pd.Series(np.where(bull & (F["trend"] > 0), gap_mid_b, np.nan)).ffill(limit=p["vida"]).values
        last_s = pd.Series(np.where(bear & (F["trend"] < 0), gap_mid_s, np.nan)).ffill(limit=p["vida"]).values
        s[(L <= last_b) & (C > last_b) & (F["trend"] > 0)] = 1
        s[(H >= last_s) & (C < last_s) & (F["trend"] < 0)] = -1
    elif fam == "FLUJO":
        up = (F["z"] > p["z"]) & (C > F["hh12"]); dn = (F["z"] < -p["z"]) & (C < F["ll12"])
        if p["con_tendencia"]:
            up &= F["trend"] > 0; dn &= F["trend"] < 0
        s[up] = 1; s[dn] = -1
    s[:300] = 0
    return s


def simulate(F, s, k, m, nbars, cost):
    """una posición a la vez; devuelve (índice de entrada, R neto)"""
    O, H, L, atr = F["O"], F["H"], F["L"], F["atr"]
    out = []
    i, n = 0, len(s)
    idx = np.nonzero(s)[0]
    j = 0
    busy_until = -1
    for i in idx:
        if i <= busy_until or i + 1 >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        dr = s[i]; e = O[i + 1]; st = k * atr[i]
        stop = e - dr * st; tgt = e + dr * m * st
        res = None; last = min(n - 1, i + 1 + nbars)
        for t in range(i + 1, last + 1):
            hit_s = (L[t] <= stop) if dr > 0 else (H[t] >= stop)
            hit_t = (H[t] >= tgt) if dr > 0 else (L[t] <= tgt)
            if hit_s:
                res = -1.0; break
            if hit_t:
                res = m; break
        if res is None:
            res = (O[last] - e) * dr / st if last < n else 0.0
            t = last
        out.append((i, res - cost / st))
        busy_until = t
    return out


def stats(r):
    r = np.array(r)
    if len(r) < 20:
        return None
    return dict(n=len(r), R=round(float(r.mean()), 3), aciertos=round(float((r > 0).mean() * 100), 1),
                t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2))


GRID = []
for fam, params in (("ORB", [dict(sesion=s, ventana=w) for s in (3.0, 9.5) for w in (1.0, 2.0)]),
                    ("BARRIDO", [dict(horas=h) for h in ("kz", "todo")]),
                    ("FVG5", [dict(vida=v) for v in (6, 24)]),
                    ("FLUJO", [dict(z=z, con_tendencia=c) for z in (1.5, 2.5) for c in (True, False)])):
    for p in params:
        for k, m, nb in itertools.product((0.5, 1.0, 1.5), (1.0, 1.5, 2.0, 3.0), (12, 48)):
            GRID.append((fam, p, k, m, nb))

_F = {}


def work(args):
    mk, fam, p, k, m, nb = args
    F, cost, T = _F[mk]
    s = signals(F, fam, p)
    tr = simulate(F, s, k, m, nb, cost)
    sel = [r for i, r in tr if T[i] < SEL_END]; val = [r for i, r in tr if SEL_END <= T[i] < VAL_END]
    test = [r for i, r in tr if T[i] >= VAL_END]
    weeks = (T[-1] - T[0]).days / 7
    return dict(mercado=mk, familia=fam, params=p, stop_atr=k, objetivo_R=m, velas_max=nb, por_semana=round(len(tr) / weeks, 1),
                eleccion=stats(sel), validacion=stats(val), prueba=stats(test))


def main():
    for mk, (path, cost, wd) in MARKETS.items():
        d = load(path, wd)
        F = features(d)
        _F[mk] = (F, cost, F["T"])
    tasks = [(mk, *g) for mk in MARKETS for g in GRID]
    with Pool(3) as pool:
        rows = pool.map(work, tasks, chunksize=4)
    rows = [r for r in rows if r["eleccion"] and r["validacion"]]
    # elegidas SOLO con el tramo de elección: R >= 0.15 y t >= 2; luego se mira validación y prueba
    chosen = [r for r in rows if r["eleccion"]["R"] >= 0.15 and r["eleccion"]["t"] >= 2]
    survive = [r for r in chosen if r["validacion"]["R"] > 0 and r["prueba"] and r["prueba"]["R"] > 0]
    out = dict(versiones=len(rows), elegidas_en_tramo_1=len(chosen), sobreviven_validacion_y_prueba=len(survive),
               sobrevivientes=sorted(survive, key=lambda r: -r["por_semana"] * r["validacion"]["R"]),
               mejores_tramo_1=sorted(rows, key=lambda r: -r["eleccion"]["t"])[:15])
    json.dump(out, open("results/hf_research.json", "w"), indent=1, default=str)
    print("versiones", len(rows), "| elegidas en tramo 1", len(chosen), "| sobreviven validación y prueba", len(survive))
    for r in out["sobrevivientes"][:15]:
        print(r["mercado"], r["familia"], r["params"], "stop", r["stop_atr"], "obj", r["objetivo_R"], "velas", r["velas_max"],
              "| por semana", r["por_semana"], "| elección", r["eleccion"], "| validación", r["validacion"], "| prueba", r["prueba"])


if __name__ == "__main__":
    main()

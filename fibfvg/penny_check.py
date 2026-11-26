"""Controles del recolector invertido: semana de 1 minuto, tope GFT de $900, y oro de 1 hora jul 2024 - nov 2026.
    PYTHONPATH=. python3 fibfvg/penny_check.py -> results/penny_controles.json
"""
import json, numpy as np, pandas as pd
from fibfvg import penny
from fibfvg.penny import run, load, SPLIT
out = {}
d5 = load("data/XAUUSD_M5_GC.csv"); d1 = load("data/XAUUSD_M1_GC.csv")
best = dict(target=700, maxloss=1000, step=1.0, maxn=5, mode="en contra", flown=12, zones="kill zones")
w1 = d1.index[0]
out["mejor_ambas_1min_semana"] = run(d1, best["target"], best["maxloss"], best["step"], best["maxn"], best["mode"], 60, 1.0, best["zones"], flip=True)
out["mejor_ambas_5min_misma_semana"] = run(d5, *[best[k] for k in ("target","maxloss","step","maxn","mode","flown")], 1.0, best["zones"], start=w1, flip=True)
out["mejor_ambas_sin_invertir"] = run(d5, *[best[k] for k in ("target","maxloss","step","maxn","mode","flown")], 1.0, best["zones"])
# GFT: tope de canasta $900 (1 % flotante) y hasta 3 entradas
g = []
for t in (300, 500, 700):
    for n in (1, 3):
        for st in (1.0, 2.0, 4.0):
            for mo in ("a favor", "en contra"):
                if n == 1 and (st != 1.0 or mo != "a favor"): continue
                a = run(d5, t, 900, st, n, mo, 12, 1.0, "kill zones", end=SPLIT, flip=True)
                b = run(d5, t, 900, st, n, mo, 12, 1.0, "kill zones", start=SPLIT, flip=True)
                f = run(d5, t, 900, st, n, mo, 12, 1.0, "kill zones", flip=True)
                if a and b and f: g.append(dict(objetivo=t, entradas=n, paso=st, modo=mo, mitad1=a["total"], mitad2=b["total"], completo=f))
out["gft_tope_900"] = sorted(g, key=lambda x: -x["completo"]["t"])[:6]
out["gft_tope_900_resumen"] = dict(versiones=len(g), positivas_ambas=sum(x["mitad1"] > 0 and x["mitad2"] > 0 for x in g))
# 1 hora, jul 2024 - nov 2026 (señal más gruesa, mucho más historia)
h = pd.read_csv("data/XAUUSD_H1.csv")
h.columns = [c.capitalize() if c.lower() in ("open","high","low","close","volume") else c for c in h.columns]
tc = h.columns[0]; h[tc] = pd.to_datetime(h[tc], utc=True); h = h.set_index(tc); h.index = h.index.tz_convert("America/New_York")
if "Volume" not in h: h["Volume"] = 1.0
h = h[["Open","High","Low","Close","Volume"]].astype(float)
hs = pd.Timestamp("2025-08-19", tz="America/New_York")
res = {}
for flip in (False, True):
    rows = []
    for t in (300, 500, 700, 1000):
        for ml in (1000, 2000):
            for n in (1, 3):
                for mo in ("a favor", "en contra"):
                    if n == 1 and mo == "en contra": continue
                    for z in ("kill zones", "todo el día"):
                        a = run(h, t, ml, 4.0, n, mo, 3, 1.0, z, end=hs, flip=flip); b = run(h, t, ml, 4.0, n, mo, 3, 1.0, z, start=hs, flip=flip)
                        if a and b: rows.append((a["total"], b["total"], a["canastas"] + b["canastas"]))
    r = np.array(rows)
    res["invertido" if flip else "original"] = dict(versiones=len(r), positivas_total=int(((r[:,0]+r[:,1]) > 0).sum()), positivas_ambas=int(((r[:,0] > 0) & (r[:,1] > 0)).sum()), mediana=int(np.median(r[:,0]+r[:,1])))
out["oro_1_hora_2024_2026"] = res
print(json.dumps(out, indent=0, default=str)[:4000])
json.dump(out, open("results/penny_controles.json","w"), indent=1, default=str)

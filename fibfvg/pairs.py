"""Recolector neutral al mercado: pares (oro/plata y S&P/Nasdaq). Se gana si la DISTANCIA entre dos mercados hermanos
vuelve a su promedio, sin importar si los dos suben o bajan.

Diferencial = log(A) - beta * log(B); beta, promedio y desviación con una ventana móvil de W velas (solo datos pasados).
z = (diferencial - promedio) / desviación.  Si z > entrada: vender A y comprar beta x B (mismo valor en dólares ajustado);
si z < -entrada: al revés.  Salida cuando z vuelve a la salida (0 o 0.5), stop si |z| llega a 4, o por tiempo.
Costos: el spread de las dos patas (fibfvg.config.SYMBOLS) en la entrada.  Resultado en puntos básicos (pb) del valor total
de las dos patas y en R (R = lo que se pierde si se toca el stop de z = 4, estimado con la desviación del momento).
Muestras: H1 jul 2024 - nov 2026 (mitades 2025-08-19), límite 24 h (Prop) o 5 días (Real);
          D1 2006 - 2026 (mitades 2016), límite 20 días.
También se mide la correlación del resultado con la dirección del mercado (¿de verdad es indiferente a la dirección?).
    python -m fibfvg.pairs -> results/pairs.json
"""
import itertools
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .levels import load_sym
from .longhold import load_long

PAIRS = [("XAUUSD", "XAGUSD"), ("US500", "NAS100")]


def frame(a, b, long):
    if long:
        A, B = load_long(a).Close, load_long(b).Close
        A = A[A.index >= pd.Timestamp("2005-01-01", tz="UTC")]
    else:
        A, B = load_sym(a)[1].Close, load_sym(b)[1].Close
    d = pd.concat([A.rename("A"), B.rename("B")], axis=1).dropna()
    return d[(d.A > 0) & (d.B > 0)]


def run(d, a, b, W, z_in, z_out, maxbars, split):
    la, lb = np.log(d.A.values), np.log(d.B.values)
    sa, sb = pd.Series(la), pd.Series(lb)
    cov = sa.rolling(W).cov(sb); var = sb.rolling(W).var()
    beta = (cov / var).shift(1).values
    spread = la - np.nan_to_num(beta) * lb
    sp = pd.Series(spread)
    # promedio y desviación del diferencial con el beta de cada momento (aprox.: ventana del diferencial calculado)
    mu = sp.rolling(W).mean().shift(1).values; sd = sp.rolling(W).std().shift(1).values
    z = (spread - mu) / sd
    T = d.index
    ca = SYMBOLS[a].spread / d.A.values; cb = SYMBOLS[b].spread / d.B.values     # costo relativo por pata
    out = []
    i = 2 * W
    n = len(d)
    while i < n - 1:
        if np.isnan(z[i]) or np.isnan(beta[i]) or abs(z[i]) < z_in or abs(z[i]) >= 3.5 or beta[i] <= 0:
            i += 1; continue
        side = -np.sign(z[i])                       # +1 = comprar el diferencial (comprar A, vender B)
        bt = beta[i]; w_a, w_b = 1 / (1 + bt), bt / (1 + bt)    # pesos en dólares de las dos patas
        e_a, e_b = la[i], lb[i]
        cost = w_a * ca[i] + w_b * cb[i]
        risk = (4 - abs(z[i])) * sd[i] * w_a        # pérdida aproximada (en fracción del total) si z llega a 4
        j_end = min(n - 1, i + maxbars)
        res = None
        for j in range(i + 1, j_end + 1):
            pnl = side * (w_a * (la[j] - e_a) - w_b * (lb[j] - e_b))
            zj = (la[j] - bt * lb[j] - mu[i]) / sd[i]
            if (side > 0 and zj >= -z_out) or (side < 0 and zj <= z_out) or abs(zj) >= 4:
                res = pnl; break
        if res is None:
            j = j_end; res = side * (w_a * (la[j] - e_a) - w_b * (lb[j] - e_b))
        net = res - cost
        mkt = (la[j] - e_a)                          # dirección del mercado A durante la operación
        out.append(dict(t=T[i], pb=net * 1e4, R=net / risk if risk > 0 else 0, gana=net > 0, velas=j - i, mercado=mkt, mitad=1 if T[i] < split else 2))
        i = j + 1
    return pd.DataFrame(out)


def st(x):
    if len(x) < 10:
        return None
    return dict(n=len(x), pb=round(float(x.pb.mean()), 2), R=round(float(x.R.mean()), 3), aciertos=round(float(x.gana.mean() * 100)),
                t=round(float(x.pb.mean() / (x.pb.std(ddof=1) / np.sqrt(len(x)))), 2))


def main():
    out = {}
    for long, split, Ws, holds in ((False, pd.Timestamp("2025-08-19", tz="UTC"), (120, 240, 500), (24, 120)),
                                   (True, pd.Timestamp("2016-01-01", tz="UTC"), (20, 60, 120), (5, 20))):
        name = "D1 2006-2026" if long else "H1 2024-2026"
        rows = []
        for (a, b) in PAIRS:
            d = frame(a, b, long)
            for W, zi, zo, mb in itertools.product(Ws, (2.0, 2.5, 3.0), (0.0, 0.5), holds):
                df = run(d, a, b, W, zi, zo, mb, split)
                if len(df) < 20:
                    continue
                m1, m2 = st(df[df.mitad == 1]), st(df[df.mitad == 2])
                if not m1 or not m2:
                    continue
                corr = float(np.corrcoef(df.pb, df.mercado)[0, 1]) if df.mercado.std() > 0 else 0
                rows.append(dict(par=f"{a}/{b}", ventana=W, entrada_z=zi, salida_z=zo, max_velas=mb, total=st(df), mitad1=m1, mitad2=m2,
                                 corr_con_mercado=round(corr, 2), velas_mediana=float(df.velas.median())))
        both = [r for r in rows if r["mitad1"]["pb"] > 0 and r["mitad2"]["pb"] > 0]
        chosen = [r for r in rows if r["mitad1"]["t"] >= 2 and r["mitad1"]["pb"] > 0]
        surv = [r for r in chosen if r["mitad2"]["pb"] > 0]
        out[name] = dict(versiones=len(rows), positivas_ambas_mitades=len(both), elegidas_mitad1_t2=len(chosen), sobreviven=len(surv),
                         sobrevivientes=sorted(surv, key=lambda r: -min(r["mitad1"]["t"], r["mitad2"]["t"])),
                         mejores_ambas=sorted(both, key=lambda r: -min(r["mitad1"]["t"], r["mitad2"]["t"]))[:8])
        print(f"== {name}: versiones {len(rows)} | positivas en ambas mitades {len(both)} | elegidas (t>=2 mitad 1) {len(chosen)} | sobreviven {len(surv)}")
        for r in out[name]["mejores_ambas"]:
            print("   ", r["par"], "W", r["ventana"], "z", r["entrada_z"], "->", r["salida_z"], "max", r["max_velas"], "| total", r["total"],
                  "| m1", r["mitad1"], "| m2", r["mitad2"], "| corr mercado", r["corr_con_mercado"], "| velas", r["velas_mediana"])
    json.dump(out, open("results/pairs.json", "w"), indent=1, default=str, ensure_ascii=False)


if __name__ == "__main__":
    main()

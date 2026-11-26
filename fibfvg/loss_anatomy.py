"""Anatomía de las pérdidas: ¿qué separa a las operaciones ganadoras de las que tocan el stop?  ¿Es el TIEMPO?

Hipótesis del usuario (26 nov 2026): "las operaciones en ganancia no son diferentes a las de stop salvo por el tiempo;
el precio es solo el eje Y".  Se prueba en tres muestras:
  1. Prop24 (bot de 24 horas, 5 mercados, jul 2024 - nov 2026, 130 operaciones) con el recorrido hora por hora (H1).
  2. Bot de posiciones (holding, salida chandelier y anual, 2006-2026, velas diarias) con el recorrido día por día.
  3. Alta frecuencia (oro y BTC, 5 min, 2024-2026): miles de operaciones, para tener fuerza estadística en el factor tiempo.
Para cada operación:
  ENTRADA (se conoce al entrar): hora NY, sesión, día de la semana, tipo de señal, dirección vs sesgo semanal/mensual,
    tamaño del stop en ATR, volatilidad del día (percentil), liquidez: distancia al máximo/mínimo del día anterior y de la
    semana anterior (en R) del lado del objetivo y del lado del stop, si ya se barrió la liquidez del día anterior antes
    de entrar y cuántas horas antes, posición de la entrada dentro del rango del día anterior.
  RECORRIDO (se conoce después): horas abierta, máxima ganancia flotante (MFE) y máxima pérdida flotante (MAE) en R y la
    hora en que ocurren, horas hasta +0.5R, resultado flotante al cierre de cada hora 1..24.
Análisis:
  a) comunes   : rasgos que comparten la mayoría de las pérdidas
  b) opuestos  : rasgos donde ganadoras y perdedoras difieren (prueba de permutación, p)
  c) cruces    : hora de entrada x horas abierta; sesión x liquidez; liquidez x tiempo de entrada
  d) incidentes: días con varias pérdidas a la vez, rachas
  e) disidentes: pérdidas que estuvieron a +0.7R o más antes del stop; ganadoras que estuvieron a -0.7R o peor
  f) el tiempo como regla: "si a la hora k la operación no va a favor, cerrarla" (se mide en ambas mitades, t)
    python -m fibfvg.loss_anatomy -> results/loss_anatomy.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import net_r, htf_bias, atr
from .levels import load_sym

NY = "America/New_York"
SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
RNG = np.random.default_rng(7)


def session(h):
    return "Asia (18-02)" if h >= 18 or h < 2 else "Londres (02-08)" if h < 8 else "NY mañana (08-12)" if h < 12 else "NY tarde (12-18)"


def perm_p(a, b, n=4000):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5:
        return None
    obs = abs(a.mean() - b.mean()); allv = np.concatenate([a, b]); k = len(a); c = 0
    for _ in range(n):
        RNG.shuffle(allv); c += abs(allv[:k].mean() - allv[k:].mean()) >= obs
    return round((c + 1) / (n + 1), 4)


def tstat(r):
    r = np.asarray(r, float)
    return round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2) if len(r) > 2 and r.std() > 0 else None


def group(df, col, order=None):
    out = []
    for k, g in df.groupby(col, observed=True):
        out.append(dict(grupo=str(k), n=len(g), aciertos=round(float((g.R > 0).mean() * 100)), R=round(float(g.R.mean()), 2), t=tstat(g.R)))
    if order:
        out.sort(key=lambda x: order.index(x["grupo"]) if x["grupo"] in order else 99)
    return out


# ------------------------------------------------------------------ 1. Prop24 con recorrido H1
def prop24_rows():
    from .prop24 import build
    a, b = build()
    data = {s: load_sym(s) for s in SYMBOLS}
    ctx = {}
    for s, (d, h) in data.items():
        bias = htf_bias(d)
        da = atr(d, 14); pct = da.rolling(250, min_periods=60).rank(pct=True)
        ha = atr(h, 14)
        dny = h.copy(); dny.index = dny.index.tz_convert(NY)
        key = (dny.index - pd.Timedelta(hours=18)).normalize()          # día de trading NY (abre 18:00)
        day = dny.groupby(key).agg(High=("High", "max"), Low=("Low", "min"))
        wk = d.resample("W-FRI").agg({"High": "max", "Low": "min"})
        ctx[s] = (d, h, bias, da, pct, ha, day, wk)
    rows = []
    for t in [(x, "A diaria") for x in a] + [(x, "B 4 horas") for x in b]:
        tr, kind = t
        d, h, bias, da, pct, ha, day, wk = ctx[tr.symbol]
        risk = abs(tr.entry - tr.stop)
        et = tr.entry_time; xt = tr.exit_time
        path = h[(h.index >= et) & (h.index <= xt)]
        if len(path) == 0 or risk <= 0:
            continue
        dr = tr.direction
        fav = ((path.High - tr.entry) if dr > 0 else (tr.entry - path.Low)) / risk
        adv = ((path.Low - tr.entry) if dr > 0 else (tr.entry - path.High)) / risk
        clo = (path.Close - tr.entry) * dr / risk
        hrs = (path.index - et) / pd.Timedelta(hours=1)
        ent_ny = et.tz_convert(NY)
        dkey = (ent_ny - pd.Timedelta(hours=18)).normalize()
        prev = day[day.index < dkey]
        pH, pL = (prev.High.iloc[-1], prev.Low.iloc[-1]) if len(prev) else (np.nan, np.nan)
        w = wk[wk.index < et.normalize()]
        wH, wL = (w.High.iloc[-1], w.Low.iloc[-1]) if len(w) else (np.nan, np.nan)
        # ¿se barrió la liquidez del día anterior hoy antes de entrar?
        hny = h.copy(); hny.index = hny.index.tz_convert(NY)
        today = hny[(hny.index >= dkey + pd.Timedelta(hours=18)) & (hny.index < ent_ny)]
        took_hi = today.index[today.High > pH] if len(today) else []
        took_lo = today.index[today.Low < pL] if len(today) else []
        swept_target = took_hi if dr > 0 else took_lo                      # la liquidez del lado del objetivo
        swept_stop = took_lo if dr > 0 else took_hi                        # la liquidez del lado del stop (barrido a favor)
        bi = bias[bias.index <= et]
        wb, mb = (bi.w.iloc[-1], bi.m.iloc[-1]) if len(bi) else (0, 0)
        a_h = ha[ha.index <= et]; a_d = pct[pct.index <= et]
        to_target_liq = ((pH - tr.entry) if dr > 0 else (tr.entry - pL)) / risk
        to_stop_liq = ((tr.entry - pL) if dr > 0 else (pH - tr.entry)) / risk
        R = net_r(tr)
        hit05 = hrs[fav.values >= 0.5]
        k_unreal = {k: float(clo[hrs <= k].iloc[-1]) if (hrs <= k).any() and (xt - et) / pd.Timedelta(hours=1) > k else None for k in range(1, 25)}
        rows.append(dict(
            mercado=tr.symbol, tipo=kind, entrada=str(et), mitad="1" if et < SPLIT else "2", R=R, gana=R > 0,
            hora=ent_ny.hour, sesion=session(ent_ny.hour), dia=["lun", "mar", "mié", "jue", "vie", "sáb", "dom"][ent_ny.dayofweek],
            direccion="compra" if dr > 0 else "venta", con_semanal=bool(wb == dr), con_mensual=bool(mb == dr),
            stop_atr_h1=float(risk / a_h.iloc[-1]) if len(a_h) and a_h.iloc[-1] > 0 else np.nan,
            vol_pct=float(a_d.iloc[-1]) if len(a_d) else np.nan,
            liq_objetivo_R=float(to_target_liq), liq_stop_R=float(to_stop_liq),
            pos_rango_ayer=float(((tr.entry - pL) / (pH - pL)) if dr > 0 else ((pH - tr.entry) / (pH - pL))) if pH > pL else np.nan,
            liq_semana_obj_R=float(((wH - tr.entry) if dr > 0 else (tr.entry - wL)) / risk),
            barrio_lado_stop=bool(len(swept_stop) > 0), barrio_lado_objetivo=bool(len(swept_target) > 0),
            horas_desde_barrido=float((ent_ny - swept_stop[-1]) / pd.Timedelta(hours=1)) if len(swept_stop) else np.nan,
            horas_abierta=float((xt - et) / pd.Timedelta(hours=1)), mfe=float(fav.max()), mae=float(adv.min()),
            hora_mfe=float(hrs[int(np.argmax(fav.values))]), hora_mae=float(hrs[int(np.argmin(adv.values))]),
            horas_a_05R=float(hit05[0]) if len(hit05) else np.nan, flotante=k_unreal, stop_px=tr.stop, entry_px=tr.entry,
        ))
    return pd.DataFrame(rows)


def time_rule(df, k, thr):
    """cerrar al cierre de la hora k si el flotante < thr; el resto igual.  Devuelve R nuevos."""
    out = []
    for _, r in df.iterrows():
        u = r.flotante.get(k)
        if u is not None and u < thr:
            out.append(u - SYMBOLS[r.mercado].spread / abs(r.entry_px - r.stop_px))
        else:
            out.append(r.R)
    return np.array(out)


def analyse(df, unit="horas"):
    W, L = df[df.gana], df[~df.gana]
    num = ["stop_atr_h1", "vol_pct", "liq_objetivo_R", "liq_stop_R", "pos_rango_ayer", "liq_semana_obj_R", "horas_desde_barrido", "hora",
           "horas_abierta", "mfe", "mae", "hora_mfe", "hora_mae", "horas_a_05R"]
    known = {"stop_atr_h1", "vol_pct", "liq_objetivo_R", "liq_stop_R", "pos_rango_ayer", "liq_semana_obj_R", "horas_desde_barrido", "hora"}
    comp = []
    for c in num:
        if c not in df:
            continue
        comp.append(dict(rasgo=c, se_conoce_al_entrar=c in known, ganadoras=round(float(W[c].median()), 2), perdedoras=round(float(L[c].median()), 2),
                         p=perm_p(W[c], L[c])))
    cat = ["sesion", "dia", "tipo", "direccion", "con_semanal", "con_mensual", "barrio_lado_stop", "barrio_lado_objetivo", "mercado"]
    shares = []
    for c in cat:
        if c not in df:
            continue
        for v in df[c].unique():
            sw, sl = float((W[c] == v).mean()), float((L[c] == v).mean())
            g = df[df[c] == v]
            shares.append(dict(rasgo=f"{c} = {v}", en_perdedoras=round(sl * 100), en_ganadoras=round(sw * 100), n=len(g),
                               R=round(float(g.R.mean()), 2), aciertos=round(float(g.gana.mean() * 100)),
                               p=perm_p(df.R[df[c] == v], df.R[df[c] != v], 2000)))
    common = sorted([s for s in shares if s["en_perdedoras"] >= 55], key=lambda s: -s["en_perdedoras"])
    opposite = sorted([s for s in shares if s["n"] >= 10], key=lambda s: -abs(s["en_perdedoras"] - s["en_ganadoras"]))[:12]
    return dict(n=len(df), ganadoras=len(W), perdedoras=len(L), R=round(float(df.R.mean()), 3), t=tstat(df.R),
                numericos=comp, comunes_en_perdidas=common, opuestos=opposite)


def prop24():
    df = prop24_rows()
    out = dict(resumen=analyse(df))
    # cruces
    df["horas_abierta_g"] = pd.cut(df.horas_abierta, [-0.1, 2, 6, 12, 18, 30], labels=["0-2 h", "2-6 h", "6-12 h", "12-18 h", "18-24 h"])
    df["liq_obj_g"] = pd.cut(df.liq_objetivo_R, [-99, 0, 0.5, 1, 2, 99], labels=["ya pasó", "<0.5R", "0.5-1R", "1-2R", ">2R"])
    df["liq_stop_g"] = pd.cut(df.liq_stop_R, [-99, 0, 1, 2, 99], labels=["stop más allá", "0-1R", "1-2R", ">2R"])
    cross = {}
    for a_, b_ in (("sesion", "horas_abierta_g"), ("sesion", "liq_obj_g"), ("liq_obj_g", "horas_abierta_g"), ("sesion", "barrio_lado_stop"),
                   ("tipo", "horas_abierta_g"), ("liq_stop_g", "horas_abierta_g")):
        tb = df.groupby([a_, b_], observed=True).R.agg(["count", "mean", lambda x: (x > 0).mean() * 100]).round(2)
        tb.columns = ["n", "R", "aciertos"]
        cross[f"{a_} x {b_}"] = [dict(a=str(i[0]), b=str(i[1]), **{k: float(v) for k, v in r.items()}) for i, r in tb.iterrows()]
    out["cruces"] = cross
    out["por_sesion"] = group(df, "sesion"); out["por_hora_abierta"] = group(df, "horas_abierta_g")
    out["por_liquidez_objetivo"] = group(df, "liq_obj_g"); out["por_dia"] = group(df, "dia", ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"])
    # el tiempo: ¿cuándo se decide cada operación?
    L = df[~df.gana]; W = df[df.gana]
    out["tiempo"] = dict(
        perdedoras_horas_al_stop=dict(mediana=float(L.horas_abierta.median()), p25=float(L.horas_abierta.quantile(.25)), p75=float(L.horas_abierta.quantile(.75))),
        ganadoras_horas_al_cierre=dict(mediana=float(W.horas_abierta.median()), p25=float(W.horas_abierta.quantile(.25)), p75=float(W.horas_abierta.quantile(.75))),
        ganadoras_horas_a_05R=float(W.horas_a_05R.median()), perdedoras_que_tocaron_05R=round(float(L.horas_a_05R.notna().mean() * 100)),
        perdedoras_hora_mfe=float(L.hora_mfe.median()), ganadoras_hora_mae=float(W.hora_mae.median()))
    curve = []
    for k in (1, 2, 3, 4, 6, 8, 12, 16, 20):
        u = df.flotante.apply(lambda f: f.get(k))
        alive = df[u.notna()]; uu = u[u.notna()]
        if len(alive) < 10:
            continue
        pos, neg = alive[uu > 0], alive[uu <= 0]
        curve.append(dict(hora=k, siguen_abiertas=len(alive), a_favor=len(pos), en_contra=len(neg),
                          R_final_si_a_favor=round(float(pos.R.mean()), 2) if len(pos) else None,
                          aciertos_si_a_favor=round(float((pos.R > 0).mean() * 100)) if len(pos) else None,
                          R_final_si_en_contra=round(float(neg.R.mean()), 2) if len(neg) else None,
                          aciertos_si_en_contra=round(float((neg.R > 0).mean() * 100)) if len(neg) else None))
    out["flotante_a_la_hora_k"] = curve
    rules = []
    base1, base2 = df.R[df.mitad == "1"], df.R[df.mitad == "2"]
    for k in (1, 2, 3, 4, 6, 8, 12):
        for thr in (-0.5, -0.25, 0.0, 0.25):
            nr = time_rule(df, k, thr)
            m1, m2 = nr[(df.mitad == "1").values], nr[(df.mitad == "2").values]
            rules.append(dict(regla=f"cerrar a la hora {k} si flotante < {thr:+.2f}R", R=round(float(nr.mean()), 3), t=tstat(nr),
                              mitad1=round(float(m1.mean()), 3), mitad2=round(float(m2.mean()), 3), cerradas=int((nr != df.R.values).sum())))
    out["reglas_de_tiempo"] = dict(base=dict(R=round(float(df.R.mean()), 3), t=tstat(df.R), mitad1=round(float(base1.mean()), 3), mitad2=round(float(base2.mean()), 3)),
                                   todas=sorted(rules, key=lambda r: -r["R"]))
    # incidentes y disidentes
    df["dia_ent"] = pd.to_datetime(df.entrada).dt.tz_convert(NY).dt.date
    days = df.groupby("dia_ent").agg(n=("R", "size"), perdidas=("gana", lambda x: int((~x).sum())), R=("R", "sum"))
    inc = days[days.perdidas >= 2].sort_values("R").reset_index()
    out["incidentes_dias_con_2+_perdidas"] = [dict(dia=str(r.dia_ent), operaciones=int(r.n), perdidas=int(r.perdidas), R=round(float(r.R), 2),
                                                   mercados=sorted(df[(df.dia_ent == r.dia_ent) & (~df.gana)].mercado.tolist())) for r in inc.itertuples()]
    s, mx = 0, 0
    for g in df.sort_values("entrada").gana:
        s = 0 if g else s + 1; mx = max(mx, s)
    out["peor_racha_perdidas"] = mx
    cols = ["mercado", "tipo", "entrada", "sesion", "R", "mfe", "mae", "horas_abierta", "hora_mfe", "liq_objetivo_R", "barrio_lado_stop"]
    out["disidentes_perdidas_que_estuvieron_a_+0.7R"] = df[(~df.gana) & (df.mfe >= 0.7)][cols].round(2).to_dict("records")
    out["disidentes_ganadoras_que_estuvieron_a_-0.7R"] = df[(df.gana) & (df.mae <= -0.7)][cols].round(2).to_dict("records")
    return out, df


# ------------------------------------------------------------------ 2. holding (diario, 20 años)
def holding():
    from .plans import position_engine
    from .longhold import load_long
    from .swaps import with_swaps
    res = {}
    for name, syms, mode in (("Oro + Plata chandelier (Billetera 2)", ["XAUUSD", "XAGUSD"], "P2 chandelier"),
                             ("S&P + Nasdaq + BTC anual", ["US500", "NAS100", "BTCUSD"], "Y1 year")):
        rows = []
        for s in syms:
            d = load_long(s)
            for t in with_swaps(position_engine(s, d, mode, start="2006-01-01")):
                risk = abs(t.entry - t.stop)
                p = d[(d.index >= t.entry_time.normalize()) & (d.index <= t.exit_time)]
                if len(p) == 0 or risk <= 0:
                    continue
                clo = (p.Close - t.entry) * t.direction / risk
                fav = ((p.High - t.entry) if t.direction > 0 else (t.entry - p.Low)) / risk
                days = (p.index - t.entry_time.normalize()).days
                hit = days[fav.values >= 0.5]
                rows.append(dict(R=net_r(t), dias=(t.exit_time - t.entry_time).days, mfe=float(fav.max()),
                                 dias_a_05R=float(hit[0]) if len(hit) else np.nan, mitad="1" if t.entry_time < pd.Timestamp("2016-01-01", tz="UTC") else "2",
                                 flot={k: float(clo[days <= k].iloc[-1]) for k in (1, 2, 3, 5, 10, 20) if (t.exit_time - t.entry_time).days > k and (days <= k).any()},
                                 sym=s, entry=t.entry, stop=t.stop))
        df = pd.DataFrame(rows)
        W, L = df[df.R > 0], df[df.R <= 0]
        curve = []
        for k in (1, 2, 3, 5, 10, 20):
            u = df.flot.apply(lambda f: f.get(k)); al = df[u.notna()]; uu = u[u.notna()]
            pos, neg = al[uu > 0], al[uu <= 0]
            curve.append(dict(dia=k, abiertas=len(al), R_si_a_favor=round(float(pos.R.mean()), 2) if len(pos) else None,
                              aciertos_si_a_favor=round(float((pos.R > 0).mean() * 100)) if len(pos) else None,
                              R_si_en_contra=round(float(neg.R.mean()), 2) if len(neg) else None,
                              aciertos_si_en_contra=round(float((neg.R > 0).mean() * 100)) if len(neg) else None, n_en_contra=len(neg)))
        rules = []
        for k in (1, 2, 3, 5, 10):
            for thr in (-0.5, -0.25, 0.0):
                nr = np.array([(r.flot[k] - SYMBOLS[r.sym].spread / abs(r.entry - r.stop)) if (k in r.flot and r.flot[k] < thr) else r.R for r in df.itertuples()])
                rules.append(dict(regla=f"cerrar el día {k} si flotante < {thr:+.2f}R", R=round(float(nr.mean()), 3), t=tstat(nr),
                                  mitad1=round(float(nr[(df.mitad == "1").values].mean()), 3), mitad2=round(float(nr[(df.mitad == "2").values].mean()), 3)))
        res[name] = dict(n=len(df), R=round(float(df.R.mean()), 3), t=tstat(df.R),
                         mitad1=round(float(df.R[df.mitad == "1"].mean()), 3), mitad2=round(float(df.R[df.mitad == "2"].mean()), 3),
                         perdedoras_dias=float(L.dias.median()), ganadoras_dias=float(W.dias.median()),
                         ganadoras_dias_a_05R=float(W.dias_a_05R.median()), perdedoras_que_tocaron_05R=round(float(L.dias_a_05R.notna().mean() * 100)),
                         flotante_al_dia_k=curve, reglas_de_tiempo=sorted(rules, key=lambda r: -r["R"])[:6])
    return res


# ------------------------------------------------------------------ 3. alta frecuencia (miles de operaciones)
def high_freq():
    from . import hf_research as hf
    res = {}
    for mk, (path, cost, wd) in hf.MARKETS.items():
        F = hf.features(hf.load(path, wd))
        O, H, L, atr5, T = F["O"], F["H"], F["L"], F["atr"], F["T"]
        hours = T.tz_convert(NY).hour
        for fam, p in (("ORB", dict(sesion=9.5, ventana=1.0)), ("BARRIDO", dict(horas="kz")), ("FLUJO", dict(z=1.5, con_tendencia=True))):
            s = hf.signals(F, fam, p)
            k, m, nb = 1.0, 2.0, 48
            recs, busy = [], -1
            for i in np.nonzero(s)[0]:
                if i <= busy or i + nb + 2 >= len(O) or np.isnan(atr5[i]) or atr5[i] <= 0:
                    continue
                dr = s[i]; e = O[i + 1]; st = k * atr5[i]
                stop = e - dr * st; tgt = e + dr * m * st
                res_r, bar, fl = None, nb, {}
                for j, t in enumerate(range(i + 1, i + 2 + nb)):
                    if (L[t] <= stop) if dr > 0 else (H[t] >= stop):
                        res_r, bar = -1.0, j; break
                    if (H[t] >= tgt) if dr > 0 else (L[t] <= tgt):
                        res_r, bar = m, j; break
                    fl[j + 1] = (F["C"][t] - e) * dr / st
                if res_r is None:
                    res_r = (O[i + 1 + nb] - e) * dr / st
                recs.append(dict(R=res_r - cost / st, velas=bar, hora=int(hours[i]), flot=fl, costo=cost / st, mitad="1" if T[i] < SPLIT.tz_convert(NY) else "2"))
                busy = i + 1 + bar
            df = pd.DataFrame(recs)
            W, Ls = df[df.R > 0], df[df.R <= 0]
            curve = []
            for kk in (1, 2, 3, 6, 12, 24):
                u = df.flot.apply(lambda f: f.get(kk)); al = df[u.notna()]; uu = u[u.notna()]
                pos, neg = al[uu > 0], al[uu <= 0]
                curve.append(dict(vela=kk, minutos=kk * 5, abiertas=len(al), R_si_a_favor=round(float(pos.R.mean()), 2),
                                  aciertos_si_a_favor=round(float((pos.R > 0).mean() * 100)), R_si_en_contra=round(float(neg.R.mean()), 2),
                                  aciertos_si_en_contra=round(float((neg.R > 0).mean() * 100))))
            rules = []
            for kk in (1, 2, 3, 6, 12):
                nr = np.array([(r.flot[kk] - r.costo) if (kk in r.flot and r.flot[kk] <= 0) else r.R for r in df.itertuples()])
                rules.append(dict(regla=f"cerrar a los {kk * 5} min si no va a favor", R=round(float(nr.mean()), 3), t=tstat(nr),
                                  mitad1=round(float(nr[(df.mitad == '1').values].mean()), 3), mitad2=round(float(nr[(df.mitad == '2').values].mean()), 3)))
            res[f"{mk} {fam}"] = dict(n=len(df), R=round(float(df.R.mean()), 3), t=tstat(df.R),
                                     perdedoras_minutos=float(Ls.velas.median() * 5), ganadoras_minutos=float(W.velas.median() * 5),
                                     flotante_a_la_vela_k=curve, reglas_de_tiempo=rules,
                                     por_hora=group(df.assign(h=df.hora.astype(str).str.zfill(2)), "h"))
    return res


def main():
    p, df = prop24()
    out = dict(prop24=p, holding=holding(), alta_frecuencia=high_freq())
    json.dump(out, open("results/loss_anatomy.json", "w"), indent=1, default=str, ensure_ascii=False)
    df.drop(columns=["flotante"]).to_csv("results/loss_anatomy_prop24_trades.csv", index=False)
    r = p["resumen"]
    print("PROP24", r["n"], "ops | gana", r["ganadoras"], "pierde", r["perdedoras"], "| R", r["R"], "t", r["t"])
    print("\n-- numéricos (mediana ganadoras / perdedoras, p)")
    for c in r["numericos"]:
        print(f"   {c['rasgo']:22s} {'ENTRADA' if c['se_conoce_al_entrar'] else 'después':8s} {c['ganadoras']:>8} {c['perdedoras']:>8}  p={c['p']}")
    print("\n-- comunes en pérdidas"); [print("  ", x) for x in r["comunes_en_perdidas"]]
    print("\n-- opuestos"); [print("  ", x) for x in r["opuestos"]]
    print("\n-- tiempo", p["tiempo"])
    print("\n-- flotante a la hora k"); [print("  ", x) for x in p["flotante_a_la_hora_k"]]
    print("\n-- reglas de tiempo base", p["reglas_de_tiempo"]["base"]); [print("  ", x) for x in p["reglas_de_tiempo"]["todas"][:8]]
    print("\n-- por sesión"); [print("  ", x) for x in p["por_sesion"]]
    print("-- por horas abierta"); [print("  ", x) for x in p["por_hora_abierta"]]
    print("-- por liquidez objetivo"); [print("  ", x) for x in p["por_liquidez_objetivo"]]
    print("-- por día"); [print("  ", x) for x in p["por_dia"]]
    for k, v in p["cruces"].items():
        print("-- cruce", k); [print("    ", x) for x in v]
    print("\n-- incidentes"); [print("  ", x) for x in p["incidentes_dias_con_2+_perdidas"]]
    print("peor racha", p["peor_racha_perdidas"])
    print("-- disidentes pérdidas a +0.7R"); [print("  ", x) for x in p["disidentes_perdidas_que_estuvieron_a_+0.7R"]]
    print("-- disidentes ganadoras a -0.7R"); [print("  ", x) for x in p["disidentes_ganadoras_que_estuvieron_a_-0.7R"]]
    for k, v in out["holding"].items():
        print("\nHOLDING", k, {x: y for x, y in v.items() if x not in ("flotante_al_dia_k", "reglas_de_tiempo")})
        [print("  ", x) for x in v["flotante_al_dia_k"]]; [print("  ", x) for x in v["reglas_de_tiempo"]]
    for k, v in out["alta_frecuencia"].items():
        print("\nHF", k, {x: y for x, y in v.items() if x not in ("flotante_a_la_vela_k", "reglas_de_tiempo", "por_hora")})
        [print("  ", x) for x in v["flotante_a_la_vela_k"]]; [print("  ", x) for x in v["reglas_de_tiempo"]]


if __name__ == "__main__":
    main()

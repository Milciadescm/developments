"""Two plans, both built on "cut losses short, let winners run".

PLAN 1 - Position (weekly to monthly holds)
  Entry exactly as the weekly engine: Monthly+Weekly bias, D1 Turtle 20-day
  breakout leg containing a daily FVG, limit at the 0.705 OTE, stop beyond
  the leg origin. Turtle adds every 0.5N (max 4 units).
  Exit styles (pre-registered, chosen on 2005-15, checked on 2016-26):
    P0 v1       : 50% at -0.272, rest at -0.618 or 20-day trail (the old plan)
    P1 run20    : no target; 20-day trail; breakeven at +1R
    P2 chandelier: no target; stop = highest high since entry - 3N; breakeven at +1R;
                  time stop: out after 10 days if the trade never reached +0.5R
    P3 monthly  : 50% at -0.272 then breakeven; runner trails the 55-day low
                  (about 11 weeks); same 10-day / +0.5R time stop

PLAN 2 - Micro (1m, 5m, 15m, 30m, 1H)
  Entry as the 4H micro engine: weekly bias, FVG + displacement candle
  (>= 0.8 ATR14), limit at 0.705 OTE capped at the FVG top, stop beyond the
  leg origin. Orders expire after 6 bars.
  Exit styles (chosen on the first half of each sample, checked on the second):
    M0 fixed    : target -0.618 extension, max 30 bars (the old plan)
    M1 run      : no target; breakeven at +1R, then trail the 3-bar low;
                  time stop: out after 6 bars if never +0.5R; max 120 bars
    M2 half-run : 50% at -0.272 then breakeven; rest trails the 3-bar low;
                  same time stop; max 120 bars
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FIB_EXT_1, FIB_EXT_2, FIB_OTE_MID, SYMBOLS
from .engines import Trade, _mirror, atr, htf_bias, load

POS_MODES = {
    "P0 v1": dict(tp1=True, tp2=True, trail="d20", be_at=None, time_stop=None),
    "P1 run20": dict(tp1=False, tp2=False, trail="d20", be_at=1.0, time_stop=None),
    "P2 chandelier": dict(tp1=False, tp2=False, trail="chand3", be_at=1.0, time_stop=(10, 0.5)),
    "P3 monthly": dict(tp1=True, tp2=False, trail="d55", be_at=None, time_stop=(10, 0.5)),
}
MICRO_MODES = {
    "M0 fixed": dict(tp=True, half=False, be_at=None, trail=None, time_stop=None, max_hold=30),
    "M1 run": dict(tp=False, half=False, be_at=1.0, trail=3, time_stop=(6, 0.5), max_hold=120),
    "M2 half-run": dict(tp=False, half=True, be_at=None, trail=3, time_stop=(6, 0.5), max_hold=120),
}
TFS = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1H": 60}


# ----------------------------------------------------------------- PLAN 1
def position_engine(symbol, daily, mode, start="2005-01-01", L=20, max_units=4):
    P = POS_MODES[mode]
    bias = htf_bias(daily)
    n_series = atr(daily, 20).values
    times = daily.index + pd.Timedelta(hours=12)
    i0 = max(L + 60, int(np.searchsorted(daily.index, pd.Timestamp(start, tz="UTC"))))
    trades = []
    for d in (1, -1):
        o, h, l, c = _mirror(daily.Open.values, daily.High.values, daily.Low.values, daily.Close.values, d)
        ok = (bias.w.values == d) & (bias.m.values == d)
        setup, pos = None, None
        for i in range(i0, len(c)):
            N = n_series[i - 1]
            if pos is not None:
                main = pos["main"]
                pos["hh"] = max(pos["hh"], h[i - 1]) if i - 1 >= pos["bar"] else pos["hh"]
                if P["trail"] == "d20":
                    trail = l[i - 20:i].min()
                elif P["trail"] == "d55":
                    trail = l[i - 55:i].min() if pos["tp1_done"] else -np.inf
                else:
                    trail = pos["hh"] - 3 * pos["N"]
                risk = pos["risk"]
                mfe = (pos["hh"] - main._entry_m) / risk
                be = (P["be_at"] is not None and mfe >= P["be_at"]) or (P["tp1"] and pos["tp1_done"])
                ts = P["time_stop"]
                time_out = ts is not None and (i - pos["bar"]) >= ts[0] and mfe < ts[1]
                closed = []
                for u in pos["units"]:
                    stop_lvl = max(u._stop_m, trail)
                    if u is main and be:
                        stop_lvl = max(stop_lvl, u._entry_m)
                    rem = 1.0 - sum(f for _, _, f in u.exits)
                    if l[i] <= stop_lvl:
                        u.exits.append((times[i], d * min(o[i], stop_lvl), rem)); closed.append(u); continue
                    if u is main and P["tp1"] and not pos["tp1_done"] and h[i] >= pos["tp1"]:
                        u.exits.append((times[i], d * max(o[i], pos["tp1"]), 0.5))
                        pos["tp1_done"] = True; rem -= 0.5
                    if P["tp2"] and h[i] >= pos["tp2"]:
                        u.exits.append((times[i], d * max(o[i], pos["tp2"]), rem)); closed.append(u); continue
                    if time_out:
                        u.exits.append((times[i], d * c[i], rem)); closed.append(u)
                if main in closed:   # one idea, one position: adds never outlive the first unit
                    xt, xp, _ = main.exits[-1]
                    for u in pos["units"]:
                        if u not in closed:
                            u.exits.append((xt, xp, 1.0 - sum(f for _, _, f in u.exits))); closed.append(u)
                pos["units"] = [u for u in pos["units"] if u not in closed]
                if pos["units"] and not time_out and pos["n"] < max_units:
                    nxt = pos["last_add"] + 0.5 * pos["N"]
                    if h[i] >= nxt and (not P["tp2"] or nxt < pos["tp2"]):
                        px = max(o[i], nxt)
                        t = Trade(symbol, "pos_add", d, times[i], d * px, d * (px - 2 * pos["N"]), pos_id=pos["id"])
                        t._entry_m, t._stop_m = px, px - 2 * pos["N"]
                        t.tf, t.bar, t.tp_final, t.tp1, t.fill_delay, t.setup_bar = "D1", i, None, None, 0, i
                        pos["units"].append(t); trades.append(t); pos["n"] += 1; pos["last_add"] = nxt
                if not pos["units"]:
                    pos = None
                continue
            if setup is not None:
                if i - setup["born"] > 15 or o[i] <= setup["stop"]:
                    setup = None
                elif l[i] <= setup["entry"]:
                    px = min(o[i], setup["entry"])
                    pid = f"P-{symbol}-{d}-{i}"
                    t = Trade(symbol, "position", d, times[i], d * px, d * setup["stop"], pos_id=pid)
                    t._entry_m, t._stop_m = px, setup["stop"]
                    t.tf, t.bar, t.tp_final, t.tp1 = "D1", i, d * setup["tp2"], d * setup["tp1"]
                    t.setup_bar, t.fill_delay, t.leg = setup["born"], i - setup["born"], setup["leg"]
                    trades.append(t)
                    if l[i] <= setup["stop"]:
                        t.exits.append((times[i], d * setup["stop"], 1.0))
                    else:
                        pos = dict(main=t, units=[t], tp1_done=False, tp1=setup["tp1"], tp2=setup["tp2"],
                                   last_add=px, N=N, n=1, id=pid, bar=i, hh=px, risk=px - setup["stop"])
                    setup = None
                    continue
            if not ok[i] or np.isnan(N) or N <= 0:
                continue
            if h[i] >= h[i - L:i].max():
                seg = l[i - L + 1:i + 1]
                j0 = i - L + 1 + int(np.argmin(seg))
                lo, hi = seg.min(), h[i]
                rng = hi - lo
                if rng < 1.5 * N or not any(l[j] > h[j - 2] for j in range(max(j0 + 2, 2), i + 1)):
                    continue
                setup = dict(entry=hi - FIB_OTE_MID * rng, stop=lo - 0.25 * N, born=i,
                             tp1=hi + FIB_EXT_1 * rng, tp2=hi + FIB_EXT_2 * rng,
                             leg=dict(lo=float(min(d * lo, d * hi)), hi=float(max(d * lo, d * hi)),
                                      frm=int(daily.index[j0].timestamp())))
    end = daily.index[-1] + pd.Timedelta(hours=12)
    for t in trades:
        rem = 1.0 - sum(f for _, _, f in t.exits)
        if rem > 1e-6:
            t.exits.append((end, float(daily.Close.iloc[-1]), rem))
    return trades


# ----------------------------------------------------------------- PLAN 2
def intraday_engine(symbol, bars, daily, tf, mode):
    P = MICRO_MODES[mode]
    mins = TFS[tf]
    b = htf_bias(daily)
    wb = b.w.copy(); wb.index = wb.index.normalize()
    bias = wb.reindex(bars.index.normalize(), method="ffill").fillna(0).values
    a = atr(bars, 14).values
    times = bars.index + pd.Timedelta(minutes=mins)
    trades = []
    for d in (1, -1):
        o, h, l, c = _mirror(bars.Open.values, bars.High.values, bars.Low.values, bars.Close.values, d)
        order, pos = None, None
        for i in range(20, len(c)):
            if pos is not None:
                t = pos["t"]; risk = pos["risk"]
                rem = 1.0 - sum(f for _, _, f in t.exits)
                pos["hh"] = max(pos["hh"], h[i - 1]) if i - 1 >= pos["bar"] else pos["hh"]
                mfe = (pos["hh"] - t._entry_m) / risk
                stop = t._stop_m
                if (P["be_at"] is not None and mfe >= P["be_at"]) or (P["half"] and pos["half_done"]):
                    stop = max(stop, t._entry_m)
                    if P["trail"]:
                        stop = max(stop, l[i - P["trail"]:i].min())
                if l[i] <= stop:
                    t.exits.append((times[i], d * min(o[i], stop), rem)); pos = None; continue
                if P["half"] and not pos["half_done"] and h[i] >= pos["tp1"]:
                    t.exits.append((times[i], d * max(o[i], pos["tp1"]), 0.5)); pos["half_done"] = True; rem -= 0.5
                if P["tp"] and h[i] >= pos["tp"]:
                    t.exits.append((times[i], d * max(o[i], pos["tp"]), rem)); pos = None; continue
                ts = P["time_stop"]
                held = i - pos["bar"]
                if (ts and held >= ts[0] and mfe < ts[1]) or held >= P["max_hold"]:
                    t.exits.append((times[i], d * c[i], rem)); pos = None
                continue
            if order is not None:
                if i - order["born"] > 6 or o[i] <= order["stop"]:
                    order = None
                elif l[i] <= order["entry"]:
                    px = min(o[i], order["entry"])
                    t = Trade(symbol, f"micro_{tf}", d, times[i] - pd.Timedelta(minutes=mins / 2), d * px, d * order["stop"])
                    t._entry_m, t._stop_m = px, order["stop"]
                    t.tf, t.bar, t.tp_final, t.tp1 = tf, i, d * order["tp"], d * order["tp1"]
                    t.setup_bar, t.fill_delay, t.leg = order["born"], i - order["born"], order["leg"]
                    trades.append(t)
                    if l[i] <= order["stop"]:
                        t.exits.append((times[i], d * order["stop"], 1.0))
                    else:
                        pos = dict(t=t, risk=px - order["stop"], bar=i, hh=px, half_done=False,
                                   tp=order["tp"] if P["tp"] else None, tp1=order["tp1"])
                    order = None
                    continue
            if bias[i] != d or np.isnan(a[i - 1]):
                continue
            if l[i] > h[i - 2] and (h[i - 1] - l[i - 1]) > 0.8 * a[i - 1] and c[i - 1] > o[i - 1]:
                lo, hi = l[i - 5:i].min(), h[i]
                rng = hi - lo
                entry = min(hi - FIB_OTE_MID * rng, l[i])
                stop = lo - 0.1 * a[i - 1]
                if entry - stop < 3 * SYMBOLS[symbol].spread:   # stop must be >= 3x spread or costs dominate
                    continue
                order = dict(entry=entry, stop=stop, born=i, tp=hi + FIB_EXT_2 * rng, tp1=hi + FIB_EXT_1 * rng,
                             leg=dict(lo=float(min(d * lo, d * hi)), hi=float(max(d * lo, d * hi)),
                                      frm=int(bars.index[i - 5].timestamp()),
                                      fvg_lo=float(min(d * h[i - 2], d * l[i])), fvg_hi=float(max(d * h[i - 2], d * l[i]))))
    end = times[-1]
    for t in trades:
        rem = 1.0 - sum(f for _, _, f in t.exits)
        if rem > 1e-6:
            t.exits.append((end, float(bars.Close.iloc[-1]), rem))
    return trades


def load_tf(symbol, tf):
    if tf == "1H":
        return load(f"data/{symbol}_H1.csv")
    return load(f"data/{symbol}_{tf}.csv")

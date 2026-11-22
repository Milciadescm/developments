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

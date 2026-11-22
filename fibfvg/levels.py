"""Plan 3 - Quarter levels x ICT kill zones x pyramiding (data 2024 -> now only).

Direction : weekly dealing-range bias (last completed week vs 4-week midpoint),
            built only from 2024+ daily bars.
Levels    : 00 / 20 / 50 / 60 / 80 of each market's big figure
            XAUUSD 100 (2400, 2420, 2450, 2460, 2480)   XAGUSD 1 (30.00, 30.20 ...)
            BTCUSD 10,000 (60k, 62k, 65k, 66k, 68k)     US500 100 (5000, 5020 ...)
            NAS100 1,000 (20000, 20200, 20500, 20600, 20800)
Time      : the reaction candle (1H, New York time) must start in a kill-zone hour:
            20:00, 00:00, 02:00, 06:00, 07:00, 09:00 (holds 9:30), 10:00, 15:00.
            Nothing during NY lunch (12:00-13:30).
Reaction  : long  - candle opens above a level, wicks to/through it, closes back above
            short - mirror. Entry at the next candle's open.
Risk      : stop = reaction wick extreme -/+ 0.1 ATR(14). Stop must be >= 3x spread.
            Cut losers: out after 8 candles if the trade never reached +0.5R.
Pyramid   : the open trade is the threshold. A new unit is added only on a fresh
            level reaction in a kill zone, in the same direction, while the first
            unit is at least +1R in profit. Each add has its own wick stop; every
            unit's stop is lifted to at least the first unit's entry. Max 5 units.
            When the first unit closes, the adds close with it.
Exits     : pre-registered, chosen on the first half of the sample, checked on the second
            X0 fixed3R  : each unit takes +3R (baseline, no running)
            X1 chand    : breakeven at +1R; from +2R trail highest high - 3 ATR(14)
            X2 daylow   : breakeven at +1R; from +2R trail the previous NY day's low
            X3 level    : breakeven at +1R; from +2R trail two quarter levels below the high
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import Trade, atr, htf_bias, load

UNIT = {"XAUUSD": 100.0, "XAGUSD": 1.0, "BTCUSD": 10_000.0, "US500": 100.0, "NAS100": 1_000.0}
FRACS = (0.0, 0.2, 0.5, 0.6, 0.8)
KZ_HOURS = {20, 0, 2, 6, 7, 9, 10, 15}
LUNCH = {12, 13}
EXITS = ("X0 fixed3R", "X1 chand", "X2 daylow", "X3 level")
# v2 (after the diagnostic): stop = 1 daily ATR, hold for days
V2 = {
    "D-day  · kill zones": dict(stop="datr", exit="X2 daylow", kz=True, ts=120),
    "D-week · kill zones": dict(stop="datr", exit="X4 weeklow", kz=True, ts=120),
    "D-day  · all hours": dict(stop="datr", exit="X2 daylow", kz=False, ts=120),
    "D-week · all hours": dict(stop="datr", exit="X4 weeklow", kz=False, ts=120),
}
START = pd.Timestamp("2024-01-01", tz="UTC")
FILES = {"XAUUSD": "XAUUSD", "XAGUSD": "XAGUSD", "BTCUSD": "BTCUSD", "US500": "US500F", "NAS100": "NAS100F"}


def levels_near(price, unit):
    base = np.floor(price / unit) * unit
    out = []
    for b in (base - unit, base, base + unit):
        out += [b + unit * f for f in FRACS]
    return np.array(sorted(out))


def level_name(L, unit):
    f = round((L / unit) % 1, 2)
    return {0.0: "00", 0.2: "20", 0.5: "50", 0.6: "60", 0.8: "80"}.get(f, "?")


def load_sym(s):
    d = load(f"data/{FILES[s]}_D1.csv")
    d = d[d.index >= START]
    h = load(f"data/{FILES[s]}_H1.csv")
    h = h[h.index >= START]
    return d, h


def engine(symbol, daily, h1, exit_mode, max_units=5, log=None, stop_mode="wick", kz=True, ts_bars=8):
    unit = UNIT[symbol]
    spread = SYMBOLS[symbol].spread
    b = htf_bias(daily)
    wb = b.w.copy(); wb.index = wb.index.normalize()
    ny = h1.index.tz_convert("America/New_York")
    bias = wb.reindex(h1.index.normalize(), method="ffill").fillna(0).values
    hours = ny.hour.values
    a = atr(h1, 14).values
    # previous NY-day low/high per bar
    nyday = ny.normalize()
    dl = h1.Low.groupby(nyday).min(); dh = h1.High.groupby(nyday).max()
    prev_low = pd.Series(dl.shift(1).reindex(nyday).values, index=h1.index).values
    prev_high = pd.Series(dh.shift(1).reindex(nyday).values, index=h1.index).values
    wk_low = pd.Series(dl.rolling(5).min().shift(1).reindex(nyday).values, index=h1.index).values
    wk_high = pd.Series(dh.rolling(5).max().shift(1).reindex(nyday).values, index=h1.index).values
    datr = atr(daily, 14).shift(1)
    datr.index = datr.index.normalize()
    datr_h = datr.reindex(h1.index.normalize(), method="ffill").values
    O, H, Lo, C = (h1[k].values for k in ("Open", "High", "Low", "Close"))
    times = h1.index
    trades = []
    for d in (1, -1):
        o, h, l, c = (O, H, Lo, C) if d == 1 else (-O, -Lo, -H, -C)
        pdl = prev_low if d == 1 else -prev_high
        pwl = wk_low if d == 1 else -wk_high
        units = []        # open units (Trade objects with ._e, ._s, ._r)
        hh = None
        first = None
        pending = None    # signal from bar i-1 -> enter at open of bar i
        for i in range(20, len(c)):
            # ---- enter pending signal at this bar's open
            if pending is not None:
                e = o[i]; s = pending["stop"]
                if e - s >= 3 * spread and e > s:
                    t = Trade(symbol, "levels", d, times[i], d * e, d * s)
                    t._e, t._s, t._r = e, s, e - s
                    t.tf, t.bar, t.setup_bar, t.fill_delay = "L1H", i, i - 1, 1
                    t.tp_final, t.tp1 = None, None
                    t.level, t.level_name, t.kz_hour = d * pending["L"], pending["name"], pending["hour"]
                    t.unit_no = len(units) + 1
                    t.leg = dict(lo=float(min(d * s, d * pending["L"])), hi=float(max(d * s, d * pending["L"])),
                                 frm=int(times[i - 1].timestamp()))
                    if first is None:
                        first = t; hh = h[i]
                        t.pos_id = f"L-{symbol}-{d}-{i}"
                    else:
                        t.pos_id = first.pos_id
                        t.engine = "levels_add"
                        for u in units:            # lift every stop to at least the first entry
                            u._s = max(u._s, first._e)
                        t._s = max(t._s, first._e) if first._e < e else t._s
                    units.append(t); trades.append(t)
                pending = None
            # ---- manage open units on bar i
            if units:
                hh = max(hh, h[i])
                mfe1 = (hh - first._e) / first._r
                trail = -np.inf
                if exit_mode != "X0 fixed3R" and mfe1 >= 2.0:
                    if exit_mode == "X1 chand":
                        trail = hh - 3 * a[i - 1]
                    elif exit_mode == "X2 daylow":
                        trail = pdl[i] if not np.isnan(pdl[i]) else -np.inf
                    elif exit_mode == "X4 weeklow":
                        trail = pwl[i] if not np.isnan(pwl[i]) else -np.inf
                    else:
                        lv = levels_near(hh, unit)
                        below = lv[lv < hh]
                        trail = below[-3] if len(below) >= 3 else -np.inf
                closed = []
                for u in units:
                    st = u._s
                    if exit_mode != "X0 fixed3R":
                        if (hh - u._e) / u._r >= 1.0 or (u is not first and mfe1 >= 1.0):
                            st = max(st, u._e if u is first else max(u._s, first._e))
                        st = max(st, trail)
                    if l[i] <= st:
                        u.exits.append((times[i], d * min(o[i], st), 1.0)); closed.append(u); continue
                    if exit_mode == "X0 fixed3R" and h[i] >= u._e + 3 * u._r:
                        u.exits.append((times[i], d * max(o[i], u._e + 3 * u._r), 1.0)); closed.append(u); continue
                # cut losers short: time stop on the first unit
                if first not in closed and (i - first.bar) >= ts_bars and mfe1 < 0.5:
                    for u in units:
                        if u not in closed:
                            u.exits.append((times[i], d * c[i], 1.0)); closed.append(u)
                if first in closed:      # adds never outlive the first unit
                    xt, xp, _ = first.exits[-1]
                    for u in units:
                        if u not in closed:
                            u.exits.append((xt, xp, 1.0)); closed.append(u)
                units = [u for u in units if u not in closed]
                if not units:
                    first = None; hh = None
            # ---- look for a reaction on bar i (signal for bar i+1)
            hr = hours[i]
            if (kz and hr not in KZ_HOURS) or hr in LUNCH or bias[i] != d or np.isnan(a[i]) or np.isnan(datr_h[i]):
                continue
            if units and (len(units) >= max_units or (hh - first._e) / first._r < 1.0):
                continue
            lv = levels_near(d * c[i], unit)
            lv = lv * d
            hit = [L for L in lv if l[i] <= L < o[i] and c[i] > L]
            if not hit:
                continue
            L = max(hit)
            stp = l[i] - 0.1 * a[i] if stop_mode == "wick" else c[i] - datr_h[i]
            pending = dict(stop=stp, L=L, name=level_name(d * L, unit), hour=int(hr))
            if log is not None:
                log.append(dict(t=str(times[i]), dir=d, level=d * L, name=pending["name"], hour=int(hr)))
    end = times[-1]
    for t in trades:
        if not t.exits:
            t.exits.append((end, float(h1.Close.iloc[-1]), 1.0))
    return trades

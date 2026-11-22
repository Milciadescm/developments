"""Signal engines. Each engine produces candidate trades (price-only; sizing is
done by the portfolio simulator so the same signals can be replayed at every
capital tier and risk level).

Shorts are handled by mirroring prices (o,h,l,c) -> (-o,-l,-h,-c), running the
long logic, and negating prices back. This guarantees long/short symmetry.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import (FIB_EXT_1, FIB_EXT_2, FIB_OTE_MID, EngineConfig)


@dataclass
class Trade:
    symbol: str
    engine: str            # "weekly" | "weekly_add" | "micro"
    direction: int         # +1 long, -1 short
    entry_time: pd.Timestamp
    entry: float
    stop: float            # initial stop (defines 1R and position size)
    exits: list = field(default_factory=list)   # [(time, price, fraction)]
    pos_id: str = ""

    @property
    def exit_time(self):
        return self.exits[-1][0]

    @property
    def r_multiple(self) -> float:
        risk = abs(self.entry - self.stop)
        pnl = sum(f * (p - self.entry) * self.direction for _, p, f in self.exits)
        return pnl / risk if risk > 0 else 0.0


# ----------------------------------------------------------------- helpers
def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df[["Open", "High", "Low", "Close"]].astype(float).dropna()
    df = df[(df.High >= df.Low) & (df.Low > 0)]
    return df[~df.index.duplicated()].sort_index()


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    pc = df.Close.shift(1)
    tr = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()   # Wilder smoothing (Turtle N)


def htf_bias(daily: pd.DataFrame) -> pd.DataFrame:
    """Monthly / Weekly / Daily bias using ONLY completed higher-timeframe bars.

    Weekly bias  = last completed week's close vs midpoint of the prior 4-week range
                   (premium/discount of the weekly dealing range).
    Monthly bias = last completed month's close vs midpoint of the prior 6-month range.
    Daily bias   = yesterday's close vs yesterday's midpoint (for the micro engine).
    """
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    w = daily.resample("W-FRI").agg(agg).dropna()
    m = daily.resample("ME").agg(agg).dropna()
    w_mid = (w.High.rolling(4).max() + w.Low.rolling(4).min()) / 2
    m_mid = (m.High.rolling(6).max() + m.Low.rolling(6).min()) / 2
    w_b = np.sign(w.Close - w_mid)
    m_b = np.sign(m.Close - m_mid)
    # a weekly bar labelled Friday is known after that Friday's close -> usable from next day
    w_b.index = w_b.index + pd.Timedelta(days=1)
    m_b.index = m_b.index + pd.Timedelta(days=1)
    out = pd.DataFrame(index=daily.index)
    out["w"] = w_b.reindex(out.index.union(w_b.index)).ffill().reindex(out.index)
    out["m"] = m_b.reindex(out.index.union(m_b.index)).ffill().reindex(out.index)
    d_mid = (daily.High + daily.Low) / 2
    out["d"] = np.sign(daily.Close - d_mid).shift(1)
    return out.fillna(0)


def _mirror(o, h, l, c, direction):
    if direction == 1:
        return o, h, l, c
    return -o, -l, -h, -c


# ----------------------------------------------------- weekly swing engine
def weekly_engine(symbol: str, daily: pd.DataFrame, cfg: EngineConfig, log: list | None = None) -> list[Trade]:
    """Monthly+Weekly bias -> Daily Turtle breakout defines the impulse leg ->
    limit order in the Fibonacci OTE zone (0.705) of that leg, only if the leg
    contains a daily FVG (displacement). Stop beyond the leg origin (1.0).
    TP1 = -0.272 extension (half off, stop to breakeven), TP2 = -0.618 extension.
    Runner + pyramid units trail on the Turtle 20-day opposite extreme.
    Turtle pyramiding: +1 unit every 0.5N, max 4 units, adds carry a 2N stop.
    """
    bias = htf_bias(daily)
    n_series = atr(daily, cfg.atr_len).values
    times = daily.index + pd.Timedelta(hours=12)
    start = np.searchsorted(daily.index, pd.Timestamp(cfg.weekly_trade_start, tz="UTC"))
    trades: list[Trade] = []

    for direction in (1, -1):
        o, h, l, c = _mirror(daily.Open.values, daily.High.values, daily.Low.values,
                             daily.Close.values, direction)
        ok_bias = ((bias.w.values == direction) & (bias.m.values == direction))
        setup = None
        pos = None   # dict(units=[Trade], tp1_done, tp1, tp2, last_add, be)
        L = cfg.breakout_len
        for i in range(max(L + 2, start), len(c)):
            N = n_series[i - 1]
            trail = l[i - cfg.exit_len:i].min()          # Turtle 20-day exit level

            # ---------------- manage open position on bar i
            if pos is not None:
                closed = []
                for u in pos["units"]:
                    stop_lvl = max(u._stop_m, trail)
                    if u is pos["units"][0] and pos["tp1_done"]:
                        stop_lvl = max(stop_lvl, u._entry_m)   # breakeven after TP1
                    rem = 1.0 - sum(f for _, _, f in u.exits)
                    if l[i] <= stop_lvl:                     # conservative: stop first
                        px = min(o[i], stop_lvl)
                        u.exits.append((times[i], direction * px, rem))
                        closed.append(u)
                        continue
                    if u is pos["units"][0] and not pos["tp1_done"] and h[i] >= pos["tp1"]:
                        u.exits.append((times[i], direction * max(o[i], pos["tp1"]), 0.5))
                        pos["tp1_done"] = True
                        rem -= 0.5
                    if h[i] >= pos["tp2"]:
                        u.exits.append((times[i], direction * max(o[i], pos["tp2"]), rem))
                        closed.append(u)
                pos["units"] = [u for u in pos["units"] if u not in closed]
                # Turtle pyramid adds
                if pos["units"] and pos["n_units"] < 4:
                    nxt = pos["last_add"] + cfg.pyramid_step_n * pos["N"]
                    if h[i] >= nxt and nxt < pos["tp2"]:
                        px = max(o[i], nxt)
                        t = Trade(symbol, "weekly_add", direction, times[i], direction * px,
                                  direction * (px - cfg.add_stop_n * pos["N"]), pos_id=pos["id"])
                        t._entry_m, t._stop_m = px, px - cfg.add_stop_n * pos["N"]
                        pos["units"].append(t)
                        trades.append(t)
                        pos["n_units"] += 1
                        pos["last_add"] = nxt
                if not pos["units"]:
                    pos = None
                continue

            # ---------------- try to fill pending OTE limit on bar i
            if setup is not None:
                if i - setup["born"] > cfg.setup_expiry_bars or o[i] <= setup["stop"]:
                    if log is not None:
                        log.append(dict(ev="cancel", eng="weekly", t=str(times[i]), dir=direction,
                                        why="expired" if o[i] > setup["stop"] else "gapped through stop"))
                    setup = None
                elif l[i] <= setup["entry"]:
                    px = min(o[i], setup["entry"])
                    pid = f"{symbol}-{direction}-{i}"
                    t = Trade(symbol, "weekly", direction, times[i], direction * px,
                              direction * setup["stop"], pos_id=pid)
                    t._entry_m, t._stop_m = px, setup["stop"]
                    t.bar, t.tf, t.tp_final = i, "D1", direction * setup["tp2"]
                    t.tp1 = direction * setup["tp1"]
                    t.setup_bar, t.fill_delay = setup["born"], i - setup["born"]
                    trades.append(t)
                    if l[i] <= setup["stop"]:        # same-bar stop-out (conservative)
                        t.exits.append((times[i], direction * setup["stop"], 1.0))
                    else:
                        pos = dict(units=[t], tp1_done=False, tp1=setup["tp1"], tp2=setup["tp2"],
                                   last_add=px, N=N, n_units=1, id=pid)
                    setup = None
                    continue

            # ---------------- create / extend setup at close of bar i
            if not ok_bias[i] or np.isnan(N) or N <= 0:
                continue
            if h[i] >= h[i - L:i].max():                 # Turtle 20-day breakout
                seg_l = l[i - L + 1:i + 1]
                j0 = i - L + 1 + int(np.argmin(seg_l))
                leg_low, leg_high = seg_l.min(), h[i]
                rng = leg_high - leg_low
                has_fvg = any(l[j] > h[j - 2] for j in range(max(j0 + 2, 2), i + 1))
                if not has_fvg or rng < 1.5 * N:
                    continue
                entry = leg_high - FIB_OTE_MID * rng
                stop = leg_low - 0.25 * N
                setup = dict(entry=entry, stop=stop, born=i,
                             tp1=leg_high + FIB_EXT_1 * rng, tp2=leg_high + FIB_EXT_2 * rng)
                if log is not None:
                    d_ = direction
                    log.append(dict(ev="setup", eng="weekly", t=str(times[i]), dir=d_,
                                    leg_from=str(times[j0]), leg_lo=d_ * leg_low, leg_hi=d_ * leg_high,
                                    entry=d_ * entry, stop=d_ * stop, tp1=d_ * setup["tp1"], tp2=d_ * setup["tp2"],
                                    N=float(N)))
    for t in trades:
        if not t.exits:   # still open at end of data -> mark at last close
            t.exits.append((daily.index[-1] + pd.Timedelta(hours=12), float(daily.Close.iloc[-1]), 1.0))
        elif sum(f for _, _, f in t.exits) < 0.999:
            t.exits.append((daily.index[-1] + pd.Timedelta(hours=12), float(daily.Close.iloc[-1]),
                            1.0 - sum(f for _, _, f in t.exits)))
    return trades


# ------------------------------------------------------- micro 4H engine
def to_4h(h1: pd.DataFrame) -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    return h1.resample("4h").agg(agg).dropna()


def micro_engine(symbol: str, h4: pd.DataFrame, daily: pd.DataFrame, cfg: EngineConfig, log: list | None = None) -> list[Trade]:
    """Weekly bias -> 4H FVG with a displacement candle -> limit in the OTE zone
    (0.705) of the displacement leg, capped at the FVG top. Stop beyond the leg
    origin. TP = -0.618 Fibonacci extension of the leg. Min 1.0R.
    (Variant chosen from a small grid on data before 2025-06; see README.)"""
    b = htf_bias(daily)
    # bias known at start of each day -> map onto 4H bars
    bias_d = b.w.copy()   # weekly dealing-range bias (daily-only bias tested negative)
    bias_d.index = bias_d.index.normalize()
    day = h4.index.normalize()
    dbias = bias_d.reindex(day, method="ffill").fillna(0).values
    a4 = atr(h4, 14).values
    times = h4.index + pd.Timedelta(hours=4)    # bar close time
    trades: list[Trade] = []
    for direction in (1, -1):
        o, h, l, c = _mirror(h4.Open.values, h4.High.values, h4.Low.values, h4.Close.values, direction)
        order = None
        pos = None
        for i in range(20, len(c)):
            if pos is not None:
                t, tp, born = pos
                if l[i] <= t._stop_m:
                    t.exits.append((times[i], direction * min(o[i], t._stop_m), 1.0)); pos = None
                elif h[i] >= tp:
                    t.exits.append((times[i], direction * max(o[i], tp), 1.0)); pos = None
                elif i - born >= cfg.micro_max_hold_bars:
                    t.exits.append((times[i], direction * c[i], 1.0)); pos = None
                continue
            if order is not None:
                if i - order["born"] > cfg.micro_expiry_bars or o[i] <= order["stop"] or h[i] >= order["tp"]:
                    if log is not None:
                        log.append(dict(ev="cancel", eng="micro", t=str(times[i]), dir=direction,
                                        why="expired" if i - order["born"] > cfg.micro_expiry_bars else
                                        ("gapped through stop" if o[i] <= order["stop"] else "target hit before fill")))
                    order = None
                elif l[i] <= order["entry"]:
                    px = min(o[i], order["entry"])
                    t = Trade(symbol, "micro", direction, times[i] - pd.Timedelta(hours=2),
                              direction * px, direction * order["stop"])
                    t._entry_m, t._stop_m = px, order["stop"]
                    t.bar, t.tf, t.tp_final = i, "H4", direction * order["tp"]
                    t.tp1 = None
                    t.setup_bar, t.fill_delay = order["born"], i - order["born"]
                    trades.append(t)
                    if l[i] <= order["stop"]:
                        t.exits.append((times[i], direction * order["stop"], 1.0))
                    else:
                        pos = (t, order["tp"], i)
                    order = None
                    continue
            # new FVG on the just-closed bar i
            if dbias[i] != direction or np.isnan(a4[i - 1]):
                continue
            disp = (h[i - 1] - l[i - 1]) > cfg.micro_disp_atr * a4[i - 1] and c[i - 1] > o[i - 1]
            if l[i] > h[i - 2] and disp:
                leg_low = l[i - 5:i].min()
                leg_high = h[i]
                # OTE 0.705 of the displacement leg, never above the FVG top
                entry = min(leg_high - FIB_OTE_MID * (leg_high - leg_low), l[i])
                stop = leg_low - 0.1 * a4[i - 1]
                tp = leg_high + FIB_EXT_2 * (leg_high - leg_low)
                if entry - stop > 0 and (tp - entry) / (entry - stop) >= cfg.micro_min_rr:
                    order = dict(entry=entry, stop=stop, tp=tp, born=i)
                    if log is not None:
                        d_ = direction
                        log.append(dict(ev="setup", eng="micro", t=str(times[i]), dir=d_,
                                        leg_from=str(times[i - 5]), leg_lo=d_ * leg_low, leg_hi=d_ * leg_high,
                                        fvg_lo=d_ * (h[i - 2] if d_ == 1 else l[i]), fvg_hi=d_ * (l[i] if d_ == 1 else h[i - 2]),
                                        entry=d_ * entry, stop=d_ * stop, tp2=d_ * tp))
    for t in trades:
        if not t.exits:
            t.exits.append((h4.index[-1], float(h4.Close.iloc[-1]), 1.0))
    return trades

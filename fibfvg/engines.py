"""Shared building blocks: Trade record, data loading, ATR, higher-timeframe bias.
(Engines live in plans.py and levels.py.) Each engine produces candidate trades (price-only; sizing is
done by the portfolio simulator so the same signals can be replayed at every
capital tier and risk level).

Shorts are handled by mirroring prices (o,h,l,c) -> (-o,-l,-h,-c), running the
long logic, and negating prices back. This guarantees long/short symmetry.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd



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


def net_r(t: Trade) -> float:
    """R multiple after the round-trip spread in fibfvg.config.SYMBOLS."""
    from .config import SYMBOLS
    return t.r_multiple - SYMBOLS[t.symbol].spread / abs(t.entry - t.stop)

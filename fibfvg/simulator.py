"""Portfolio simulator: replays candidate trades in time order against a real
account balance, applying position sizing, broker lot constraints, Turtle
portfolio caps, open-risk caps and (optionally) prop-firm loss limits."""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import SYMBOLS, RiskConfig


@dataclass
class Fill:
    symbol: str
    engine: str
    direction: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry: float
    stop: float
    lots: float
    risk_usd: float
    pnl_usd: float
    r_multiple: float
    equity_before: float


def size_lots(spec, risk_usd, stop_dist):
    raw = risk_usd / (stop_dist * spec.contract)
    lots = math.floor(raw / spec.lot_step + 1e-9) * spec.lot_step
    return min(round(lots, 2), spec.max_lot)


def simulate(trades, capital: float, risk: RiskConfig, record=True):
    trades = sorted(trades, key=lambda t: t.entry_time)
    balance = capital
    peak = capital
    day_start_bal, cur_day = capital, None
    open_pos = {}          # id(trade) -> dict
    events = []            # heap of (time, seq, kind, payload)
    seq = 0
    for t in trades:
        heapq.heappush(events, (t.entry_time, 0, seq, "entry", t)); seq += 1
    fills: list[Fill] = []
    skipped = {"min_lot": 0, "caps": 0, "halted": 0}
    curve = [(trades[0].entry_time if trades else None, capital)]
    halted = False
    breach = None
    max_dd = 0.0

    def open_risk():
        return sum(p["risk_open"] for p in open_pos.values())

    while events:
        tm, pri, _, kind, payload = heapq.heappop(events)
        d = tm.normalize()
        if d != cur_day:
            cur_day, day_start_bal = d, balance
        if kind == "entry":
            t = payload
            spec = SYMBOLS[t.symbol]
            if halted:
                skipped["halted"] += 1; continue
            unit_r = risk.micro_risk if t.engine == "micro" else risk.weekly_unit_risk
            stop_dist = abs(t.entry - t.stop)
            if stop_dist <= 0:
                continue
            # Turtle caps (weekly engine units) + total open-risk cap
            if t.engine != "micro":
                sym_units = sum(1 for p in open_pos.values() if p["t"].symbol == t.symbol and p["t"].engine != "micro")
                grp_units = sum(1 for p in open_pos.values() if SYMBOLS[p["t"].symbol].group == spec.group and p["t"].engine != "micro")
                if sym_units >= risk.max_units_per_symbol or grp_units >= risk.max_units_per_group:
                    skipped["caps"] += 1; continue
            if t.engine == "weekly_add" and not any(p["t"].pos_id == t.pos_id for p in open_pos.values()):
                continue   # parent position was never taken -> no add
            risk_usd = balance * unit_r
            lots = size_lots(spec, risk_usd, stop_dist)
            if lots < spec.min_lot:
                if risk.skip_if_below_min_lot:
                    skipped["min_lot"] += 1; continue
                lots = spec.min_lot
            real_risk = lots * stop_dist * spec.contract
            if (open_risk() + real_risk) > risk.max_open_risk * balance:
                skipped["caps"] += 1; continue
            cost = spec.spread * lots * spec.contract
            balance -= cost
            open_pos[id(t)] = dict(t=t, lots=lots, risk_open=real_risk, risk0=real_risk, eq0=balance + cost, cost=cost, pnl=-cost)
            for (xt, px, fr) in t.exits:
                heapq.heappush(events, (xt, 1, seq, "exit", (id(t), px, fr))); seq += 1
        else:
            key, px, fr = payload
            p = open_pos.get(key)
            if p is None:
                continue
            t = p["t"]
            spec = SYMBOLS[t.symbol]
            pnl = (px - t.entry) * t.direction * p["lots"] * spec.contract * fr
            balance += pnl
            p["pnl"] += pnl
            p["filled"] = p.get("filled", 0) + fr
            p["risk_open"] = p["risk0"] * max(0.0, 1 - p["filled"])
            if p["filled"] >= 0.999:
                del open_pos[key]
                if record:
                    fills.append(Fill(t.symbol, t.engine, t.direction, t.entry_time, tm, t.entry, t.stop,
                                      p["lots"], p["lots"] * abs(t.entry - t.stop) * spec.contract,
                                      p["pnl"], t.r_multiple, p["eq0"]))
            peak = max(peak, balance)
            # conservative equity = balance minus all open risk (if every stop is hit)
            max_dd = max(max_dd, (peak - balance) / peak)
            curve.append((tm, balance))
            if risk.max_loss_limit is not None and not halted:
                ref = peak if risk.trailing_max_loss else capital
                floor = ref - risk.max_loss_limit * capital
                if balance <= floor:
                    halted, breach = True, f"max loss breached {tm.date()}"
            if risk.daily_loss_limit is not None and not halted:
                if day_start_bal - balance >= risk.daily_loss_limit * capital:
                    halted, breach = True, f"daily loss breached {tm.date()}"
            if balance <= 0:
                halted, breach = True, f"account blown {tm.date()}"
                balance = 0.0
    return dict(final=balance, fills=fills, skipped=skipped, max_dd=max_dd,
                curve=curve, breach=breach)


def stats(res, capital):
    f = res["fills"]
    if not f:
        return dict(trades=0, final=res["final"], ret_pct=0, cagr_pct=0, years=0, win_rate=0, pf=0, avg_r=0,
                    max_dd=res["max_dd"], **res["skipped"], breach=res["breach"])
    pnl = np.array([x.pnl_usd for x in f])
    wins, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    t0, t1 = f[0].entry_time, max(x.exit_time for x in f)
    yrs = max((t1 - t0).days / 365.25, 1e-9)
    final = res["final"]
    cagr = (final / capital) ** (1 / yrs) - 1 if final > 0 else -1
    return dict(trades=len(f), final=round(final, 2), ret_pct=round((final / capital - 1) * 100, 1),
                cagr_pct=round(cagr * 100, 1), years=round(yrs, 1),
                win_rate=round((pnl > 0).mean() * 100, 1),
                pf=round(wins / losses, 2) if losses > 0 else float("inf"),
                avg_r=round(np.mean([x.r_multiple for x in f]), 3),
                max_dd=round(res["max_dd"] * 100, 1), **res["skipped"], breach=res["breach"])

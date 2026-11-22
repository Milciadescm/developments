"""Prop-firm vs real-money simulator (2024 -> now).

Account rules come from the user's screenshots (Nov 2026):
  FundedNext Stellar Instant : $2K $59.99 | $5K $149.99 | $10K $299.99 | $20K $599.99
                               no profit target, no daily loss limit, 6% TRAILING max loss,
                               no consistency rule, no minimum days. Profit split not shown -> 80% assumed.
  Instant Premium (2nd firm) : $15K $240 | $25K $332 | $50K $465 | $100K $740 (50% promo prices)
                               no profit target, 3% daily loss, 6% max loss (type not shown -> trailing
                               assumed, the stricter case), 80% split, bi-weekly rewards, fee 100% refundable
                               (refund assumed with the first reward).

Bot protection ("never burn the account"):
  dd_budget    : a new trade is refused if  drawdown-from-peak + open stop-risk + new stop-risk
                 would exceed the budget (5% for a 6% limit). If every open stop is hit at once the
                 account still sits above the firm's line. Only gaps/slippage beyond the stop can breach.
  daily_budget : same check against today's starting balance (2.5% for a 3% daily limit).
  payouts      : every 14 days, profit above the starting balance is withdrawn; the trader keeps the
                 split, balance and trailing peak go back to the starting balance.

EDGE GATE (the coded "edge found" rule, recomputed after every closed position):
  EDGE_CONFIRMED : last 20 closed positions  sum net R >= +3  and  profit factor >= 1.3
                   and drawdown from peak <= 2%                     -> NORMAL risk
  STRONG_EDGE    : last 40 closed positions  sum net R >= +8  and  profit factor >= 1.5
                   and drawdown from peak <= 1.5%                   -> AGGRESSIVE risk
  otherwise, or drawdown from peak >= 3%                            -> CONSERVATIVE risk
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import SYMBOLS

MODES = {
    "Conservative": dict(p1=0.0015, p3=0.0005),
    "Normal": dict(p1=0.0025, p3=0.0010),
    "Aggressive": dict(p1=0.0050, p3=0.0025),
}


@dataclass
class Account:
    firm: str
    size: float
    fee: float
    daily: float | None      # firm daily loss limit (fraction of start)
    max_loss: float | None   # firm max loss (fraction of start)
    trailing: bool = True
    split: float = 0.80
    refundable: bool = False
    payout_days: int | None = 14
    real: bool = False

    @property
    def name(self):
        return f"{self.firm} ${self.size / 1000:g}K" if not self.real else f"Real money ${self.size:,.0f}"


PROP_ACCOUNTS = [
    Account("FundedNext Stellar Instant", 2_000, 59.99, None, 0.06),
    Account("FundedNext Stellar Instant", 5_000, 149.99, None, 0.06),
    Account("FundedNext Stellar Instant", 10_000, 299.99, None, 0.06),
    Account("FundedNext Stellar Instant", 20_000, 599.99, None, 0.06),
    Account("Instant Premium", 15_000, 240, 0.03, 0.06, refundable=True),
    Account("Instant Premium", 25_000, 332, 0.03, 0.06, refundable=True),
    Account("Instant Premium", 50_000, 465, 0.03, 0.06, refundable=True),
    Account("Instant Premium", 100_000, 740, 0.03, 0.06, refundable=True),
]


def edge_mode(hist, dd):
    if dd >= 0.03 or len(hist) < 20:
        return "Conservative"
    def pf(x):
        x = np.asarray(x); g = x[x > 0].sum(); l = -x[x < 0].sum()
        return g / l if l > 0 else 9.9
    h40, h20 = hist[-40:], hist[-20:]
    if len(hist) >= 40 and sum(h40) >= 8 and pf(h40) >= 1.5 and dd <= 0.015:
        return "Aggressive"
    if sum(h20) >= 3 and pf(h20) >= 1.3 and dd <= 0.02:
        return "Normal"
    return "Conservative"


def run(trades, acct: Account, mode: str, start=None, end=None, guard=True):
    """mode: Conservative | Normal | Aggressive | Edge gate"""
    tr = sorted([t for t in trades if (start is None or t.entry_time >= start) and (end is None or t.entry_time < end)],
                key=lambda t: t.entry_time)
    cap = acct.size
    bal, peak = cap, cap
    budget = (acct.max_loss - 0.01) if (guard and acct.max_loss) else None
    dbudget = (acct.daily - 0.005) if (guard and acct.daily) else None
    day, day_bal = None, cap
    ev = []; seq = 0
    for t in tr:
        heapq.heappush(ev, (t.entry_time, 0, seq, "in", t)); seq += 1
    open_ = {}
    hist = []
    fills = []
    paid, refunded, breach = 0.0, False, None
    payouts = []
    next_pay = tr[0].entry_time + pd.Timedelta(days=acct.payout_days) if (tr and acct.payout_days and not acct.real) else None
    skipped = dict(min_lot=0, guard=0)
    mode_log = {"Conservative": 0, "Normal": 0, "Aggressive": 0}
    curve = []
    worst_dd = 0.0
    breach_info = None

    def orisk():
        return sum(p["risk"] for p in open_.values())

    while ev:
        tm, _, _, kind, x = heapq.heappop(ev)
        if tm.normalize() != day:
            day, day_bal = tm.normalize(), bal
        # bi-weekly reward
        if next_pay is not None and tm >= next_pay:
            while next_pay <= tm:
                next_pay += pd.Timedelta(days=acct.payout_days)
            prof = bal - cap - orisk()          # realized profit not needed to cover open risk
            if prof > 0:
                paid += prof * acct.split
                if acct.refundable and not refunded:
                    paid += acct.fee; refunded = True
                bal -= prof
                day_bal -= prof                  # a withdrawal is not a trading loss
                peak = bal                       # trailing high-water mark restarts from the post-payout balance
                payouts.append((tm, round(prof * acct.split, 2)))
        if breach:
            if kind == "in":
                continue
        if kind == "in":
            t = x
            spec = SYMBOLS[t.symbol]
            m = mode if mode != "Edge gate" else edge_mode(hist, (peak - bal) / peak)
            plan = getattr(t, "plan", "Plan 1")
            r = MODES[m]["p3" if plan == "Plan 3" else "p1"]
            if t.engine in ("pos_add", "levels_add") and not any(p["t"].pos_id == t.pos_id for p in open_.values()):
                continue
            dist = abs(t.entry - t.stop)
            lots = math.floor(cap * r / (dist * spec.contract) / spec.lot_step + 1e-9) * spec.lot_step if acct.real is False \
                else math.floor(bal * r / (dist * spec.contract) / spec.lot_step + 1e-9) * spec.lot_step
            lots = min(round(lots, 2), spec.max_lot)
            if lots < spec.min_lot:
                skipped["min_lot"] += 1; continue
            risk = lots * dist * spec.contract
            ref = peak if acct.trailing else cap
            room = []
            if budget is not None:
                room.append(budget * cap - (ref - bal) - orisk())
            if dbudget is not None:
                room.append(dbudget * cap - (day_bal - bal) - orisk())
            if room and risk > 0.5 * min(room):
                # near the limit: shrink the trade to half of the remaining room instead of stopping
                allowed = max(0.0, 0.5 * min(room))
                lots = math.floor(allowed / (dist * spec.contract) / spec.lot_step + 1e-9) * spec.lot_step
                lots = round(lots, 2)
                if lots < spec.min_lot:
                    skipped["guard"] += 1; continue
                risk = lots * dist * spec.contract
            cost = spec.spread * lots * spec.contract
            bal -= cost
            mode_log[m] += 1
            open_[id(t)] = dict(t=t, lots=lots, risk=risk, risk0=risk, pnl=-cost, f=0.0, mode=m, eq=bal + cost)
            for (xt, px, fr) in t.exits:
                heapq.heappush(ev, (xt, 1, seq, "out", (id(t), px, fr))); seq += 1
        else:
            k, px, fr = x
            p = open_.get(k)
            if p is None:
                continue
            t = p["t"]; spec = SYMBOLS[t.symbol]
            pnl = (px - t.entry) * t.direction * p["lots"] * spec.contract * fr
            bal += pnl; p["pnl"] += pnl; p["f"] += fr
            p["risk"] = p["risk0"] * max(0, 1 - p["f"])
            if p["f"] >= 0.999:
                del open_[k]
                nr = p["pnl"] / p["risk0"]
                if t.engine in ("position", "levels", "weekly", "micro"):
                    hist.append(nr)
                fills.append(dict(symbol=t.symbol, plan=getattr(t, "plan", "Plan 1"), engine=t.engine,
                                  entry_time=t.entry_time, exit_time=tm, dir=t.direction, entry=t.entry, stop=t.stop,
                                  lots=p["lots"], risk_usd=round(p["risk0"], 2), pnl=round(p["pnl"], 2),
                                  net_r=round(nr, 3), mode=p["mode"], equity=round(p["eq"], 2)))
            peak = max(peak, bal)
            worst_dd = max(worst_dd, (peak - bal) / cap)
            curve.append((tm, bal + paid))
            prev_breach = breach
            if acct.max_loss is not None and not breach:
                ref = peak if acct.trailing else cap
                if bal <= ref - acct.max_loss * cap:
                    breach = f"max loss {tm.date()}"
            if acct.daily is not None and not breach and day_bal - bal >= acct.daily * cap:
                breach = f"daily loss {tm.date()}"
            if bal <= 0 and not breach:
                breach = f"blown {tm.date()}"
            if breach and not prev_breach:
                gap = (t.stop - px) * t.direction > 0
                breach_info = dict(symbol=t.symbol, exit_px=px, stop=t.stop, beyond_stop=bool(gap),
                                   open_risk_pct=round(orisk() / cap * 100, 2))
    if acct.real:
        net = bal - cap
    else:
        net = paid - acct.fee + (0 if breach else 0)
    return dict(account=acct.name, firm=acct.firm, size=acct.size, fee=acct.fee, mode=mode, real=acct.real,
                trades=len(fills), skipped_min_lot=skipped["min_lot"], skipped_guard=skipped["guard"],
                breach=breach, breach_info=breach_info, payouts=len(payouts), paid_to_trader=round(paid, 2), end_balance=round(bal, 2),
                net_profit=round(net, 2), roi_on_cash=round(net / acct.fee * 100, 1) if acct.fee else None,
                worst_dd_pct=round(worst_dd * 100, 2), modes_used=mode_log, fills=fills,
                curve=[[int(a.timestamp()), round(b, 2)] for a, b in curve])

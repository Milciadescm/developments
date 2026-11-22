"""Overnight financing (swap) estimate for CFD positions held past the daily close.
Assumed yearly rate on notional, charged per calendar day held (weekends included):
metals and indices 5%, BTC 15%. Prop firms and brokers set their own swaps; check the
symbol specification (Market Watch > Specification > Swap long / short) and replace these.
"""
import copy

RATE = {"XAUUSD": 0.05, "XAGUSD": 0.05, "US500": 0.05, "NAS100": 0.05, "BTCUSD": 0.15}


def with_swaps(trades):
    out = []
    for t in trades:
        u = copy.copy(t)
        u.exits = []
        for (xt, px, fr) in t.exits:
            days = max(0.0, (xt - t.entry_time).total_seconds() / 86400)
            u.exits.append((xt, px - t.direction * abs(t.entry) * RATE[t.symbol] * days / 365, fr))
        out.append(u)
    return out

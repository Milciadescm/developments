"""Goat Funded Trader (rules published Nov 2026) vs the two bots, 2024 -> now, $100K accounts.

Instant Premium ($740 promo, fee refundable): no target, 3% daily, 6% intraday-trailing max loss, floating loss of
  all open trades <= 1% of the initial balance (accounts bought from 2 Sep 2026), 5 profitable days (>= +0.5% each)
  needed per payout, payouts every 14 days, 80% split.  -> Prop24 bot.
2-Step Premium funded: 10% static, 3-4% daily, Goat Guard (open floating loss 2% -> split 50%; second time breach),
  $3,000 daily profit cap (excess deducted), 7 profitable days (>= +0.5%) per payout, 85% split.  -> Hold bot.
  Evaluation: +10% then +5%, 10% static, 4% daily, 3 profitable days per step.
Model: each trade risks a fixed % of the initial balance; a new trade is skipped if the stops of all open trades
plus the new one would exceed the floating-loss limit minus a 0.1% buffer (worst case = all stops hit). A day is
"profitable" when that day's closed P&L is >= +0.5% of the initial balance. Max-loss check on closed balance
(intraday equity peaks are not in the data, so the trailing line is modelled slightly kinder than reality).
    python -m fibfvg.gft -> results/gft.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import load, net_r
from .plans import position_engine
from .prop24 import build as prop_build
from .swaps import with_swaps

START = pd.Timestamp("2024-01-01", tz="UTC")
NOW = pd.Timestamp("2026-11-22", tz="UTC")
SIZE = 100_000.0


def daily_pnl(tr, risk, float_cap):
    """closed P&L per day after the floating-loss filter; returns Series and number skipped."""
    tr = sorted(tr, key=lambda t: t.entry_time)
    open_, taken, skipped = [], [], 0
    for t in tr:
        open_ = [x for x in open_ if x.exit_time > t.entry_time]
        if (len(open_) + 1) * risk > float_cap - 0.001:
            skipped += 1; continue
        open_.append(t); taken.append(t)
    rows = {}
    for t in taken:
        d = t.exit_time.normalize()
        rows[d] = rows.get(d, 0.0) + net_r(t) * risk * SIZE
    s = pd.Series(rows).sort_index()
    return s[(s.index >= START)], skipped, len(taken)


def account(days, split, need_days, cap_day, max_loss, trailing, payout_every=14, start=None, end=None):
    if start is not None:
        days = days[(days.index >= start) & (days.index < end)]
    bal, peak, paid, prof_days, last_pay, breach, pays = 0.0, 0.0, 0.0, 0, None, None, []
    for d, p in days.items():
        if cap_day is not None and p > cap_day:
            p = cap_day                                    # profit above the daily cap is deducted
        bal += p
        if p >= 0.005 * SIZE:
            prof_days += 1
        peak = max(peak, bal)
        line = (min(peak, 0.0) if not trailing else min(peak - max_loss * SIZE, 0.0) + (max_loss * SIZE if peak - max_loss * SIZE >= 0 else 0.0))
        floor = (-max_loss * SIZE) if not trailing else min(peak - max_loss * SIZE, 0.0)
        if bal <= floor:
            breach = str(d.date()); break
        if last_pay is None:
            last_pay = d
        if (d - last_pay).days >= payout_every and prof_days >= need_days and bal > 0:
            paid += split * bal; pays.append((str(d.date()), round(split * bal))); bal = 0.0; peak = 0.0; prof_days = 0; last_pay = d
    return dict(paid=round(paid), payouts=len(pays), breach=breach, list=pays)


def challenge(days, targets=(0.10, 0.05), need_days=3, max_loss=0.10):
    res = []
    for s0 in pd.date_range("2024-07-01", "2025-11-01", freq="MS", tz="UTC"):
        d = days[days.index >= s0]
        t0, ok = s0, True
        for tg in targets:
            bal, pdays, hit = 0.0, 0, None
            for day, p in d[d.index >= t0].items():
                bal += p; pdays += p >= 0.005 * SIZE
                if bal <= -max_loss * SIZE:
                    break
                if bal >= tg * SIZE and pdays >= need_days:
                    hit = day; break
            if hit is None:
                ok = False; break
            t0 = hit + pd.Timedelta(days=1)
        res.append((ok, (t0 - s0).days / 30.44 if ok else None))
    p = [m for ok, m in res if ok]
    return dict(pass_rate=round(len(p) / len(res) * 100), median_months=round(float(np.median(p)), 1) if p else None)


def main():
    a, b = prop_build()
    P24 = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    HOLD = with_swaps([t for s in SYMBOLS for t in position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= START], "P2 chandelier", start="2024-01-01")])
    out = {}
    y1 = NOW - pd.Timedelta(days=365)
    for name, tr, risk, cap, split, need, cap_day, ml, trail in (
            ("Instant Premium $100K + Prop24 0.45% (2 open max)", P24, 0.0045, 0.01, 0.80, 5, None, 0.06, True),
            ("Instant Premium $100K + Prop24 0.9% (1 open max)", P24, 0.009, 0.01, 0.80, 5, None, 0.06, True),
            ("2-Step Premium funded $100K + Hold 0.45% per unit (4 units = 1.8%)", HOLD, 0.0045, 0.02, 0.85, 7, 3000.0, 0.10, False),
            ("2-Step Premium funded $100K + Hold 0.9% per unit (2 units max)", HOLD, 0.009, 0.02, 0.85, 7, 3000.0, 0.10, False),
            ("2-Step Premium funded $100K + Prop24 0.9% (2 open max)", P24, 0.009, 0.02, 0.85, 7, 3000.0, 0.10, False)):
        days, skipped, taken = daily_pnl(tr, risk, cap)
        full = account(days, split, need, cap_day, ml, trail)
        last = account(days, split, need, cap_day, ml, trail, start=y1, end=NOW)
        prof_days = int((days >= 0.005 * SIZE).sum())
        row = dict(trades_taken=taken, skipped_floating_limit=skipped, profitable_days_total=prof_days, paid_total=full["paid"],
                   payouts=full["payouts"], breach=full["breach"], last12_paid=last["paid"], last12_payouts=last["payouts"],
                   payout_list=full["list"])
        if "2-Step" in name:
            row["challenge"] = challenge(days)
        out[name] = row
        print(name, {k: v for k, v in row.items() if k != "payout_list"})
    json.dump(out, open("results/gft.json", "w"), indent=1)


if __name__ == "__main__":
    main()

"""12-month payout roadmap simulated on real 2024-2026 trades, from many start months.

Month 0  buy 1 x biggest instant account (Instant Premium $100K: no profit target, 3% daily,
         6% max loss, no consistency rule, 80% split, refundable fee).
Month 1  small first reward (proves the firm pays): up to FIRST_AMOUNT of available profit.
Month 3  major reward: ALL realized profit. All of it buys more $100K accounts (same firm,
         or a second firm such as Lucid - set FIRM_B). Account 1 restarts from its base.
Month 4-8 monthly rewards: available profit clipped to [MIN_PAYOUT, MAX_PAYOUT].
Month 9  major reward from every account; all of it buys as many accounts as possible.
Month 10-12 monthly rewards again. Every new account follows the same cycle from its own start.

    python -m fibfvg.roadmap -> results/roadmap.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import load
from .levels import engine as levels_engine, load_sym
from .plans import position_engine
from .propsim import Account, run

START = pd.Timestamp("2024-01-01", tz="UTC")
FIRM_A = Account("Instant Premium", 100_000, 740.0, 0.03, 0.06, refundable=True)        # promo price from screenshot
FIRM_B = Account("Second firm (e.g. Lucid)", 100_000, 740.0, None, 0.06)              # placeholder: set real price/rules
FIRST_AMOUNT = 1_000.0
MIN_PAYOUT, MAX_PAYOUT = 100.0, None
MONTH = pd.Timedelta(days=30.44)


def portfolios():
    data = {s: load_sym(s) for s in SYMBOLS}
    p1 = []
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv"); d = d[d.index >= START]
        p1 += position_engine(s, d, "P2 chandelier", start="2024-01-01")
    for t in p1:
        t.plan = "Plan 1"

    def p3(**kw):
        out = [t for s, (d, h) in data.items()
               for t in levels_engine(s, d, h, "X4 weeklow", stop_mode="datr", kz=False, ts_bars=120, **kw)]
        for t in out:
            t.plan = "Plan 3"
        return out
    return {"Core (Plan 1 + Plan 3)": p1 + p3(), "Core + 2R bank (half at +2R)": p1 + p3(half_at=2.0)}


def schedule(a0, horizon):
    s = [(a0 + 1 * MONTH, "first"), (a0 + 3 * MONTH, "all"), (a0 + 9 * MONTH, "all")]
    s += [(a0 + m * MONTH, "monthly") for m in (4, 5, 6, 7, 8, 10, 11, 12)]
    return [x for x in s if x[0] <= horizon]


def roadmap(trades, mode, s0, cap_accounts=None, fee_mult=1.0):
    horizon = s0 + 12 * MONTH
    accts = [(s0, FIRM_A)]
    cash = -FIRM_A.fee * fee_mult
    log = []
    first_reward = None
    bought = {}

    def sim(a0, firm):
        return run(trades, firm, mode, start=a0, end=horizon, schedule=schedule(a0, horizon),
                   min_payout=MIN_PAYOUT, max_payout=MAX_PAYOUT, first_amount=FIRST_AMOUNT)

    # month-3 purchase from account 1's month-3 major reward
    r1 = sim(s0, FIRM_A)
    m3 = s0 + 3 * MONTH
    m3_cash = sum(v for d, v in r1["payout_list"] if pd.Timestamp(d, tz="UTC") <= m3.normalize() + pd.Timedelta(days=1)
                  and pd.Timestamp(d, tz="UTC") >= (s0 + 2.5 * MONTH).normalize())
    n3 = int(m3_cash // (FIRM_A.fee * fee_mult))
    if cap_accounts:
        n3 = min(n3, cap_accounts - 1)
    bought["month 3"] = n3
    accts += [(m3, FIRM_A)] * n3
    # month-9 purchase from every account's month-9 major reward
    m9 = s0 + 9 * MONTH
    runs = [r1] + [sim(m3, FIRM_A)] * (1 if n3 else 0)
    m9_cash = 0.0
    for (a0, firm), r in zip([(s0, FIRM_A)] + ([(m3, FIRM_A)] if n3 else []), runs):
        mult = 1 if a0 == s0 else n3
        m9_cash += mult * sum(v for d, v in r["payout_list"] if (m9 - 0.5 * MONTH).normalize() <= pd.Timestamp(d, tz="UTC") <= m9.normalize() + pd.Timedelta(days=1))
    n9 = int(m9_cash // (FIRM_B.fee * fee_mult))
    if cap_accounts:
        n9 = min(n9, cap_accounts)
    bought["month 9"] = n9
    r9 = sim(m9, FIRM_B) if n9 else None
    # cash flow to you: all rewards minus fees spent on purchases
    flows = []
    for d, v in r1["payout_list"]:
        flows.append((d, v))
    if n3:
        r3 = runs[1]
        for d, v in r3["payout_list"]:
            flows.append((d, v * n3))
    if n9:
        for d, v in r9["payout_list"]:
            flows.append((d, v * n9))
    flows.sort()
    if r1["payout_list"]:
        first_reward = r1["payout_list"][0]
    total = sum(v for _, v in flows)
    spent = (n3 * FIRM_A.fee + n9 * FIRM_B.fee) * fee_mult
    by_month = {}
    for d, v in flows:
        m = int((pd.Timestamp(d, tz="UTC") - s0) / MONTH) + 1
        by_month[m] = round(by_month.get(m, 0) + v, 2)
    breaches = [x["breach"] for x in (r1, runs[1] if n3 else None, r9) if x and x["breach"]]
    return dict(start=str(s0.date()), mode=mode, first_reward=first_reward,
                month1_paid=round(by_month.get(1, 0) + by_month.get(2, 0) * 0, 2),
                month3_major=round(m3_cash, 2), accounts_bought_m3=n3, month9_major=round(m9_cash, 2), accounts_bought_m9=n9,
                accounts_at_end=1 + n3 + n9, rewards_total=round(total, 2), spent_on_accounts=round(spent + FIRM_A.fee * fee_mult, 2),
                net_to_you=round(total - spent - FIRM_A.fee * fee_mult, 2), by_month=by_month, breaches=breaches)


def main():
    P = portfolios()
    starts = pd.date_range("2024-08-01", "2025-11-01", freq="MS", tz="UTC")
    out = []
    for pname, tr in P.items():
        for mode in ("Normal", "Aggressive"):
            for cap in (None, 6):
                rows = [roadmap(tr, mode, s0, cap_accounts=cap) for s0 in starts]
                for r in rows:
                    r.update(portfolio=pname, cap=cap)
                out += rows
                df = pd.DataFrame(rows)
                print(f"{pname:30s} {mode:10s} cap {str(cap):4s} | month-1 reward in {np.mean(df.month1_paid > 0) * 100:3.0f}% of starts "
                      f"(median ${df.month1_paid.median():,.0f}) | month-3 major median ${df.month3_major.median():,.0f} "
                      f"| accounts end median {df.accounts_at_end.median():.0f} (max {df.accounts_at_end.max()}) "
                      f"| net to you 12m median ${df.net_to_you.median():,.0f} min ${df.net_to_you.min():,.0f} max ${df.net_to_you.max():,.0f} "
                      f"| breaches {sum(len(b) for b in df.breaches)}")
    json.dump(out, open("results/roadmap.json", "w"), indent=1, default=str)
    return out


if __name__ == "__main__":
    main()

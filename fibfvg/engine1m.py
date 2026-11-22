"""The Cueto & Co. prop engine, simulated on real 2024-2026 trades from 16 start months.

Rules (from the plan):
  - Month 0: buy one $100K instant account (no profit target, no consistency rule, 6% max loss).
  - Every account withdraws ALL closed profit at each month end, so it restarts at $100,000.
  - Month 1 rewards -> the founder's private account.
  - From month 2, rewards collect in a pot; at each quarter end (months 3, 6, 9, 12) the pot goes to
    Cueto & Co., which buys as many new $100K accounts as it covers (optionally capped) and keeps the rest.
    New accounts start trading the day they are bought.
    python -m fibfvg.engine1m -> results/engine1m.json
"""
import json

import numpy as np
import pandas as pd

from .edgebook import IP100, build
from .propsim import run

MONTH = pd.Timedelta(days=30.44)


def monthly_payouts(trades, start, horizon, mode="Normal"):
    sched = [(start + m * MONTH, "all") for m in range(1, 13) if start + m * MONTH <= horizon]
    r = run(trades, IP100, mode, start=start, end=horizon, schedule=sched, min_payout=1.0)
    out = {}
    for d, v in r["payout_list"]:
        m = int(round((pd.Timestamp(d, tz="UTC") - start) / MONTH))
        out[m] = out.get(m, 0) + v
    return out, r["breach"]


def engine(trades, s0, fee=740.0, cap=None, reinvest=1.0, mode="Normal"):
    horizon = s0 + 12 * MONTH
    cohorts = {0: 1}                       # purchase month -> accounts bought
    cache = {}
    private, company_cash, fees, breaches = 0.0, 0.0, fee, 0
    monthly = []
    pot = 0.0
    for m in range(1, 13):
        earned = 0.0
        for c, n in cohorts.items():
            if c not in cache:
                cache[c], b = monthly_payouts(trades, s0 + c * MONTH, horizon, mode)
                breaches += bool(b) * n
            earned += n * cache[c].get(m - c, 0.0)
        if m == 1:
            private += earned
        else:
            pot += earned
        bought = 0
        if m % 3 == 0:
            company_cash += pot
            budget = company_cash * reinvest
            bought = int(budget // fee)
            if cap:
                bought = max(0, min(bought, cap - sum(cohorts.values())))
            if bought and m < 12:
                cohorts[m] = cohorts.get(m, 0) + bought
                company_cash -= bought * fee; fees += bought * fee
            else:
                bought = 0
            pot = 0.0
        monthly.append(dict(month=m, accounts=sum(n for c, n in cohorts.items() if c < m) if m > 1 else 1,
                            earned=round(earned, 2), bought=bought))
    company_cash += pot
    return dict(start=str(s0.date()), private=round(private, 2), company_cash=round(company_cash, 2),
                fees=round(fees, 2), accounts=sum(cohorts.values()), breaches=breaches,
                gross=round(sum(x["earned"] for x in monthly), 2), monthly=monthly)


def main():
    _, P = build()
    tr = P["Plan 1 Position"] + P["Plan 3B Levels 2R bank"]
    starts = pd.date_range("2024-08-01", "2025-11-01", freq="MS", tz="UTC")
    res = {}
    for name, kw in {"promo fee $740, no cap": dict(fee=740.0), "promo fee $740, cap 20 accounts": dict(fee=740.0, cap=20),
                     "regular fee $1,480, no cap": dict(fee=1480.0), "promo $740, reinvest 50%": dict(fee=740.0, reinvest=0.5)}.items():
        rows = [engine(tr, s0, **kw) for s0 in starts]
        df = pd.DataFrame(rows)
        res[name] = rows
        print(f"{name:34s} accounts med {df.accounts.median():.0f} (max {df.accounts.max()}) | private M1 med ${df.private.median():,.0f} "
              f"| Cueto & Co cash at month 12 med ${df.company_cash.median():,.0f} min ${df.company_cash.min():,.0f} max ${df.company_cash.max():,.0f} "
              f"| gross rewards med ${df.gross.median():,.0f} max ${df.gross.max():,.0f} | breaches {df.breaches.sum()}")
    # one account, all 16 starts: annual rewards with monthly reset -> accounts needed for $1M
    one = [engine(tr, s0, cap=1) for s0 in starts]
    yr = np.array([x["gross"] for x in one])
    res["one_account_year"] = dict(median=float(np.median(yr)), mean=float(yr.mean()), min=float(yr.min()), max=float(yr.max()))
    res["accounts_for_1M"] = dict(at_median=int(np.ceil(1e6 / np.median(yr))), at_mean=int(np.ceil(1e6 / yr.mean())))
    print(res["one_account_year"], res["accounts_for_1M"])
    json.dump(res, open("results/engine1m.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

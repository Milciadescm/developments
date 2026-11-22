"""How many funded accounts and how much reserve make a fixed bi-weekly withdrawal safe?
    python -m fibfvg.withdrawals -> results/withdrawals.json
Rewards land lumpy (some fortnights nothing). The plan: every reward goes into a personal
reserve; you pay yourself a fixed amount every 14 days from the reserve.
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import load
from .plans import position_engine
from .propsim import PROP_ACCOUNTS, run
from .since2024 import CHOSEN, build

START = pd.Timestamp("2024-01-01", tz="UTC")


def fortnight_series(payout_list, t0, t1):
    idx = pd.date_range(t0, t1, freq="14D")
    s = pd.Series(0.0, index=idx)
    for d, v in payout_list:
        k = idx.searchsorted(pd.Timestamp(d, tz="UTC"), side="right") - 1
        if k >= 0:
            s.iloc[k] += v
    return s


def salary_test(series, n_acc, salary, reserve0):
    """reserve starts at reserve0, receives n_acc * rewards, pays `salary` each fortnight."""
    r = reserve0; low = r; miss = 0
    for v in series.values:
        r += n_acc * v - salary
        if r < 0:
            miss += 1; r = 0
        low = min(low, r)
    return dict(misses=miss, lowest_reserve=round(low, 2), end_reserve=round(r, 2))


def main():
    data, p1m, v1, v2 = build()
    p3 = v2[CHOSEN]
    p1c = []
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv"); d = d[d.index >= START]
        p1c += position_engine(s, d, "P2 chandelier", start="2024-01-01")
    for t in p1c:
        t.plan = "Plan 1"
    tr = p1c + p3
    t0 = min(t.entry_time for t in tr); t1 = max(t.exit_time for t in tr)
    out = {"accounts": [], "plans": []}
    for acct in PROP_ACCOUNTS:
        for mode in ("Conservative", "Normal"):
            r = run(tr, acct, mode)
            ser = fortnight_series(r["payout_list"], t0, t1)
            nz = ser[ser > 0]
            first = r["payout_list"][0][0] if r["payout_list"] else None
            row = dict(account=acct.name, fee=acct.fee, size=acct.size, mode=mode, fortnights=len(ser),
                       paid=round(ser.sum(), 2), avg_per_fortnight=round(ser.mean(), 2),
                       fortnights_with_reward=int((ser > 0).sum()), median_reward=round(float(nz.median()), 2) if len(nz) else 0,
                       first_reward=first, worst_6m=round(float(ser.rolling(13).sum().min()), 2),
                       per_100k_per_fortnight=round(ser.mean() / acct.size * 100_000, 2), breach=r["breach"])
            out["accounts"].append(row)
            for salary in (1000, 1500, 2000):
                # accounts needed so the average covers the salary 1.5x (safety margin)
                n = int(np.ceil(salary * 1.5 / max(ser.mean(), 1e-9)))
                for res_weeks in (0, 12, 26):
                    reserve0 = salary * res_weeks / 2
                    st = salary_test(ser, n, salary, reserve0)
                    out["plans"].append(dict(account=acct.name, mode=mode, salary=salary, accounts_needed=n,
                                             funded_total=n * acct.size, fees_total=round(n * acct.fee, 2),
                                             starting_reserve=reserve0, **st))
    json.dump(out, open("results/withdrawals.json", "w"), indent=1, default=str)
    a = pd.DataFrame(out["accounts"])
    print(a[["account", "mode", "paid", "avg_per_fortnight", "fortnights_with_reward", "fortnights", "median_reward", "first_reward", "worst_6m", "per_100k_per_fortnight"]].to_string())
    p = pd.DataFrame(out["plans"])
    print(p[(p.account.str.contains("100K|50K|20K"))].to_string())
    return out


if __name__ == "__main__":
    main()


def ladder(series, n_acc, levels=(1000, 1500, 2000), start_mult=13, down_mult=6):
    """Salary ladder: rewards go to the reserve. Start paying the first level once the reserve
    covers `start_mult` fortnights of it; step up when it covers `start_mult` of the next level;
    step down when it falls under `down_mult` fortnights of the current level."""
    r, lvl, paid, misses, hist = 0.0, -1, 0.0, 0, []
    for d, v in series.items():
        r += n_acc * v
        nxt = lvl + 1
        if nxt < len(levels) and r >= start_mult * levels[nxt]:
            lvl = nxt
        while lvl >= 0 and r < down_mult * levels[lvl]:
            lvl -= 1
        sal = levels[lvl] if lvl >= 0 else 0
        if sal:
            if r >= sal:
                r -= sal; paid += sal
            else:
                misses += 1
        hist.append((str(d.date()), sal, round(r, 0)))
    first = next((h[0] for h in hist if h[1] > 0), None)
    return dict(accounts=n_acc, paid_to_you=round(paid), misses=misses, first_salary=first, end_reserve=round(r),
                fortnights_at={str(l): sum(1 for h in hist if h[1] == l) for l in (0,) + tuple(levels)}, path=hist)

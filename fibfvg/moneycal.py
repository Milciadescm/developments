"""Money calendar Dec 2026 - Dec 2027: every account separate, every pay date, income statement and balance sheet.

One typical year: of 2,000 simulated paths (3-month blocks of real 2024-2026 monthly results), the path whose
2027 withdrawals are the median is shown in full, so every number adds up. The baseline of one account (what a
single $100K account makes in a month) is shown separately, from the real 2024-2026 backtest months.
Pay dates: salary $1,000 on the 15th and $1,000 on the 30th. Inheritance RD$3,000,000 (US$47,619 at RD$63) on
1 July 2027 into the fund; the fund pays 0.98% of the total every month (US$467) from 30 July.
Accounts: Dec 1 2026 A1 (6% trailing, Prop24) and B1 (no drawdown limit, Hold 5 markets); 1 Mar A2, 1 Apr A3,
1 May A4 (6% trailing); 1 June A5-A9 (6% trailing, 5 accounts). Withdrawals 26 May and 30 Dec 2027, 80% split.
Apartment (safest plan): $35,000 down payment on 30 Dec 2027, $400 a month from January 2028.
    python -m fibfvg.moneycal -> results/moneycal.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import load
from .plans import position_engine
from .prop24 import build as prop_build
from .propsim import Account
from .swaps import with_swaps
from .plan2027 import monthly_pnl, MONTHS, START

PLAN = pd.date_range("2026-12-01", "2027-12-01", freq="MS")
FEE, SPLIT = 740.0, 0.80
INHERIT = 3_000_000 / 63.0
FUND_MONTH = INHERIT * 0.0098
GROUPS = [("A1", "A", "2026-12-01", 1), ("B1", "B", "2026-12-01", 1), ("A2", "A", "2027-03-01", 1), ("A3", "A", "2027-04-01", 1),
          ("A4", "A", "2027-05-01", 1), ("A5-A9", "A", "2027-06-01", 5)]


def path(pa, pb):
    held = {g[0]: 0.0 for g in GROUPS}; peak = dict(held); dead = set()
    rows = []; wd = {}
    for k, m in enumerate(PLAN):
        row = {}
        for name, kind, s, cnt in GROUPS:
            if pd.Timestamp(s) > m or name in dead:
                row[name] = None if pd.Timestamp(s) > m else "lost"; continue
            held[name] += pa[k] if kind == "A" else pb[k]
            peak[name] = max(peak[name], held[name])
            if kind == "A" and peak[name] - held[name] >= 6_000:
                dead.add(name); row[name] = "lost"; continue
            row[name] = held[name]
        if m.month in (5, 12) and m.year == 2027:
            for name, kind, s, cnt in GROUPS:
                if name not in dead and pd.Timestamp(s) <= m and held[name] > 0:
                    wd[(m.month, name)] = SPLIT * held[name] * cnt
                    held[name] = 0.0; peak[name] = 0.0
        rows.append(row)
    total = sum(wd.values())
    return rows, wd, total, dead


def main():
    a, b = prop_build()
    P24 = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    HOLD = with_swaps([t for s in SYMBOLS for t in position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= START], "P2 chandelier", start="2024-01-01")])
    for t in HOLD:
        t.plan = "Plan 1"
    pa, _ = monthly_pnl(P24, Account("6%", 100_000, 740.0, None, 0.06, payout_days=None), 0.0075)
    pb, _ = monthly_pnl(HOLD, Account("none", 100_000, 740.0, None, None, trailing=False, payout_days=None), 0.01)
    base = dict(A=dict(median=round(float(np.median(pa))), mean=round(float(pa.mean())), best=round(float(pa.max())), worst=round(float(pa.min())),
                       up_months=int((pa > 0).sum()), months=len(pa), year_mean=round(float(pa.mean() * 12))),
                B=dict(median=round(float(np.median(pb))), mean=round(float(pb.mean())), best=round(float(pb.max())), worst=round(float(pb.min())),
                       up_months=int((pb > 0).sum()), months=len(pb), year_mean=round(float(pb.mean() * 12))))
    print("baseline one account per month:", base)
    rng = np.random.default_rng(27); n = len(MONTHS)
    sims = []
    for _ in range(2000):
        i = np.concatenate([np.arange(j, j + 3) for j in rng.integers(0, n - 2, 5)])[:13]
        sims.append((i,) + path(pa.values[i], pb.values[i]))
    totals = np.array([s[3] for s in sims]); med = np.median(totals)
    pick = min(range(len(sims)), key=lambda j: abs(totals[j] - med))
    idx, rows, wd, total, dead = sims[pick]
    src_months = [MONTHS[j].strftime("%b %Y") for j in idx]
    print("typical path built from real months:", src_months, "total withdrawn", round(total), "range p10/p90", round(np.percentile(totals, 10)), round(np.percentile(totals, 90)))
    for m, r in zip(PLAN, rows):
        print(m.strftime("%b %Y"), {k: (round(v) if isinstance(v, float) else v) for k, v in r.items()})
    print("withdrawals:", {f"{'May' if k[0] == 5 else 'Dec'} {k[1]}": round(v) for k, v in wd.items()})
    out = dict(baseline=base, typical_path_source_months=src_months, totals=dict(median=round(med), p10=round(float(np.percentile(totals, 10))), p90=round(float(np.percentile(totals, 90)))),
               held=[{k: (round(v) if isinstance(v, float) else v) for k, v in r.items()} | dict(month=m.strftime("%b %Y")) for m, r in zip(PLAN, rows)],
               withdrawals={f"{'May' if k[0] == 5 else 'Dec'} {k[1]}": round(v) for k, v in wd.items()}, fund_month=round(FUND_MONTH, 2), inheritance=round(INHERIT))
    json.dump(out, open("results/moneycal.json", "w"), indent=1)


if __name__ == "__main__":
    main()

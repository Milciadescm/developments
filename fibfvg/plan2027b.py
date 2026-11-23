"""2027 with a growing number of $100K prop accounts (simulation from 2024-2026 results, not a promise).

Accounts: 1 Dec 2026 two accounts - A (6% trailing, FibFVG_Prop24 0.75%) and B (no drawdown limit, FibFVG_Hold
5 markets 1%). March, April and May 2027: one more 6% account each from personal funds ($740 each) -> 5 accounts.
26 May 2027: withdraw all profit (80% split). 1 June 2027: add 6% accounts to reach 10 or 15 in total ($740 each).
December 2027: withdraw everything. Accounts bought the same month take the same trades and move together.
    python -m fibfvg.plan2027b -> results/plan2027b.json
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


def one_path(pa, pb, total_after_may):
    # groups: (kind, start month) -> number of accounts
    groups = {("A", PLAN[0]): 1, ("B", PLAN[0]): 1}
    for m in ("2027-03-01", "2027-04-01", "2027-05-01"):
        groups[("A", pd.Timestamp(m))] = 1
    held, peaks, dead = {}, {}, set()
    may = dec = 0.0
    for k, mth in enumerate(PLAN):
        if mth == pd.Timestamp("2027-06-01"):
            add = max(0, total_after_may - sum(groups.values()))
            if add:
                groups[("A", mth)] = add
        for key, cnt in groups.items():
            kind, s = key
            if s > mth or key in dead:
                continue
            p = pa[k] if kind == "A" else pb[k]
            held[key] = held.get(key, 0.0) + p
            peaks[key] = max(peaks.get(key, 0.0), held[key])
            if kind == "A" and peaks[key] - held[key] >= 6_000:     # 6% trailing line: these accounts are lost
                dead.add(key); held[key] = 0.0
        if mth.month in (5, 12) and mth.year == 2027:
            tot = sum(SPLIT * held[key] * cnt for key, cnt in groups.items() if key in held and key not in dead and held[key] > 0)
            for key in held:
                if key not in dead and held[key] > 0:
                    held[key] = 0.0; peaks[key] = 0.0
            if mth.month == 5:
                may = tot
            else:
                dec = tot
    lost = sum(cnt for key, cnt in groups.items() if key in dead)
    return may, dec, lost


def main():
    a, b = prop_build()
    P24 = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    HOLD = with_swaps([t for s in SYMBOLS for t in position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= START], "P2 chandelier", start="2024-01-01")])
    for t in HOLD:
        t.plan = "Plan 1"
    pa, _ = monthly_pnl(P24, Account("6%", 100_000, 740.0, None, 0.06, payout_days=None), 0.0075)
    pb, _ = monthly_pnl(HOLD, Account("none", 100_000, 740.0, None, None, trailing=False, payout_days=None), 0.01)
    rng = np.random.default_rng(27); n = len(MONTHS)
    idxs = [np.concatenate([np.arange(j, j + 3) for j in rng.integers(0, n - 2, 5)])[:13] for _ in range(2000)]
    q = lambda x: dict(median=round(float(np.median(x))), p10=round(float(np.percentile(x, 10))), p90=round(float(np.percentile(x, 90))))
    out = {}
    for total in (5, 10, 15):
        res = [one_path(pa.values[i], pb.values[i], total) for i in idxs]
        may = np.array([r[0] for r in res]); dec = np.array([r[1] for r in res]); lost = np.array([r[2] for r in res])
        row = dict(may=q(may), december=q(dec), total=q(may + dec), fees_2027=round(3 * FEE + (total - 5) * FEE),
                   paths_with_lost_accounts_pct=round(float((lost > 0).mean() * 100), 1), lost_median_if_any=float(np.median(lost[lost > 0])) if (lost > 0).any() else 0,
                   may_covers_10_accounts_pct=round(float((may >= 10 * FEE).mean() * 100), 1))
        for label, s0 in (("good year (Dec 2024-Dec 2025)", "2024-12-01"), ("weak year (last 12 months)", "2025-11-01")):
            i0 = list(MONTHS).index(pd.Timestamp(s0, tz="UTC")); i = [min(i0 + k, n - 1) for k in range(13)]
            r = one_path(pa.values[i], pb.values[i], total)
            row[label] = dict(may=round(r[0]), december=round(r[1]), total=round(r[0] + r[1]), lost_accounts=r[2])
        out[f"{total} accounts"] = row
        print(total, json.dumps(row))
    json.dump(out, open("results/plan2027b.json", "w"), indent=1)


if __name__ == "__main__":
    main()

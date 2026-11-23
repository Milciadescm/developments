"""FundedNext CFD rules (published Nov 2026) checked against the two bots, 2024 -> now.

Rules used: Stellar Instant 6% trailing max loss (trailing stops once it reaches the initial balance), no daily limit,
no target. Stellar 2-Step: 10% static max loss, 5% daily loss (realized + unrealized, resets 00:00 server),
targets 8% (phase 1) then 5% (phase 2), min 5 trading days. Stellar 1-Step: 6% static, 3% daily, 10% target.
Stellar Lite: 8% static, 4% daily, 8% then 4% targets. All CFD accounts: deactivated after 60 days without a trade.
Reward share 80% (up to 90% with scale-up, 95% add-on).
Checks:
  1. Longest gap between new trades for each bot (60-day inactivity rule).
  2. Hold bot (5 markets) on the 2-Step / Lite / 1-Step funded accounts at 0.5% and 1% per unit: payouts, breaches.
  3. Hold bot passing the 2-Step challenge: how often and how fast, from every start month.
    python -m fibfvg.fundednext -> results/fundednext.json
"""
import json

import numpy as np
import pandas as pd

from . import propsim
from .config import SYMBOLS
from .engines import load
from .plans import position_engine
from .prop24 import build as prop_build
from .propsim import Account, run
from .swaps import with_swaps

START = pd.Timestamp("2024-01-01", tz="UTC")


def gaps(tr):
    t = sorted({x.entry_time for x in tr})
    d = np.diff([x.value for x in t]) / 86400e9
    return dict(max_gap_days=round(float(d.max()), 1), gaps_over_45=int((d > 45).sum()), gaps_over_60=int((d > 60).sum()),
                first=str(t[0].date()), last=str(t[-1].date()))


def challenge(tr, risk, size=100_000):
    """2-Step: phase 1 +8% then phase 2 +5%, 10% static, 5% daily, from every start month."""
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    res = []
    for s0 in pd.date_range("2024-07-01", "2025-11-01", freq="MS", tz="UTC"):
        acct = Account("2-Step challenge", size, 0.0, 0.05, 0.10, trailing=False, payout_days=None)
        days = None; t0 = s0; ok = True
        for target in (0.08, 0.05):
            o = run(tr, acct, "X", start=t0, end=pd.Timestamp("2026-11-22", tz="UTC"))
            hit = None
            for ts, v in o["curve"]:
                if v >= size * (1 + target):
                    hit = pd.Timestamp(ts, unit="s", tz="UTC"); break
            if o["breach"] and (hit is None or pd.Timestamp(o["breach"].split()[-1], tz="UTC") <= hit):
                ok = False; break
            if hit is None:
                ok = False; break
            t0 = hit + pd.Timedelta(days=1)
        res.append(dict(start=str(s0.date()), passed=ok, months=round((t0 - s0).days / 30.44, 1) if ok else None))
    p = [r for r in res if r["passed"]]
    return dict(pass_rate=round(len(p) / len(res) * 100), median_months=float(np.median([r["months"] for r in p])) if p else None, starts=res)


def main():
    a, b = prop_build()
    P24 = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    HOLD = with_swaps([t for s in SYMBOLS for t in position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= START], "P2 chandelier", start="2024-01-01")])
    for t in HOLD:
        t.plan = "Plan 1"
    out = dict(inactivity=dict(Prop24=gaps(P24), Hold=gaps(HOLD)))
    print("60-day rule:", out["inactivity"])
    funded = {"2-Step funded (10% static, 5% daily)": (0.05, 0.10), "Lite funded (8% static, 4% daily)": (0.04, 0.08),
              "1-Step funded (6% static, 3% daily)": (0.03, 0.06)}
    out["hold_funded"] = {}
    for name, (dl, ml) in funded.items():
        for risk in (0.005, 0.01):
            propsim.MODES["X"] = dict(p1=risk, p3=risk)
            o = run(HOLD, Account(name, 100_000, 0.0, dl, ml, trailing=False), "X", start=START)
            by = {}
            for d, v in o["payout_list"]:
                by[d[:4]] = by.get(d[:4], 0) + v
            key = f"{name} | {risk * 100:.1f}% per unit"
            out["hold_funded"][key] = dict(paid=round(o["paid_to_trader"]), by_year={k: round(v) for k, v in by.items()}, breach=o["breach"],
                                           dd=o["worst_dd_pct"], skipped_guard=o["skipped_guard"])
            print(key, out["hold_funded"][key])
    out["hold_2step_challenge"] = {f"{r * 100:.1f}%": challenge(HOLD, r) for r in (0.005, 0.01)}
    for k, v in out["hold_2step_challenge"].items():
        print("2-Step challenge, Hold bot", k, "pass rate", v["pass_rate"], "% median months", v["median_months"])
    json.dump(out, open("results/fundednext.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

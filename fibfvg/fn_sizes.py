"""FundedNext accounts where EAs are allowed ($5K-$25K), 2024 -> now. 80% reward share (up to 95% with scale-up).
  Instant $20K : 6% trailing (locks at the start balance), no daily limit -> Prop24 bot, 0.75% per trade.
  2-Step $25K  : 10% static, 5% daily, challenge 8% then 5% -> Hold bot (5 markets, chandelier), 0.75% per unit
                 (4 units = 3%: FundedNext's maximum risk per trade).
  1-Step $25K  : 6% static, 3% daily, challenge 10% -> Hold bot 0.75% / 0.5% per unit.
  Lite $25K    : 8% static, 4% daily, challenge 8% then 4% -> Hold bot 0.75% per unit.
Funded results from mid-2024 (no challenge), and challenge pass rate / months from every start month.
    python -m fibfvg.fn_sizes -> results/fn_sizes.json
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
NOW = pd.Timestamp("2026-11-22", tz="UTC")


def challenge(tr, risk, size, daily, maxloss, targets):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    res = []
    for s0 in pd.date_range("2024-07-01", "2025-11-01", freq="MS", tz="UTC"):
        t0, ok = s0, True
        for target in targets:
            o = run(tr, Account("challenge", size, 0.0, daily, maxloss, trailing=False, payout_days=None), "X", start=t0, end=NOW)
            hit = next((pd.Timestamp(ts, unit="s", tz="UTC") for ts, v in o["curve"] if v >= size * (1 + target)), None)
            if hit is None or (o["breach"] and pd.Timestamp(o["breach"].split()[-1], tz="UTC") <= hit):
                ok = False; break
            t0 = hit + pd.Timedelta(days=1)
        res.append((ok, (t0 - s0).days / 30.44 if ok else None))
    p = [m for ok, m in res if ok]
    return dict(pass_rate=round(len(p) / len(res) * 100), median_months=round(float(np.median(p)), 1) if p else None, starts=len(res))


def funded(tr, size, daily, maxloss, trailing, risk):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    acct = Account("funded", size, 0.0, daily, maxloss, trailing=trailing)
    o = run(tr, acct, "X", start=START)
    l = run(tr, acct, "X", start=NOW - pd.Timedelta(days=365), end=NOW)
    by = {}
    for d, v in o["payout_list"]:
        by[d[:4]] = by.get(d[:4], 0) + v
    return dict(paid=round(o["paid_to_trader"]), by_year={k: round(v) for k, v in by.items()}, last12=round(l["paid_to_trader"]),
                breach=o["breach"], dd=o["worst_dd_pct"], skipped_min_lot=o["skipped_min_lot"], taken=o["trades"])


def main():
    a, b = prop_build()
    P24 = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    HOLD = with_swaps([t for s in SYMBOLS for t in position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= START], "P2 chandelier", start="2024-01-01")])
    for t in HOLD:
        t.plan = "Plan 1"
    out = {}
    rows = [
        ("Instant $20K + Prop24 0.75%", P24, 20_000, None, 0.06, True, 0.0075, None),
        ("Instant $10K + Prop24 0.75%", P24, 10_000, None, 0.06, True, 0.0075, None),
        ("2-Step $25K + Hold 0.75%", HOLD, 25_000, 0.05, 0.10, False, 0.0075, (0.08, 0.05)),
        ("2-Step $15K + Hold 0.75%", HOLD, 15_000, 0.05, 0.10, False, 0.0075, (0.08, 0.05)),
        ("1-Step $25K + Hold 0.75%", HOLD, 25_000, 0.03, 0.06, False, 0.0075, (0.10,)),
        ("1-Step $25K + Hold 0.5%", HOLD, 25_000, 0.03, 0.06, False, 0.005, (0.10,)),
        ("Lite $25K + Hold 0.75%", HOLD, 25_000, 0.04, 0.08, False, 0.0075, (0.08, 0.04)),
        ("2-Step $25K + Prop24 0.75%", P24, 25_000, 0.05, 0.10, False, 0.0075, (0.08, 0.05)),
    ]
    for name, tr, size, dl, ml, trail, risk, targets in rows:
        r = funded(tr, size, dl, ml, trail, risk)
        if targets:
            r["challenge"] = challenge(tr, risk, size, dl, ml, targets)
        out[name] = r
        print(name, r)
    json.dump(out, open("results/fn_sizes.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

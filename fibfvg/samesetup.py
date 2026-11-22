"""Should prop accounts and real money use the same holding setup? 2006-2026 daily history, all 5 markets.

Entries: bot v3 position plan. Exits: P2 chandelier (holds days-weeks) and Y1 year (trail the 120-day low).
Swaps charged. Per market: win rate, RR, R per trade, both halves. Then:
  prop  : one $100K FundedNext instant account (6% trailing line, 5% guard), 0.5% risk, started every January
          2007-2025, 12 months each: paid, breached or not.
  real  : $100K real money at 0.5% per unit, whole period: growth, worst drawdown.
    python -m fibfvg.samesetup -> results/samesetup.json
"""
import json

import numpy as np
import pandas as pd

from . import plans, propsim
from .engines import net_r
from .plans import position_engine
from .propsim import Account, run
from .swaps import with_swaps
from .livefund import monthly, max_dd
from .longhold import load_long

plans.POS_MODES["Y1 year"] = dict(tp1=False, tp2=False, trail="d120", be_at=1.0, time_stop=None)
MKTS = ("XAUUSD", "XAGUSD", "BTCUSD", "US500", "NAS100")
SPLIT = pd.Timestamp("2016-01-01", tz="UTC")
FN100 = Account("FundedNext instant", 100_000, 740.0, None, 0.06)


def stats(r, a, b):
    w, l = r[r > 0], r[r <= 0]
    return dict(n=len(r), win=round(float((r > 0).mean() * 100), 1), rr=round(float(w.mean() / -l.mean()), 2) if len(l) and len(w) else None,
                net=round(float(r.mean()), 3), first=round(float(a.mean()), 3) if len(a) else None, second=round(float(b.mean()), 3) if len(b) else None,
                t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2) if len(r) > 2 else None)


def main():
    out = {}
    for mode in ("P2 chandelier", "Y1 year"):
        allt = []; per = {}
        for s in MKTS:
            tr = with_swaps(position_engine(s, load_long(s), mode, start="2006-01-01"))
            for t in tr:
                t.plan = "Plan 1"
            allt += tr
            r = np.array([net_r(t) for t in tr])
            per[s] = stats(r, np.array([net_r(t) for t in tr if t.entry_time < SPLIT]), np.array([net_r(t) for t in tr if t.entry_time >= SPLIT]))
        r = np.array([net_r(t) for t in allt])
        per["All 5"] = stats(r, np.array([net_r(t) for t in allt if t.entry_time < SPLIT]), np.array([net_r(t) for t in allt if t.entry_time >= SPLIT]))
        propsim.MODES["X"] = dict(p1=0.005, p3=0.005)
        prop = []
        for y in range(2007, 2026):
            s0 = pd.Timestamp(f"{y}-01-01", tz="UTC")
            o = run(allt, FN100, "X", start=s0, end=s0 + pd.Timedelta(days=365))
            prop.append(dict(year=y, paid=round(o["paid_to_trader"]), breach=o["breach"], dd=o["worst_dd_pct"]))
        o = run(allt, Account("Live", 100_000, 0.0, None, None, real=True), "X", start=pd.Timestamp("2006-01-01", tz="UTC"))
        m = monthly(o["curve"], 100_000)
        real = dict(end=round(o["end_balance"]), cagr=round(((o["end_balance"] / 1e5) ** (12 / len(m)) - 1) * 100, 1), max_dd=round(max_dd(m) * 100, 1))
        paid = [p["paid"] for p in prop]
        out[mode] = dict(by_market=per, prop_years=prop, prop_summary=dict(median=round(float(np.median(paid))), worst=min(paid), best=max(paid),
                         breaches=sum(1 for p in prop if p["breach"]), years=len(prop), zero_years=sum(1 for v in paid if v <= 0)), real=real)
        print(mode)
        for k, v in per.items():
            print(f"  {k:7s}", v)
        print("  prop 12-month windows:", out[mode]["prop_summary"])
        print("  ", [(p["year"], p["paid"], "BREACH" if p["breach"] else "") for p in prop])
        print("  real money:", real)
    json.dump(out, open("results/samesetup.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

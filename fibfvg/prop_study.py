"""Prop accounts vs the same cash in a real account, Jan 2024 -> now.
    python -m fibfvg.prop_study -> results/prop_study.json, results/prop_trades_*.csv
"""
import json
import math

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import load
from .plans import position_engine
from .propsim import MODES, PROP_ACCOUNTS, Account, run
from .since2024 import CHOSEN, build

START = pd.Timestamp("2024-01-01", tz="UTC")


def main():
    data, p1m, v1, v2 = build()
    p3 = v2[CHOSEN]
    p1c = []
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv"); d = d[d.index >= START]
        p1c += position_engine(s, d, "P2 chandelier", start="2024-01-01")
    for t in p1c + p1m:
        t.plan = "Plan 1"
    prop_trades = p1c + p3
    real_trades = p1m + p3
    modes = list(MODES) + ["Edge gate"]
    out = dict(results=[], rolling=[], lots_used=[], lots_recommended=[], period=None)
    first = min(t.entry_time for t in prop_trades); last = max(t.exit_time for t in prop_trades)
    out["period"] = [str(first.date()), str(last.date())]
    for acct in PROP_ACCOUNTS:
        real = Account("Real", acct.fee, acct.fee, None, None, real=True, payout_days=None)
        for m in modes:
            r = run(prop_trades, acct, m)
            q = run(real_trades, real, m)
            for res in (r, q):
                f = pd.DataFrame(res["fills"])
                if len(f):
                    lots = f.groupby("symbol").lots.agg(["median", "max"]).round(2).reset_index().to_dict("records")
                    f.to_csv(f"results/prop_trades_{res['account'].replace(' ', '_').replace('$', '')}_{m.replace(' ', '_')}.csv", index=False)
                else:
                    lots = []
                res["lots"] = lots
                res.pop("fills")
            r["vs_real"] = dict(end_balance=q["end_balance"], net_profit=q["net_profit"], trades=q["trades"],
                                skipped_min_lot=q["skipped_min_lot"], breach=q["breach"], lots=q["lots"], worst_dd_pct=q["worst_dd_pct"])
            r.pop("curve") if m != "Edge gate" else None
            out["results"].append(r)
            print(f"{r['account']:34s} {m:12s} trades {r['trades']:4d} minlot-skip {r['skipped_min_lot']:4d} guard-skip {r['skipped_guard']:4d} "
                  f"breach {str(r['breach']):18s} paid ${r['paid_to_trader']:>9,.0f} net ${r['net_profit']:>9,.0f} ddmax {r['worst_dd_pct']}% | "
                  f"real ${acct.fee:.0f} -> ${q['end_balance']:,.0f} ({q['trades']} trades)")
    # rolling starts: open the account on the 1st of each month, hold 6 months
    starts = pd.date_range("2024-07-01", "2026-05-01", freq="MS", tz="UTC")
    for acct in PROP_ACCOUNTS:
        for m in modes:
            br, pays = 0, []
            for s0 in starts:
                r = run(prop_trades, acct, m, start=s0, end=s0 + pd.DateOffset(months=6))
                br += bool(r["breach"]); pays.append(r["paid_to_trader"])
            out["rolling"].append(dict(account=acct.name, mode=m, starts=len(starts), breached=br,
                                       breach_pct=round(br / len(starts) * 100, 1),
                                       median_paid_6m=round(float(np.median(pays)), 2),
                                       mean_paid_6m=round(float(np.mean(pays)), 2)))
    # recommended lots: median stop distance per symbol and plan
    dist = {}
    for plan, tr in (("Plan 1", p1c), ("Plan 3", p3)):
        for s in SYMBOLS:
            ds = [abs(t.entry - t.stop) for t in tr if t.symbol == s and t.engine in ("position", "levels")]
            dist[(plan, s)] = float(np.median(ds)) if ds else None
    for size in (2_000, 5_000, 10_000, 15_000, 20_000, 25_000, 50_000, 100_000):
        for m, rr in MODES.items():
            for plan in ("Plan 1", "Plan 3"):
                row = dict(account=size, mode=m, plan=plan, risk_pct=rr["p1" if plan == "Plan 1" else "p3"] * 100)
                for s in SYMBOLS:
                    spec = SYMBOLS[s]; dd = dist[(plan, s)]
                    lots = math.floor(size * row["risk_pct"] / 100 / (dd * spec.contract) / spec.lot_step + 1e-9) * spec.lot_step
                    row[s] = round(lots, 2) if lots >= spec.min_lot else 0.0
                out["lots_recommended"].append(row)
    out["stop_distance_median"] = {f"{p}|{s}": round(v, 4) for (p, s), v in dist.items() if v}
    with open("results/prop_study.json", "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(pd.DataFrame(out["rolling"]).to_string())
    return out


if __name__ == "__main__":
    main()

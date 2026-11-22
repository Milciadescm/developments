"""Cueto & Co. cascade: withdraw every 14 days, buy accounts with 50%, 25% to Cueto & Co., 25% personal.
Per-account fortnight payouts come from the backtest (one $100K Instant Premium account, Normal mode,
all closed profit withdrawn every 14 days, started on 16 different months). Paths of 78 fortnights
(3 years) are built by resampling half-year blocks of those real sequences. Every account takes the
same trades, so all accounts get the same payout in a fortnight.
    python -m fibfvg.cascade -> results/cascade.json
"""
import json

import numpy as np
import pandas as pd

from .edgebook import IP100, build
from .propsim import run

FN = pd.Timedelta(days=14)


def fortnight_sequences(trades):
    seqs = []
    for s0 in pd.date_range("2024-08-01", "2025-11-01", freq="MS", tz="UTC"):
        end = min(s0 + pd.Timedelta(days=365), pd.Timestamp("2026-11-20", tz="UTC"))
        n = int((end - s0) / FN)
        sched = [(s0 + (k + 1) * FN, "all") for k in range(n)]
        r = run(trades, IP100, "Normal", start=s0, end=end, schedule=sched, min_payout=100.0)
        seq = np.zeros(n)
        for d, v in r["payout_list"]:
            k = int(round((pd.Timestamp(d, tz="UTC") - s0) / FN)) - 1
            if 0 <= k < n:
                seq[k] += v
        seqs.append(seq)
    return seqs


def simulate(seqs, paths=2000, fortnights=78, fee=740.0, cap=50, block=13, seed=7):
    rng = np.random.default_rng(seed)
    blocks = [s[i:i + block] for s in seqs for i in range(0, len(s) - block + 1, block)]
    res = {k: np.zeros((paths, fortnights)) for k in ("accounts", "cueto", "personal", "paid")}
    first = np.full(paths, np.nan)
    for p in range(paths):
        path = np.concatenate([blocks[rng.integers(len(blocks))] for _ in range(fortnights // block + 1)])[:fortnights]
        acc, pot, cueto, personal, paid = 1, 0.0, 0.0, 0.0, 0.0
        for f in range(fortnights):
            pay = acc * path[f]
            if pay > 0 and np.isnan(first[p]):
                first[p] = f + 1
            paid += pay
            pot += 0.5 * pay; cueto += 0.25 * pay; personal += 0.25 * pay
            buy = int(pot // fee)
            if cap:
                buy = max(0, min(buy, cap - acc))
            acc += buy; pot -= buy * fee
            if cap and acc >= cap and pot > 0:      # at the cap, the reinvest share goes to Cueto & Co.
                cueto += pot; pot = 0.0
            res["accounts"][p, f], res["cueto"][p, f], res["personal"][p, f], res["paid"][p, f] = acc, cueto, personal, paid
    return res, first


def summary(res, first):
    out = {}
    for y, f in (("year 1", 25), ("year 2", 51), ("year 3", 77)):
        row = {}
        for k in ("accounts", "cueto", "personal", "paid"):
            v = res[k][:, f]
            row[k] = dict(worst=float(np.percentile(v, 5)), median=float(np.median(v)), best=float(np.percentile(v, 95)), max=float(v.max()))
        out[y] = row
    out["first_payout_fortnight"] = dict(median=float(np.nanmedian(first)), p90=float(np.nanpercentile(first, 90)), never=float(np.isnan(first).mean()))
    out["p_cueto_100M_by_y3"] = float((res["cueto"][:, 77] >= 1e8).mean())
    # median path per fortnight for the chart
    out["path"] = {k: [dict(f=i + 1, worst=float(np.percentile(res[k][:, i], 5)), median=float(np.median(res[k][:, i])),
                            best=float(np.percentile(res[k][:, i], 95))) for i in range(0, 78, 2)] for k in ("accounts", "cueto")}
    return out


def main():
    _, P = build()
    configs = {"All 5 markets": P["Plan 1 Position"] + P["Plan 3B Levels 2R bank"],
               "BTC + Nasdaq only": [t for t in P["Plan 1 Position"] + P["Plan 3B Levels 2R bank"] if t.symbol in ("BTCUSD", "NAS100")]}
    out = {}
    for name, tr in configs.items():
        seqs = fortnight_sequences(tr)
        yr = [s[:26].sum() for s in seqs]
        for cap in (50, 100, None):
            res, first = simulate(seqs, cap=cap)
            key = f"{name} | cap {cap or 'none'}"
            out[key] = summary(res, first)
            out[key]["one_account_year"] = dict(median=float(np.median(yr)), max=float(max(yr)), min=float(min(yr)))
            s = out[key]
            print(key, "| 1 acct/yr med", round(np.median(yr)), "max", round(max(yr)),
                  "| first payout fortnight med", s["first_payout_fortnight"]["median"], "never", s["first_payout_fortnight"]["never"])
            for y in ("year 1", "year 2", "year 3"):
                print("  ", y, {k: (round(v["worst"]), round(v["median"]), round(v["best"])) for k, v in s[y].items()})
            print("   P(Cueto >= $100M by y3):", s["p_cueto_100M_by_y3"])
    json.dump(out, open("results/cascade.json", "w"), indent=1)


if __name__ == "__main__":
    main()

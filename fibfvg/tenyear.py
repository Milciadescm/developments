"""10-year projection of the Cueto & Co. prop engine (simulation, not a forecast).

Engine: $100K instant accounts, position plan only, 0.5% risk per unit, swaps charged, all closed
profit withdrawn every 14 days. Per-account 14-day rewards are real backtest sequences (16 start
months), resampled in half-year blocks into 10-year paths. All accounts take the same trades.

Wallet rules
  Below the account cap : 50% buys $100K accounts ($740 each), 25% Cueto & Co., 25% crypto cold wallet
  At the account cap    : 70% Cueto & Co., 25% crypto cold wallet, 5% expenses
  Crypto loan           : once the crypto wallet first holds $100K, borrow 20% of its value (10%/yr
                          interest) into a live bot account (own capital, position plan, 14%/yr backtest rate)
Crypto prices are held flat (0%/yr) unless a scenario says otherwise.
    python -m fibfvg.tenyear -> results/tenyear.json
"""
import json

import numpy as np
import pandas as pd

from .edgebook import IP100, build
from . import propsim
from .propsim import run
from .swaps import with_swaps

FN = pd.Timedelta(days=14)
FEE = 740.0


def sequences():
    _, P = build()
    T = with_swaps(P["Plan 1 Position"])
    propsim.MODES["P1"] = dict(p1=0.005, p3=0.0)
    seqs = []
    for s0 in pd.date_range("2024-08-01", "2025-11-01", freq="MS", tz="UTC"):
        end = min(s0 + pd.Timedelta(days=365), pd.Timestamp("2026-11-20", tz="UTC"))
        n = int((end - s0) / FN)
        r = run(T, IP100, "P1", start=s0, end=end, schedule=[(s0 + (k + 1) * FN, "all") for k in range(n)], min_payout=100.0)
        seq = np.zeros(n)
        for d, v in r["payout_list"]:
            k = int(round((pd.Timestamp(d, tz="UTC") - s0) / FN)) - 1
            if 0 <= k < n:
                seq[k] += v
        seqs.append(seq)
    return seqs


def simulate(seqs, cap=50, years=10, paths=2000, decay_after=None, decay=1.0, stop_after=None,
             crypto_growth=0.0, live_rate=0.14, loan_rate=0.10, seed=11):
    rng = np.random.default_rng(seed)
    F = 26 * years
    blocks = [s[i:i + 13] for s in seqs for i in range(0, len(s) - 12, 13)]
    keys = ("accounts", "cueto", "crypto", "expenses", "live", "loan", "rewards")
    yearly = {k: np.zeros((paths, years)) for k in keys}
    for p in range(paths):
        path = np.concatenate([blocks[rng.integers(len(blocks))] for _ in range(F // 13 + 1)])[:F]
        acc, pot, cueto, crypto, exp, live, loan, rew = 1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        for f in range(F):
            y = f / 26
            per = path[f]
            if decay_after is not None and y >= decay_after:
                per *= decay
            if stop_after is not None and y >= stop_after:
                per = 0.0
            pay = acc * per
            rew += pay
            if acc < cap:
                pot += 0.5 * pay; cueto += 0.25 * pay; crypto += 0.25 * pay
                buy = min(int(pot // FEE), cap - acc)
                acc += buy; pot -= buy * FEE
                if acc >= cap:
                    cueto += pot; pot = 0.0
            else:
                cueto += 0.70 * pay; crypto += 0.25 * pay; exp += 0.05 * pay
            crypto *= (1 + crypto_growth) ** (1 / 26)
            if loan == 0.0 and crypto >= 100_000:
                loan = 0.2 * crypto; live += loan
            live *= (1 + live_rate) ** (1 / 26)
            loan *= (1 + loan_rate) ** (1 / 26)          # interest accrues on the loan
            if (f + 1) % 26 == 0:
                yi = (f + 1) // 26 - 1
                for k, v in zip(keys, (acc, cueto, crypto, exp, live, loan, rew)):
                    yearly[k][p, yi] = v
    out = {}
    for k in keys:
        out[k] = [dict(year=y + 1, worst=float(np.percentile(yearly[k][:, y], 5)), median=float(np.median(yearly[k][:, y])),
                       best=float(np.percentile(yearly[k][:, y], 95))) for y in range(years)]
    net = yearly["cueto"] + yearly["crypto"] + yearly["live"] - yearly["loan"]
    out["net_worth"] = [dict(year=y + 1, worst=float(np.percentile(net[:, y], 5)), median=float(np.median(net[:, y])),
                             best=float(np.percentile(net[:, y], 95))) for y in range(years)]
    out["p_100M_by_y3"] = float((net[:, 2] >= 1e8).mean()); out["p_100M_by_y10"] = float((net[:, 9] >= 1e8).mean())
    return out


def main():
    seqs = sequences()
    yr = [s[:26].sum() for s in seqs]
    print("one account, first 12 months paid: median", round(np.median(yr)), "min", round(min(yr)), "max", round(max(yr)),
          "zero-years", sum(1 for v in yr if v == 0), "of", len(yr))
    scen = {
        "Base: 1 firm, 50 accounts": dict(cap=50),
        "Expansion: 3 firms, 150 accounts": dict(cap=150),
        "Edge halves after year 2 (150 cap)": dict(cap=150, decay_after=2, decay=0.5),
        "Prop income stops after year 3 (150 cap)": dict(cap=150, stop_after=3),
        "Crypto falls 50% every year (150 cap)": dict(cap=150, crypto_growth=-0.5),
    }
    out = {"one_account_first_year": dict(median=float(np.median(yr)), min=float(min(yr)), max=float(max(yr)),
                                          zero_years=int(sum(1 for v in yr if v == 0)), starts=len(yr))}
    for name, kw in scen.items():
        res = simulate(seqs, **kw)
        out[name] = res
        nw = res["net_worth"]
        print(name, "| net worth y1/y3/y5/y10 median:", [round(nw[i]["median"]) for i in (0, 2, 4, 9)],
              "| y10 worst/best:", round(nw[9]["worst"]), round(nw[9]["best"]),
              "| accounts y1/y3 median:", round(res["accounts"][0]["median"]), round(res["accounts"][2]["median"]),
              "| P($100M) y3/y10:", res["p_100M_by_y3"], res["p_100M_by_y10"])
    json.dump(out, open("results/tenyear.json", "w"), indent=1)


if __name__ == "__main__":
    main()

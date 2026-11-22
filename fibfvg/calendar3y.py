"""Dated plan for years 1-3 (1 Dec 2026 -> 30 Nov 2029). Simulation, not a promise.

Reward day every 14 days from 15 Dec 2026 (check the firm's dashboard for the real cycle). 2,000 paths drawn
exactly as in wallets3 (real backtest 14-day reward sequences of one $100K account, in half-year blocks).
On every reward day:
  below 50 accounts : 50% -> Wallet 1 pot (buys accounts at $740 the same day), 25% -> Wallet 2, 25% -> Wallet 3
  at 50 accounts    : 70% -> Wallet 2, 25% -> Wallet 3, 5% -> burn reserve until $3,700, then to Wallet 2
Wallet 2: live bot starts the first reward day Wallet 2 holds $100K (half into the bot), rebalanced to 50/50
every quarter, grows at the median backtest year (+14.9%). Crypto held flat; 20% loan once Wallet 3 holds $100K.
Output: for every reward day, the median (and 10th-90th percentile) of accounts, reward, transfers and wallets;
and the date each milestone is reached (median, early 10%, late 10%).
    python -m fibfvg.calendar3y -> results/calendar3y.json
"""
import json

import numpy as np
import pandas as pd

from .wallets3 import prop_sequences

FEE, CAP, RES_FULL = 740.0, 50, 3_700.0
D0 = pd.Timestamp("2026-12-01")
LIVE_YEAR = 0.183          # median one-year bootstrap, gold + silver holding plan at 0.5%
F = 78
COLS = ("accounts", "reward", "to_w1", "bought", "to_w2", "w2_cash", "live", "to_w3", "w3", "reserve")
MILES = ("2 accounts", "5 accounts", "12 accounts", "25 accounts", "50 accounts", "Wallet 2 reaches $100K: live bot starts",
         "Wallet 3 reaches $100K: crypto loan")


def plan(path):
    acc, pot, res, cash, live, w3, loan = 1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    out = np.zeros((F, len(COLS))); miles = {}
    for k in range(F):
        pay = acc * path[k]; bought = 0
        if acc < CAP:
            to1, to2, to3 = 0.5 * pay, 0.25 * pay, 0.25 * pay
            pot += to1
            while pot >= FEE and acc < CAP:
                pot -= FEE; acc += 1; bought += 1
            if acc >= CAP:
                add = min(pot, RES_FULL - res); res += add; to2 += pot - add; pot = 0.0
        else:
            to3 = 0.25 * pay
            to1 = min(0.05 * pay, max(0.0, RES_FULL - res)); res += to1
            to2 = pay - to1 - to3
        cash += to2; w3 += to3
        if live > 0:
            live *= (1 + LIVE_YEAR) ** (14 / 365)
            if (k + 1) % 7 == 0:
                tot = cash + live; move = 0.5 * tot - live; live += move; cash -= move
        if live == 0 and cash >= 100_000:
            live = 0.5 * cash; cash -= live; miles.setdefault(MILES[5], k)
        if loan == 0 and w3 >= 100_000:
            loan = 0.2 * w3; live += loan; miles.setdefault(MILES[6], k)
        for lvl, name in ((2, MILES[0]), (5, MILES[1]), (12, MILES[2]), (25, MILES[3]), (50, MILES[4])):
            if acc >= lvl:
                miles.setdefault(name, k)
        out[k] = (acc, pay, to1, bought, to2, cash, live, to3, w3, res)
    return out, miles


def day(k):
    return D0 + pd.Timedelta(days=14 * (k + 1))


def main():
    seqs = prop_sequences()
    blocks = [s[i:i + 13] for s in seqs for i in range(0, len(s) - 12, 13)]
    rng = np.random.default_rng(5)
    runs, ms = [], []
    for _ in range(2000):
        p = np.concatenate([blocks[rng.integers(len(blocks))] for _ in range(F // 13 + 1)])[:F]
        o, m = plan(p); runs.append(o); ms.append(m)
    A = np.stack(runs)                                   # paths x fortnights x cols
    med = np.median(A, axis=0); p10 = np.percentile(A, 10, axis=0); p90 = np.percentile(A, 90, axis=0)
    rows = []
    for k in range(F):
        r = dict(date=str(day(k).date()), **{c: round(float(med[k, i])) for i, c in enumerate(COLS)})
        r["accounts_p10"] = round(float(p10[k, 0])); r["accounts_p90"] = round(float(p90[k, 0]))
        r["reward_p10"] = round(float(p10[k, 1])); r["reward_p90"] = round(float(p90[k, 1]))
        rows.append(r)
    miles = {}
    for name in MILES:
        ks = np.array([m.get(name, 10_000) for m in ms])
        hit = ks[ks < 10_000]
        miles[name] = dict(reached_pct=round(len(hit) / len(ks) * 100, 1),
                           median=str(day(int(np.median(ks))).date()) if np.median(ks) < 10_000 else "after Nov 2029",
                           early=str(day(int(np.percentile(ks, 10))).date()) if np.percentile(ks, 10) < 10_000 else "after Nov 2029",
                           late=str(day(int(np.percentile(ks, 90))).date()) if np.percentile(ks, 90) < 10_000 else "after Nov 2029")
        print(name, miles[name])
    years = []
    for y in range(3):
        sl = A[:, 26 * y:26 * (y + 1), :]
        tot = sl.sum(axis=1)
        years.append(dict(year=y + 1, rewards=round(float(np.median(tot[:, 1]))), rewards_p10=round(float(np.percentile(tot[:, 1], 10))),
                          rewards_p90=round(float(np.percentile(tot[:, 1], 90))), to_w1=round(float(np.median(tot[:, 2]))),
                          bought=round(float(np.median(tot[:, 3]))), to_w2=round(float(np.median(tot[:, 4]))),
                          to_w3=round(float(np.median(tot[:, 7]))), accounts_end=round(float(np.median(sl[:, -1, 0]))),
                          w2_end=round(float(np.median(sl[:, -1, 5] + sl[:, -1, 6]))), w3_end=round(float(np.median(sl[:, -1, 8])))))
        print(years[-1])
    for r in rows[:26]:
        print(r["date"], r["accounts"], r["accounts_p10"], r["accounts_p90"], r["reward"], r["to_w2"], r["w2_cash"], r["w3"])
    json.dump(dict(rows=rows, milestones=miles, years=years), open("results/calendar3y.json", "w"), indent=1)


if __name__ == "__main__":
    main()

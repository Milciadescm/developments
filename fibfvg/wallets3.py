"""Three wallets, 10 years from 1 December 2026 (simulation, not a forecast).

Wallet 1  Prop firms   : one firm at a time, $100K instant accounts ($740), 24-hour prop plan (prop24) at
                         0.5% risk, rewards every 14 days (real backtest sequences, resampled in half-year blocks).
                         Below 50 accounts: 50% of every reward buys accounts, 25% to Wallet 2, 25% to Wallet 3.
                         At 50 accounts : 70% Wallet 2, 25% Wallet 3, 5% kept as the burn reserve until it holds
                         5 account fees ($3,700); after that the 5% goes to Wallet 2.
                         v2 (22 Nov 2026): prop trades BTC, S&P, Nasdaq at 0.75%; live bot trades gold and silver only.
                         Burned accounts: assumed 2% chance per account per year (none in the backtest); replaced
                         from the reserve (or the buying pot).
Wallet 2  Cueto & Co.  : real funds. The live bot starts once Wallet 2 holds $100K: half goes into the live
                         account, half stays in cash; rebalanced to 50/50 every quarter while the bot is running.
                         Live bot = position plan (holds allowed), 0.5% per unit; monthly returns drawn from the
                         real 2024-2026 monthly returns (livefund) in 3-month blocks. Hard stop: if the live
                         account falls 10% below its high it stops trading until the next quarter's review.
Wallet 3  Crypto       : BTC, ETH, BNB, XRP, LINK, held flat in price (0%/yr) in the base case.
                         Once it first holds $100K, 20% of its value is borrowed (10%/yr) into the live account.
    python -m fibfvg.wallets3 -> results/wallets3.json
"""
import json

import numpy as np
import pandas as pd

from . import propsim
from .propsim import run
from .intraday24 import FN100
from .prop24 import build
from .livefund import monthly, trades as live_trades
from .propsim import Account

FN = pd.Timedelta(days=14)
FEE = 740.0
CAP = 50
LIVE_START = 100_000.0
RESERVE_FULL = 5 * FEE
BURN_P = 0.02 / 26
PROP_MARKETS = ("BTCUSD", "US500", "NAS100")     # markets positive in both halves on the 24-hour plan
PROP_RISK = 0.0075
LIVE_MARKETS = ("XAUUSD", "XAGUSD")              # markets positive in both halves on the holding plan


def prop_sequences(symbols=PROP_MARKETS, risk=PROP_RISK):
    a, b = build()
    T = sorted([t for t in a + b if t.symbol in symbols], key=lambda t: t.entry_time)
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    seqs = []
    for s0 in pd.date_range("2024-03-01", "2025-11-01", freq="MS", tz="UTC"):
        end = min(s0 + pd.Timedelta(days=365), pd.Timestamp("2026-11-20", tz="UTC"))
        n = int((end - s0) / FN)
        r = run(T, FN100, "X", start=s0, end=end, schedule=[(s0 + (k + 1) * FN, "all") for k in range(n)], min_payout=100.0)
        seq = np.zeros(n)
        for d, v in r["payout_list"]:
            k = int(round((pd.Timestamp(d, tz="UTC") - s0) / FN)) - 1
            if 0 <= k < n:
                seq[k] += v
        seqs.append(seq)
    return seqs


def live_returns(symbols=LIVE_MARKETS):
    propsim.MODES["X"] = dict(p1=0.005, p3=0.005)
    o = run([t for t in live_trades() if t.symbol in symbols], Account("Live", 100_000, 0.0, None, None, real=True), "X", start=pd.Timestamp("2024-01-01", tz="UTC"))
    return monthly(o["curve"], 100_000)


def simulate(seqs, lrets, years=10, paths=2000, crypto_growth=0.0, stop_after=None, seed=5):
    rng = np.random.default_rng(seed)
    F = 26 * years
    blocks = [s[i:i + 13] for s in seqs for i in range(0, len(s) - 12, 13)]
    keys = ("accounts", "w1_reserve", "w2_cash", "w2_live", "w2_total", "w3_crypto", "loan", "rewards", "burned")
    Y = {k: np.zeros((paths, years)) for k in keys}
    t50, tlive, w2_down_years, live_loss_years, below_paidin = [], [], 0, 0, 0
    for p in range(paths):
        path = np.concatenate([blocks[rng.integers(len(blocks))] for _ in range(F // 13 + 1)])[:F]
        lpath = np.concatenate([lrets[j:j + 3] for j in rng.integers(0, len(lrets) - 2, years * 4 + 1)])
        acc, pot, res, cash, live, live_hi, crypto, loan, rew, burned = 1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0
        paid_in, started, halted, reached, m = 0.0, False, False, None, 0
        prev_w2, live_year_start = 0.0, 0.0
        for f in range(F):
            y = f / 26
            per = 0.0 if (stop_after is not None and y >= stop_after) else path[f]
            # burned accounts
            lost = rng.binomial(acc, BURN_P)
            if lost:
                burned += lost; acc -= lost
                for _ in range(lost):
                    if res >= FEE:
                        res -= FEE; acc += 1
                    elif pot >= FEE:
                        pot -= FEE; acc += 1
            pay = acc * per; rew += pay
            if acc < CAP and reached is None:
                pot += 0.5 * pay; to2 = 0.25 * pay; crypto += 0.25 * pay
                buy = min(int(pot // FEE), CAP - acc); acc += buy; pot -= buy * FEE
                if acc >= CAP:
                    reached = y; add = min(pot, RESERVE_FULL - res); res += add; cash += pot - add; paid_in += pot - add; pot = 0.0
            else:
                to2 = 0.70 * pay; crypto += 0.25 * pay
                if res < RESERVE_FULL:
                    add = min(0.05 * pay, RESERVE_FULL - res); res += add; to2 += 0.05 * pay - add
                else:
                    to2 += 0.05 * pay
                if acc < CAP:                                   # rebuy burned accounts from the reserve first
                    while acc < CAP and res >= FEE:
                        res -= FEE; acc += 1
            cash += to2; paid_in += to2
            crypto *= (1 + crypto_growth) ** (1 / 26)
            if loan == 0.0 and crypto >= 100_000:
                loan = 0.2 * crypto; live += loan; live_hi = max(live_hi, live)
            loan *= 1.10 ** (1 / 26)
            # monthly step for the live account (every ~2.17 fortnights)
            if int((f + 1) * 12 / 26) > m:
                m = int((f + 1) * 12 / 26)
                if not started and cash + live >= LIVE_START:
                    started = True; tlive.append(y)
                    move = 0.5 * (cash + live) - live; live += move; cash -= move; live_hi = live
                if started or live > 0:
                    if not halted:
                        live *= 1 + lpath[m % len(lpath)]
                    live_hi = max(live_hi, live)
                    if live < 0.90 * live_hi:
                        halted = True
                    if m % 3 == 0:                                 # quarterly review and 50/50 rebalance
                        halted = False
                        if started:
                            tot = cash + live; move = 0.5 * tot - live; live += move; cash -= move; live_hi = max(live_hi * 0 + live, live)
            if (f + 1) % 26 == 0:
                yi = (f + 1) // 26 - 1
                w2 = cash + live - loan
                if yi > 0 and w2 < prev_w2:
                    w2_down_years += 1
                prev_w2 = w2
                if w2 < paid_in - 1:
                    below_paidin += 1
                for k, v in zip(keys, (acc, res, cash, live, cash + live - loan, crypto, loan, rew, burned)):
                    Y[k][p, yi] = v
        t50.append(reached if reached is not None else np.nan)
    out = {k: [dict(year=y + 1, worst=float(np.percentile(Y[k][:, y], 5)), median=float(np.median(Y[k][:, y])),
                    best=float(np.percentile(Y[k][:, y], 95))) for y in range(years)] for k in keys}
    nw = Y["w2_total"] + Y["w3_crypto"] + Y["w1_reserve"]
    out["net_worth"] = [dict(year=y + 1, worst=float(np.percentile(nw[:, y], 5)), median=float(np.median(nw[:, y])),
                             best=float(np.percentile(nw[:, y], 95))) for y in range(years)]
    t50 = np.array(t50)
    out["months_to_50"] = dict(median=round(float(np.nanmedian(t50) * 12), 1), worst=round(float(np.nanpercentile(t50, 95) * 12), 1),
                               best=round(float(np.nanpercentile(t50, 5) * 12), 1), never=int(np.isnan(t50).sum()))
    tl = np.array(tlive)
    out["months_to_live_start"] = dict(median=round(float(np.median(tl) * 12), 1), worst=round(float(np.percentile(tl, 95) * 12), 1),
                                       best=round(float(np.percentile(tl, 5) * 12), 1), never=paths - len(tl))
    out["w2_years_down_pct"] = round(w2_down_years / (paths * (years - 1)) * 100, 2)
    out["w2_below_paid_in_pct"] = round(below_paidin / (paths * years) * 100, 2)
    return out


def main():
    seqs = prop_sequences()
    yr = [s[:26].sum() for s in seqs]
    print("one account, 12 months paid: median", round(np.median(yr)), "min", round(min(yr)), "max", round(max(yr)))
    lr = live_returns()
    res = {"one_account_12m": dict(median=float(np.median(yr)), worst=float(min(yr)), best=float(max(yr)))}
    for name, kw in {"Base": {}, "Crypto falls 50% every year": dict(crypto_growth=-0.5),
                     "Prop income stops after year 3": dict(stop_after=3)}.items():
        o = simulate(seqs, lr, **kw); res[name] = o
        print(name, "| 50 accounts in months", o["months_to_50"], "| live bot starts month", o["months_to_live_start"],
              "| W2 down years %", o["w2_years_down_pct"], "| W2 below paid-in %", o["w2_below_paid_in_pct"])
        for k in ("w2_total", "w3_crypto", "net_worth"):
            print("   ", k, [round(o[k][i]["median"] / 1000) for i in range(10)], "y10 worst", round(o[k][9]["worst"] / 1000))
    json.dump(res, open("results/wallets3.json", "w"), indent=1)


if __name__ == "__main__":
    main()

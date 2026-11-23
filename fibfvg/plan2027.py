"""Two $100K prop accounts through 2027 (simulation from 2024-2026 results, not a promise).

Account A: 6% trailing max loss, FibFVG_Prop24 (BTC, S&P 500, Nasdaq 100; flat within 24 h), 0.75% per trade.
           Bought 1 Dec 2026.
Account B: no drawdown limit, no consistency rule, FibFVG_Hold with AllFiveMarkets (chandelier exit, holds days to
           weeks), 1% per unit, bot hard stop 15%. Bought 1 Mar 2027 with personal funds.
Withdrawals: none until 26 May 2027 -> withdraw all profit (80% split assumed for both firms); then nothing until
           December 2027 -> withdraw the maximum available. Accounts restart at $100K after each withdrawal.
Monthly closed P&L of each bot comes from its 2024-2026 backtest on a $100K account with no withdrawals.
2,000 paths draw those months in 3-month blocks; three replays use real consecutive months instead.
    python -m fibfvg.plan2027 -> results/plan2027.json
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
MONTHS = pd.date_range("2024-07-01", "2026-11-01", freq="MS", tz="UTC")
PLAN = pd.date_range("2026-12-01", "2027-12-01", freq="MS")           # Dec 2026 .. Dec 2027
SPLIT = 0.80


def monthly_pnl(tr, acct, risk):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    o = run(tr, acct, "X", start=START)
    s = pd.Series([v for _, v in o["curve"]], index=pd.to_datetime([a for a, _ in o["curve"]], unit="s", utc=True))
    s = pd.concat([pd.Series([acct.size], index=[START]), s]).groupby(level=0).last()
    m = s.resample("MS").last().ffill()
    m = m.reindex(MONTHS, method="ffill")
    prev = s[s.index < MONTHS[0]].iloc[-1] if (s.index < MONTHS[0]).any() else acct.size
    pnl = m.diff(); pnl.iloc[0] = m.iloc[0] - prev
    return pnl.fillna(0.0), o


def simulate(pa, pb):
    """pa, pb: 13 monthly P&L values for Dec 2026..Dec 2027 (pb used from March 2027).
    Returns month rows and the two withdrawals."""
    rows = []; prof = dict(A=0.0, B=0.0); peak = dict(A=0.0, B=0.0); alive = dict(A=True, B=True); halted = dict(B=False)
    w_may = w_dec = 0.0
    for k, mth in enumerate(PLAN):
        for acc, p in (("A", pa[k]), ("B", pb[k])):
            if acc == "B" and mth < pd.Timestamp("2027-03-01"):
                continue
            if not alive[acc] or (acc == "B" and halted["B"]):
                continue
            prof[acc] += p
            peak[acc] = max(peak[acc], prof[acc])
            if acc == "A" and peak[acc] - prof[acc] >= 6_000:          # 6% trailing line breached
                alive["A"] = False; prof["A"] = 0.0
            if acc == "B" and peak[acc] - prof[acc] >= 15_000:         # bot hard stop: stop trading
                halted["B"] = True
        if mth == pd.Timestamp("2027-05-01"):                         # 26 May 2027
            for acc in ("A", "B"):
                if prof[acc] > 0 and alive[acc]:
                    w_may += SPLIT * prof[acc]; prof[acc] = 0.0; peak[acc] = 0.0
        if mth == pd.Timestamp("2027-12-01"):
            for acc in ("A", "B"):
                if prof[acc] > 0 and alive[acc]:
                    w_dec += SPLIT * prof[acc]; prof[acc] = 0.0
        rows.append((prof["A"], prof["B"], alive["A"]))
    return rows, w_may, w_dec


def main():
    a, b = prop_build()
    P24 = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    HOLD = with_swaps([t for s in SYMBOLS for t in position_engine(s, load(f"data/{s}_D1.csv")[lambda d: d.index >= START], "P2 chandelier", start="2024-01-01")])
    for t in HOLD:
        t.plan = "Plan 1"
    pa, oa = monthly_pnl(P24, Account("6% trailing", 100_000, 740.0, None, 0.06, payout_days=None), 0.0075)
    pb, ob = monthly_pnl(HOLD, Account("No drawdown limit", 100_000, 740.0, None, None, trailing=False, payout_days=None), 0.01)
    print("A monthly P&L 2024-07..2026-11:", [round(x) for x in pa.values], "breach", oa["breach"])
    print("B monthly P&L 2024-07..2026-11:", [round(x) for x in pb.values])
    out = dict(source=dict(A=[round(float(x)) for x in pa.values], B=[round(float(x)) for x in pb.values], months=[str(m.date()) for m in MONTHS]))
    # 2,000 paths, 3-month blocks drawn from the same calendar positions for A and B (keeps their correlation)
    rng = np.random.default_rng(27)
    n = len(MONTHS); res = []
    for _ in range(2000):
        idx = np.concatenate([np.arange(j, j + 3) for j in rng.integers(0, n - 2, 5)])[:13]
        res.append(simulate(pa.values[idx], pb.values[idx]))
    bal = np.array([[r[0] for r in rows] for rows, _, _ in res]), np.array([[r[1] for r in rows] for rows, _, _ in res])
    may = np.array([x[1] for x in res]); dec = np.array([x[2] for x in res]); alive = np.array([rows[-1][2] for rows, _, _ in res])
    table = []
    for k, mth in enumerate(PLAN):
        table.append(dict(month=mth.strftime("%b %Y"),
                          A_median=round(float(np.median(bal[0][:, k]))), A_p10=round(float(np.percentile(bal[0][:, k], 10))), A_p90=round(float(np.percentile(bal[0][:, k], 90))),
                          B_median=round(float(np.median(bal[1][:, k]))), B_p10=round(float(np.percentile(bal[1][:, k], 10))), B_p90=round(float(np.percentile(bal[1][:, k], 90)))))
    q = lambda x: dict(median=round(float(np.median(x))), p10=round(float(np.percentile(x, 10))), p90=round(float(np.percentile(x, 90))),
                       zero_pct=round(float((x <= 0).mean() * 100), 1))
    out["monte_carlo"] = dict(table=table, may_26=q(may), december=q(dec), total_2027=q(may + dec),
                              a_breached_pct=round(float((~alive).mean() * 100), 1))
    print("profit held in each account at month end (median, 10%-90%):")
    for r in table:
        print(f"  {r['month']}: A {r['A_median']:7,d} ({r['A_p10']:7,d} .. {r['A_p90']:7,d})   B {r['B_median']:7,d} ({r['B_p10']:7,d} .. {r['B_p90']:7,d})")
    print("withdrawal 26 May 2027:", out["monte_carlo"]["may_26"], "| December 2027:", out["monte_carlo"]["december"],
          "| total 2027:", out["monte_carlo"]["total_2027"], "| A breached:", out["monte_carlo"]["a_breached_pct"], "%")
    # replays: real consecutive months as if 2027 repeated them
    out["replays"] = {}
    for label, s0 in (("2027 like Dec 2024 - Dec 2025", "2024-12-01"), ("2027 like Dec 2025 - Nov 2026 (+ Nov again)", "2025-11-01"), ("2027 like Jul 2024 - Jul 2025", "2024-07-01")):
        i0 = list(MONTHS).index(pd.Timestamp(s0, tz="UTC"))
        idx = [min(i0 + k, n - 1) for k in range(13)]
        rows, wm, wd = simulate(pa.values[idx], pb.values[idx])
        out["replays"][label] = dict(may_26=round(wm), december=round(wd), total=round(wm + wd),
                                     months=[dict(month=PLAN[k].strftime("%b %Y"), A=round(r[0]), B=round(r[1])) for k, r in enumerate(rows)])
        print(label, "-> May", round(wm), "Dec", round(wd), "total", round(wm + wd))
    json.dump(out, open("results/plan2027.json", "w"), indent=1)


if __name__ == "__main__":
    main()

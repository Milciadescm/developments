"""Wallet book: each wallet's strategy measured on its own, market by market, plus the 6%-a-month test.

Wallet 1 (prop, flat within 24 h)  : prop24 trades.
Wallet 2 (Cueto & Co., holds)      : bot v3 position plan with swaps (each unit counted as a trade).
Per market: trades, win rate, average win / loss in R, reward-to-risk (avg win / avg loss), net R per trade,
first / second half, longest losing streak, worst trade, best trade.
Risk: $100K account month by month at 0.5%; 6%-a-month test at higher risk levels.
    python -m fibfvg.walletbook -> results/walletbook.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .engines import net_r
from . import propsim
from .propsim import Account, run
from .intraday24 import FN100, START
from .prop24 import build
from .livefund import trades as live_trades, monthly, max_dd

SPLIT = pd.Timestamp("2025-08-19", tz="UTC")


def streak(r):
    best = cur = 0
    for x in r:
        cur = cur + 1 if x <= 0 else 0
        best = max(best, cur)
    return best


def table(items):
    """items: list of (symbol, time, R)"""
    rows = {}
    for s in list(SYMBOLS) + ["All"]:
        xs = sorted([(t, r) for (sy, t, r) in items if s == "All" or sy == s])
        if not xs:
            continue
        r = np.array([v for _, v in xs]); w, l = r[r > 0], r[r <= 0]
        a = np.array([v for t, v in xs if t < SPLIT]); b = np.array([v for t, v in xs if t >= SPLIT])
        rows[s] = dict(trades=len(r), win_rate=round(float((r > 0).mean() * 100), 1),
                       avg_win=round(float(w.mean()), 2) if len(w) else 0.0, avg_loss=round(float(l.mean()), 2) if len(l) else 0.0,
                       rr=round(float(w.mean() / -l.mean()), 2) if len(w) and len(l) and l.mean() < 0 else None,
                       net=round(float(r.mean()), 3), first=round(float(a.mean()), 3) if len(a) else None,
                       second=round(float(b.mean()), 3) if len(b) else None, losing_streak=streak(r),
                       worst=round(float(r.min()), 2), best=round(float(r.max()), 2),
                       both_halves_positive=bool(len(a) and len(b) and a.mean() > 0 and b.mean() > 0))
    return rows


def month_stats(curve, cap):
    rets = monthly(curve, cap)
    return dict(avg_month=round(float(rets.mean() * 100), 2), median_month=round(float(np.median(rets) * 100), 2),
                worst_month=round(float(rets.min() * 100), 2), best_month=round(float(rets.max() * 100), 2),
                months_ge_6=int((rets >= 0.06).sum()), months=len(rets), months_down=int((rets < 0).sum()),
                max_dd=round(max_dd(rets) * 100, 1))


def main():
    a, b = build()
    prop = sorted(a + b, key=lambda t: t.entry_time)
    live = live_trades()
    out = dict(wallet1=dict(by_market=table([(t.symbol, t.entry_time, t.net) for t in prop])),
               wallet2=dict(by_market=table([(t.symbol, t.entry_time, net_r(t)) for t in live])))
    for k in ("wallet1", "wallet2"):
        print(k)
        for s, v in out[k]["by_market"].items():
            print(f"  {s:7s} n {v['trades']:3d} win {v['win_rate']:5.1f}% avgW {v['avg_win']:+.2f} avgL {v['avg_loss']:+.2f} RR {v['rr']} net {v['net']:+.3f} halves {v['first']}/{v['second']} streak {v['losing_streak']}")
    # month-by-month risk and the 6%-a-month test
    out["six_pct"] = dict(prop=[], live=[])
    for r in (0.005, 0.01, 0.015, 0.02, 0.03):
        propsim.MODES["X"] = dict(p1=r, p3=r)
        o = run(prop, Account("FundedNext instant", 100_000, 740.0, None, 0.06, payout_days=None), "X", start=START)
        g = run(prop, Account("No limit", 100_000, 0.0, None, None, payout_days=None), "X", start=START)
        row = dict(risk=r * 100, with_6pct_line=dict(breach=o["breach"], profit=round(o["end_balance"] - 100_000)),
                   no_line=month_stats(g["curve"], 100_000))
        out["six_pct"]["prop"].append(row); print("prop", row)
        o = run(live, Account("Live", 100_000, 0.0, None, None, real=True), "X", start=START)
        row = dict(risk=r * 100, end=round(o["end_balance"]), **month_stats(o["curve"], 100_000))
        out["six_pct"]["live"].append(row); print("live", row)
    json.dump(out, open("results/walletbook.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()

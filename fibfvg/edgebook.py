"""Edge book: everything that makes money, 2024 -> now, in one run.
    python -m fibfvg.edgebook   -> results/edge_book.json, results/trades_*.csv, results/roadmap.json

Plans kept (all others were tested and removed, see RESEARCH_LOG.md):
  Plan 1  Position      : MN+W bias, D1 Turtle breakout leg with FVG, 0.705 OTE limit, Turtle adds,
                          chandelier exit (highest high - 3N), breakeven at +1R, 10-day time stop.
  Plan 3  Levels        : W bias, 1H reaction at 00/20/50/60/80 levels (no NY lunch), stop 1 daily ATR,
                          breakeven at +1R, 5-day-low trail from +2R, adds while the first unit is >= +1R.
  Plan 3B Levels 2R bank: Plan 3 + half of every unit closed at +2R (NEW default; steadier rewards).
"""
import json

import numpy as np
import pandas as pd

from .calendar import CPI, news_days
from .config import SYMBOLS
from .engines import atr, load, net_r
from .levels import engine as levels_engine, load_sym
from .plans import position_engine
from .propsim import Account, run
from . import roadmap as RM

START = pd.Timestamp("2024-01-01", tz="UTC")
SPLIT = pd.Timestamp("2025-08-19", tz="UTC")       # median entry date: first half decides, second half checks
PIP = {"XAUUSD": 0.1, "XAGUSD": 0.01, "BTCUSD": 1.0, "US500": 0.1, "NAS100": 0.1}
IP100 = Account("Instant Premium", 100_000, 740.0, 0.03, 0.06, refundable=True)


def build():
    data = {s: load_sym(s) for s in SYMBOLS}
    p1 = []
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv"); d = d[d.index >= START]
        p1 += position_engine(s, d, "P2 chandelier", start="2024-01-01")
    for t in p1:
        t.plan = "Plan 1"

    def p3(name, **kw):
        out = [t for s, (d, h) in data.items()
               for t in levels_engine(s, d, h, "X4 weeklow", stop_mode="datr", kz=False, ts_bars=120, **kw)]
        for t in out:
            t.plan = "Plan 3"; t.variant = name
        return out
    return data, {"Plan 1 Position": p1, "Plan 3 Levels": p3("Plan 3"), "Plan 3B Levels 2R bank": p3("Plan 3B", half_at=2.0)}


def plan_stats(tr):
    r = np.array([net_r(t) for t in tr])
    w, l = r[r > 0], r[r <= 0]
    pips = np.array([(sum(f * (p - t.entry) for _, p, f in t.exits) * t.direction) / PIP[t.symbol] for t in tr])
    a = np.array([net_r(t) for t in tr if t.entry_time < SPLIT]); b = np.array([net_r(t) for t in tr if t.entry_time >= SPLIT])
    return dict(trades=len(r), net_r=round(r.mean(), 3), first_half=round(a.mean(), 3), second_half=round(b.mean(), 3),
                win_rate=round((r > 0).mean() * 100, 1), avg_win_r=round(w.mean(), 2), avg_loss_r=round(l.mean(), 2),
                realized_rr=round(w.mean() / -l.mean(), 2), r10=int((r >= 10).sum()), best_r=round(r.max(), 1),
                avg_win_pips=round(float(pips[pips > 0].mean()), 0), avg_loss_pips=round(float(pips[pips <= 0].mean()), 0),
                by_symbol={s: round(float(np.mean([net_r(t) for t in tr if t.symbol == s])), 3) for s in SYMBOLS if any(t.symbol == s for t in tr)})


def main():
    data, P = build()
    out = {"period": None, "pips": {}, "plans": {}, "prop": [], "weak_spots": {}, "roadmap": None}
    allt = [t for v in P.values() for t in v]
    out["period"] = [str(min(t.entry_time for t in allt).date()), str(max(t.exit_time for t in allt).date())]
    for s in SYMBOLS:
        d, h = data[s]
        rng = (d.High - d.Low) / PIP[s]
        out["pips"][s] = dict(pip=PIP[s], median_day=round(rng.median()), mean_day=round(rng.mean()),
                              p25=round(rng.quantile(.25)), p75=round(rng.quantile(.75)), atr14_now=round(atr(d, 14).iloc[-1] / PIP[s]))
    for name, tr in P.items():
        out["plans"][name] = plan_stats(tr)
    # weak spots (informational: first entries of Plan 3)
    nd = news_days()
    f3 = [t for t in P["Plan 3 Levels"] if t.engine == "levels"]
    df = pd.DataFrame(dict(r=[net_r(t) for t in f3], half=["first" if t.entry_time < SPLIT else "second" for t in f3],
                           dow=[t.entry_time.tz_convert("America/New_York").dayofweek for t in f3],
                           news=["|".join(nd.get(str(t.entry_time.tz_convert("America/New_York").date()), [])) or "none" for t in f3]))
    out["weak_spots"]["by_weekday"] = df.groupby(["dow", "half"]).r.mean().round(3).unstack().reset_index().to_dict("records")
    out["weak_spots"]["by_news"] = df.groupby(["news", "half"]).r.agg(["count", "mean"]).round(3).reset_index().to_dict("records")
    # prop: Instant Premium $100K, Normal vs Aggressive, Core vs Core + 2R bank
    portfolios = {"Core (Plan 1 + Plan 3)": P["Plan 1 Position"] + P["Plan 3 Levels"],
                  "New: Core + 2R bank (Plan 1 + Plan 3B)": P["Plan 1 Position"] + P["Plan 3B Levels 2R bank"]}
    for pname, tr in portfolios.items():
        for mode in ("Normal", "Aggressive"):
            r = run(tr, IP100, mode)
            fills = pd.DataFrame(r["fills"])
            fills.to_csv(f"results/trades_{'core2r' if '2R' in pname else 'core'}_{mode.lower()}_IP100K.csv", index=False)
            lots = fills.groupby("symbol").lots.agg(["median", "max"]).round(2).reset_index().to_dict("records")
            out["prop"].append(dict(portfolio=pname, mode=mode, trades=r["trades"], paid=r["paid_to_trader"], net=r["net_profit"],
                                    rewards=r["payouts"], worst_dd=r["worst_dd_pct"], breach=r["breach"],
                                    first_reward=r["payout_list"][0] if r["payout_list"] else None, lots=lots))
            print(f"{pname:42s} {mode:10s} paid ${r['paid_to_trader']:>9,.0f} rewards {r['payouts']:3d} worst DD {r['worst_dd_pct']}% breach {r['breach']}")
    # 12-month roadmap from 16 start months
    starts = pd.date_range("2024-08-01", "2025-11-01", freq="MS", tz="UTC")
    rm = []
    for pname, tr in portfolios.items():
        for mode in ("Normal", "Aggressive"):
            for s0 in starts:
                x = RM.roadmap(tr, mode, s0, cap_accounts=6); x.update(portfolio=pname); rm.append(x)
    json.dump(rm, open("results/roadmap.json", "w"), indent=1, default=str)
    rdf = pd.DataFrame(rm)
    out["roadmap"] = [dict(portfolio=p, mode=m, starts=len(g), month1_reward_pct=round(float((g.month1_paid > 0).mean() * 100), 0),
                           first_reward_within_90d_pct=round(float(np.mean([x is not None and (pd.Timestamp(x[0], tz="UTC") - pd.Timestamp(s, tz="UTC")).days <= 92 for x, s in zip(g.first_reward, g.start)]) * 100), 0),
                           month3_major_median=round(float(g.month3_major.median()), 2), accounts_end_median=float(g.accounts_at_end.median()),
                           accounts_end_max=int(g.accounts_at_end.max()), net_12m_median=round(float(g.net_to_you.median()), 2),
                           net_12m_min=round(float(g.net_to_you.min()), 2), net_12m_max=round(float(g.net_to_you.max()), 2),
                           breaches=int(sum(len(b) for b in g.breaches)))
                      for (p, m), g in rdf.groupby(["portfolio", "mode"])]
    json.dump(out, open("results/edge_book.json", "w"), indent=1, default=str)
    print(json.dumps(out["plans"], indent=1)); print(pd.DataFrame(out["roadmap"]).to_string())
    return out


if __name__ == "__main__":
    main()

"""Run both plans, every exit style, IS/OOS selection, portfolio results.
    python -m fibfvg.plans_study  -> results/plans.json
"""
import json

import numpy as np
import pandas as pd

from .config import CAPITAL_TIERS, SYMBOLS, RiskConfig
from .engines import load
from .experiments import net_r
from .plans import MICRO_MODES, POS_MODES, TFS, intraday_engine, load_tf, position_engine
from .simulator import simulate, stats

SPLIT1 = pd.Timestamp("2016-01-01", tz="UTC")


def summ(rs):
    rs = np.asarray(rs, float)
    if not len(rs):
        return dict(n=0, avg=None, total=0.0, win=None)
    return dict(n=int(len(rs)), avg=round(float(rs.mean()), 3), total=round(float(rs.sum()), 1),
                win=round(float((rs > 0).mean() * 100), 1))


def hold_days(t):
    return (t.exit_time - t.entry_time).total_seconds() / 86400


def main():
    daily = {s: load(f"data/{s}_D1.csv") for s in SYMBOLS}
    out = {"plan1": {}, "plan2": {}}
    # ---------------- PLAN 1
    p1_trades = {}
    for mode in POS_MODES:
        tr = [t for s in SYMBOLS for t in position_engine(s, daily[s], mode)]
        p1_trades[mode] = tr
        main_ = [t for t in tr if t.engine == "position"]
        allr = lambda sel: [net_r(t) for t in sel]
        res = dict(
            IS=summ(allr([t for t in tr if t.entry_time < SPLIT1])),
            OOS=summ(allr([t for t in tr if t.entry_time >= SPLIT1])),
            main_IS=summ(allr([t for t in main_ if t.entry_time < SPLIT1])),
            main_OOS=summ(allr([t for t in main_ if t.entry_time >= SPLIT1])),
            hold_median_days=round(float(np.median([hold_days(t) for t in main_])), 1),
            hold_p90_days=round(float(np.percentile([hold_days(t) for t in main_], 90)), 1),
            avg_loss_R=round(float(np.mean([net_r(t) for t in main_ if net_r(t) <= 0])), 3),
            avg_win_R=round(float(np.mean([net_r(t) for t in main_ if net_r(t) > 0])), 3),
            best_R=round(float(max(net_r(t) for t in tr)), 2),
        )
        st = stats(simulate(tr, 50_000, RiskConfig(weekly_unit_risk=0.005)), 50_000)
        res["sim_50k"] = {k: st[k] for k in ("trades", "final", "cagr_pct", "max_dd", "pf", "win_rate")}
        for lo, hi, nm in (("2005", "2016", "IS"), ("2016", "2027", "OOS")):
            sub = [t for t in tr if pd.Timestamp(lo, tz="UTC") <= t.entry_time < pd.Timestamp(hi, tz="UTC")]
            s2 = stats(simulate(sub, 50_000, RiskConfig(weekly_unit_risk=0.005)), 50_000)
            res[f"sim_{nm}"] = {k: s2[k] for k in ("trades", "final", "cagr_pct", "max_dd", "pf")}
        res["by_symbol_OOS"] = {s: summ(allr([t for t in tr if t.symbol == s and t.entry_time >= SPLIT1])) for s in SYMBOLS}
        out["plan1"][mode] = res
    pick1 = max(POS_MODES, key=lambda m: out["plan1"][m]["IS"]["avg"])
    out["plan1_pick"] = pick1
    # ---------------- PLAN 2
    p2_trades = {}
    for tf in TFS:
        out["plan2"][tf] = {}
        bars = {s: load_tf(s, tf) for s in SYMBOLS}
        for mode in MICRO_MODES:
            tr = [t for s in SYMBOLS for t in intraday_engine(s, bars[s], daily[s], tf, mode)]
            p2_trades[(tf, mode)] = tr
            ts = sorted(t.entry_time for t in tr)
            mid = ts[len(ts) // 2] if ts else None
            r = dict(
                IS=summ([net_r(t) for t in tr if t.entry_time < mid]) if mid else summ([]),
                OOS=summ([net_r(t) for t in tr if t.entry_time >= mid]) if mid else summ([]),
                ALL=summ([net_r(t) for t in tr]),
                gross=summ([t.r_multiple for t in tr]),
                hold_median_bars=round(float(np.median([hold_days(t) * 1440 / TFS[tf] for t in tr])), 1) if tr else None,
                avg_loss_R=round(float(np.mean([net_r(t) for t in tr if net_r(t) <= 0])), 3) if tr else None,
                avg_win_R=round(float(np.mean([net_r(t) for t in tr if net_r(t) > 0])), 3) if tr else None,
                days=round((ts[-1] - ts[0]).days, 0) if tr else 0,
                mon_wed=summ([net_r(t) for t in tr if t.entry_time.dayofweek <= 2]),
                thu_fri=summ([net_r(t) for t in tr if t.entry_time.dayofweek in (3, 4)]),
                by_symbol={s: summ([net_r(t) for t in tr if t.symbol == s]) for s in SYMBOLS},
            )
            out["plan2"][tf][mode] = r
        pick = max(MICRO_MODES, key=lambda m: (out["plan2"][tf][m]["IS"]["avg"] or -9))
        out["plan2"][tf]["pick"] = pick
    # combined: plan 1 pick + plan 2 1H pick (longest intraday sample), portfolio by tier
    p2_pick = out["plan2"]["1H"]["pick"]
    combo = [t for t in p1_trades[pick1] if t.entry_time >= pd.Timestamp("2024-07-03", tz="UTC")]
    micro = p2_trades[("1H", p2_pick)]
    for t in micro:
        t.engine = "micro"
    rk = RiskConfig(weekly_unit_risk=0.005, micro_risk=0.0025)
    tiers = []
    for cap in CAPITAL_TIERS:
        st = stats(simulate(combo + micro, cap, rk), cap)
        tiers.append(dict(capital=cap, **{k: st[k] for k in ("trades", "final", "ret_pct", "cagr_pct", "max_dd", "pf", "min_lot")}))
    out["combined_recent_tiers"] = tiers
    out["plan1_tiers"] = []
    for cap in CAPITAL_TIERS:
        st = stats(simulate(p1_trades[pick1], cap, RiskConfig(weekly_unit_risk=0.005)), cap)
        out["plan1_tiers"].append(dict(capital=cap, **{k: st[k] for k in ("trades", "final", "ret_pct", "cagr_pct", "max_dd", "pf", "min_lot")}))
    alt = "P2 chandelier"
    for wr in (0.001, 0.0025):
        st = stats(simulate([t for t in p1_trades[alt] if t.entry_time >= pd.Timestamp("2016-01-01", tz="UTC")], 50_000,
                            RiskConfig(weekly_unit_risk=wr, daily_loss_limit=0.03, max_loss_limit=0.06)), 50_000)
        out[f"prop_chandelier_{wr}"] = {k: st[k] for k in ("trades", "final", "cagr_pct", "max_dd", "breach")}
    full = stats(simulate(p1_trades[pick1], 50_000, RiskConfig(weekly_unit_risk=0.005)), 50_000)
    out["plan1_full_50k"] = full
    res = simulate(p1_trades[pick1], 50_000, RiskConfig(weekly_unit_risk=0.005))
    out["plan1_curve"] = [[int(t.timestamp()), round(b, 2)] for t, b in res["curve"] if t is not None]
    with open("results/plans.json", "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    return out, p1_trades, p2_trades, daily


if __name__ == "__main__":
    out, *_ = main()
    for m, r in out["plan1"].items():
        print(f"{m:14s} IS {r['IS']['avg']:+.3f} OOS {r['OOS']['avg']:+.3f} | main IS {r['main_IS']['avg']} OOS {r['main_OOS']['avg']} "
              f"| hold med {r['hold_median_days']}d p90 {r['hold_p90_days']}d | loss {r['avg_loss_R']} win {r['avg_win_R']} best {r['best_R']} "
              f"| 50k IS {r['sim_IS']['cagr_pct']}%/{r['sim_IS']['max_dd']}% OOS {r['sim_OOS']['cagr_pct']}%/{r['sim_OOS']['max_dd']}% full {r['sim_50k']['cagr_pct']}%/{r['sim_50k']['max_dd']}%")
    print("pick1", out["plan1_pick"])
    for tf, d in out["plan2"].items():
        for m in MICRO_MODES:
            r = d[m]
            print(f"{tf:4s} {m:12s} n={r['ALL']['n']:4d} days={r['days']} IS {r['IS']['avg']} OOS {r['OOS']['avg']} gross {r['gross']['avg']} "
                  f"loss {r['avg_loss_R']} win {r['avg_win_R']} hold {r['hold_median_bars']}b MW {r['mon_wed']['avg']} TF {r['thu_fri']['avg']}")
        print("  pick", d["pick"])
    print(pd.DataFrame(out["combined_recent_tiers"]).to_string())

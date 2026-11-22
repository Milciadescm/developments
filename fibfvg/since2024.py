"""Backtest 2024 -> now using ONLY 2024+ data.
Plan 1  : position engine (monthly exit), daily bars from 2024-01-01 only.
Plan 3  : quarter levels x reactions (+ kill-zone variant), 1H bars, pyramiding on profit.
    python -m fibfvg.since2024  -> results/since2024.json (+ replay files)
"""
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from .config import CAPITAL_TIERS, SYMBOLS, RiskConfig
from .engines import load
from .experiments import net_r
from .levels import EXITS, V2, engine, load_sym
from .plans import position_engine
from .simulator import simulate, stats

START = pd.Timestamp("2024-01-01", tz="UTC")
CHOSEN = "D-week · all hours"
KZ = "D-week · kill zones"


def summ(rs):
    rs = np.asarray(rs, float)
    return dict(n=int(len(rs)), avg=round(float(rs.mean()), 3) if len(rs) else None, total=round(float(rs.sum()), 1),
                win=round(float((rs > 0).mean() * 100), 1) if len(rs) else None,
                r10=int((rs >= 10).sum()), r50=int((rs >= 50).sum()), best=round(float(rs.max()), 1) if len(rs) else None)


def build():
    data = {s: load_sym(s) for s in SYMBOLS}
    p1 = []
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv")
        d = d[d.index >= START]
        p1 += position_engine(s, d, "P3 monthly", start="2024-01-01")
    for t in p1:
        t.plan = "Plan 1"
    v1 = {}
    for X in EXITS:
        v1[X] = [t for s, (d, h) in data.items() for t in engine(s, d, h, X)]
    v2 = {}
    for name, v in V2.items():
        v2[name] = [t for s, (d, h) in data.items()
                    for t in engine(s, d, h, v["exit"], stop_mode=v["stop"], kz=v["kz"], ts_bars=v["ts"])]
        for t in v2[name]:
            t.plan = "Plan 3"
    return data, p1, v1, v2


def as_micro(trs):
    out = []
    for t in trs:
        t2 = t
        t2.engine_orig = t.engine
        t2.engine = "micro"          # sized with micro_risk, no Turtle caps; open-risk cap still applies
        out.append(t2)
    return out


def main():
    data, p1, v1, v2 = build()
    out = {"tight_stop_v1": {}, "v2": {}}
    for X, tr in v1.items():
        ts = sorted(t.entry_time for t in tr); mid = ts[len(ts) // 2]
        out["tight_stop_v1"][X] = dict(ALL=summ([net_r(t) for t in tr]), gross=summ([t.r_multiple for t in tr]),
                                       IS=summ([net_r(t) for t in tr if t.entry_time < mid]),
                                       OOS=summ([net_r(t) for t in tr if t.entry_time >= mid]))
    for name, tr in v2.items():
        ts = sorted(t.entry_time for t in tr); mid = ts[len(ts) // 2]
        out["v2"][name] = dict(ALL=summ([net_r(t) for t in tr]), gross=summ([t.r_multiple for t in tr]),
                               IS=summ([net_r(t) for t in tr if t.entry_time < mid]),
                               OOS=summ([net_r(t) for t in tr if t.entry_time >= mid]),
                               firsts=summ([net_r(t) for t in tr if t.engine == "levels"]),
                               adds=summ([net_r(t) for t in tr if t.engine == "levels_add"]),
                               hold_days=round(float(np.median([(t.exit_time - t.entry_time).total_seconds() / 86400 for t in tr])), 1),
                               by_symbol={s: summ([net_r(t) for t in tr if t.symbol == s]) for s in SYMBOLS},
                               by_hour={int(h): summ([net_r(t) for t in tr if t.engine == "levels" and t.kz_hour == h])
                                        for h in sorted({t.kz_hour for t in tr})},
                               by_level={n: summ([net_r(t) for t in tr if t.engine == "levels" and t.level_name == n])
                                         for n in ("00", "20", "50", "60", "80")},
                               mid=str(mid.date()))
    out["plan1"] = dict(ALL=summ([net_r(t) for t in p1]), main=summ([net_r(t) for t in p1 if t.engine == "position"]))
    # ---- portfolio: Plan 1 (0.5%/unit) + Plan 3 chosen (x% per unit)
    p3 = as_micro(v2[CHOSEN])
    sweep = []
    for mr in (0.001, 0.0025, 0.005, 0.01):
        rk = RiskConfig(weekly_unit_risk=0.005, micro_risk=mr, max_open_risk=0.08)
        st = stats(simulate(p1 + p3, 50_000, rk), 50_000)
        sweep.append(dict(plan3_risk=mr, **{k: st[k] for k in ("trades", "final", "ret_pct", "cagr_pct", "max_dd", "pf", "win_rate")}))
    out["risk_sweep_50k"] = sweep
    for label, tr in (("Plan 1 only", p1), ("Plan 3 only", p3), ("Plan 1 + Plan 3", p1 + p3)):
        st = stats(simulate(tr, 50_000, RiskConfig(weekly_unit_risk=0.005, micro_risk=0.0025, max_open_risk=0.08)), 50_000)
        out.setdefault("plans_50k", []).append(dict(plan=label, **{k: st[k] for k in ("trades", "final", "ret_pct", "cagr_pct", "max_dd", "pf", "win_rate", "years")}))
    rk = RiskConfig(weekly_unit_risk=0.005, micro_risk=0.0025, max_open_risk=0.08)
    tiers = []
    for cap in CAPITAL_TIERS:
        r_ = rk if cap != 50_000 else replace(rk, weekly_unit_risk=0.0025, micro_risk=0.001,
                                              daily_loss_limit=0.03, max_loss_limit=0.06)
        st = stats(simulate(p1 + p3, cap, r_), cap)
        tiers.append(dict(capital=cap, prop=cap == 50_000, **{k: st[k] for k in ("trades", "final", "ret_pct", "cagr_pct", "max_dd", "pf", "min_lot", "breach")}))
    out["tiers"] = tiers
    res = simulate(p1 + p3, 50_000, rk)
    out["curve"] = [[int(t.timestamp()), round(b, 2)] for t, b in res["curve"] if t is not None]
    for t in p3:
        t.engine = t.engine_orig
    with open("results/since2024.json", "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    return out, data, p1, v2


if __name__ == "__main__":
    out, *_ = main()
    for k, v in out["v2"].items():
        print(k, v["ALL"], "firsts", v["firsts"]["avg"], "adds", v["adds"]["avg"])
    print("by level", {k: v["avg"] for k, v in out["v2"][CHOSEN]["by_level"].items()})
    print("by hour (KZ var)", {k: (v["avg"], v["n"]) for k, v in out["v2"][KZ]["by_hour"].items()})
    print("plan1", out["plan1"])
    print(pd.DataFrame(out["plans_50k"]).to_string())
    print(pd.DataFrame(out["risk_sweep_50k"]).to_string())
    print(pd.DataFrame(out["tiers"]).to_string())

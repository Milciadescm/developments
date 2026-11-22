"""Experiments requested after v1:

1. "Duality" / inversion: when a component loses, take the opposite side.
   Two fade designs are replayed on real bars:
     fade_mirror : opposite direction, stop at the original final target,
                   target at the original stop (exact mirror of the bet)
     fade_1to1   : opposite direction, stop at the original stop distance,
                   target at the original stop (1:1)
2. Time before price: pre-registered time filters
     fib_delay   : enter only if the fill happens a Fibonacci number of bars
                   (1,2,3,5,8,13) after the setup formed
     early_week  : weekly engine fills Monday-Wednesday only
                   (weekly high/low tends to form early in the week)
     killzones   : micro engine fills only in London (07-10 UTC) or
                   New York (12-16 UTC) sessions
Every choice is made on the IN-SAMPLE period and judged on OUT-OF-SAMPLE:
  weekly engine : IS 2005-2015, OOS 2016-2026
  micro engine  : IS before 2025-06-01, OOS after
"""
from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd

from .config import SYMBOLS, EngineConfig, RiskConfig
from .engines import Trade, load, micro_engine, to_4h, weekly_engine
from .simulator import simulate, stats

FIB = {1, 2, 3, 5, 8, 13, 21}
SPLIT = {"D1": pd.Timestamp("2016-01-01", tz="UTC"), "H4": pd.Timestamp("2025-06-01", tz="UTC")}


def build(cfg=EngineConfig()):
    data, trades, logs = {}, [], {}
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv")
        h4 = to_4h(load(f"data/{s}_H1.csv"))
        data[s] = {"D1": d, "H4": h4}
        lg = []
        trades += weekly_engine(s, d, cfg, lg) + micro_engine(s, h4, d, cfg, lg)
        logs[s] = lg
    return data, trades, logs


def net_r(t: Trade) -> float:
    spec = SYMBOLS[t.symbol]
    return t.r_multiple - spec.spread / abs(t.entry - t.stop)


def fade(t: Trade, bars: pd.DataFrame, kind: str, max_hold: int) -> Trade | None:
    d = -t.direction
    e = t.entry
    if kind == "fade_mirror":
        stop, tgt = t.tp_final, t.stop
    else:
        stop, tgt = e - d * abs(e - t.stop), t.stop
    if (stop - e) * d >= 0 or (tgt - e) * d <= 0:
        return None
    off = pd.Timedelta(hours=12) if t.tf == "D1" else pd.Timedelta(hours=4)
    o, h, l, c = (bars[k].values for k in ("Open", "High", "Low", "Close"))
    f = Trade(t.symbol, t.engine if t.engine == "micro" else "weekly", d, t.entry_time, e, stop)
    f.tf, f.bar, f.tp_final, f.fill_delay = t.tf, t.bar, tgt, t.fill_delay
    f.kind = kind
    for i in range(t.bar, min(len(c), t.bar + max_hold)):
        adverse = h[i] >= stop if d == -1 else l[i] <= stop
        fav = l[i] <= tgt if d == -1 else h[i] >= tgt
        tm = bars.index[i] + off
        if adverse:   # conservative: stop first
            px = stop if i == t.bar else (max(o[i], stop) if d == -1 else min(o[i], stop))
            f.exits.append((tm, px, 1.0)); return f
        if fav:
            px = tgt if i == t.bar else (min(o[i], tgt) if d == -1 else max(o[i], tgt))
            f.exits.append((tm, px, 1.0)); return f
    i = min(len(c), t.bar + max_hold) - 1
    f.exits.append((bars.index[i] + off, c[i], 1.0))
    return f


def era(t):
    return "IS" if t.entry_time < SPLIT[t.tf] else "OOS"


def agg(rs):
    rs = np.asarray(rs, float)
    return dict(n=int(len(rs)), avg=round(float(rs.mean()), 3) if len(rs) else None,
                total=round(float(rs.sum()), 1), win=round(float((rs > 0).mean() * 100), 1) if len(rs) else None)


def main():
    data, trades, logs = build()
    base = [t for t in trades if t.engine in ("weekly", "micro")]
    adds = [t for t in trades if t.engine == "weekly_add"]
    out = {"inversion": [], "time": [], "notes": {}}

    # ---------------- 1. inversion
    fades = {}
    for kind in ("fade_mirror", "fade_1to1"):
        fades[kind] = []
        for t in base:
            f = fade(t, data[t.symbol][t.tf], kind, 60 if t.tf == "D1" else 30)
            if f is not None:
                f.src = t
                fades[kind].append(f)
    for s in SYMBOLS:
        for eng in ("weekly", "micro"):
            orig = [t for t in base if t.symbol == s and t.engine == eng]
            row = dict(symbol=s, engine=eng)
            for e in ("IS", "OOS"):
                row[f"orig_{e}"] = agg([net_r(t) for t in orig if era(t) == e])
                for kind in fades:
                    row[f"{kind}_{e}"] = agg([net_r(f) for f in fades[kind]
                                              if f.symbol == s and f.engine == eng and era(f) == e])
            # decision rule, decided on IS only: invert if the best fade beats the original by > 0.05R in IS
            cand = {k: row[f"{k}_IS"]["avg"] for k in fades if row[f"{k}_IS"]["n"] >= 15}
            o_is = row["orig_IS"]["avg"]
            pick = "original"
            if cand and o_is is not None:
                best = max(cand, key=cand.get)
                if cand[best] > o_is + 0.05 and cand[best] > 0:
                    pick = best
            row["pick_from_IS"] = pick
            oos_key = "orig_OOS" if pick == "original" else f"{pick}_OOS"
            row["picked_OOS"] = row[oos_key]
            row["orig_OOS_avg"] = row["orig_OOS"]["avg"]
            out["inversion"].append(row)
    # all-in fades (what "always reverse" would have done)
    for kind in fades:
        out["notes"][f"all_{kind}"] = {e: agg([net_r(f) for f in fades[kind] if era(f) == e]) for e in ("IS", "OOS")}
    out["notes"]["all_original"] = {e: agg([net_r(t) for t in base if era(t) == e]) for e in ("IS", "OOS")}

    # ---------------- 2. time filters (pre-registered)
    def tf_rows(name, eng, pred):
        sel = [t for t in base if t.engine == eng]
        r = dict(filter=name, engine=eng)
        for e in ("IS", "OOS"):
            r[f"in_{e}"] = agg([net_r(t) for t in sel if era(t) == e and pred(t)])
            r[f"out_{e}"] = agg([net_r(t) for t in sel if era(t) == e and not pred(t)])
        keep = (r["in_IS"]["avg"] or -9) > (r["out_IS"]["avg"] or -9) + 0.05
        r["adopt_from_IS"] = bool(keep)
        r["confirmed_OOS"] = bool(keep and (r["in_OOS"]["avg"] or -9) > (r["out_OOS"]["avg"] or -9))
        out["time"].append(r)

    tf_rows("fib_delay", "weekly", lambda t: t.fill_delay in FIB)
    tf_rows("early_week", "weekly", lambda t: t.entry_time.dayofweek <= 2)
    tf_rows("fib_delay", "micro", lambda t: t.fill_delay in FIB)
    tf_rows("killzones", "micro", lambda t: (7 <= t.entry_time.hour < 10) or (12 <= t.entry_time.hour < 16))
    tf_rows("early_week", "micro", lambda t: t.entry_time.dayofweek <= 2)

    # descriptive tables for the artifact (not used for decisions)
    def bucket(eng, key):
        sel = [t for t in base if t.engine == eng]
        df = pd.DataFrame({"k": [key(t) for t in sel], "r": [net_r(t) for t in sel], "era": [era(t) for t in sel]})
        g = df.groupby(["k", "era"]).r.agg(["count", "mean"]).round(3).reset_index()
        return g.to_dict("records")
    out["dow_weekly"] = bucket("weekly", lambda t: t.entry_time.dayofweek)
    out["delay_weekly"] = bucket("weekly", lambda t: min(t.fill_delay, 15))
    out["hour_micro"] = bucket("micro", lambda t: t.entry_time.hour)
    out["dow_micro"] = bucket("micro", lambda t: t.entry_time.dayofweek)

    # ---------------- 3. plan v2 = v1 + only what survived OOS
    inv_ok = [r for r in out["inversion"] if r["pick_from_IS"] != "original"
              and (r["picked_OOS"]["avg"] or -9) > (r["orig_OOS_avg"] or -9)]
    time_ok = [r for r in out["time"] if r["confirmed_OOS"]]
    out["v2_rules"] = dict(inversions=[(r["symbol"], r["engine"], r["pick_from_IS"]) for r in inv_ok],
                           time_filters=[(r["filter"], r["engine"]) for r in time_ok])

    def v2_trades():
        keep = []
        inv = {(a, b): k for a, b, k in out["v2_rules"]["inversions"]}
        tfil = set(out["v2_rules"]["time_filters"])
        preds = {"fib_delay": lambda t: t.fill_delay in FIB, "early_week": lambda t: t.entry_time.dayofweek <= 2,
                 "killzones": lambda t: (7 <= t.entry_time.hour < 10) or (12 <= t.entry_time.hour < 16)}
        dropped_pos = set()
        for t in base:
            if any(not preds[f](t) for f, e in tfil if e == t.engine):
                dropped_pos.add(t.pos_id); continue
            k = inv.get((t.symbol, t.engine))
            if k:
                f = fade(t, data[t.symbol][t.tf], k, 60 if t.tf == "D1" else 30)
                if f:
                    keep.append(f)
                dropped_pos.add(t.pos_id)    # no Turtle adds on a faded position
            else:
                keep.append(t)
        keep += [a for a in adds if a.pos_id not in dropped_pos]
        return keep

    v2 = v2_trades()
    rk = RiskConfig(weekly_unit_risk=0.005, micro_risk=0.0025)
    comp = []
    for label, tr in (("v1", trades), ("v2", v2)):
        for lo, hi, name in (("2005-01-01", "2016-01-01", "IS 2005-15"), ("2016-01-01", "2027-01-01", "OOS 2016-26"),
                             ("2005-01-01", "2027-01-01", "Full 2005-26")):
            sub = [t for t in tr if pd.Timestamp(lo, tz="UTC") <= t.entry_time < pd.Timestamp(hi, tz="UTC")]
            st = stats(simulate(sub, 50_000, rk), 50_000)
            comp.append(dict(plan=label, period=name, **{k: st[k] for k in ("trades", "final", "ret_pct", "cagr_pct", "max_dd", "win_rate", "pf")}))
    out["v1_vs_v2"] = comp
    with open("results/experiments.json", "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    return data, trades, logs, out, v2


if __name__ == "__main__":
    _, _, _, out, _ = main()
    for r in out["inversion"]:
        print(f'{r["symbol"]:7s} {r["engine"]:6s} orig IS {r["orig_IS"]["avg"]} OOS {r["orig_OOS"]["avg"]} | '
              f'mirror IS {r["fade_mirror_IS"]["avg"]} OOS {r["fade_mirror_OOS"]["avg"]} | '
              f'1to1 IS {r["fade_1to1_IS"]["avg"]} OOS {r["fade_1to1_OOS"]["avg"]} -> {r["pick_from_IS"]}')
    print(json.dumps(out["notes"], indent=0))
    for r in out["time"]:
        print(r["filter"], r["engine"], "IS in/out", r["in_IS"]["avg"], r["out_IS"]["avg"], "OOS in/out",
              r["in_OOS"]["avg"], r["out_OOS"]["avg"], r["adopt_from_IS"], r["confirmed_OOS"])
    print(out["v2_rules"])
    print(pd.DataFrame(out["v1_vs_v2"]).to_string())

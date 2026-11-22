"""Export bars, decision logs, trades and equity for the backtest-replay page.
    python -m fibfvg.export_replay   -> results/replay/*.json
"""
import json
import os

import numpy as np
import pandas as pd

from .config import SYMBOLS, RiskConfig
from .engines import htf_bias
from .experiments import FIB, main as run_experiments, net_r
from .simulator import simulate

OUT = "results/replay"


def r4(x):
    return float(f"{x:.6g}")


def main():
    os.makedirs(OUT, exist_ok=True)
    data, trades, logs, exp, v2 = run_experiments()
    rk = RiskConfig(weekly_unit_risk=0.005, micro_risk=0.0025)
    res = simulate(v2, 50_000, rk)
    fills = {(f.symbol, f.entry_time, round(f.entry, 6), f.direction): f for f in res["fills"]}
    inv = {(a, b) for a, b, _ in exp["v2_rules"]["inversions"]}

    # one row per main trade (weekly entry or micro), v1 candidate with its v2 fate
    v2_main = {(t.symbol, t.entry_time, round(t.entry, 6)): t for t in v2 if t.engine in ("weekly", "micro")}
    adds_by_pos = {}
    for t in v2:
        if t.engine == "weekly_add":
            adds_by_pos.setdefault(t.pos_id, []).append(t)
    setups = {}
    for s_, lg in logs.items():
        for e in lg:
            if e["ev"] == "setup":
                setups[(s_, e["eng"], e["dir"], e["t"])] = e
    off = {"D1": pd.Timedelta(hours=12), "H4": pd.Timedelta(hours=4)}
    rows = []
    for t in sorted([t for t in trades if t.engine in ("weekly", "micro")], key=lambda x: x.entry_time):
        b = htf_bias(data[t.symbol]["D1"])
        day = t.entry_time.normalize()
        bi = b.loc[:day].iloc[-1] if len(b.loc[:day]) else None
        key = (t.symbol, t.entry_time, round(t.entry, 6))
        status = "taken"
        taken = v2_main.get(key)
        if t.engine == "micro" and t.entry_time.dayofweek > 2:
            status, taken = "filtered (Thu/Fri)", None
        elif (t.symbol, t.engine) in inv:
            status = "reversed"
            taken = next((x for x in v2 if getattr(x, "src", None) is t), None) or \
                next((x for x in v2 if x.engine == t.engine and x.symbol == t.symbol and x.entry_time == t.entry_time
                      and x.direction == -t.direction), None)
        elif taken is None:
            status = "filtered (Thu/Fri)"
        f = fills.get((taken.symbol, taken.entry_time, round(taken.entry, 6), taken.direction)) if taken is not None else None
        if taken is not None and f is None:
            status = status if status != "taken" else "skipped (risk cap)"
        rows.append(dict(
            id=len(rows), sym=t.symbol, eng=t.engine, tf=t.tf, dir=t.direction,
            setup_t=int(data[t.symbol][t.tf].index[t.setup_bar].timestamp()),
            fill_t=int(data[t.symbol][t.tf].index[t.bar].timestamp()),
            exit_t=int(t.exit_time.timestamp()), delay=int(t.fill_delay), fib_delay=t.fill_delay in FIB,
            entry=r4(t.entry), stop=r4(t.stop), tp1=r4(t.tp1) if t.tp1 is not None else None, tp2=r4(t.tp_final),
            exits=[[int(x[0].timestamp()), r4(x[1]), round(x[2], 3)] for x in t.exits],
            r=round(t.r_multiple, 3), net_r=round(net_r(t), 3), dow=int(t.entry_time.dayofweek),
            wbias=int(bi.w) if bi is not None else 0, mbias=int(bi.m) if bi is not None else 0,
            status=status,
            leg=(lambda e: None if e is None else dict(lo=r4(min(e["leg_lo"], e["leg_hi"])), hi=r4(max(e["leg_lo"], e["leg_hi"])),
                 frm=int(pd.Timestamp(e["leg_from"]).timestamp()) - (43200 if t.tf == "D1" else 14400),
                 fvg_lo=r4(e["fvg_lo"]) if "fvg_lo" in e else None, fvg_hi=r4(e["fvg_hi"]) if "fvg_hi" in e else None))(
                setups.get((t.symbol, t.engine, t.direction, str(data[t.symbol][t.tf].index[t.setup_bar] + off[t.tf])))),
            rev=None if status != "reversed" or taken is None else dict(
                dir=taken.direction, stop=r4(taken.stop), tp=r4(taken.tp_final),
                exits=[[int(x[0].timestamp()), r4(x[1]), 1.0] for x in taken.exits], net_r=round(net_r(taken), 3)),
            adds=[dict(t=int(a.entry_time.timestamp()), px=r4(a.entry), stop=r4(a.stop), r=round(a.r_multiple, 3))
                  for a in adds_by_pos.get(t.pos_id, [])] if t.engine == "weekly" else [],
            lots=f.lots if f else None, pnl=round(f.pnl_usd, 2) if f else None,
            eq=round(f.equity_before, 2) if f else None,
        ))
    # setups / cancels from the decision log
    for s in SYMBOLS:
        bars = {}
        for tf in ("D1", "H4"):
            df = data[s][tf]
            if tf == "D1":
                df = df[df.index >= pd.Timestamp("2004-06-01", tz="UTC")]
            bars[tf] = [[int(i.timestamp()), r4(o), r4(h), r4(l), r4(c)]
                        for i, o, h, l, c in zip(df.index, df.Open, df.High, df.Low, df.Close)]
        ev = [e for e in logs[s]]
        with open(f"{OUT}/{s}.json", "w") as fh:
            json.dump(dict(symbol=s, bars=bars, log=ev), fh, separators=(",", ":"))
    curve = [[int(t.timestamp()), round(b, 2)] for t, b in res["curve"] if t is not None]
    meta = dict(symbols=list(SYMBOLS), trades=rows, curve=curve,
                experiments={k: exp[k] for k in ("inversion", "time", "notes", "v2_rules", "v1_vs_v2",
                                                  "dow_weekly", "delay_weekly", "hour_micro", "dow_micro")})
    with open(f"{OUT}/meta.json", "w") as fh:
        json.dump(meta, fh, separators=(",", ":"), default=str)
    print(len(rows), "trades;", pd.Series([r["status"] for r in rows]).value_counts().to_dict())


if __name__ == "__main__":
    main()

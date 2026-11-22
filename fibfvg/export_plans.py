"""Export Plan 1 / Plan 2 trades and bars for the replay page (adds to results/replay/)."""
import json

import pandas as pd

from .config import RiskConfig, SYMBOLS
from .engines import htf_bias
from .experiments import FIB, net_r
from .plans import TFS, load_tf
from .plans_study import main as study
from .simulator import simulate


def r4(x):
    return float(f"{x:.6g}")


def main():
    out, p1, p2, daily = study()
    meta = json.load(open("results/replay/meta.json"))
    pick1 = out["plan1_pick"]
    res = simulate(p1[pick1], 50_000, RiskConfig(weekly_unit_risk=0.005))
    fills = {(f.symbol, f.entry_time, round(f.entry, 6)): f for f in res["fills"]}
    bias = {s: htf_bias(daily[s]) for s in SYMBOLS}
    rows = [t for t in meta["trades"] if t["eng"] in ("weekly", "micro")]

    def row(t, eng, tfkey, bars_index, adds):
        b = bias[t.symbol]
        bi = b.loc[:t.entry_time.normalize()].iloc[-1]
        f = fills.get((t.symbol, t.entry_time, round(t.entry, 6))) if eng == "position" else None
        L = t.leg
        return dict(id=len(rows), sym=t.symbol, eng=eng, tf=tfkey, dir=t.direction,
                    setup_t=int(bars_index[t.setup_bar].timestamp()), fill_t=int(bars_index[t.bar].timestamp()),
                    exit_t=int(t.exit_time.timestamp()), delay=int(t.fill_delay), fib_delay=t.fill_delay in FIB,
                    entry=r4(t.entry), stop=r4(t.stop), tp1=r4(t.tp1) if t.tp1 is not None else None,
                    tp2=r4(t.tp_final) if t.tp_final is not None else None,
                    exits=[[int(x[0].timestamp()), r4(x[1]), round(x[2], 3)] for x in t.exits],
                    r=round(t.r_multiple, 3), net_r=round(net_r(t), 3), dow=int(t.entry_time.dayofweek),
                    wbias=int(bi.w), mbias=int(bi.m), status="taken",
                    leg=dict(lo=r4(L["lo"]), hi=r4(L["hi"]), frm=L["frm"], fvg_lo=r4(L["fvg_lo"]) if "fvg_lo" in L else None,
                             fvg_hi=r4(L["fvg_hi"]) if "fvg_hi" in L else None),
                    rev=None, adds=adds, lots=f.lots if f else None, pnl=round(f.pnl_usd, 2) if f else None,
                    eq=round(f.equity_before, 2) if f else None)

    addmap = {}
    for t in p1[pick1]:
        if t.engine == "pos_add":
            addmap.setdefault(t.pos_id, []).append(dict(t=int(t.entry_time.timestamp()), px=r4(t.entry), stop=r4(t.stop), r=round(t.r_multiple, 3)))
    for t in sorted([t for t in p1[pick1] if t.engine == "position"], key=lambda x: x.entry_time):
        rows.append(row(t, "position", "D1", daily[t.symbol].index, addmap.get(t.pos_id, [])))
    for tf in TFS:
        pick = out["plan2"][tf]["pick"]
        bars = {s: load_tf(s, tf) for s in SYMBOLS}
        for t in sorted(p2[(tf, pick)], key=lambda x: x.entry_time):
            rows.append(row(t, "p2_" + tf, tf, bars[t.symbol].index, []))
        for s in SYMBOLS:
            df = bars[s]
            json.dump([[int(i.timestamp()), r4(o), r4(h), r4(l), r4(c)] for i, o, h, l, c in
                       zip(df.index, df.Open, df.High, df.Low, df.Close)],
                      open(f"results/replay/{s}_{tf}.json", "w"), separators=(",", ":"))
    for i, r in enumerate(rows):
        r["id"] = i
    meta["trades"] = rows
    meta["plans"] = {k: v for k, v in out.items() if k != "plan1_curve"}
    meta["plan1_curve"] = out["plan1_curve"]
    json.dump(meta, open("results/replay/meta.json", "w"), separators=(",", ":"), default=str)
    print(len(rows), "rows;", pd.Series([r["eng"] for r in rows]).value_counts().to_dict())
    print({k: out[k] for k in out if k.startswith("prop_")})
    print(pd.DataFrame(out["plan1_tiers"]).to_string())


if __name__ == "__main__":
    main()

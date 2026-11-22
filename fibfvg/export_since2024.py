"""Add the 2024+ backtest (Plan 1 since 2024, Plan 3 levels) to the replay page data."""
import json

import pandas as pd

from .config import SYMBOLS
from .engines import htf_bias
from .experiments import net_r
from .levels import UNIT
from .simulator import simulate
from .config import RiskConfig
from .since2024 import CHOSEN, KZ, main as run


def r4(x):
    return float(f"{x:.6g}")


def main():
    out, data, p1, v2 = run()
    meta = json.load(open("results/replay/meta.json"))
    keep = [t for t in meta["trades"] if t["eng"] not in ("levels", "levels_kz", "pos24")]
    rows = keep
    # $ P&L for the combined 2024 portfolio
    p3 = v2[CHOSEN]
    for t in p3:
        t.engine_orig = t.engine; t.engine = "micro"
    res = simulate(p1 + p3, 50_000, RiskConfig(weekly_unit_risk=0.005, micro_risk=0.0025, max_open_risk=0.08))
    for t in p3:
        t.engine = t.engine_orig
    fills = {(f.symbol, f.entry_time, round(f.entry, 6), f.direction): f for f in res["fills"]}
    bias = {}
    for s in SYMBOLS:
        bias[s] = htf_bias(data[s][0])

    def add(t, eng, tf, idx, adds):
        f = fills.get((t.symbol, t.entry_time, round(t.entry, 6), t.direction))
        b = bias[t.symbol]
        bi = b.loc[:t.entry_time.normalize()]
        bi = bi.iloc[-1] if len(bi) else None
        L = getattr(t, "leg", None) or {}
        rows.append(dict(
            id=0, sym=t.symbol, eng=eng, tf=tf, dir=t.direction,
            setup_t=int(idx[t.setup_bar].timestamp()), fill_t=int(idx[t.bar].timestamp()),
            exit_t=int(t.exit_time.timestamp()), delay=int(t.fill_delay), fib_delay=False,
            entry=r4(t.entry), stop=r4(t.stop), tp1=r4(t.tp1) if t.tp1 is not None else None,
            tp2=r4(t.tp_final) if t.tp_final is not None else None,
            exits=[[int(x[0].timestamp()), r4(x[1]), round(x[2], 3)] for x in t.exits],
            r=round(t.r_multiple, 3), net_r=round(net_r(t), 3), dow=int(t.entry_time.dayofweek),
            wbias=int(bi.w) if bi is not None else 0, mbias=int(bi.m) if bi is not None else 0, status="taken",
            leg=dict(lo=r4(L["lo"]), hi=r4(L["hi"]), frm=L["frm"], fvg_lo=None, fvg_hi=None) if L else None,
            rev=None, adds=adds, lots=f.lots if f else None, pnl=round(f.pnl_usd, 2) if f else None,
            eq=round(f.equity_before, 2) if f else None,
            level=r4(t.level) if hasattr(t, "level") else None, level_name=getattr(t, "level_name", None),
            kz_hour=getattr(t, "kz_hour", None), unit=UNIT.get(t.symbol)))

    for name, eng in ((CHOSEN, "levels"), (KZ, "levels_kz")):
        tr = v2[name]
        addmap = {}
        for t in tr:
            if t.engine == "levels_add":
                addmap.setdefault(t.pos_id, []).append(dict(t=int(t.entry_time.timestamp()), px=r4(t.entry), stop=r4(t.stop),
                                                            r=round(net_r(t), 3), level=r4(t.level), name=t.level_name))
        for t in sorted([t for t in tr if t.engine == "levels"], key=lambda x: x.entry_time):
            add(t, eng, "L1H", data[t.symbol][1].index, addmap.get(t.pos_id, []))
    addmap = {}
    for t in p1:
        if t.engine == "pos_add":
            addmap.setdefault(t.pos_id, []).append(dict(t=int(t.entry_time.timestamp()), px=r4(t.entry), stop=r4(t.stop), r=round(net_r(t), 3)))
    for t in sorted([t for t in p1 if t.engine == "position"], key=lambda x: x.entry_time):
        d = data[t.symbol][0]
        from .engines import load
        dd = load(f"data/{t.symbol}_D1.csv"); dd = dd[dd.index >= pd.Timestamp("2024-01-01", tz="UTC")]
        add(t, "pos24", "D24", dd.index, addmap.get(t.pos_id, []))
    for s in SYMBOLS:
        h = data[s][1]
        json.dump([[int(i.timestamp()), r4(o), r4(hh), r4(l), r4(c)] for i, o, hh, l, c in zip(h.index, h.Open, h.High, h.Low, h.Close)],
                  open(f"results/replay/{s}_L1H.json", "w"), separators=(",", ":"))
        from .engines import load
        dd = load(f"data/{s}_D1.csv"); dd = dd[dd.index >= pd.Timestamp("2024-01-01", tz="UTC")]
        json.dump([[int(i.timestamp()), r4(o), r4(hh), r4(l), r4(c)] for i, o, hh, l, c in zip(dd.index, dd.Open, dd.High, dd.Low, dd.Close)],
                  open(f"results/replay/{s}_D24.json", "w"), separators=(",", ":"))
    for i, r in enumerate(rows):
        r["id"] = i
    meta["trades"] = rows
    meta["since2024"] = {k: v for k, v in out.items() if k != "curve"}
    meta["curve2024"] = out["curve"]
    json.dump(meta, open("results/replay/meta.json", "w"), separators=(",", ":"), default=str)
    print(pd.Series([r["eng"] for r in rows]).value_counts().to_dict())


if __name__ == "__main__":
    main()

"""Three-way project, recent data only (2024 -> now).

New exit rule (overlay "BE30+TP"): once a trade reaches +0.73R its stop moves to entry + 30 pips;
take profit in 5 steps of 20% at 100, 200, 300, 400, 500 pips. Tested on every strategy below.

Strategies
  PROP24  : Wallet 1 prop plan (daily + 4-hour setups at 0.705, stop at the leg origin, flat within 24 h);
            BTC, S&P 500, Nasdaq 100.
  HOLD    : bot v3 position plan (holds days-weeks, chandelier exit), all 5 markets.
  WEEKLY  : real-money weekly Turtle plan. Direction = monthly + weekly ranges agree. Unit 1 at Monday's open,
            unit 2 at Tuesday's open, unit 3 at Wednesday's open (variant: add only if the week is in profit).
            Stop 2N (20-day ATR) from the newest entry, shared by all open units (Turtle rule).
            Friday close: units 2 and 3 close; unit 1 stays as a runner with its stop at breakeven if it is
            in profit (otherwise it closes too). Runner exits: breakeven stop only ("manual" = end of data),
            or breakeven + 20-day trail.
Accounts (12 months to 22 Nov 2026, and every 12-month window since 2024)
  REAL $150 / $200 : compounding on the balance; broker minimum 0.01 lot (trades that would need more risk are
                     skipped, never oversized); allowed worst drawdown 50%.
  PROP $100K       : FundedNext instant, 6% trailing line, 5% guard, rewards every 14 days.
    python -m fibfvg.threeway -> results/threeway.json
"""
import json

import numpy as np
import pandas as pd

from . import propsim
from .config import SYMBOLS
from .engines import Trade, atr, htf_bias, load, net_r
from .levels import load_sym
from .livefund import trades as hold_trades, max_dd
from .prop24 import build as prop_build
from .intraday24 import friday_close
from .propsim import Account, run
from .swaps import RATE, with_swaps

PIP = {"XAUUSD": 0.1, "XAGUSD": 0.01, "BTCUSD": 1.0, "US500": 0.1, "NAS100": 0.1}
SPLIT = pd.Timestamp("2025-08-19", tz="UTC")
NOW = pd.Timestamp("2026-11-22", tz="UTC")
Y1 = NOW - pd.Timedelta(days=365)
FN100 = Account("FundedNext instant", 100_000, 740.0, None, 0.06)
PROP_MKTS = ("BTCUSD", "US500", "NAS100")


# ----------------------------------------------------------------- new exit rule replay
def overlay(t, bars, end=None, swap_days_cap=None):
    """Replay a trade's entry with the BE30+TP rule on the given bars. Returns a new Trade (real prices)."""
    d, e, s0, sym = t.direction, t.entry, t.stop, t.symbol
    risk = abs(e - s0); pip = PIP[sym]
    if risk <= 0:
        return None
    i0 = int(bars.index.searchsorted(t.entry_time))
    if i0 >= len(bars):
        return None
    H, L, C, T = bars.High.values, bars.Low.values, bars.Close.values, bars.index
    # the bar where the limit actually fills: first bar from the entry time that trades through the entry price
    jf = None
    for j in range(i0, min(len(C), i0 + 30)):
        if (L[j] <= e) if d == 1 else (H[j] >= e):
            jf = j; break
    if jf is None:
        return None
    i0 = jf
    tps = [e + d * k * pip for k in (100, 200, 300, 400, 500)]
    stop, left, k, be = s0, 1.0, 0, False
    exits = []; j = i0
    for j in range(i0, len(C)):
        if end is not None and T[j] >= end:
            j -= 1; break
        hi, lo = (H[j], L[j]) if d == 1 else (-L[j], -H[j])
        if lo <= d * stop:
            exits.append((T[j], stop, left)); left = 0; break
        if j == i0:
            continue            # fill bar: its high/low may have come before the fill, so only the stop counts
        while k < 5 and hi >= d * tps[k]:
            exits.append((T[j], tps[k], 0.2)); left -= 0.2; k += 1
        if not be and (hi - d * e) / risk >= 0.73:
            stop = e + d * 30 * pip; be = True
        if left <= 1e-9:
            break
    if left > 1e-9:
        jj = max(i0, min(j, len(C) - 1))
        exits.append((T[jj] + (T[1] - T[0]), C[jj], left))
    x = Trade(sym, t.engine, d, t.entry_time, e, s0, pos_id=t.pos_id + "-o")
    x.plan = getattr(t, "plan", "Plan 1")
    # swaps: position value x rate x days held (fraction-weighted)
    x.exits = []
    for (xt, px, fr) in exits:
        days = max(0.0, (xt - t.entry_time).total_seconds() / 86400)
        if swap_days_cap is not None:
            days = min(days, swap_days_cap)
        x.exits.append((xt, px - d * abs(e) * RATE[sym] * days / 365, fr))
    return x


# ----------------------------------------------------------------- weekly Turtle plan
def weekly(sym, daily, add_only_in_profit=False, runner="be", overlay_rule=False):
    b = htf_bias(daily)
    N = atr(daily, 20).shift(1)
    O, H, L, C = (daily[k].values for k in ("Open", "High", "Low", "Close"))
    T = daily.index; dow = T.dayofweek
    out = []
    i = 25
    while i < len(T):
        if dow[i] != 0:
            i += 1; continue
        d = int(b.w.values[i]) if b.w.values[i] == b.m.values[i] else 0
        n = N.values[i]
        if d == 0 or np.isnan(n) or n <= 0:
            i += 1; continue
        # the trading days of this week
        wk = [i]
        while wk[-1] + 1 < len(T) and dow[wk[-1] + 1] in (1, 2, 3, 4) and dow[wk[-1] + 1] > dow[wk[-1]]:
            wk.append(wk[-1] + 1)
        units = []          # dicts: e, stop0, t
        stop = None; closed = False
        for j in wk:
            # new unit at the open (Mon, Tue, Wed)
            if dow[j] in (0, 1, 2) and not closed:
                e = O[j]
                if dow[j] == 0 or not add_only_in_profit or (e - units[0]["e"]) * d > 0:
                    units.append(dict(e=e, s0=e - d * 2 * n, t=T[j]))
                    stop = e - d * 2 * n if stop is None else (max(stop, e - d * 2 * n) if d == 1 else min(stop, e - d * 2 * n))
            if not units or closed:
                continue
            hi, lo = (H[j], L[j]) if d == 1 else (-L[j], -H[j])
            if lo <= d * stop:                                   # shared stop hit: all units out
                for u in units:
                    u["x"] = (T[j] + pd.Timedelta(hours=20), min(O[j], stop) if d == 1 else max(O[j], stop))
                closed = True
        if units and not closed:                                 # Friday (last day of the week) close
            jf = wk[-1]; cf = C[jf]; xt = T[jf] + pd.Timedelta(hours=20)
            for u in units[1:]:
                u["x"] = (xt, cf)
            u1 = units[0]
            if (cf - u1["e"]) * d > 0:                           # runner: stop at breakeven
                st = u1["e"]; x = None
                for j in range(jf + 1, len(T)):
                    hi, lo = (H[j], L[j]) if d == 1 else (-L[j], -H[j])
                    if runner == "trail":
                        tr = L[max(0, j - 20):j].min() if d == 1 else H[max(0, j - 20):j].max()
                        st = max(st, tr) if d == 1 else min(st, tr)
                    if lo <= d * st:
                        x = (T[j] + pd.Timedelta(hours=20), min(O[j], st) if d == 1 else max(O[j], st)); break
                u1["x"] = x if x else (T[-1] + pd.Timedelta(hours=20), C[-1])
            else:
                u1["x"] = (xt, cf)
        for k, u in enumerate(units):
            t = Trade(sym, "position" if k == 0 else "pos_add", d, u["t"], u["e"], u["s0"], pos_id=f"W-{sym}-{T[i].date()}")
            t.exits = [(u["x"][0], u["x"][1], 1.0)]
            t.plan = "Plan 1"
            out.append(t)
        i = wk[-1] + 1
    return with_swaps(out)


# ----------------------------------------------------------------- statistics and accounts
def stats(tr):
    r = np.array([net_r(t) for t in tr])
    if len(r) < 3:
        return dict(n=len(r))
    a = np.array([net_r(t) for t in tr if t.entry_time < SPLIT]); b = np.array([net_r(t) for t in tr if t.entry_time >= SPLIT])
    w, l = r[r > 0], r[r <= 0]
    return dict(n=len(r), win=round(float((r > 0).mean() * 100), 1), avg_win=round(float(w.mean()), 2) if len(w) else 0,
                avg_loss=round(float(l.mean()), 2) if len(l) else 0, rr=round(float(w.mean() / -l.mean()), 2) if len(w) and len(l) else None,
                net=round(float(r.mean()), 3), first=round(float(a.mean()), 3) if len(a) else None,
                second=round(float(b.mean()), 3) if len(b) else None, t=round(float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))), 2))


def curve_months(curve, cap, start, end):
    s = pd.Series([v for _, v in curve], index=pd.to_datetime([a for a, _ in curve], unit="s", utc=True))
    s = pd.concat([pd.Series([cap], index=[start]), s[(s.index >= start) & (s.index < end)]]).groupby(level=0).last()
    m = s.resample("ME").last().ffill()
    return m


def dd_of(curve, cap, start, end):
    s = pd.Series([v for _, v in curve], index=pd.to_datetime([a for a, _ in curve], unit="s", utc=True))
    s = pd.concat([pd.Series([cap], index=[start]), s[(s.index >= start) & (s.index < end)]])
    pk = s.cummax()
    return float(((pk - s) / pk).max() * 100)


def real_account(tr, cap, risk, start, end):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    o = run(tr, Account("Real", cap, 0.0, None, None, real=True, payout_days=None), "X", start=start, end=end)
    m = curve_months(o["curve"], cap, start, end)
    monthly = []; prev = cap
    for ts, v in m.items():
        monthly.append(dict(month=ts.strftime("%Y-%m"), end=round(float(v), 2), pnl=round(float(v - prev), 2))); prev = v
    return dict(cap=cap, risk=risk * 100, end=round(o["end_balance"], 2), ret=round((o["end_balance"] / cap - 1) * 100, 1),
                dd=round(dd_of(o["curve"], cap, start, end), 1), taken=o["trades"], skipped=o["skipped_min_lot"],
                blown=o["end_balance"] < cap * 0.5, monthly=monthly)


def prop_account(tr, risk, start, end):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    o = run(tr, FN100, "X", start=start, end=end)
    by = {}
    for d, v in o["payout_list"]:
        k = d[:7]; by[k] = by.get(k, 0) + v
    return dict(risk=risk * 100, paid=round(o["paid_to_trader"]), breach=o["breach"], dd=o["worst_dd_pct"], trades=o["trades"],
                monthly=[dict(month=k, paid=round(v)) for k, v in sorted(by.items())])


def windows(tr, fn, **kw):
    """every 12-month window starting on the 1st of a month, 2024-07 .. 2025-11"""
    res = []
    for s0 in pd.date_range("2024-07-01", "2025-11-01", freq="MS", tz="UTC"):
        res.append(fn(tr, start=s0, end=s0 + pd.Timedelta(days=365), **kw))
    return res


def main():
    data = {s: load_sym(s) for s in SYMBOLS}
    out = dict(strategies={}, real={}, prop={})
    # --- strategies
    a, b = prop_build()
    p24 = sorted([t for t in a + b if t.symbol in PROP_MKTS], key=lambda t: t.entry_time)
    p24o = [x for t in p24 if (x := overlay(t, data[t.symbol][1], end=min(t.entry_time + pd.Timedelta(hours=24), friday_close(t.entry_time)))) is not None]
    hold = [t for t in hold_trades() if t.engine == "position"]
    holdo = [x for t in hold if (x := overlay(t, data[t.symbol][0])) is not None]
    hold_all = hold_trades()
    S = {
        "PROP24 (current best, 3 markets)": p24,
        "PROP24 + BE30+TP rule": p24o,
        "HOLD (first units, 5 markets)": hold,
        "HOLD + BE30+TP rule (first units)": holdo,
    }
    wk = {}
    for add in (False, True):
        for runner in ("be", "trail"):
            name = f"WEEKLY Turtle | adds {'only in profit' if add else 'always'} | runner {'BE only' if runner == 'be' else 'BE + 20-day trail'}"
            wk[name] = [t for s in SYMBOLS for t in weekly(s, data[s][0], add_only_in_profit=add, runner=runner)]
            S[name] = wk[name]
    for name, tr in S.items():
        out["strategies"][name] = st = stats(tr)
        bysym = {s: stats([t for t in tr if t.symbol == s]) for s in SYMBOLS}
        out["strategies"][name]["by_market"] = {s: dict(n=v.get("n"), win=v.get("win"), rr=v.get("rr"), net=v.get("net")) for s, v in bysym.items()}
        print(f"{name:62s} n {st.get('n'):4d} win {st.get('win')}% RR {st.get('rr')} net {st.get('net')} halves {st.get('first')}/{st.get('second')} t {st.get('t')}")
        print("      by market:", {s: (v.get('n'), v.get('net')) for s, v in bysym.items()})
    # --- weekly: the best version profitable in both halves, then only markets profitable in both halves
    best_week = max(wk, key=lambda k: out["strategies"][k]["net"] if (out["strategies"][k].get("first") or -1) > 0 and (out["strategies"][k].get("second") or -1) > 0 else -9)
    bw = wk[best_week]
    keep = []
    for sym in SYMBOLS:
        st_ = stats([t for t in bw if t.symbol == sym])
        out["strategies"][best_week]["by_market"][sym].update(first=st_.get("first"), second=st_.get("second"))
        if st_.get("first") and st_.get("second") and st_["first"] > 0 and st_["second"] > 0:
            keep.append(sym)
    wsel = [t for t in bw if t.symbol in keep]
    out["weekly_markets_kept"] = keep
    out["strategies"]["WEEKLY best, markets kept"] = stats(wsel)
    print("weekly markets kept:", keep, out["strategies"]["WEEKLY best, markets kept"])
    # --- real-money accounts: last 12 months and every 12-month window since mid-2024
    real_sets = {"WEEKLY (kept markets)": wsel, "HOLD (bot v3, 5 markets)": hold_all}
    for name, tr in real_sets.items():
        out["real"][name] = {}
        for cap in (150, 200, 500, 1000, 2500, 5000):
            for risk in (0.02, 0.05, 0.10):
                last = real_account(tr, cap, risk, Y1, NOW)
                ws = windows(tr, lambda tr_, start, end, cap=cap, risk=risk: real_account(tr_, cap, risk, start, end))
                last["windows"] = dict(median_ret=round(float(np.median([w["ret"] for w in ws])), 1), worst_ret=round(float(min(w["ret"] for w in ws)), 1),
                                       best_ret=round(float(max(w["ret"] for w in ws)), 1), worst_dd=round(float(max(w["dd"] for w in ws)), 1),
                                       over_50_dd=int(sum(w["dd"] > 50 for w in ws)), n=len(ws))
                out["real"][name][f"${cap} at {risk * 100:.0f}%"] = last
                print(f"REAL {name:24s} ${cap:5d} {risk * 100:3.0f}%  last12m {last['ret']:+7.1f}% dd {last['dd']:5.1f}% taken {last['taken']:3d} skipped {last['skipped']:3d} | windows median {last['windows']['median_ret']:+.1f}% worst {last['windows']['worst_ret']:+.1f}% worst dd {last['windows']['worst_dd']}% >50%dd {last['windows']['over_50_dd']}")
    # --- prop $100K
    for name, tr in {"PROP24 (current best)": p24, "PROP24 + BE30+TP rule": p24o}.items():
        out["prop"][name] = {}
        for risk in (0.005, 0.0075, 0.01):
            last = prop_account(tr, risk, Y1, NOW)
            ws = windows(tr, lambda tr_, start, end, risk=risk: prop_account(tr_, risk, start, end))
            last["windows"] = dict(median=round(float(np.median([w["paid"] for w in ws]))), worst=min(w["paid"] for w in ws),
                                   best=max(w["paid"] for w in ws), breaches=sum(bool(w["breach"]) for w in ws), n=len(ws),
                                   worst_dd=max(w["dd"] for w in ws))
            out["prop"][name][f"{risk * 100:.2f}%"] = last
            print(f"PROP {name:24s} {risk * 100:.2f}% last12m paid {last['paid']} dd {last['dd']} breach {last['breach']} | windows median {last['windows']['median']} worst {last['windows']['worst']} breaches {last['windows']['breaches']}")
    out["best_weekly"] = best_week
    json.dump(out, open("results/threeway.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

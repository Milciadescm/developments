"""Three bots, recent data only (2024 -> now), and 2,000-path projections for 2027 and 2028.

Part 1 - Silver Bullet day trading (ICT). Only BTC has 5-minute history (Binance, 2024-2026); the other markets have
1-hour candles only, which cannot show a 5-minute fair value gap, so they cannot be tested this way here.
  Days    : Monday to Thursday; CPI release days skipped; FOMC and other news days traded.
  Windows : 03:00-04:00 (London), 10:00-11:00 (New York AM), 14:00-15:00 (New York PM), New York time.
  Bias    : monthly + weekly ranges agree (as the other bots) or yesterday's close vs the prior 5-day midpoint.
  Setup   : inside the window price first takes the high/low of the 2 hours before the window (liquidity sweep),
            then a displacement candle leaves a 5-minute fair value gap in the bias direction.
  Entry   : limit at the middle of the gap (live until the window ends). Stop beyond the sweep. Target 2R / 3R / 4R.
            Flat at 16:00 New York. One trade per window, at most 3 a day. Spread $15 and $40 tested.
Part 2 - Accounts 2024 -> now:
  Bot 1 : $1,000 real money, broker minimum 0.01 lot, at most 2 trades open at once.
  Bot 2 : $100K prop, 6% trailing limit.
  Bot 3 : $5K / $10K / $25K / $50K prop, 6% trailing limit.
Part 3 - 2,000 one-year paths for 2027 and for 2028 from the real monthly results, under three price regimes:
  base (all months), range (prices stay between the 2023 lows and the recent highs: the quieter half of months),
  breakout (new highs or a fall back toward the 2023 lows: the trending half of months).
    python -m fibfvg.threebots -> results/threebots.json
"""
import json

import numpy as np
import pandas as pd

from . import propsim
from .config import SYMBOLS
from .engines import Trade, htf_bias, load, net_r
from .levels import load_sym
from .livefund import trades as hold_trades
from .prop24 import build as prop_build
from .propsim import Account, run
from .threeway import stats, weekly, NOW, Y1
from .longhold import load_long

CPI = ["2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10", "2024-05-15", "2024-06-12", "2024-07-11", "2024-08-14", "2024-09-11",
       "2024-10-10", "2024-11-13", "2024-12-11", "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11",
       "2025-07-15", "2025-08-12", "2025-09-11", "2025-10-24", "2025-12-18", "2026-01-13", "2026-02-11", "2026-03-11", "2026-04-10",
       "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14", "2026-11-12"]   # Jul-Nov 2026 approximate
CPI_DAYS = set(CPI)
WINDOWS = {"London 03-04": 3, "NY AM 10-11": 10, "NY PM 14-15": 14}
START = pd.Timestamp("2024-01-01", tz="UTC")
MONTHS = pd.date_range("2024-07-01", "2026-11-01", freq="MS", tz="UTC")


# ----------------------------------------------------------------- Part 1: Silver Bullet on BTC 5-minute candles
def silver_bullet(m5, daily, windows, bias_kind, tp_r, spread):
    ny = m5.index.tz_convert("America/New_York")
    hb = htf_bias(daily)
    wm = pd.Series(np.where(hb.w.values == hb.m.values, hb.w.values, 0), index=hb.index.normalize())
    dc = daily.Close; mid5 = ((daily.High.rolling(5).max() + daily.Low.rolling(5).min()) / 2)
    dbias = pd.Series(np.sign(dc.shift(1) - mid5.shift(2)).values, index=daily.index.normalize())
    O, H, L, C = (m5[k].values for k in ("Open", "High", "Low", "Close"))
    T = m5.index
    nyd = ny.normalize(); hours = ny.hour.values; dows = ny.dayofweek.values
    day_start = {}
    for i, d in enumerate(nyd):
        day_start.setdefault(d, i)
    out = []
    for d0, i0 in day_start.items():
        if d0.dayofweek > 3 or str(d0.date()) in CPI_DAYS:
            continue
        key = pd.Timestamp(d0.date(), tz="UTC")
        src = wm if bias_kind == "monthly+weekly" else dbias
        if key not in src.index:
            continue
        b = int(src.loc[key]) if not np.isnan(src.loc[key]) else 0
        if b == 0:
            continue
        # bars of this NY day
        i1 = i0
        while i1 < len(T) and nyd[i1] == d0:
            i1 += 1
        close_16 = None
        for w in windows:
            h0 = WINDOWS[w]
            win = [i for i in range(i0, i1) if hours[i] == h0]
            pre = [i for i in range(max(0, i0 - 300), i1) if (T[i] >= T[win[0]] - pd.Timedelta(hours=2)) and T[i] < T[win[0]]] if win else []
            if len(win) < 6 or len(pre) < 12:
                continue
            ref_lo, ref_hi = L[pre].min(), H[pre].max()
            swept, ext = False, None
            order = None
            for i in win:
                if b == 1:
                    if L[i] < ref_lo:
                        swept = True; ext = L[i] if ext is None else min(ext, L[i])
                    if swept and i - 2 >= win[0] and L[i] > H[i - 2] and C[i - 1] > O[i - 1]:
                        e = (L[i] + H[i - 2]) / 2; s = ext - spread; r = e - s
                        if r > 3 * spread:
                            order = (i, e, s); break
                else:
                    if H[i] > ref_hi:
                        swept = True; ext = H[i] if ext is None else max(ext, H[i])
                    if swept and i - 2 >= win[0] and H[i] < L[i - 2] and C[i - 1] < O[i - 1]:
                        e = (H[i] + L[i - 2]) / 2; s = ext + spread; r = s - e
                        if r > 3 * spread:
                            order = (i, e, s); break
            if order is None:
                continue
            i, e, s = order; r = abs(e - s); tp = e + b * tp_r * r
            # fill before the window ends
            jf = None
            for j in range(i + 1, i1):
                if hours[j] > h0:
                    break
                if (L[j] <= e) if b == 1 else (H[j] >= e):
                    jf = j; break
            if jf is None:
                continue
            px, xt = None, None
            for j in range(jf, i1):
                if hours[j] >= 16:
                    px, xt = O[j], T[j]; break
                lo_, hi_ = (L[j], H[j]) if b == 1 else (-H[j], -L[j])
                if lo_ <= b * s:
                    px, xt = s, T[j]; break
                if j > jf and hi_ >= b * tp:
                    px, xt = tp, T[j]; break
            if px is None:
                px, xt = C[i1 - 1], T[i1 - 1]
            t = Trade("BTCUSD", "position", b, T[jf], e, s, pos_id=f"SB-{d0.date()}-{h0}")
            # spread charged by the caller through net_r (config spread); add the difference for the tested spread
            t.exits = [(xt + pd.Timedelta(minutes=5), px - b * (spread - SYMBOLS["BTCUSD"].spread), 1.0)]
            t.plan = "Plan 1"; t.window = w
            out.append(t)
    return out


# ----------------------------------------------------------------- helpers
def limit_open(trades, k):
    """keep a trade only if fewer than k trades are open when it starts (by first-unit position)."""
    keep, open_ = [], []
    for t in sorted(trades, key=lambda x: x.entry_time):
        open_ = [x for x in open_ if x.exit_time > t.entry_time]
        if len(open_) < k:
            keep.append(t); open_.append(t)
    return keep


def month_series_real(tr, cap, risk, start, end):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    o = run(tr, Account("Real", cap, 0.0, None, None, real=True, payout_days=None), "X", start=start, end=end)
    s = pd.Series([v for _, v in o["curve"]], index=pd.to_datetime([a for a, _ in o["curve"]], unit="s", utc=True))
    s = pd.concat([pd.Series([cap], index=[start]), s]).groupby(level=0).last()
    m = s.resample("MS").last().ffill().reindex(MONTHS).ffill().fillna(cap)
    ret = m.pct_change().fillna(m.iloc[0] / cap - 1)
    pk = s.cummax(); dd = float(((pk - s) / pk).max() * 100)
    return ret, o, dd


def month_series_prop(tr, acct, risk, start, end):
    propsim.MODES["X"] = dict(p1=risk, p3=risk)
    o = run(tr, acct, "X", start=start, end=end)
    by = pd.Series(0.0, index=MONTHS)
    for d, v in o["payout_list"]:
        k = pd.Timestamp(d[:7] + "-01", tz="UTC")
        if k in by.index:
            by[k] += v
    return by, o


def regimes():
    """trend score per month: average over the 5 markets of |3-month price change|; top half = trending."""
    sc = []
    for s in SYMBOLS:
        c = load_long(s).Close.resample("MS").last()
        sc.append((c / c.shift(3) - 1).abs().rename(s))
    sc = pd.concat(sc, axis=1).mean(axis=1).reindex(MONTHS)
    med = sc.median()
    return (sc > med).rename("trend")


def project(monthly, kind, trend, cap=None, paths=2000, seed=3):
    """2,000 one-year paths for 2027 and 2028 (2028 continues 2027). kind 'pct' compounds, 'usd' adds payouts."""
    rng = np.random.default_rng(seed)
    pools = {"base": monthly.values, "range (2023 lows to recent highs)": monthly[~trend].values,
             "breakout (new highs or back to 2023 lows)": monthly[trend].values}
    out = {}
    for name, pool in pools.items():
        if len(pool) < 3:
            continue
        months = rng.choice(pool, size=(paths, 24))
        if kind == "pct":
            eq = np.empty((paths, 25)); eq[:, 0] = cap
            for k in range(24):
                eq[:, k + 1] = eq[:, k] * (1 + months[:, k])
            pnl = np.diff(eq, axis=1)
            y27 = eq[:, 12]; y28 = eq[:, 24]
            pk = np.maximum.accumulate(eq, axis=1); dd = ((pk - eq) / pk).max(axis=1)
            out[name] = dict(
                monthly_2027=dict(median=round(float(np.median(pnl[:, :12])), 2), p10=round(float(np.percentile(pnl[:, :12], 10)), 2), p90=round(float(np.percentile(pnl[:, :12], 90)), 2)),
                end_2027=dict(median=round(float(np.median(y27))), p10=round(float(np.percentile(y27, 10))), p90=round(float(np.percentile(y27, 90)))),
                end_2028=dict(median=round(float(np.median(y28))), p10=round(float(np.percentile(y28, 10))), p90=round(float(np.percentile(y28, 90)))),
                p_below_half=round(float((eq.min(axis=1) < cap * 0.5).mean() * 100), 1), dd_median=round(float(np.median(dd) * 100), 1))
        else:
            y27 = months[:, :12].sum(axis=1); y28 = months[:, 12:].sum(axis=1)
            out[name] = dict(
                monthly=dict(median=round(float(np.median(months))), mean=round(float(months.mean())), p90=round(float(np.percentile(months, 90))),
                             months_zero_pct=round(float((months <= 0).mean() * 100))),
                year_2027=dict(median=round(float(np.median(y27))), p10=round(float(np.percentile(y27, 10))), p90=round(float(np.percentile(y27, 90)))),
                year_2028=dict(median=round(float(np.median(y28))), p10=round(float(np.percentile(y28, 10))), p90=round(float(np.percentile(y28, 90)))))
    return out


def main():
    out = dict(silver_bullet={}, bot1={}, bot2={}, bot3={}, projections={})
    data = {s: load_sym(s) for s in SYMBOLS}
    m5 = load("data/BTCUSD_M5.csv")
    btc_d = data["BTCUSD"][0]
    # ---------------- Part 1
    best, best_key = None, None
    for wins in (("NY AM 10-11",), ("London 03-04", "NY AM 10-11", "NY PM 14-15")):
        for bias in ("monthly+weekly", "daily"):
            for tp in (2, 3, 4):
                for spread in (15.0, 40.0):
                    tr = silver_bullet(m5, btc_d, wins, bias, tp, spread)
                    st = stats(tr)
                    key = f"{'+'.join(w.split()[0] + ' ' + w.split()[1] for w in wins)} | bias {bias} | TP {tp}R | spread ${spread:.0f}"
                    st["per_day"] = round(len(tr) / max(1, len({t.entry_time.date() for t in tr})), 2)
                    st["per_month"] = round(len(tr) / 34.7, 1)
                    out["silver_bullet"][key] = st
                    print(f"SB {key:70s} n {st.get('n'):4d} ({st['per_month']}/mo) win {st.get('win')}% RR {st.get('rr')} net {st.get('net')} halves {st.get('first')}/{st.get('second')} t {st.get('t')}")
                    if spread == 15.0 and st.get("n", 0) > 30 and (best is None or (st.get("first") or -9) > (out["silver_bullet"][best_key].get("first") or -9)):
                        best, best_key = tr, key
    sb_ok = best is not None and (out["silver_bullet"][best_key].get("first") or -1) > 0 and (out["silver_bullet"][best_key].get("second") or -1) > 0
    out["silver_bullet_choice"] = dict(key=best_key, passes_both_halves=sb_ok, **out["silver_bullet"][best_key])
    print("SB chosen on first half:", best_key, "passes both halves:", sb_ok)
    # ---------------- strategy pools
    a, b = prop_build()
    P24 = sorted([t for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")], key=lambda t: t.entry_time)
    WK = [t for s in ("XAGUSD", "BTCUSD") for t in weekly(s, data[s][0], add_only_in_profit=True, runner="trail")]
    HOLD5 = hold_trades()
    pools = {"Weekly Turtle (silver + BTC)": WK, "Prop 24-hour plan (BTC, S&P, Nasdaq)": P24, "Hold, chandelier (5 markets)": HOLD5}
    if best is not None:
        pools["Silver Bullet (BTC 5-min)"] = best
    trend = regimes()
    out["regime_months"] = {str(k.date()): bool(v) for k, v in trend.items()}
    # ---------------- Bot 1: $1,000 real, min lot, max 2 open
    for name, tr in pools.items():
        tr2 = limit_open(tr, 2)
        out["bot1"][name] = {}
        for risk in (0.02, 0.05, 0.10):
            ret, o, dd = month_series_real(tr2, 1000, risk, START, NOW)
            ret_l, ol, ddl = month_series_real(tr2, 1000, risk, Y1, NOW)
            out["bot1"][name][f"{risk * 100:.0f}%"] = dict(end=round(o["end_balance"]), dd=round(dd, 1), taken=o["trades"], skipped=o["skipped_min_lot"],
                                                         last12_end=round(ol["end_balance"]), last12_dd=round(ddl, 1),
                                                         monthly_pct=[round(float(x) * 100, 1) for x in ret.values])
            print(f"BOT1 $1,000 {name:38s} {risk * 100:3.0f}%  Jul-2024->now ${o['end_balance']:9,.0f} dd {dd:5.1f}% taken {o['trades']} skipped {o['skipped_min_lot']} | last 12 months ${ol['end_balance']:8,.0f} dd {ddl:.1f}%")
    # ---------------- Bot 2 and Bot 3: prop with a 6% trailing limit
    sizes = {"$5K": (5_000, 149.99), "$10K": (10_000, 299.99), "$25K": (25_000, 332.0), "$50K": (50_000, 465.0), "$100K": (100_000, 740.0)}
    for label, (size, fee) in sizes.items():
        acct = Account("FundedNext instant", size, fee, None, 0.06)
        by, o = month_series_prop(P24, acct, 0.0075, START, NOW)
        l = run(P24, acct, "X", start=Y1, end=NOW)
        yrs = {}
        for d, v in o["payout_list"]:
            yrs[d[:4]] = yrs.get(d[:4], 0) + v
        row = dict(fee=fee, paid_total=round(o["paid_to_trader"]), by_year={k: round(v) for k, v in yrs.items()}, last12=round(l["paid_to_trader"]),
                   breach=o["breach"], dd=o["worst_dd_pct"], skipped_min_lot=o["skipped_min_lot"], taken=o["trades"], monthly=[round(float(x)) for x in by.values])
        (out["bot2"] if size == 100_000 else out["bot3"])[label] = row
        print(f"PROP {label:6s} fee ${fee:7.2f} paid {row['paid_total']:7,d} by year {row['by_year']} last 12m {row['last12']} breach {row['breach']} skipped {row['skipped_min_lot']} of {row['taken'] + row['skipped_min_lot']}")
        out["projections"][f"prop {label}"] = project(by, "usd", trend)
    # ---------------- projections for bot 1 (best real-money pool that never fell below 50%)
    cand = [(n, r) for n, d in out["bot1"].items() for r, v in d.items() if v["dd"] <= 50 and v["end"] > 1000]
    if cand:
        n_best, r_best = max(cand, key=lambda x: out["bot1"][x[0]][x[1]]["end"])
        ret, o, dd = month_series_real(limit_open(pools[n_best], 2), 1000, float(r_best.strip("%")) / 100, START, NOW)
        out["bot1_choice"] = dict(strategy=n_best, risk=r_best)
        out["projections"]["$1,000 real"] = project(ret, "pct", trend, cap=1000)
        print("BOT1 choice:", n_best, r_best)
    for k, v in out["projections"].items():
        print("PROJ", k, json.dumps(v)[:600])
    json.dump(out, open("results/threebots.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

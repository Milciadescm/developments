"""Full study: real-data backtest across capital tiers, money-management sweep,
prop-firm guard and a 10,000-trade Monte Carlo built from the real trades.

    python -m fibfvg.run_backtest
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, replace

import numpy as np
import pandas as pd

from .config import CAPITAL_TIERS, SYMBOLS, EngineConfig, RiskConfig
from .engines import load, micro_engine, to_4h, weekly_engine
from .simulator import simulate, stats

OUT = "results"
RNG = np.random.default_rng(42)
PROP_START = pd.Timestamp("2024-07-03", tz="UTC")


def candidates(cfg: EngineConfig):
    trades = []
    for s in SYMBOLS:
        d = load(f"data/{s}_D1.csv")
        trades += weekly_engine(s, d, cfg)
        trades += micro_engine(s, to_4h(load(f"data/{s}_H1.csv")), d, cfg)
    return trades


def prop_risk(base: RiskConfig) -> RiskConfig:
    # Conservative guard for a $50k funded account. CONFIGURE to your account's
    # actual rules -- every funded account has a hard loss limit of some kind.
    return replace(base, daily_loss_limit=0.03, max_loss_limit=0.06, trailing_max_loss=True)


def fills_df(res):
    return pd.DataFrame([asdict(f) for f in res["fills"]])


def monte_carlo(net_r: np.ndarray, engines: np.ndarray, risk: RiskConfig, n_trades=10_000,
                paths=2000, prop=False):
    """Bootstrap 10,000-trade sequences from REAL net R-multiples (after costs).
    Fixed-fractional sizing. Returns distribution of outcomes."""
    frac = np.where(engines == "micro", risk.micro_risk, risk.weekly_unit_risk)
    idx = RNG.integers(0, len(net_r), size=(paths, n_trades))
    rets = net_r[idx] * frac[idx]
    logeq = np.cumsum(np.log1p(np.clip(rets, -0.99, None)), axis=1)
    peak = np.maximum.accumulate(np.maximum(logeq, 0), axis=1)
    dd = 1 - np.exp(logeq - peak)
    maxdd = dd.max(axis=1)
    out = dict(
        median_multiple=float(np.exp(np.median(logeq[:, -1]))),
        p5_multiple=float(np.exp(np.percentile(logeq[:, -1], 5))),
        p95_multiple=float(np.exp(np.percentile(logeq[:, -1], 95))),
        median_maxdd=float(np.median(maxdd)), p95_maxdd=float(np.percentile(maxdd, 95)),
        p_dd_over_20=float((maxdd > 0.20).mean()), p_dd_over_50=float((maxdd > 0.50).mean()),
        p_loss_after_1000=float((logeq[:, 999] < 0).mean()),
    )
    if prop:   # probability the 6% trailing limit is hit at some point
        out["p_breach_6pct_trailing"] = float((dd > 0.06).any(axis=1).mean())
        first = np.where((dd > 0.06).any(axis=1), (dd > 0.06).argmax(axis=1), n_trades)
        out["median_trades_to_breach"] = float(np.median(first))
        for k in (100, 250, 500):
            out[f"p_breach_within_{k}"] = float((first < k).mean())
    return out, rets[0]


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = EngineConfig()
    base = RiskConfig()
    trades = candidates(cfg)
    summary = {"candidates": len(trades)}

    # ---- 1. every capital tier, default money management -------------------
    tiers = []
    for cap in CAPITAL_TIERS:
        if cap == 50_000:
            # funded account: prop-safe risk, run on the recent window where the
            # 4H micro engine has data (2024-07 -> now)
            rk = replace(prop_risk(base), weekly_unit_risk=0.0025, micro_risk=0.0025)
            res = simulate([t for t in trades if t.entry_time >= PROP_START], cap, rk)
        else:
            rk = base
            res = simulate(trades, cap, rk)
        st = stats(res, cap)
        st["capital"] = cap
        tiers.append(st)
        fills_df(res).to_csv(f"{OUT}/trades_{cap}.csv", index=False)
        if cap == 50_000:   # also without the prop guard, to see what the guard costs
            res2 = simulate(trades, cap, base)
            st2 = stats(res2, cap); st2["capital"] = "50000 (no prop guard)"
            tiers.append(st2)
            base_fills = fills_df(res2)
            curve = pd.DataFrame(res2["curve"], columns=["time", "balance"])
            curve.to_csv(f"{OUT}/equity_50000_noguard.csv", index=False)
        print(st)
    summary["tiers"] = tiers

    # per engine / symbol breakdown from the unconstrained $50k run
    base_fills["net_r"] = base_fills.pnl_usd / base_fills.risk_usd
    base_fills["year"] = pd.to_datetime(base_fills.entry_time).dt.year
    summary["by_engine"] = base_fills.groupby("engine").net_r.agg(["count", "mean", "sum"]).round(3).reset_index().to_dict("records")
    summary["by_symbol"] = base_fills.groupby(["symbol", "engine"]).net_r.agg(["count", "mean", "sum"]).round(3).reset_index().to_dict("records")
    summary["by_year"] = base_fills.groupby("year").net_r.agg(["count", "sum"]).round(2).reset_index().to_dict("records")
    summary["win_rate_by_engine"] = base_fills.groupby("engine").net_r.apply(lambda r: round((r > 0).mean() * 100, 1)).to_dict()

    # ---- 2. money-management sweep (the "sweet spot") ----------------------
    sweep = []
    for wr in [0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02]:
        for mr in [0.0, 0.0025, 0.005, 0.01, 0.02]:
            rk = replace(base, weekly_unit_risk=wr, micro_risk=mr, max_open_risk=max(0.06, 8 * wr))
            tr = trades if mr > 0 else [t for t in trades if t.engine != "micro"]
            for cap in (500, 50_000):
                st = stats(simulate(tr, cap, rk, record=True), cap)
                sweep.append(dict(capital=cap, weekly_unit_risk=wr, micro_risk=mr, **{k: st[k] for k in
                             ("trades", "final", "cagr_pct", "max_dd", "pf", "min_lot")}))
    sw = pd.DataFrame(sweep)
    sw["mar"] = (sw.cagr_pct / sw.max_dd.replace(0, np.nan)).round(2)
    sw.to_csv(f"{OUT}/mm_sweep.csv", index=False)
    summary["sweep"] = sw.to_dict("records")

    # ---- 3. 10,000-trade Monte Carlo from real net R ------------------------
    net_r = base_fills.net_r.values
    eng = base_fills.engine.values
    mc = {}
    for name, rk, prop in [("default (0.5% unit / 1% micro)", base, False),
                           ("conservative (0.25% / 0.25%)", replace(base, weekly_unit_risk=0.0025, micro_risk=0.0025), False),
                           ("prop $50k (0.25% / 0.25%)", replace(base, weekly_unit_risk=0.0025, micro_risk=0.0025), True),
                           ("prop $50k (0.10% / 0.10%)", replace(base, weekly_unit_risk=0.001, micro_risk=0.001), True),
                           ("aggressive (1.5% / 2%)", replace(base, weekly_unit_risk=0.015, micro_risk=0.02), False),
                           ("reckless (3% / 5%)", replace(base, weekly_unit_risk=0.03, micro_risk=0.05), False)]:
        res, path = monte_carlo(net_r, eng, rk, prop=prop)
        mc[name] = res
        if name.startswith("default"):
            eq = 50_000 * np.cumprod(1 + path)
            pd.DataFrame({"trade_no": np.arange(1, 10_001), "return_pct": (path * 100).round(4),
                          "equity_from_50k": eq.round(2)}).to_csv(f"{OUT}/montecarlo_10000_trades_sample_path.csv", index=False)
    summary["montecarlo"] = mc
    yrs = (pd.to_datetime(base_fills.exit_time).max() - pd.to_datetime(base_fills.entry_time).min()).days / 365.25
    recent = base_fills[pd.to_datetime(base_fills.entry_time) >= pd.Timestamp("2024-07-03", tz="UTC")]
    summary["trades_per_year_all_history"] = round(len(base_fills) / yrs, 1)
    summary["trades_per_year_recent_with_micro"] = round(len(recent) / ((pd.Timestamp.now(tz="UTC") - pd.Timestamp("2024-07-03", tz="UTC")).days / 365.25), 1)
    summary["net_r_mean"] = float(net_r.mean())
    summary["kelly_fraction_per_R"] = float(net_r.mean() / (net_r ** 2).mean())   # f* ~ mu/E[R^2]
    with open(f"{OUT}/summary.json", "w") as fh:
        json.dump(summary, fh, indent=1, default=str)
    print(json.dumps({k: summary[k] for k in ("by_engine", "montecarlo", "trades_per_year_all_history",
                                               "trades_per_year_recent_with_micro", "kelly_fraction_per_R")}, indent=1, default=str))


if __name__ == "__main__":
    main()

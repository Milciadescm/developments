"""Falsification checks for the three remaining candidates (2024 -> now, hourly data).

A. Random-direction test: keep every rule (days traded, entry, stop, exits) but replace the direction with a coin flip,
   1,000 times. p = share of random runs whose average R is at least the real one. Small p = the direction rule
   carries information; large p = the result is within what luck produces.
B. Neighbourhood test (gold midnight): move the entry hour (00-03 NY) and the exit hour (12-15 NY). A real edge
   should stay positive around the chosen hours; an isolated spike is a warning.
C. Multiple testing: this project has tried roughly 400 rule versions on the same 2024-2026 data. If none had any
   edge, the best of 400 random versions would typically show t ~ 3 by luck alone (expected maximum of 400 draws).
    python -m fibfvg.falsify -> results/falsify.json
"""
import json

import numpy as np
import pandas as pd

from .config import SYMBOLS
from .midnight import days_of as mdays
from .goldsilver import trade as gtrade
from .candle10 import days_of as cdays, trade as ctrade
from .prop24 import build as prop_build
from .threeway import PIP

RNG = np.random.default_rng(2026)


def random_test(days, run, n=1000):
    real = [t for day in days if (t := run(day, None)) is not None]
    obs = float(np.mean([t["R"] for t in real]))
    sims = []
    for _ in range(n):
        flips = RNG.choice([-1, 1], size=len(days))
        rs = [t["R"] for day, f in zip(days, flips) if (t := run(day, f)) is not None]
        sims.append(np.mean(rs) if rs else 0.0)
    sims = np.array(sims)
    return dict(trades=len(real), real_avg_R=round(obs, 3), random_avg_R_median=round(float(np.median(sims)), 3),
                random_95th=round(float(np.percentile(sims, 95)), 3), p_value=round(float((sims >= obs).mean()), 3))


def main():
    out = {}
    # gold midnight: 0.75 ATR stop + breakeven (the EA default)
    gd = mdays("XAUUSD")

    def g_run(day, f):
        d0 = day["bias"] if day["bias"] == day["yest"] else 0
        if d0 == 0:
            return None
        dd = dict(day)
        if f is not None:
            dd["bias"] = dd["yest"] = f
        return gtrade(dd, "XAUUSD", 0.75, True)
    out["gold_midnight"] = random_test(gd, g_run)
    print("gold midnight random-direction test:", out["gold_midnight"])

    # NY10 nasdaq: bias + limit + half-range stop + 2R + out 14:00
    nd = cdays("NAS100")

    def n_run(day, f):
        if day["b_wm"] == 0:
            return None
        dd = dict(day)
        if f is not None:
            dd["b_wm"] = f
        return ctrade(dd, "NAS100", "D1 bias", "E2 limit", "S2 half range", "T2 2R", 14)
    out["ny10_nasdaq"] = random_test(nd, n_run)
    print("NY10 Nasdaq random-direction test:", out["ny10_nasdaq"])

    # Prop24: real trades vs the same trades with a random sign on the P&L (direction value only)
    a, b = prop_build()
    P = [t.net for t in a + b if t.symbol in ("BTCUSD", "US500", "NAS100")]
    obs = float(np.mean(P)); sims = np.array([np.mean(np.array(P) * RNG.choice([-1, 1], size=len(P))) for _ in range(5000)])
    out["prop24"] = dict(trades=len(P), real_avg_R=round(obs, 3), p_value_sign_flip=round(float((sims >= obs).mean()), 3),
                         note="sign flip ignores that exits are not symmetric; a rough check only")
    print("Prop24 sign-flip test:", out["prop24"])

    # B. neighbourhood for gold midnight
    from .levels import load_sym
    d, h = load_sym("XAUUSD")
    ny = h.index.tz_convert("America/New_York")
    df = h.copy(); df["hr"] = ny.hour; df["date"] = ny.normalize()
    bias = {day["date"]: (day["bias"] if day["bias"] == day["yest"] else 0, day["atr"]) for day in gd}
    grid = {}
    for eh in (0, 1, 2, 3):
        for xh in (12, 13, 14, 15):
            rs = []
            for k, g in df.groupby("date"):
                if k not in bias or bias[k][0] == 0:
                    continue
                dd, a14 = bias[k]
                ge = g[g.hr == eh]; gx = g[g.hr == xh]
                if len(ge) == 0 or len(gx) == 0:
                    continue
                e = ge.Open.iloc[0]; x = gx.Open.iloc[0]
                w = g[(g.hr >= eh) & (g.hr < xh)]
                stop = e - dd * 0.75 * a14
                hit = (w.Low <= stop).any() if dd == 1 else (w.High >= stop).any()
                px = stop if hit else x
                rs.append(((px - e) * dd - SYMBOLS["XAUUSD"].spread) / (0.75 * a14))
            grid[f"enter {eh:02d}:00 exit {xh}:00"] = round(float(np.mean(rs)), 3) if rs else None
    out["gold_neighbourhood_avgR"] = grid
    print("gold neighbourhood (avg R per trade, stop 0.75 ATR, no breakeven):")
    for k, v in grid.items():
        print("   ", k, v)
    out["multiple_testing"] = dict(rule_versions_tried_approx=400, expected_best_t_by_luck=round(float(np.sqrt(2 * np.log(400))), 2))
    json.dump(out, open("results/falsify.json", "w"), indent=1)


if __name__ == "__main__":
    main()

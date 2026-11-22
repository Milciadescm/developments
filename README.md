# Fib-FVG Dual Engine

A trading bot with two engines that share one Fibonacci model:

| Engine | Bias | Execution | Entry | Stop | Targets |
|---|---|---|---|---|---|
| **Weekly swing** (holds days to weeks) | Monthly + Weekly dealing range (close vs range midpoint) | Daily Turtle 20-day breakout defines the impulse leg; the leg must contain a daily FVG | Limit at **0.705** of the leg (OTE zone 0.618–0.786) | Beyond leg origin (1.0) − 0.25N | TP1 **−0.272** ext (50% off, stop to BE), TP2 **−0.618** ext; runner trails the Turtle 20-day opposite extreme |
| **Micro** (intraday, 4H) | Weekly dealing range | 4H FVG with a displacement candle (≥ 0.8 × ATR14) | OTE 0.705 of the displacement leg, capped at the FVG top | Beyond leg origin − 0.1 ATR | **−0.618** ext; time exit after 30 bars |

Turtle rules on the weekly engine: N = 20-day Wilder ATR, +1 unit every 0.5N in favour (max 4 per market), adds carry a 2N stop, max 6 units per correlated group, total open risk capped at 6%.

Why Fibonacci: the 1s-and-2s video shows the recursion F(n) = F(n−1) + F(n−2) (13 = 8 + 5, "21212212" = "21212" + "212"). The ratio F(n−1)/F(n) converges to 0.618, which sets the OTE entry zone and the extension targets.

## Layout

```
data/                  Yahoo Finance daily + hourly OHLC used for the backtest
fibfvg/config.py       Fibonacci levels, symbol specs, risk + engine settings
fibfvg/engines.py      Weekly swing engine and 4H micro engine (signal generation)
fibfvg/simulator.py    Portfolio replay: sizing, min-lot rules, Turtle caps, prop guard
fibfvg/run_backtest.py Capital tiers, money-management sweep, 10,000-trade Monte Carlo
fibfvg/report.py       Builds results/report.html
mql5/FibFVG_DualEngine.mq5        MT5 Expert Advisor (FundedNext / any MT5 broker)
tradingview/FibFVG_DualEngine.pine TradingView strategy for forward testing
results/               summary.json, per-tier trade logs, MM sweep, Monte Carlo path, report
```

Run it again: `pip install pandas numpy yfinance` then `python -m fibfvg.run_backtest && python -m fibfvg.report`.

## Headline results (real data, after spread)

- Average net R per trade: weekly entries +0.10, Turtle adds +0.17, 4H micro +0.06.
- $50k, 2005–2026, 0.5% per unit: +61% total (~2.2%/yr), 41% max drawdown, 1,081 trades.
- US500, NAS100 and XAGUSD are profitable. XAUUSD and BTCUSD are net negative on these rules.
- Accounts under $1,000 skip most signals because 0.01 lot would exceed the risk budget.
- Funded $50k (0.25% risk, Jul 2024 → now): +21% in 1.8 years, 5.6% max DD, then a 6% trailing limit was hit.
- Recommended: 0.5% per Turtle unit + 0.25% per micro trade (personal), 0.10–0.25% (funded).

## Plan v2 (reverse test + time study)

`python -m fibfvg.experiments` tests two ideas, deciding on early data and checking on later data
(weekly: 2005-15 vs 2016-26; micro: before vs after June 2025):

- **Reversing losers:** reversing every trade loses (mirror −0.06R, 1:1 −0.52R per trade on later data).
  Only gold 4H micro passed (−0.19R → +0.03R, roughly breakeven). `MicroReverse=true` on the XAUUSD chart only;
  switching gold micro off is an equally valid choice.
- **Time rules:** Fibonacci bar counts to fill, London/NY sessions and Mon–Wed weekly entries all failed.
  **Micro fills Monday–Wednesday only** held up (+0.25R vs −0.38R on later data) and is on by default (`MicroMonWedOnly`).
- 2016–26 at $50k: 3.0%/yr → 4.0%/yr, max drawdown 28.9% → 26.2%, profit factor 1.21 → 1.39.

`python -m fibfvg.export_replay` writes the data for `results/lab.html`, the trade-by-trade replay page.

## Two plans: cut losses short, let winners run

`python -m fibfvg.plans_study` (results in `results/plans.json`, replay in `results/lab.html` → "Two plans").

**Plan 1 · Position (weeks to months).** Same entry as the weekly engine. Exit styles chosen on 2005–15, checked on 2016–26:

| Exit style | Net R/trade 2005–15 | 2016–26 | Median hold | $50k 2005–26 |
|---|---|---|---|---|
| V1 (fixed targets) | +0.08 | +0.21 | 6 d | 1.7%/yr, DD 26% |
| Run, 20-day trail | +0.34 | +0.60 | 4 d | 5.6%/yr, DD 25% |
| Chandelier + time stop | +0.18 | +0.44 | 10 d | 4.7%/yr, DD 18% |
| **Monthly (default)** | **+0.38** | **+1.66** | 18 d (top 10%: 7+ months) | **10.7%/yr, DD 36%** |

Monthly = half off at −0.272, breakeven, runner trails the 55-day low, out after 10 days if never +0.5R.
Adds close with the first unit. Chandelier is the funded-account choice (0.25% risk since 2016: 3.2%/yr, 3.6% max DD, no breach).
EA: `PositionExit`, `TimeStopDays`, `TimeStopMinR`. Pine: "Plan 1 exit style".

**Plan 2 · Micro (1m, 5m, 15m, 30m, 1H).** No timeframe has an edge after spread (gross +0.01 to +0.17R, net
negative or inconsistent between halves; 1m only 26 days and 5–30m about 81 days of data). Letting winners run cut the average
loss from ~−1.2R to ~−0.7R but also cut the wins. `UseMicroEngine` now defaults to false; use `MicroTF` + `MicroLetRun`
on a demo account only.

## Limits

- The S&P 15s/30s/45s FVG idea is in the EA as an experimental module (`UseSecondsScalper`, off by default). It is **not backtested**: no second-level history was available.
- MT5 contract specs in `config.py` are typical values. Check your broker's symbol specification.
- The EA keeps TP1 state in memory. After a terminal restart, TP1 partials for open weekly trades are not re-armed (TP2, stops and trailing still work).
- The EA and Pine script were written to match the Python rules but were not compiled here. Compile in MetaEditor and the Pine editor, then run them on a demo before going live.

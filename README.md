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

## Limits

- The S&P 15s/30s/45s FVG idea is in the EA as an experimental module (`UseSecondsScalper`, off by default). It is **not backtested**: no second-level history was available.
- MT5 contract specs in `config.py` are typical values. Check your broker's symbol specification.
- The EA keeps TP1 state in memory. After a terminal restart, TP1 partials for open weekly trades are not re-armed (TP2, stops and trailing still work).
- The EA and Pine script were written to match the Python rules but were not compiled here. Compile in MetaEditor and the Pine editor, then run them on a demo before going live.

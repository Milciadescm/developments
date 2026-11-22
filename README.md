# FibFVG Pro

Trading bot for XAUUSD, XAGUSD, BTCUSD, US500 and NAS100 on instant prop accounts (no profit target,
no consistency rule, 6% max loss). Only the plans that made money on 2024 → now data are kept.

| Plan | What it does | 2024 → now (net R per trade, after spread) |
|---|---|---|
| Plan 1 Position | Monthly + weekly bias, daily Turtle breakout leg with a fair value gap, limit at the 0.705 Fibonacci OTE, Turtle adds, chandelier exit, breakeven at +1R, 10-day time stop | +0.82R · 52% wins · realized R:R 3.3 |
| Plan 3 Levels | Weekly bias, 1H reaction at the 00/20/50/60/80 levels (no NY lunch), stop = 1 daily ATR, breakeven at +1R, 5-day-low trail from +2R, adds only while the first unit is ≥ +1R | +0.16R · 28% wins · realized R:R 3.4 |
| Plan 3B Levels · 2R bank (default) | Plan 3 plus half of every unit closed at +2R | +0.11R · 32% wins · realized R:R 2.6, earlier rewards |

Default portfolio: **Core + 2R bank** (Plan 1 + Plan 3B) in **Normal** mode.
Instant Premium $100K, Jul 2024 → now: $24,501 paid to the trader, 14 rewards, worst drawdown 4.65%, no breach.
12-month roadmap from 16 start months: first reward within 90 days in 69% of starts, median net $15,809 (worst +$3,827).

## Files

```
fibfvg/edgebook.py   all results (plans, pips, weak spots, prop, roadmap)  -> results/edge_book.json, trades_*.csv
fibfvg/playbook.py   builds results/playbook.html from those results
fibfvg/plans.py      Plan 1 engine          fibfvg/levels.py   Plan 3 / 3B engine
fibfvg/propsim.py    prop-account simulator (guard, rewards, edge gate)
fibfvg/roadmap.py    12-month payout roadmap    fibfvg/calendar.py  CPI / NFP / FOMC dates
mql5/FibFVG_Pro.mq5  mql4/FibFVG_Pro.mq4  ctrader/FibFVGPro.cs   the bots (see INSTALL.md)
data/                Yahoo Finance daily (2024+) and hourly bars used by the plans
```

Rebuild everything: `pip install pandas numpy yfinance && python -m fibfvg.edgebook && python -m fibfvg.playbook`.
Rejected ideas and their numbers are in `RESEARCH_LOG.md`.

## Limits

- Hourly history from Yahoo starts July 2024 (BTC November 2024). Gold/silver use futures prices; indices use cash (daily) and futures (hourly).
- Contract sizes and spreads in `fibfvg/config.py` are typical MT5 CFD values; the bots read the broker's real values.
- None of the bots has been compiled here (no MetaEditor or cTrader in this environment). Compile, then run on a demo first.
- July 2024 → now was a strong trend for gold and silver; longer history earned less per year.

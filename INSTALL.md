# FibFVG Pro: install and run

One bot, three platforms, same rules. Drop it on **any one chart**. It finds your broker's names for
gold, silver, BTC, US500 and NAS100 (GOLD, XAUUSD.r, USTEC, US100.cash and so on) and trades all of them from that chart.

| Platform | File | Install |
|---|---|---|
| MetaTrader 5 | `mql5/FibFVG_Pro.mq5` | File → Open Data Folder → `MQL5/Experts` → paste → open in MetaEditor → Compile (F7) → drag onto a chart → tick "Allow Algo Trading" |
| MetaTrader 4 | `mql4/FibFVG_Pro.mq4` | Same, in `MQL4/Experts`; enable "Allow live trading" |
| cTrader | `ctrader/FibFVGPro.cs` | Automate → New cBot → paste → Build → add instance to a chart → Start |

None of the three files has been compiled yet. Fix any compile messages, then run on a demo first.

## Settings that matter

| Setting | Default | Choose |
|---|---|---|
| Preset | FundedNext Stellar Instant | FundedNext Stellar Instant (6% trailing, no daily), Instant Premium (3% daily, 6% max), Personal, Custom |
| RiskMode | Normal | Conservative 0.15% / 0.05% · Normal 0.25% / 0.10% · Aggressive 0.50% / 0.25% · Edge gate |
| Plan1Exit | Chandelier | Chandelier for prop accounts, Monthly for personal money |
| KillZonesOnly | false | true limits entries to 20, 00, 02, 06, 07, 09, 10, 15 NY (tested: fewer trades, no gain) |
| StartBalance | 0 (auto) | set it to the account's starting size on a funded account |

Risk is a share of the **starting balance** per unit (Plan 1 / Plan 3).

## What protects the account

- Before every trade: drawdown from peak + open stop-risk + the new trade's risk must stay under the firm limit minus 1%
  (5% of a 6% limit) and under the daily limit minus 0.5%. Near the line, trades are shrunk to half the room left.
- Emergency line: equity within 0.5% of the firm's max-loss line closes everything and halts the bot (restart needed);
  within 0.3% of the daily line closes everything until the next day.
- State (start balance, peak, Plan 1 TP1 status, adds) is kept in terminal global variables / cTrader LocalStorage, so restarts are safe.
- Lots below the broker's minimum are skipped, never rounded up.

The chart panel shows the mode, the room left before the bot's line, and lots per market (recommended and open).

## The edge rule (RiskMode = Edge gate)

```
EDGE_CONFIRMED -> Normal     : last 20 closed positions  sum >= +3R  and PF >= 1.3  and drawdown <= 2%
STRONG_EDGE    -> Aggressive : last 40 closed positions  sum >= +8R  and PF >= 1.5  and drawdown <= 1.5%
otherwise (or drawdown >= 3%) -> Conservative
```

## Bi-weekly withdrawals ($1,000–$2,000)

1. Every 14 days, on each account, request only the **"withdrawable now"** amount on the chart panel
   (balance − start − open stop-risk). Open trades can stay open. The bot detects the withdrawal and moves its
   high-water mark down by the same amount, so the guard does not treat it as a loss.
2. Put every reward into a separate reserve. Pay yourself from the reserve, never straight from rewards:
   start $1,000 at a $13,000 reserve, $1,500 at $19,500, $2,000 at $26,000; drop one level if the reserve is
   under 6 payments of the current level.
3. Backtest (Jul 2024 → now): 3 × $100K Instant Premium, Normal → first salary Oct 2025, $2,000 for 28 fortnights,
   $58,500 paid, no missed payment. Rewards are lumpy (9 of 63 fortnights per account). Never raise risk to meet a payment.
4. Same trades on every account: income and drawdowns scale together. Check each firm's maximum allocation and
   multi-account rules.

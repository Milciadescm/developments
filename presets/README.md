# $100K plug-and-play presets

| File | Platform | Use |
|---|---|---|
| FibFVG_Pro_100K_Normal.set | MT5 / MT4 | Instant Premium-style $100K (3% daily, 6% max). Recommended. |
| FibFVG_Pro_100K_Normal_NoDaily.set | MT5 / MT4 | $100K with 6% trailing max loss and no daily limit (FundedNext Stellar Instant rules). |
| FibFVG_Pro_100K_Aggressive.set | MT5 / MT4 | Same account, Aggressive mode (paid less in the backtest). |
| *.cbotset | cTrader | Same three, as cBot parameter files. If import fails, type the values in the cBot's parameter panel. |

Steps: compile the bot (MetaEditor F7 / cTrader Build) → attach it to ONE chart (any symbol) → Inputs → Load the preset → enable algo trading.
The bot trades XAUUSD, XAGUSD, BTCUSD, US500 and NAS100 from that one chart and shows lot sizes, the guard's room and the payout plan.

Payout plan on the panel: month-to-date closed profit is withdrawn at each month end so the account restarts at $100,000.
Month 1 → founder's private account. Months 2+ collect per quarter → Cueto & Co → new $100K accounts (fee set by AccountFee).

# Cueto & Co. / FibFVG Pro — working rules

## One master document
Everything (tests, results, plans, bot changes, live trades, payouts, accounts, company steps) is logged in the
**Cueto & Co. — Master Document**: https://claude.ai/artifact/6ugpp8DiUYF5Np6ESd1KeL
- Add each new item as a row at the top of the **Log (the best result wins)** tab (date, type, what, result, decision).
- Update the other tabs (Strategy, Tests, Plans, Setup, Company, Risks) when their content changes.
- Do not create new artifacts for results; earlier artifacts and the white paper are archive only.

## The best result wins
The bot changes only if a new rule beats the current best on all four checks:
1. More R per trade after spread and swap fees.
2. Profitable in both halves of the data (split 2025-08-19).
3. t-statistic >= 2.
4. Worst drawdown on a $100K account < 5% (firm line 6%).
Anything that fails is logged as rejected or optional and stays out of the default preset.

## Two kinds of money
- Prop accounts (Wallet 1): no trade held over 24 hours or over the weekend. Current best: `fibfvg/prop24.py`
  (daily + 4-hour setups at 0.705, stop at leg origin, flat within 24 h, 0.5% per trade): +0.23R, t = 1.8.
- Cueto & Co. real money (Wallet 2): holds allowed. Bot v3 position plan, 0.5% per unit, chandelier exit
  (+0.71R after swaps, t = 4.0). Starts when Wallet 2 >= $100K, half in the bot, 10% hard stop (`fibfvg/livefund.py`).
- Wallets (`fibfvg/wallets3.py`): one prop firm at a time up to 50 accounts; below 50: 50% buys accounts,
  25% Wallet 2, 25% Wallet 3 crypto; at 50: 70% Wallet 2, 25% crypto, 5% burn reserve (5 accounts), then to Wallet 2.

First live $100K account: 1 December 2026. All numbers before then are backtests.

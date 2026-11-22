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

Current best: FibFVG Pro v3, position plan only, 0.5% per unit, chandelier exit (+0.71R after swaps, t = 4.0).
First live $100K account: 1 December 2026. All numbers before then are backtests.

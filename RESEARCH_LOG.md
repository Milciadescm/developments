# Research log: ideas tested and removed

Kept so nobody re-tests them. Numbers are net R per trade after spread unless stated.

| Idea | Result | Why removed |
|---|---|---|
| Weekly swing v1 (fixed TP1/TP2), 2005–2026 | +0.10R, ~2%/yr, 41% DD at $50k | Superseded by Plan 1 exits (letting winners run tripled the edge) |
| Micro 4H FVG engine | +0.06R, +0.03R out of sample | Too thin |
| Micro 1m / 5m / 15m / 30m / 1H FVG (3 exit styles) | Gross +0.01 to +0.17R, net negative or flips between halves | No edge after spread |
| S&P 15/30/45-second FVG scalper | Not testable (no second data) | Never validated |
| Reversing losing trades (mirror / 1:1) | −0.06R / −0.52R | Costs paid on both sides; only gold micro reached breakeven |
| Fibonacci bar-count timing, London/NY sessions, Mon–Wed weekly entries | Helped early data, failed later data | Overfit |
| Levels + kill zones with the stop past the reaction wick | −0.12 to −0.36R (gross negative); a few 10R/50R runners | Stop inside normal noise |
| Kill-zone-only entries (daily-ATR stop) | No better than all hours, fewer trades | Off by default (`KillZonesOnly`) |
| Fixed 2R target on the levels entries | +2R hit first ~35%; ≈ breakeven after costs | No edge |
| London Judas (Asia-range sweep) + 2R | −0.155R (both halves negative) | No edge |
| NY sweep of the previous day's high/low + 2R | −0.105R (both halves negative) | No edge |
| Half at +2R with a half-day-range stop | −0.03R | Stop too tight |
| Skipping CPI days | No measurable change (7 trades) | Not needed |

## Risk gates (Core + 2R bank, Instant Premium $100K, Jul 2024 → Nov 2026) — `results/gates.json`

| Gate | Paid | Worst DD | Paid per 1% DD | 12-month median (worst) |
|---|---|---|---|---|
| Fixed Normal (kept: prop default) | $24,501 | 4.65% | $5,269 | $15,809 (+$3,827) |
| Market gate + Normal (kept: company/fund money; not yet in the bots) | $17,424 | 2.55% | $6,833 | $12,432 (+$1,371) |
| Normal-first gate | $21,855 | 3.98% | $5,491 | $10,770 (−$427) |
| Edge gate (20/40-trade rule) | $16,138 | 4.47% | $3,610 | $9,214 (−$113) |
| Fixed Aggressive | $8,184 | 4.94% | $1,657 | $20,023 (−$740) |

No gate produced a larger edge; the market gate trades pay for half the drawdown.

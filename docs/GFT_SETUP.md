# Goat Funded Trader: setting up the two EAs

| EA | Market | When it trades | Risk default | Account |
|---|---|---|---|---|
| `mql5/FibFVG_NY10.mq5` | Nasdaq 100 | Limit order at 10:00 New York, filled by 11:00 or cancelled; breakeven at +0.5R; closed at 14:00 | 0.6% of the start balance | **$5K and up** |
| `mql5/FibFVG_GoldMidnight.mq5` | Gold | Market order at 00:00 New York when the trend and yesterday agree; closed at 14:00 | 0.9% (cost of the emergency stop) | **$50K and up** (on $5K the 0.01-lot minimum is too big) |

Both EAs are built for **Instant Premium**: 6% intraday trailing max loss (stops rising at the start balance),
3% daily loss from 17:00 New York, 1% floating-loss limit for all open trades, payouts every 14 days after
5 profitable days of at least +0.5%. Each EA:
- trades only one position at a time and never holds overnight;
- sizes every trade so all open stops stay under the 1% floating limit, and stops trading 1% before the 6% line;
- closes its trades if the account comes within 0.5% of the 6% line or 2.7% of the daily limit;
- counts your profitable days since the last payout on its panel (5 needed per payout);
- writes every event to `MQL5\Files\FibFVG_<EA>_<account>.csv`.

## Before you buy

- Start small: the **$5K Instant Premium** ($74 with the current code). Only use money that is not needed for
  debts or bills; the fee is refundable only once the account pays.
- Backtests (Jul 2024 - Nov 2026, hourly data) are encouraging but **not proven** (t about 1.4-1.5).
  The first weeks are a live test.

## Install (your own Windows PC: GFT bans VPS, VPN and proxies)

1. Install GFT's MT5 and log in. Do not use a VPN or remote server at any time.
2. `File > Open Data Folder > MQL5 > Experts`: copy `FibFVG_NY10.mq5` (and `FibFVG_GoldMidnight.mq5` for $50K+).
   `MQL5 > Presets`: copy the files from `presets/gft/`.
3. Open each `.mq5` in MetaEditor (F4) and press **Compile (F7)**. Send me a screenshot if the Errors tab shows anything.
4. `Tools > Options > Expert Advisors`: tick *Allow algorithmic trading*; the **Algo Trading** button must be green.
5. Open a **Nasdaq H1** chart (NAS100 / USTEC / US100), drag **FibFVG_NY10** onto it, *Inputs > Load*
   `GFT_5K_NY10_Nasdaq.set`, OK. The panel must show the symbol, the firm line and "waiting for 10:00 New York".
6. Keep the PC on and MetaTrader open from 09:30 to 14:30 New York on trading days (the gold EA: 23:30 to 14:30).
7. Keep this repository: GFT may ask for proof that you built the EA (source code and its history).

## What to send

- After each trading day or each week: a screenshot of the panel and the History tab, and the CSV log.
- Any `ERROR` or `HALT` line in the log, straight away.

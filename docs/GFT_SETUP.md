# Goat Funded Trader: setting up the EA

> **23 Nov 2026: FibFVG_NY10 (Nasdaq 10am candle) is withdrawn.** Its backtest edge came from a bug (breakeven triggered by the fill candle's high, which came before the fill). Corrected, it loses on every market. Do not run it.

| EA | Market | When it trades | Risk default | Account |
|---|---|---|---|---|
| `mql5/FibFVG_GoldMidnight.mq5` | Gold | Market order at 00:00 New York when the trend and yesterday agree; closed at 14:00 | 0.9% (cost of the emergency stop) | **$50K and up** (on $5K the 0.01-lot minimum is too big) |

The EA is built for **Instant Premium**: 6% intraday trailing max loss (stops rising at the start balance),
3% daily loss from 17:00 New York, 1% floating-loss limit for all open trades, payouts every 14 days after
5 profitable days of at least +0.5%. It:
- trades only one position at a time and never holds overnight;
- sizes every trade so all open stops stay under the 1% floating limit, and stops trading 1% before the 6% line;
- closes its trades if the account comes within 0.5% of the 6% line or 2.7% of the daily limit;
- counts your profitable days since the last payout on its panel (5 needed per payout);
- writes every event to `MQL5\Files\FibFVG_<EA>_<account>.csv`.

## Before you buy

- The gold EA needs $10K+ (0.01-lot minimum); $50K or $100K is where it was tested. Only use money that is not
  needed for debts or bills; the fee is refunded only once the account pays.
- Backtests (Jul 2024 - Nov 2026, hourly data) are encouraging but **not proven** (t about 1.4-1.5).
  The first weeks are a live test.

## Install (your own Windows PC: GFT bans VPS, VPN and proxies)

1. Install GFT's MT5 and log in. Do not use a VPN or remote server at any time.
2. `File > Open Data Folder > MQL5 > Experts`: copy `FibFVG_GoldMidnight.mq5` (or `FibFVG_Prop24.mq5` with preset `presets/GFT_InstantPremium_100K_Prop24.set`).
   `MQL5 > Presets`: copy the files from `presets/gft/`.
3. Open each `.mq5` in MetaEditor (F4) and press **Compile (F7)**. Send me a screenshot if the Errors tab shows anything.
4. `Tools > Options > Expert Advisors`: tick *Allow algorithmic trading*; the **Algo Trading** button must be green.
5. Open a **gold H1** chart, drag **FibFVG_GoldMidnight** onto it, *Inputs > Load* `GFT_50K_GoldMidnight.set`
   (or the $100K / silver preset), OK. The panel must show the symbol, the firm line and "waiting for 00:00 New York".
6. Keep the PC on and MetaTrader open from 23:30 to 14:30 New York on trading days.
7. Keep this repository: GFT may ask for proof that you built the EA (source code and its history).

## What to send

- After each trading day or each week: a screenshot of the panel and the History tab, and the CSV log.
- Any `ERROR` or `HALT` line in the log, straight away.

# 4-week demo test: Exness (Normal) vs Vantage (Aggressive)

Two bots run on each demo account at the same time, so all 5 markets trade together:

| Bot | File | Wallet | Markets | Holds | Normal (Exness) | Aggressive (Vantage) |
|---|---|---|---|---|---|---|
| Prop24 | `mql5/FibFVG_Prop24.mq5` | 1, prop accounts | BTC, S&P 500, Nasdaq 100 | up to 24 hours | 0.5% of $100K per trade | 0.75% of $100K per trade |
| Hold | `mql5/FibFVG_Hold.mq5` | 2, Cueto & Co. real money | Gold, silver | weeks to a year | 0.5% of $50K per unit | 1.0% of $50K per unit |

Each bot keeps its **own virtual account** (its start balance plus only its own trades, found by magic number),
so the two bots can share one demo account without mixing results. Each writes its own log file.

## 1. Set up (once per broker)

1. **Demo account.** Exness: Personal Area > Open new account > Demo > MT5 Standard. Vantage: Client Portal > Demo
   account > MT5. Balance **$150,000 or more** (Prop24 trades $100K, Hold trades $50K). If the broker caps the demo
   lower, use the cap: the bots size from their own virtual balances, and only margin is shared. Leverage 1:100 or more.
2. **MetaTrader 5.** Install each broker's MT5 in its **own folder** (two terminals), so both run at the same time.
   Log in with the demo account.
3. **Copy the files.** `File > Open Data Folder`:
   - `MQL5\Experts` ← `FibFVG_Prop24.mq5` and `FibFVG_Hold.mq5`
   - `MQL5\Presets` ← Exness: `Prop24_Normal_Exness.set`, `Hold_Normal_Exness.set`;
     Vantage: `Prop24_Aggressive_Vantage.set`, `Hold_Aggressive_Vantage.set`
4. **Compile.** Open each `.mq5` in MetaEditor (F4) and press **Compile (F7)**. If the Errors tab shows anything,
   send me a screenshot of it before going on.
5. **Market Watch.** Right-click > *Show All* (or add the symbols): Exness Standard uses `BTCUSDm`, `US500m`,
   `USTECm`, `XAUUSDm`, `XAGUSDm`; Vantage uses `BTCUSD`, `SP500`, `NAS100`, `XAUUSD`, `XAGUSD`.
6. **Algo trading.** `Tools > Options > Expert Advisors` > tick *Allow algorithmic trading*; the toolbar
   **Algo Trading** button must be green.
7. **Attach.**
   - Open a **BTCUSD H1** chart, drag **FibFVG_Prop24** onto it, *Inputs > Load* the Prop24 preset, OK.
   - Open an **XAUUSD H1** chart, drag **FibFVG_Hold** onto it, *Inputs > Load* the Hold preset, OK.
   - The panel must list **3 markets** (Prop24) and **2 markets** (Hold). If one is missing, type your broker's exact
     names in `SymbolsToTrade` (e.g. `BTCUSDm,US500m,USTECm`).
8. `File > Profiles > Save As` "FibFVG demo", and keep both terminals running 24/7 (PC or VPS) for 4 weeks.

## 2. What to send me

| When | Send |
|---|---|
| Day 0 | Screenshot of each bot's panel (4 panels: 2 bots × 2 brokers) and the **Experts** tab showing the `START` lines |
| Every Friday after 17:00 New York | Screenshots of each panel, the **Trade** tab and the **History** tab (with the Magic and Comment columns on); upload the 4 log files |
| Any time an error appears | Screenshot of the **Experts** and **Journal** tabs |

**Log files:** `File > Open Data Folder > MQL5 > Files`:
- `FibFVG_Prop24_<account>.csv`
- `FibFVG_Hold_<account>.csv`

Each row is one event: `START`, `ORDER`, `FILL`, `STOP` (stop moved), `EXIT` (with P&L, R and reason), `CANCEL`,
`SKIP`, `ERROR`, `HALT`, `DAY` (daily win rate, average win and loss in R, RR), `STOP` (bot removed).

## 3. What I will check every week

1. **Rules followed:** every `ORDER` matches the chart (20-bar breakout, leg at least 1.5 ATR, fair value gap, entry at
   0.705, stop at the leg origin; Hold stop 0.25 N beyond it).
2. **Prop24 timing:** no trade open longer than 24 hours; nothing open after Friday 16:00 New York.
3. **Sizing:** `risk_usd` ≈ 0.5% / 0.75% of $100K (Prop24) and 0.5% / 1% of the Hold balance per unit.
4. **Stops:** Hold moves the first unit to breakeven at +1R and then trails the 120-day low; adds close with the
   first unit.
5. **Errors:** every `ERROR` explained (symbol names, fill mode, market closed, minimum lot).
6. **Results vs backtest:** win rate, RR and R per trade from the `DAY` lines.

## 4. What to expect in 4 weeks

| | Backtest 2024–2026 | Expected in 4 weeks |
|---|---|---|
| Prop24 (3 markets) | 82 trades in 34 months: 58.5% wins, avg win +1.20R, avg loss −0.84R, RR 1.42 | about 2–3 trades (0–6 is normal) |
| Hold (gold + silver) | 45 units in 29 months; 2006–2026: about 1 in 7 units wins, but winners average ~18× the losers | 0–3 fills; a position may stay open for months |

Four weeks proves the bots **follow the rules on a real broker feed**. It cannot prove profit: with 2–6 trades,
luck dominates. Profit is judged after 3 months (Prop24) and 12 months (Hold).

## 5. What the A/B test can and cannot show

- **Size:** Normal and Aggressive use the same rules; only the size differs. In R per trade they should match;
  in dollars Aggressive should be 1.5× (Prop24) and 2× (Hold).
- **Broker candles differ.** Exness MT5 runs on UTC (server GMT+0), so its daily and 4-hour candles match the
  backtest. Vantage runs on GMT+2/+3, so its daily candle closes at 17:00 New York and its 4-hour candles start
  2–3 hours later. Some setups will appear on one broker and not the other. That is part of what this test measures:
  which candle clock the live bots should use.
- **Prices and spreads:** small differences in fills and spreads change R slightly.

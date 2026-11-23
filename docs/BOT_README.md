# FibFVG Pro v3 — bot README and MT5 setup (Windows PC running 24/7)

## What the bot does, in one paragraph

FibFVG Pro trades gold (XAUUSD), silver (XAGUSD), Bitcoin (BTCUSD), S&P 500 (US500) and Nasdaq 100 (NAS100)
from **one chart**. It only trades in the direction of the monthly and weekly trend. When price breaks the
20-day high (or low) with a fair value gap, it places a limit order at the **0.705 Fibonacci level** of that
move (the OTE zone), with the stop just beyond the start of the move. Winners are held for days to weeks: the
stop moves to breakeven at +1R and then trails 3 daily ranges behind the best price. Losers are cut after 10
days if they never reached +0.5R. While a trade works, it adds up to 3 more units (Turtle rules).
A guard keeps drawdown plus open risk under 5% so the account never touches the firm's 6% line.

## Best rules for a $100K account (v3, file `presets/FibFVG_Pro_100K_Best.set`)

| Setting | Value | Why |
|---|---|---|
| Position plan (Plan 1) | ON | +0.71R per trade after swap fees, proven (t = 4.0) |
| Levels plan (Plan 3) | OFF | After swap fees only +0.06R and more drawdown |
| Risk per unit | 0.5% of $100,000 = $500 | Best pay with worst drawdown under 5% in backtest |
| Exit | Chandelier (3 daily ranges), breakeven at +1R, 10-day time stop | Lets winners run, cuts dead trades |
| Guard | 5% (firm line 6%), shrinks trades near the line | No breach in any test |
| Day trading only | NOT used | Every intraday-only version lost money (−0.02R to −0.31R per trade) |

Backtest, July 2024 → November 2026, swaps included: **$23,541 paid** on one $100K account, worst drawdown
under 5%, about 4 trades a month across 5 markets, median $13,900 paid per 12 months; 1 of 16 start months paid
$0 in its first year. These are simulations, not live results.

## Weekend and market-close behaviour

- The bot checks each market before doing anything: the broker's trading session must be open **and** a fresh
  quote must have arrived in the last 10 minutes. Closed markets (Friday 17:00 NY → Sunday 18:00 NY for gold,
  silver and indices; daily breaks; holidays) are simply skipped and retried every 5 seconds.
- BTC trades through the weekend.
- Positions stay open over the weekend with their stops in place at the broker. A gap can jump a stop; the guard
  keeps a 1% buffer for this.
- State (start balance, peak, trade progress) is saved in terminal global variables, so a restart, a reboot or
  a weekend disconnect does not lose track of trades.

## Setup on your Windows PC (runs 24/7)

### 1. Install

1. Download MetaTrader 5 from your prop firm's dashboard (or metatrader5.com) and log in with the $100K account.
2. `File > Open Data Folder` → `MQL5\Experts` → copy `FibFVG_Pro.mq5` there.
3. `MQL5\Presets` → copy `FibFVG_Pro_100K_Best.set` there.
4. Open `FibFVG_Pro.mq5` in MetaEditor (F4) → **Compile (F7)**. Fix any message it shows before going on.

### 2. Turn on algo trading

1. `Tools > Options > Expert Advisors`: tick **Allow algorithmic trading**. Untick *Disable algorithmic trading
   when the account has been changed* and *…when the profile has been changed*.
2. Click the **Algo Trading** button on the toolbar (it turns green).

### 3. Attach the bot

1. Open one chart (XAUUSD H1 is fine). Drag **FibFVG_Pro** from the Navigator onto it.
2. **Common** tab: tick *Allow Algo Trading*. **Inputs** tab: **Load** → `FibFVG_Pro_100K_Best.set` → OK.
3. Check the panel on the chart: it lists the 5 markets it found, the guard room and lots. A smiley/blue hat icon
   in the chart's top-right corner means it is running.
4. `File > Profiles > Save As` "FibFVG" so MT5 reopens this chart and bot after a restart.

### 4. Keep the PC running 24/7

| Item | Setting |
|---|---|
| Power | `Settings > System > Power`: sleep **Never**, screen off is fine. Disable hibernate. |
| Windows Update | Set *active hours*, pause updates for 5 weeks at a time, and restart manually on Saturdays |
| Auto-start | Put a shortcut to `terminal64.exe` in `shell:startup`; enable automatic sign-in |
| BIOS | *Restore on AC power loss* = **Power On**, so the PC restarts itself after an outage |
| Power cut | UPS (battery backup) of 600–1000 VA |
| Internet | Backup 4G/5G router or phone hotspot; MT5 reconnects by itself |
| Check | Look at the Journal and Experts tabs once a day; the panel shows "HALTED" if the guard ever stops the bot |

A Windows VPS in a data centre (or the MT5 built-in VPS) is more reliable than a home PC and removes the power
and internet risks. **Check the firm first:** Goat Funded Trader bans VPS, VPN, proxies and any hosting service
on all accounts from 6 Oct 2026 (the bot must run on your own computer and connection), and FundedNext allows
EAs and VPS only on $5K-$25K accounts, each with a paid add-on. Never use a VPN while trading a prop account.

**Proof of ownership:** some firms (Goat Funded Trader) allow only EAs you built yourself and may ask for the
source code. Keep this repository (source code and its commit history) as that proof.

### 5. Many accounts (up to 50 per firm)

- MT5 logs in one account per terminal. For several accounts, install MT5 once per account in separate folders
  (or use the firm's multi-terminal installer) and attach the bot to each with the same preset.
- Same rules + same prices = the same entries on every account, so a trade copier is optional. If you use one,
  copy *signals*, not lots: each account sizes its own trade from its own $100K start.
- Each terminal uses roughly 300–500 MB of RAM. 50 terminals need a VPS with about 16–32 GB RAM.
- Example sizing: if the bot opens 0.05 lots of XAGUSD on one account, 50 accounts hold 2.5 lots in total — 50
  times the dollar profit and 50 times the dollar loss. Check each firm's rules on identical trades across accounts.

## Costs (approximate, verify before buying)

| Item | Cost | When |
|---|---|---|
| $100K instant account | $740 (promo seen in your screenshot); about $1,480 at full price | Per account |
| MetaTrader 5 and MetaEditor | Free | — |
| Home PC electricity, 24/7 | about $10–20 a month | Monthly |
| UPS 600–1000 VA | about $80–150 | Once |
| Backup internet | about $20–40 a month | Monthly |
| Windows VPS, 1–3 terminals | about $15–40 a month | Monthly |
| Windows VPS, 50 terminals (16–32 GB RAM) | about $80–200 a month | Monthly |
| Trade copier (optional) | about $20–50 a month or $100–300 once | Optional |
| Hardware crypto wallet (cold wallet) | about $79–150 | Once |

## Files

| File | Use |
|---|---|
| `mql5/FibFVG_Pro.mq5` | MetaTrader 5 bot |
| `mql4/FibFVG_Pro.mq4` | MetaTrader 4 version |
| `ctrader/FibFVGPro.cs` | cTrader version |
| `presets/FibFVG_Pro_100K_Best.set` | Best rules, $100K, 6% max loss, no daily limit |
| `presets/FibFVG_Pro_100K_Best_3pctDaily.set` | Same, for firms with a 3% daily limit |
| `presets/FibFVG_Pro_100K_Best.cbotset` | cTrader parameters |

The bots have not been compiled or run live yet. Compile, run 4 weeks on a demo or the first account with
close attention, and compare its trades with the backtest before adding accounts.

"""Build results/report.html (self-contained, inline SVG) from results/*.json/csv."""
import html
import json

import numpy as np
import pandas as pd

S = json.load(open("results/summary.json"))
CURVE = pd.read_csv("results/equity_50000_noguard.csv")
CURVE["time"] = pd.to_datetime(CURVE.time, utc=True, format="mixed")


def money(x):
    x = float(x)
    return f"${x:,.0f}" if abs(x) >= 100 else f"${x:,.2f}"


def svg_line(df, w=760, h=260, pad=(48, 16, 28, 64)):
    t = (df.time - df.time.min()).dt.total_seconds().values
    y = df.balance.values
    l, tp, b, r = pad[3], pad[1], pad[2], pad[0]
    x0, x1, y0, y1 = t.min(), t.max(), y.min() * 0.95, y.max() * 1.03
    X = lambda v: l + (v - x0) / (x1 - x0) * (w - l - r)
    Y = lambda v: tp + (1 - (v - y0) / (y1 - y0)) * (h - tp - b)
    pts = " ".join(f"{X(a):.1f},{Y(c):.1f}" for a, c in zip(t, y))
    area = f"{X(t[0]):.1f},{Y(y0):.1f} " + pts + f" {X(t[-1]):.1f},{Y(y0):.1f}"
    ticks = ""
    for v in np.linspace(y0, y1, 5):
        ticks += f'<line x1="{l}" x2="{w - r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/><text x="{l - 6}" y="{Y(v) + 4:.1f}" class="ax" text-anchor="end">{v / 1000:.0f}k</text>'
    for yr in range(df.time.min().year + 1, df.time.max().year + 1, 3):
        ts = (pd.Timestamp(f"{yr}-01-01", tz="UTC") - df.time.min()).total_seconds()
        ticks += f'<text x="{X(ts):.1f}" y="{h - 8}" class="ax" text-anchor="middle">{yr}</text>'
    start = f'<line x1="{l}" x2="{w - r}" y1="{Y(50000):.1f}" y2="{Y(50000):.1f}" class="base"/>'
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Equity curve">{ticks}{start}'
            f'<polygon points="{area}" class="area"/><polyline points="{pts}" class="line"/>'
            f'<circle cx="{X(t[-1]):.1f}" cy="{Y(y[-1]):.1f}" r="4" class="dot"/></svg>')


def svg_bars(rows, w=760, h=220):
    l, r, tp, b = 40, 10, 12, 28
    vals = [x["sum"] for x in rows]
    m = max(abs(min(vals)), abs(max(vals))) * 1.1
    bw = (w - l - r) / len(rows)
    Y = lambda v: tp + (1 - (v + m) / (2 * m)) * (h - tp - b)
    out = f'<line x1="{l}" x2="{w - r}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="base"/>'
    for v in (-m / 1.1, m / 1.1):
        out += f'<text x="{l - 6}" y="{Y(v) + 4:.1f}" class="ax" text-anchor="end">{v:+.0f}R</text>'
    for i, x in enumerate(rows):
        v = x["sum"]
        y0, y1 = sorted([Y(0), Y(v)])
        cls = "pos" if v >= 0 else "neg"
        out += f'<rect x="{l + i * bw + 2:.1f}" y="{y0:.1f}" width="{bw - 4:.1f}" height="{max(1, y1 - y0):.1f}" class="{cls}"><title>{int(x["year"])}: {v:+.1f}R over {int(x["count"])} trades</title></rect>'
        if int(x["year"]) % 3 == 2 or i == len(rows) - 1:
            out += f'<text x="{l + i * bw + bw / 2:.1f}" y="{h - 8}" class="ax" text-anchor="middle">{int(x["year"])}</text>'
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Net R by year">{out}</svg>'


def table(df, cols, fmt=None, cls=""):
    fmt = fmt or {}
    th = "".join(f"<th>{html.escape(c[1])}</th>" for c in cols)
    trs = ""
    for _, row in df.iterrows():
        tds = ""
        for key, _ in cols:
            v = row[key]
            s = fmt[key](v) if key in fmt else ("—" if (v is None or (isinstance(v, float) and np.isnan(v))) else html.escape(str(v)))
            tds += f"<td>{s}</td>"
        trs += f"<tr>{tds}</tr>"
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


tiers = pd.DataFrame(S["tiers"])
tiers["capital_s"] = tiers.capital.apply(lambda c: money(c) if not isinstance(c, str) else "$50,000 · no guard")
tiers.loc[tiers.capital == 50000, "capital_s"] = "$50,000 · prop guard"
tiers["breach"] = tiers.breach.fillna("")
tier_tbl = table(tiers, [("capital_s", "Start"), ("trades", "Trades taken"), ("min_lot", "Skipped: below min lot"),
                         ("final", "End balance"), ("ret_pct", "Total return"), ("cagr_pct", "Per year"),
                         ("max_dd", "Max drawdown"), ("pf", "Profit factor"), ("years", "Years"), ("breach", "Rule breach")],
                 fmt={"final": money, "ret_pct": lambda v: f"{v:+.1f}%", "cagr_pct": lambda v: f"{v:+.1f}%",
                      "max_dd": lambda v: f"{v:.1f}%", "pf": lambda v: f"{v:.2f}"})

by_sym = pd.DataFrame(S["by_symbol"])
by_sym["engine"] = by_sym.engine.map({"weekly": "Weekly entry", "weekly_add": "Turtle add", "micro": "4H micro"})
sym_tbl = table(by_sym, [("symbol", "Market"), ("engine", "Engine"), ("count", "Trades"), ("mean", "Avg net R"), ("sum", "Total net R")],
                fmt={"mean": lambda v: f'<span class="{"g" if v > 0 else "r"}">{v:+.3f}</span>',
                     "sum": lambda v: f'<span class="{"g" if v > 0 else "r"}">{v:+.1f}</span>'})

sw = pd.DataFrame(S["sweep"])
sw50 = sw[sw.capital == 50000].copy()
piv = sw50.pivot(index="weekly_unit_risk", columns="micro_risk", values="cagr_pct")
pdd = sw50.pivot(index="weekly_unit_risk", columns="micro_risk", values="max_dd")
hm = '<div class="tw"><table class="hm"><thead><tr><th>Weekly risk / unit ↓ · Micro risk →</th>' + "".join(
    f"<th>{c * 100:.2g}%</th>" for c in piv.columns) + "</tr></thead><tbody>"
for wr in piv.index:
    hm += f"<tr><th>{wr * 100:.2g}%</th>"
    for mr in piv.columns:
        c, d = piv.loc[wr, mr], pdd.loc[wr, mr]
        tone = "ok" if d <= 20 else ("warn" if d <= 35 else "bad")
        star = " ★" if (wr, mr) in [(0.005, 0.0025), (0.0075, 0.0025)] else ""
        hm += f'<td class="{tone}"><b>{c:+.1f}%/yr</b><br><span>DD {d:.0f}%{star}</span></td>'
    hm += "</tr>"
hm += "</tbody></table></div>"

mc = pd.DataFrame(S["montecarlo"]).T.reset_index().rename(columns={"index": "plan"})
mc_tbl = table(mc, [("plan", "Risk plan"), ("median_multiple", "Median ×"), ("p5_multiple", "Bad case (5%) ×"),
                    ("median_maxdd", "Median max DD"), ("p95_maxdd", "Bad-case max DD"), ("p_dd_over_50", "P(DD > 50%)"),
                    ("p_loss_after_1000", "P(losing after 1,000 trades)")],
               fmt={"median_multiple": lambda v: f"{v:,.1f}×", "p5_multiple": lambda v: f"{v:,.1f}×",
                    "median_maxdd": lambda v: f"{v * 100:.0f}%", "p95_maxdd": lambda v: f"{v * 100:.0f}%",
                    "p_dd_over_50": lambda v: f"{v * 100:.1f}%", "p_loss_after_1000": lambda v: f"{v * 100:.1f}%"})
prop = {k: v for k, v in S["montecarlo"].items() if k.startswith("prop")}
eng = {r["engine"]: r for r in S["by_engine"]}
tpy_all, tpy_recent = S["trades_per_year_all_history"], S["trades_per_year_recent_with_micro"]
yrs_for_10k = 10000 / tpy_recent
p50k = tiers[tiers.capital_s == "$50,000 · prop guard"].iloc[0]
noguard = tiers[tiers.capital_s == "$50,000 · no guard"].iloc[0]

page = f"""<title>Fib-FVG Dual Engine</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Archivo:wght@600;800&display=swap">
<style>
/* Layout: single reading column like a trading-desk research note; tables scroll in place. */
:root {{ --bg:#f6f7f5; --panel:#ffffff; --fg:#17201c; --muted:#5d6b64; --line:#dfe4e0; --accent:#0f7b5f; --gold:#b07d12;
  --pos:#1f8a5b; --neg:#c2463a; --ok:#e3f3ea; --warn:#fbf0d6; --bad:#f8e0dc;
  --display:"Archivo",system-ui,sans-serif; --body:"IBM Plex Sans",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,monospace; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#0f1412; --panel:#161d1a; --fg:#e6ece9; --muted:#9aaba3; --line:#26302c;
  --accent:#3cc497; --gold:#e0b24a; --pos:#45c08a; --neg:#ef7b6f; --ok:#16352a; --warn:#3a3018; --bad:#3d1f1b; color-scheme:dark; }} }}
:root[data-theme="dark"] {{ --bg:#0f1412; --panel:#161d1a; --fg:#e6ece9; --muted:#9aaba3; --line:#26302c;
  --accent:#3cc497; --gold:#e0b24a; --pos:#45c08a; --neg:#ef7b6f; --ok:#16352a; --warn:#3a3018; --bad:#3d1f1b; color-scheme:dark; }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.6 var(--body); }}
main {{ max-width:880px; margin:0 auto; padding-block:40px 80px; padding-left:max(16px,env(safe-area-inset-left,0px)); padding-right:max(16px,env(safe-area-inset-right,0px)); display:grid; grid-template-columns:minmax(0,1fr); gap:40px; }}
h1,h2 {{ font-family:var(--display); text-wrap:balance; margin:0; letter-spacing:-0.01em; }}
h1 {{ font-size:clamp(28px,5vw,44px); font-weight:800; line-height:1.1; }}
h2 {{ font-size:22px; font-weight:600; }}
p {{ margin:0; max-width:68ch; }}
section {{ display:grid; grid-template-columns:minmax(0,1fr); gap:14px; min-width:0; }} p,li {{ overflow-wrap:anywhere; }}
.eyebrow {{ font:500 12px/1 var(--mono); letter-spacing:.08em; text-transform:uppercase; color:var(--accent); }}
.lede {{ color:var(--muted); font-size:17px; }}
.verdict {{ background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--gold); padding:18px 20px; display:grid; gap:10px; border-radius:4px; }}
.verdict ul {{ margin:0; padding-left:20px; display:grid; gap:6px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }}
.kpi {{ background:var(--panel); border:1px solid var(--line); padding:14px 16px; border-radius:4px; display:grid; gap:2px; }}
.kpi b {{ font:600 24px/1.2 var(--mono); font-variant-numeric:tabular-nums; }}
.kpi span {{ color:var(--muted); font-size:13px; }}
.tw {{ overflow-x:auto; border:1px solid var(--line); border-radius:4px; background:var(--panel); }}
table {{ border-collapse:collapse; width:100%; font-size:13.5px; font-variant-numeric:tabular-nums; }}
th,td {{ padding:8px 12px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; }}
th:first-child,td:first-child {{ text-align:left; }}
thead th {{ font:500 11.5px/1.3 var(--mono); text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }}
td {{ font-family:var(--mono); }}
.hm td {{ text-align:center; line-height:1.3; }} .hm td span {{ font-size:12px; color:var(--muted); }}
.hm .ok {{ background:var(--ok); }} .hm .warn {{ background:var(--warn); }} .hm .bad {{ background:var(--bad); }}
.g {{ color:var(--pos); }} .r {{ color:var(--neg); }}
figure {{ margin:0; background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:12px; }}
figure svg {{ width:100%; height:auto; display:block; }}
figcaption {{ color:var(--muted); font-size:13px; padding:6px 4px 0; }}
.grid {{ stroke:var(--line); stroke-width:1; }} .base {{ stroke:var(--muted); stroke-dasharray:3 3; stroke-width:1; }}
.ax {{ fill:var(--muted); font:11px var(--mono); }}
.line {{ fill:none; stroke:var(--accent); stroke-width:1.6; }} .area {{ fill:var(--accent); opacity:.12; }} .dot {{ fill:var(--accent); }}
.pos {{ fill:var(--pos); }} .neg {{ fill:var(--neg); }}
code {{ font-family:var(--mono); font-size:13px; background:var(--panel); border:1px solid var(--line); padding:1px 5px; border-radius:3px; }}
.math {{ font-family:var(--mono); background:var(--panel); border:1px solid var(--line); padding:14px 16px; border-radius:4px; overflow-x:auto; font-size:13.5px; white-space:pre; }}
ol,ul {{ max-width:68ch; }}
</style>
<main>
<header style="display:grid;gap:12px">
  <div class="eyebrow">Backtest report · XAUUSD · XAGUSD · BTCUSD · US500 · NAS100</div>
  <h1>Fib-FVG Dual Engine</h1>
  <p class="lede">A weekly swing engine (Monthly/Weekly bias, Daily Turtle breakout, entry in the 0.618–0.786 Fibonacci OTE zone, targets at the −0.272 and −0.618 extensions) plus a 4H FVG micro engine. Tested on real price history with broker lot rules and costs.</p>
</header>

<div class="verdict">
  <b>The short version</b>
  <ul>
    <li>The edge is real but thin: <b>+{eng['weekly']['mean']:.2f}R</b> per weekly entry, <b>+{eng['weekly_add']['mean']:.2f}R</b> per Turtle add, <b>+{eng['micro']['mean']:.2f}R</b> per 4H micro trade, after spread.</li>
    <li>Over 2005–2026 at $50k with 0.5% per unit, it made <b>{noguard.ret_pct:+.0f}% in total ({noguard.cagr_pct:.1f}%/yr)</b> with a <b>{noguard.max_dd:.0f}% max drawdown</b>. Profits came in bursts: 2008–09, 2013, 2017 and 2025.</li>
    <li>US500, NAS100 and XAGUSD made the money. <b>XAUUSD and BTCUSD lost money net</b> on these rules.</li>
    <li>Accounts under $1,000 cannot size most signals. Even 0.01 lot would risk too much, so the bot skips them instead of over-leveraging.</li>
    <li>At 0.25% risk, a 6% trailing-loss prop rule is breached in every 10,000-trade simulation (median after ~{prop['prop $50k (0.25% / 0.25%)']['median_trades_to_breach']:.0f} trades). At 0.10% risk, the chance within 500 trades is {prop['prop $50k (0.10% / 0.10%)']['p_breach_within_500'] * 100:.1f}%.</li>
  </ul>
</div>

<section>
  <div class="eyebrow">Real history · $50,000 · no prop guard</div>
  <h2>Equity curve, 2005–2026</h2>
  <div class="kpis">
    <div class="kpi"><b>{int(noguard.trades):,}</b><span>trades taken</span></div>
    <div class="kpi"><b>{money(noguard.final)}</b><span>end balance</span></div>
    <div class="kpi"><b>{noguard.win_rate:.0f}%</b><span>win rate (trend system)</span></div>
    <div class="kpi"><b>{noguard.pf:.2f}</b><span>profit factor</span></div>
  </div>
  <figure>{svg_line(CURVE)}<figcaption>Closed-trade balance, 0.5% risk per Turtle unit and 1% per micro trade. Dashed line = starting $50,000.</figcaption></figure>
  <figure>{svg_bars(S['by_year'])}<figcaption>Net R by year, all engines. The 4H micro engine only has data from mid-2024, which is why trade counts jump in 2024–2026.</figcaption></figure>
</section>

<section>
  <div class="eyebrow">Your capital tiers</div>
  <h2>Every starting balance, same rules</h2>
  <p>Each tier replays the same signals. Smaller accounts take fewer trades because a position smaller than the broker's 0.01-lot minimum is skipped rather than oversized. The $50k funded row uses 0.25% risk, a 3% daily and 6% trailing loss guard, and runs from July 2024, when the 4H data starts.</p>
  {tier_tbl}
  <p style="color:var(--muted);font-size:13px">$50k with prop guard: {p50k.ret_pct:+.1f}% over {p50k.years} years ({p50k.cagr_pct:+.1f}%/yr), max drawdown {p50k.max_dd:.1f}%, then the trailing limit was hit ({p50k.breach}).</p>
</section>

<section>
  <div class="eyebrow">Where the edge comes from</div>
  <h2>Results by market and engine</h2>
  <p>Avg net R is profit per trade divided by the amount risked, after spread. Turtle pyramid adds carry the system. On gold the weekly entries are flat and the adds lose.</p>
  {sym_tbl}
</section>

<section>
  <div class="eyebrow">Money management</div>
  <h2>Finding the sweet spot</h2>
  <p>Return per year and max drawdown at $50k, 2005–2026, for each pair of risk settings. Green: drawdown up to 20%. Amber: up to 35%. Red: deeper. Doubling the risk roughly doubles the drawdown but does not double the return, because losing streaks compound. ★ marks the recommended settings for a personal account.</p>
  {hm}
  <p>Recommended: <b>0.5% per Turtle unit, 0.25% per micro trade</b> for a personal account. For a funded account, use <b>0.10–0.25% per unit</b> and set the EA's guard to your account's real limits. The Kelly fraction from the trade data is {S['kelly_fraction_per_R'] * 100:.1f}% per trade. The recommended settings are a sixth to a third of full Kelly, which is the usual safe range when the edge is uncertain.</p>
</section>

<section>
  <div class="eyebrow">10,000 trades</div>
  <h2>Monte Carlo from the real trades</h2>
  <p>Each row resamples the {int(noguard.trades):,} real net R-multiples into 2,000 sequences of 10,000 trades. At the recent pace of about {tpy_recent:.0f} trades a year across five markets, 10,000 trades is roughly <b>{yrs_for_10k:.0f} years</b> of trading. The full sample path is in <code>results/montecarlo_10000_trades_sample_path.csv</code>.</p>
  {mc_tbl}
</section>

<section>
  <div class="eyebrow">The billions question</div>
  <h2>What compounding can and cannot do</h2>
  <p>The math from your video is the engine here. The ratio of consecutive Fibonacci numbers (5/8, 8/13, 13/21…) converges to 0.618, which is the OTE entry and the extension targets. Fibonacci gives the levels. It does not create edge by itself. Edge is measured, and here it is about 0.1–0.2R per trade.</p>
  <div class="math">Growth per trade  ≈ risk × avg R           = 0.005 × {S['net_r_mean']:.3f} ≈ {0.005 * S['net_r_mean'] * 100:.3f}%
$1,000 → $1,000,000,000 needs ln(1e6) = 13.8 log-units of growth
Trades needed      ≈ 13.8 / {0.005 * S['net_r_mean']:.5f}  ≈ {13.8 / (0.005 * S['net_r_mean']):,.0f} trades  ≈ {13.8 / (0.005 * S['net_r_mean']) / tpy_recent:,.0f} years at {tpy_recent:.0f}/yr</div>
  <p>Raising risk to get there faster runs into drawdown first: at 3% per unit the median 10,000-trade path falls {S['montecarlo']['reckless (3% / 5%)']['median_maxdd'] * 100:.0f}% at some point. Liquidity also caps size. Past a few million dollars, orders move the price, and the per-order lot limits in the backtest start to bind. A realistic goal for this system is steady growth at 0.5% risk, with the funded account as the main lever for scale.</p>
</section>

<section>
  <div class="eyebrow">Scope</div>
  <h2>What was and was not tested</h2>
  <ul>
    <li><b>Data:</b> Yahoo Finance daily bars (gold and silver futures and S&amp;P from 2000, BTC from 2014, Nasdaq-100 from 1985; trading from 2005) and hourly bars for the last ~2 years, built into 4H. Index hourly bars cover cash hours only. Futures stand in for spot XAU/XAG.</li>
    <li><b>Not tested:</b> the S&amp;P 15s/30s/45s FVG idea. No second-level history was reachable from here. The EA has it as an experimental module, off by default, for demo forward testing only.</li>
    <li><b>Fills:</b> limit orders fill at the level or a better open. If a bar touches both stop and target, the stop counts first. Spread is charged on every trade. Swap and commission are not modelled.</li>
    <li><b>Tuning:</b> weekly rules were fixed before testing and stayed positive in both 2005–15 and 2016–26. The micro engine variant was picked from a 108-combination grid on data before June 2025. It held up afterwards, but only just (+0.03R before costs), so treat it as unproven.</li>
    <li><b>Contract specs</b> (contract size, 0.01 min lot, spread) are typical MT5 CFD values. Check them against FundedNext's symbol specifications before trusting the small-account rows.</li>
  </ul>
</section>
</main>"""
open("results/report.html", "w").write(page)
print("ok", len(page))

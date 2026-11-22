"""Build results/playbook.html from results/edge_book.json and results/roadmap.json.
    python -m fibfvg.playbook
"""
import html
import json

import pandas as pd

E = json.load(open("results/edge_book.json"))
RM = json.load(open("results/roadmap.json"))


def money(v):
    v = float(v)
    return ("−$" if v < 0 else "$") + f"{abs(v):,.0f}"


def sg(v, d=2):
    v = float(v)
    return f'<span class="{"g" if v > 0 else "r"}">{"+" if v > 0 else ""}{v:.{d}f}</span>'


def table(head, rows, cls="", wrap=None):
    th = "".join(f"<th>{h}</th>" for h in head)
    tb = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'


plans = E["plans"]
plan_rows = [[n.replace("Plan 3B Levels 2R bank", "Plan 3B Levels · 2R bank <span class='chip ok'>new</span>"), p["trades"], sg(p["net_r"], 3),
              sg(p["first_half"], 3), sg(p["second_half"], 3), f'{p["win_rate"]}%', f'{p["avg_win_r"]:.2f}R', f'{p["avg_loss_r"]:.2f}R',
              f'<b>{p["realized_rr"]:.2f}</b>', p["r10"], f'{p["best_r"]}R'] for n, p in plans.items()]
pip_rows = [[s, p["pip"], f'{p["median_day"]:,}', f'{p["p25"]:,} – {p["p75"]:,}', f'{p["atr14_now"]:,}'] for s, p in E["pips"].items()]
prop_rows = []
for r in E["prop"]:
    fr = r["first_reward"]
    prop_rows.append([html.escape(r["portfolio"]), r["mode"], r["trades"], r["rewards"], money(r["paid"]), f'{r["worst_dd"]}%',
                      '<span class="chip ok">none</span>' if not r["breach"] else r["breach"], fr[0] if fr else "none"])
rm_rows = []
for r in E["roadmap"]:
    rm_rows.append([html.escape(r["portfolio"]), r["mode"], f'{r["month1_reward_pct"]:.0f}%', f'{r["first_reward_within_90d_pct"]:.0f}%',
                    money(r["month3_major_median"]), f'{r["accounts_end_median"]:g} (max {r["accounts_end_max"]})',
                    f'<b>{money(r["net_12m_median"])}</b>', f'{money(r["net_12m_min"])} to {money(r["net_12m_max"])}', r["breaches"]])
lots = {r["portfolio"] + "|" + r["mode"]: r["lots"] for r in E["prop"]}
lot_rows = []
for k, v in lots.items():
    p, m = k.split("|")
    d = {x["symbol"]: f'{x["median"]:.2f} / {x["max"]:.2f}' for x in v}
    lot_rows.append([html.escape(p), m] + [d.get(s, "–") for s in ("XAUUSD", "XAGUSD", "BTCUSD", "US500", "NAS100")])
news = {(x["news"], x["half"]): x for x in E["weak_spots"]["by_news"]}
news_rows = [[n, f'{news[(n,"first")]["count"]} / {news[(n,"second")]["count"]}', sg(news[(n, "first")]["mean"], 2), sg(news[(n, "second")]["mean"], 2)]
             for n in ("CPI", "NFP", "FOMC", "none") if (n, "first") in news and (n, "second") in news]

rm_json = json.dumps([dict(p=r["portfolio"], m=r["mode"], s=r["start"], f=r["first_reward"], m1=r["month1_paid"], m3=r["month3_major"],
                           b3=r["accounts_bought_m3"], m9=r["month9_major"], b9=r["accounts_bought_m9"], n=r["net_to_you"], bm=r["by_month"]) for r in RM])

page = f"""<title>FibFVG Pro Playbook</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Archivo:wght@600;800&display=swap">
<style>
/* Layout: one reading column, a trading desk's playbook: verdict first, then plans, then the 12-month roadmap. */
:root{{--bg:#f4f6f4;--panel:#fff;--sunk:#eef1ee;--fg:#16201b;--muted:#5b6a63;--line:#dce2de;--accent:#0f7b5f;--gold:#a8740b;--up:#1f8a5b;--down:#c2463a;--ok:#e2f3e9;--warn:#fbefd4;--bad:#f8dfdb;
--display:"Archivo",system-ui,sans-serif;--body:"IBM Plex Sans",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0e1311;--panel:#151c19;--sunk:#111815;--fg:#e5ebe8;--muted:#98a9a1;--line:#25302b;--accent:#3cc497;--gold:#e1b34c;--up:#45c08a;--down:#ef7b6f;--ok:#15342a;--warn:#3a3018;--bad:#3d1f1b;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#0e1311;--panel:#151c19;--sunk:#111815;--fg:#e5ebe8;--muted:#98a9a1;--line:#25302b;--accent:#3cc497;--gold:#e1b34c;--up:#45c08a;--down:#ef7b6f;--ok:#15342a;--warn:#3a3018;--bad:#3d1f1b;color-scheme:dark}}
body{{background:var(--bg);color:var(--fg);font:14.5px/1.6 var(--body)}}
main{{max-width:1000px;margin:0 auto;padding-block:32px 72px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;grid-template-columns:minmax(0,1fr);gap:30px}}
section{{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}}
h1,h2,h3{{font-family:var(--display);margin:0;text-wrap:balance}} h1{{font-size:clamp(28px,4.5vw,42px);font-weight:800}} h2{{font-size:21px;font-weight:600}} h3{{font-size:15px;font-weight:600}}
p{{margin:0;max-width:72ch}} p,li{{overflow-wrap:anywhere}}
.eyebrow{{font:500 11.5px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}}
.lede{{color:var(--muted);font-size:16px}}
.verdict{{background:var(--sunk);border:1px solid var(--line);border-radius:5px;padding:16px 18px;display:grid;gap:8px}}
.verdict ul,.steps{{margin:0;padding-left:20px;display:grid;gap:6px}}
.tw{{overflow-x:auto;border:1px solid var(--line);border-radius:5px;background:var(--panel)}}
table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}}
th,td{{padding:7px 11px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}} th:first-child,td:first-child{{text-align:left}}
thead th{{font:500 11px var(--mono);text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}} td{{font-family:var(--mono)}}
.g{{color:var(--up)}} .r{{color:var(--down)}}
.chip{{font:500 11px var(--mono);padding:4px 8px;border-radius:3px;white-space:nowrap;display:inline-block}} .chip.ok{{background:var(--ok)}} .chip.warn{{background:var(--warn)}} .chip.bad{{background:var(--bad)}}
.bar{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
select{{font:500 13px var(--body);color:var(--fg);background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:6px 10px}}
select:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.note{{color:var(--muted);font-size:12.5px}}
.month{{display:grid;grid-template-columns:96px minmax(0,1fr);gap:10px;padding:10px 0;border-bottom:1px solid var(--line)}}
.month b{{font:600 13px var(--mono);color:var(--accent)}}
svg text{{fill:var(--muted);font:11px var(--mono)}}
</style>
<main>
<header style="display:grid;gap:10px">
  <div class="eyebrow">Playbook · data {E["period"][0]} → {E["period"][1]} · XAUUSD XAGUSD BTCUSD US500 NAS100</div>
  <h1>FibFVG Pro Playbook</h1>
  <p class="lede">Only the plans that made money on 2024+ data. The plan for instant accounts (no profit target, no consistency rule, 6% max loss), Normal vs Aggressive, and the 12-month payout roadmap tested from 16 different start months.</p>
</header>

<div class="verdict"><b>The short version</b><ul>
  <li><b>No fixed-2R intraday plan has an edge.</b> Asia-range and previous-day sweeps with a 2R target lost money in both halves of the data, and so did a 2R target on the current entries. All the losing plans were removed from the code.</li>
  <li><b>The plans that make money already pay more than 2 to 1:</b> the average win is 2.2–2.5R against an average loss of 0.7R. That edge comes from letting winners run.</li>
  <li><b>New plan, Core + 2R bank:</b> takes half off at +2R and lets the rest run. The edge per trade is a little lower, but profit is closed sooner. The first reward came within 90 days in 69% of start months (44% without banking), and the worst 12-month result was +$3,827 instead of breakeven.</li>
  <li><b>A first reward in month 1 happened in only about 1 start month in 5.</b> Plan on months 2–3 for the first reward.</li>
  <li><b>No breach</b> in any plan, mode or start month. The guard keeps drawdown plus open stop-risk under 5% (the firm line is 6%).</li></ul></div>

<section>
  <div class="eyebrow">Plans kept</div><h2>What makes money</h2>
  {table(["Plan","Trades","Net R per trade","First half","Second half","Win rate","Avg win","Avg loss","Realized R:R","≥10R","Best"], plan_rows)}
  <p class="note">Net R is after spread. Plan 1 holds weeks to months, Plan 3 holds days. First half = before 19 Aug 2025, second half = after.</p>
</section>

<section>
  <div class="eyebrow">Price range</div><h2>Pips per day (2024 → now)</h2>
  {table(["Market","1 pip","Median day","Middle half of days","Average day now (ATR 14)"], pip_rows)}
  <p>Gold moves about 530 pips on a typical day, so 100–500 pip targets fit inside one day. The bot sizes from the daily range: the levels plan's stop is one day's average range, and its 2R bank sits at two days' range.</p>
</section>

<section>
  <div class="eyebrow">Weak spots</div><h2>What the trade logs say</h2>
  <div class="verdict"><ul>
    <li><b>Fixed 2R targets:</b> on the levels entries +2R is hit before the stop only ~35% of the time, about breakeven after costs.</li>
    <li><b>Hours:</b> the result for each New York hour flips between the two halves of the data, so no hour is a reliable weak spot. Kill-zone-only entries were not better than all hours.</li>
    <li><b>Weekdays:</b> Thursday was slightly negative in both halves (−0.03R and −0.16R). It's too small to act on.</li>
    <li><b>News:</b> CPI days lost in both halves but only 14 trades fell on them, so skipping CPI made no measurable difference. FOMC and NFP days did well.</li>
    <li><b>Markets:</b> gold and silver carry the plans. BTC is roughly flat.</li></ul></div>
  {table(["News day","Trades (1st / 2nd half)","Net R first half","Net R second half"], news_rows)}
  <p class="note">News dates come from the published FOMC, BLS CPI and NFP schedules. Verify them against an economic calendar.</p>
</section>

<section>
  <div class="eyebrow">Normal vs Aggressive</div><h2>Instant Premium $100K, July 2024 → now</h2>
  {table(["Portfolio","Mode","Trades","Rewards","Paid to you","Worst drawdown","Breach","First reward"], prop_rows)}
  <p>Aggressive pays less over the full period. Near the 5% guard line its trades get shrunk, and recovering takes longer. Normal is the default.</p>
  <h3>Lots used (median / max)</h3>
  {table(["Portfolio","Mode","XAUUSD","XAGUSD","BTCUSD","US500","NAS100"], lot_rows)}
</section>

<section>
  <div class="eyebrow">Roadmap</div><h2>Your 12-month plan, tested</h2>
  <div class="verdict"><b>The schedule</b>
    <div class="month"><b>Month 0</b><span>Buy 1 × Instant Premium $100K (instant, no profit target, no consistency rule, 6% max loss). Run the new plan in Normal mode.</span></div>
    <div class="month"><b>Month 1</b><span>Request a small first reward (up to $1,000 of closed profit) if there is any. This proves the firm pays and returns the fee. It happened in about 1 start month in 5.</span></div>
    <div class="month"><b>Month 3</b><span>Withdraw all closed profit. Spend all of it on more $100K accounts. Account 1 restarts from its base.</span></div>
    <div class="month"><b>Months 4–8</b><span>Monthly rewards: closed profit above the firm's minimum, up to the firm's per-reward maximum. Set both to your firm's real values in the bot docs.</span></div>
    <div class="month"><b>Month 9</b><span>Withdraw everything from every account and buy as many accounts as it covers (same firm or a second firm).</span></div>
    <div class="month"><b>Months 10–12</b><span>Monthly rewards again. Repeat the cycle through 2027.</span></div></div>
  {table(["Portfolio","Mode","Reward in month 1","First reward by day 90","Month-3 withdrawal (median)","Accounts at month 12","Net to you, 12 months (median)","Range","Breaches"], rm_rows)}
  <p class="note">Net to you = all rewards minus every account fee, with month-3 and month-9 withdrawals spent on new accounts (capped at 6 accounts). 16 start months, Aug 2024 → Nov 2025. Fee $740 per $100K (the promo price in your screenshot).</p>
  <div class="bar"><label for="sc" class="note">Scenario</label><select id="sc"></select></div>
  <svg id="ch" viewBox="0 0 760 230" role="img" aria-label="Money to you by month"></svg>
  <div class="tw"><table id="st"><thead><tr><th>Start</th><th>First reward</th><th>Month 1</th><th>Month 3 withdrawal</th><th>Bought month 3</th><th>Month 9 withdrawal</th><th>Bought month 9</th><th>Net to you, 12 months</th></tr></thead><tbody></tbody></table></div>
</section>

<section>
  <div class="eyebrow">Before you buy</div><h2>Check these with each firm</h2>
  <ul class="steps">
    <li>Minimum and maximum amount per reward, and how soon the first reward can be requested.</li>
    <li>Maximum funded capital per trader, and whether the same bot may run on several accounts. Six $100K accounts at one firm may exceed its limit.</li>
    <li>Whether a reward can be requested with trades open. The bot shows "withdrawable now" and adjusts its guard after each reward.</li>
    <li>Profit split (80% assumed) and when the refundable fee is returned (assumed with the first reward).</li>
    <li><b>Lucid Trading is a futures prop firm.</b> Its accounts trade CME futures on NinjaTrader, Tradovate or Rithmic, not MT4/MT5/cTrader CFDs, and its drawdown is measured in dollars. This bot needs a futures version first. I don't have Lucid's current prices and rules, so its row here is a placeholder priced like Instant Premium.</li>
    <li>All accounts take the same trades, so drawdowns arrive on every account at once. More accounts scale income and risk together.</li></ul>
</section>
</main>
<script>
(function(){{
const RM={rm_json};
const $=s=>document.querySelector(s);
const money=v=>(v<0?"−$":"$")+Math.abs(v).toLocaleString("en-US",{{maximumFractionDigits:0}});
const keys=[...new Set(RM.map(r=>r.p+" · "+r.m))];
$("#sc").innerHTML=keys.map(k=>`<option>${{k}}</option>`).join("");
$("#sc").value=keys.find(k=>k.includes("2R")&&k.endsWith("Normal"))||keys[0];
function draw(){{const k=$("#sc").value;const rows=RM.filter(r=>r.p+" · "+r.m===k);
  $("#st tbody").innerHTML=rows.map(r=>`<tr><td>${{r.s}}</td><td>${{r.f?r.f[0]+" · "+money(r.f[1]):"none"}}</td><td>${{money(r.m1)}}</td><td>${{money(r.m3)}}</td><td>${{r.b3}}</td><td>${{money(r.m9)}}</td><td>${{r.b9}}</td><td class="${{r.n>0?"g":"r"}}">${{money(r.n)}}</td></tr>`).join("");
  const W=760,H=230,l=60,rp=10,t=12,b=30;const months=[...Array(13).keys()].slice(1);
  const med=months.map(m=>{{const v=rows.map(r=>+(r.bm[m]||0)).sort((a,b)=>a-b);return v[Math.floor(v.length/2)];}});
  const avg=months.map(m=>rows.reduce((a,r)=>a+(+(r.bm[m]||0)),0)/rows.length);
  const mx=Math.max(1000,...avg)*1.15;const bw=(W-l-rp)/12;const Y=v=>t+(1-v/mx)*(H-t-b);
  let o="";[0,mx/2,mx].forEach(v=>o+=`<line x1="${{l}}" x2="${{W-rp}}" y1="${{Y(v)}}" y2="${{Y(v)}}" stroke="var(--line)"/><text x="${{l-6}}" y="${{Y(v)+4}}" text-anchor="end">${{money(v)}}</text>`);
  months.forEach((m,i)=>{{o+=`<rect x="${{l+i*bw+5}}" y="${{Y(avg[i])}}" width="${{bw-10}}" height="${{Math.max(1,Y(0)-Y(avg[i]))}}" fill="var(--accent)" opacity=".85"><title>Month ${{m}}: average ${{money(avg[i])}}, median ${{money(med[i])}}</title></rect><text x="${{l+i*bw+bw/2}}" y="${{H-12}}" text-anchor="middle">M${{m}}</text>`;}});
  o+=`<text x="${{W-rp}}" y="${{t+8}}" text-anchor="end">average rewards to you per month, all accounts</text>`;
  $("#ch").innerHTML=o;}}
$("#sc").onchange=draw;draw();
}})();
</script>"""
open("results/playbook.html", "w").write(page)
print("ok", len(page))

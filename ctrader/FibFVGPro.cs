// FibFVG Pro - cTrader cBot port of FibFVG_Pro.mq5 (same rules and presets).
// Add as a new cBot in cTrader Automate, build, attach to ANY chart. It trades the
// markets it can find among XAUUSD, XAGUSD, BTCUSD, US500, NAS100 (broker names resolved).
using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    public enum Preset { FundedNextStellarInstant, InstantPremium, Personal, Custom }
    public enum RiskModeE { Conservative, Normal, Aggressive, EdgeGate }
    public enum P1Exit { Chandelier, Monthly }

    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class FibFVGPro : Robot
    {
        [Parameter("Preset", DefaultValue = Preset.FundedNextStellarInstant)] public Preset PresetSel { get; set; }
        [Parameter("Risk mode", DefaultValue = RiskModeE.Normal)] public RiskModeE Mode { get; set; }
        [Parameter("Symbols (AUTO or list)", DefaultValue = "AUTO")] public string SymbolsToTrade { get; set; }
        [Parameter("Use Plan 1", DefaultValue = true)] public bool UsePlan1 { get; set; }
        [Parameter("Use Plan 3", DefaultValue = true)] public bool UsePlan3 { get; set; }
        [Parameter("Plan 1 exit", DefaultValue = P1Exit.Chandelier)] public P1Exit Plan1Exit { get; set; }
        [Parameter("Kill zones only", DefaultValue = false)] public bool KillZonesOnly { get; set; }
        [Parameter("Start balance (0 = auto)", DefaultValue = 0)] public double StartBalance { get; set; }
        [Parameter("Custom daily loss %", DefaultValue = 0)] public double CustomDaily { get; set; }
        [Parameter("Custom max loss %", DefaultValue = 6)] public double CustomMax { get; set; }
        [Parameter("Custom trailing", DefaultValue = true)] public bool CustomTrailing { get; set; }
        [Parameter("Label", DefaultValue = "FibPro")] public string Tag { get; set; }

        const double OTE = 0.705, EXT1 = 0.272; const int BRK = 20;
        static readonly int[] KZ = { 20, 0, 2, 6, 7, 9, 10, 15 };
        static readonly double[] FR = { 0, 0.2, 0.5, 0.6, 0.8 };
        readonly List<(Symbol sym, int fam)> markets = new List<(Symbol, int)>();
        readonly Dictionary<string, DateTime> lastD1 = new Dictionary<string, DateTime>(), lastH1 = new Dictionary<string, DateTime>();
        double dailyLim, maxLim, startBal; bool trailing, halted;

        string K(string k) => Tag + "_" + k;
        double Get(string k, double def = 0) { var v = LocalStorage.GetString(K(k)); return v == null ? def : double.Parse(v, System.Globalization.CultureInfo.InvariantCulture); }
        void Set(string k, double v) => LocalStorage.SetString(K(k), v.ToString(System.Globalization.CultureInfo.InvariantCulture));
        static double P1Risk(RiskModeE m) => m == RiskModeE.Conservative ? 0.0015 : m == RiskModeE.Normal ? 0.0025 : 0.0050;
        static double P3Risk(RiskModeE m) => m == RiskModeE.Conservative ? 0.0005 : m == RiskModeE.Normal ? 0.0010 : 0.0025;
        static double Unit(int f) => f == 0 ? 100 : f == 1 ? 1 : f == 2 ? 10000 : f == 3 ? 100 : 1000;
        string L1 => Tag + "P1"; string L1A => Tag + "P1+"; string L3 => Tag + "P3"; string L3A => Tag + "P3+";

        protected override void OnStart()
        {
            switch (PresetSel)
            {
                case Preset.FundedNextStellarInstant: dailyLim = 0; maxLim = 0.06; trailing = true; break;
                case Preset.InstantPremium: dailyLim = 0.03; maxLim = 0.06; trailing = true; break;
                case Preset.Personal: dailyLim = 0; maxLim = 0; trailing = false; break;
                default: dailyLim = CustomDaily / 100; maxLim = CustomMax / 100; trailing = CustomTrailing; break;
            }
            startBal = StartBalance > 0 ? StartBalance : Get("start", Account.Balance);
            Set("start", startBal);
            if (Get("peak") <= 0) Set("peak", startBal);
            halted = Get("halt") > 0;
            Resolve();
            Timer.Start(TimeSpan.FromSeconds(5));
            Print($"FibFVG Pro: {markets.Count} markets, preset {PresetSel}, mode {Mode}, start {startBal}");
        }

        static int Family(string n)
        {
            n = n.ToUpperInvariant();
            if (n.StartsWith("XAUUSD") || n.StartsWith("GOLD")) return 0;
            if (n.StartsWith("XAGUSD") || n.StartsWith("SILVER")) return 1;
            if (n.StartsWith("BTCUSD") || n.StartsWith("BITCOIN")) return 2;
            if (n.StartsWith("US500") || n.StartsWith("SPX500") || n.StartsWith("SP500") || n.StartsWith("USA500") || n.StartsWith("SPX")) return 3;
            if (n.StartsWith("NAS100") || n.StartsWith("USTEC") || n.StartsWith("US100") || n.StartsWith("NDX100") || n.StartsWith("NAS")) return 4;
            return -1;
        }
        void Add(string name)
        {
            int f = Family(name); if (f < 0 || markets.Any(m => m.fam == f)) return;
            var s = Symbols.GetSymbol(name); if (s == null) return;
            markets.Add((s, f));
        }
        void Resolve()
        {
            if (SymbolsToTrade != "AUTO") { foreach (var n in SymbolsToTrade.Split(',')) Add(n.Trim()); return; }
            Add(SymbolName);
            foreach (var n in Symbols) { if (markets.Count >= 5) break; Add(n); }
        }

        // ---------------------------------------------------------------- helpers
        static double ATRw(Bars b, int len, int shift)
        {
            int n = b.Count; double a = 0; bool init = false;
            for (int k = shift + len * 5; k >= shift; k--)
            {
                int i = n - 1 - k; if (i < 1) continue;
                double tr = Math.Max(b.HighPrices[i], b.ClosePrices[i - 1]) - Math.Min(b.LowPrices[i], b.ClosePrices[i - 1]);
                if (!init) { a = tr; init = true; } else a += (tr - a) / len;
            }
            return a;
        }
        // index helpers: shift 0 = forming bar, 1 = last closed (MT-style)
        static double Hs(Bars b, int sh) => b.HighPrices[b.Count - 1 - sh];
        static double Ls(Bars b, int sh) => b.LowPrices[b.Count - 1 - sh];
        static double Os(Bars b, int sh) => b.OpenPrices[b.Count - 1 - sh];
        static double Cs(Bars b, int sh) => b.ClosePrices[b.Count - 1 - sh];
        static double HH(Bars b, int from, int n) { double m = double.MinValue; for (int i = from; i < from + n; i++) m = Math.Max(m, Hs(b, i)); return m; }
        static double LL(Bars b, int from, int n) { double m = double.MaxValue; for (int i = from; i < from + n; i++) m = Math.Min(m, Ls(b, i)); return m; }
        static int Bias(Bars b, int look) { double mid = (HH(b, 1, look) + LL(b, 1, look)) / 2, c = Cs(b, 1); return c > mid ? 1 : c < mid ? -1 : 0; }
        static double MoneyPerPrice(Symbol s) => s.PipValue / s.PipSize;          // per 1 unit of volume
        double LotsFor(Symbol s, double riskMoney, double dist)
        {
            if (dist <= 0) return 0;
            double units = riskMoney / (dist * MoneyPerPrice(s));
            double vol = s.NormalizeVolumeInUnits(units, RoundingMode.Down);
            if (vol < s.VolumeInUnitsMin) return 0;                                // never oversize to reach the minimum
            return Math.Min(vol, s.VolumeInUnitsMax);
        }
        static int NYHour()
        {
            var ny = TimeZoneInfo.FindSystemTimeZoneById(Environment.OSVersion.Platform == PlatformID.Win32NT ? "Eastern Standard Time" : "America/New_York");
            return TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, ny).Hour;
        }
        IEnumerable<Position> Mine(Symbol s, string label) => Positions.Where(p => p.SymbolName == s.Name && p.Label == label);
        double OpenRisk() => Positions.Where(p => p.Label != null && p.Label.StartsWith(Tag) && p.StopLoss.HasValue)
            .Sum(p => { int d = p.TradeType == TradeType.Buy ? 1 : -1; double dist = (p.EntryPrice - p.StopLoss.Value) * d;
                        var s = Symbols.GetSymbol(p.SymbolName); return dist > 0 ? dist * MoneyPerPrice(s) * p.VolumeInUnits : 0; });
        double Peak => Get("peak", startBal);
        double DayStart => Get("day", Account.Balance);
        void UpdateDay()
        {
            double key = Server.Time.Year * 1000 + Server.Time.DayOfYear;
            if (Get("daykey") != key) { Set("daykey", key); Set("day", Math.Max(Account.Balance, Account.Equity)); }
        }
        double Room()
        {
            double eq = Account.Equity, room = double.MaxValue;
            if (maxLim > 0) room = Math.Min(room, (maxLim - 0.01) * startBal - ((trailing ? Peak : startBal) - eq) - OpenRisk());
            if (dailyLim > 0) room = Math.Min(room, (dailyLim - 0.005) * startBal - (DayStart - eq) - OpenRisk());
            return room;
        }
        void CloseAll(string why)
        {
            foreach (var p in Positions.Where(p => p.Label != null && p.Label.StartsWith(Tag)).ToList()) ClosePosition(p);
            foreach (var o in PendingOrders.Where(o => o.Label != null && o.Label.StartsWith(Tag)).ToList()) CancelPendingOrder(o);
            Print("FibFVG Pro guard: " + why);
        }
        // Withdrawals/deposits: balance moved while no trade closed -> shift peak and day start by the same amount.
        double lastBal = double.NaN; int lastHist = -1;
        void SyncBalanceOps()
        {
            int h = History.Count;
            if (!double.IsNaN(lastBal) && h == lastHist && Math.Abs(Account.Balance - lastBal) > 0.01)
            {
                double moved = Account.Balance - lastBal;
                Set("peak", Math.Max(startBal, Peak + moved)); Set("day", DayStart + moved);
                Print($"FibFVG Pro: balance operation {moved:F2} - peak and day start adjusted");
            }
            lastBal = Account.Balance; lastHist = h;
        }
        double Withdrawable() => Math.Max(0, Account.Balance - startBal - OpenRisk());
        bool Guard()
        {
            SyncBalanceOps();
            UpdateDay();
            if (Account.Balance > Peak) Set("peak", Account.Balance);
            if (halted) return false;
            double eq = Account.Equity;
            if (maxLim > 0 && (trailing ? Peak : startBal) - eq >= (maxLim - 0.005) * startBal) { CloseAll("max-loss emergency line"); halted = true; Set("halt", 1); return false; }
            if (dailyLim > 0 && DayStart - eq >= (dailyLim - 0.003) * startBal) { CloseAll("daily emergency line"); return false; }
            return true;
        }
        RiskModeE EdgeMode()
        {
            if (Mode != RiskModeE.EdgeGate) return Mode;
            double dd = ((trailing ? Peak : startBal) - Account.Equity) / startBal;
            if (dd >= 0.03) return RiskModeE.Conservative;
            var rs = History.Where(h => h.Label == L1 || h.Label == L3).OrderBy(h => h.ClosingTime)
                .Select(h => { var c = h.Comment ?? ""; int p = c.IndexOf("r="); double r = p >= 0 ? double.Parse(c.Substring(p + 2), System.Globalization.CultureInfo.InvariantCulture) : 0;
                               return r > 0 ? h.NetProfit / r : double.NaN; })
                .Where(x => !double.IsNaN(x)).ToList();
            int k = rs.Count; if (k < 20) return RiskModeE.Conservative;
            var r20 = rs.Skip(k - 20).ToList(); var r40 = rs.Skip(Math.Max(0, k - 40)).ToList();
            double pf(List<double> x) { double g = x.Where(v => v > 0).Sum(), l = -x.Where(v => v < 0).Sum(); return l > 0 ? g / l : 9.9; }
            if (k >= 40 && r40.Sum() >= 8 && pf(r40) >= 1.5 && dd <= 0.015) return RiskModeE.Aggressive;
            if (r20.Sum() >= 3 && pf(r20) >= 1.3 && dd <= 0.02) return RiskModeE.Normal;
            return RiskModeE.Conservative;
        }
        double SizeTrade(Symbol s, double pct, double dist)
        {
            double risk = startBal * pct, room = Room();
            if (room < double.MaxValue && risk > 0.5 * room) risk = Math.Max(0, 0.5 * room);
            return LotsFor(s, risk, dist);
        }
        void ModifySL(Symbol s, string label, double nsl, int d)
        {
            foreach (var p in Mine(s, label).ToList())
            {
                double sl = p.StopLoss ?? (d == 1 ? 0 : double.MaxValue);
                double want = d == 1 ? Math.Max(sl, nsl) : Math.Min(sl, nsl);
                double px = d == 1 ? s.Bid : s.Ask;
                if (Math.Abs(want - sl) > s.TickSize && (d == 1 ? want < px : want > px)) ModifyPosition(p, want, p.TakeProfit);
            }
        }
        void CloseLabel(Symbol s, string label) { foreach (var p in Mine(s, label).ToList()) ClosePosition(p); }

        // ---------------------------------------------------------------- PLAN 1
        void Plan1NewDay(Symbol s)
        {
            if (Mine(s, L1).Any() || Mine(s, L1A).Any()) return;
            var d1 = MarketData.GetBars(TimeFrame.Daily, s.Name); var w1 = MarketData.GetBars(TimeFrame.Weekly, s.Name); var mn = MarketData.GetBars(TimeFrame.Monthly, s.Name);
            int dir = Bias(w1, 4); if (dir == 0 || dir != Bias(mn, 6)) return;
            double N = ATRw(d1, 20, 1);
            bool brk = dir == 1 ? Hs(d1, 1) >= HH(d1, 2, BRK) : Ls(d1, 1) <= LL(d1, 2, BRK);
            if (!brk) return;
            int ext = 1; double best = dir == 1 ? double.MaxValue : double.MinValue;
            for (int i = 1; i <= BRK; i++) { double v = dir == 1 ? Ls(d1, i) : Hs(d1, i); if (dir == 1 ? v < best : v > best) { best = v; ext = i; } }
            double origin = best, extreme = dir == 1 ? Hs(d1, 1) : Ls(d1, 1), rng = Math.Abs(extreme - origin);
            bool fvg = false;
            for (int j = ext - 2; j >= 1 && !fvg; j--) fvg = dir == 1 ? Ls(d1, j) > Hs(d1, j + 2) : Hs(d1, j) < Ls(d1, j + 2);
            if (!fvg || rng < 1.5 * N) return;
            double entry = extreme - dir * OTE * rng, sl = origin - dir * 0.25 * N;
            double vol = SizeTrade(s, P1Risk(EdgeMode()), Math.Abs(entry - sl)); if (vol <= 0) return;
            foreach (var o in PendingOrders.Where(o => o.SymbolName == s.Name && o.Label == L1).ToList()) CancelPendingOrder(o);
            Set(s.Name + "_N", N); Set(s.Name + "_tp1", extreme + dir * EXT1 * rng); Set(s.Name + "_tp1done", 0);
            Set(s.Name + "_last", entry); Set(s.Name + "_risk", Math.Abs(entry - sl));
            string cm = "FP1 r=" + (vol * Math.Abs(entry - sl) * MoneyPerPrice(s)).ToString("F2", System.Globalization.CultureInfo.InvariantCulture);
            PlaceLimitOrder(dir == 1 ? TradeType.Buy : TradeType.Sell, s.Name, vol, entry, L1, Math.Abs(entry - sl) / s.PipSize, null, Server.Time.AddDays(15), cm);
        }
        void Plan1Manage(Symbol s)
        {
            var main = Mine(s, L1).FirstOrDefault();
            if (main == null) { CloseLabel(s, L1A); return; }
            int d = main.TradeType == TradeType.Buy ? 1 : -1;
            var d1 = MarketData.GetBars(TimeFrame.Daily, s.Name);
            double N = Get(s.Name + "_N"), r = Get(s.Name + "_risk"); if (r <= 0 && main.StopLoss.HasValue) r = Math.Abs(main.EntryPrice - main.StopLoss.Value);
            int sh = 0; for (int i = d1.Count - 1; i >= 0 && d1.OpenTimes[i] > main.EntryTime; i--) sh++;
            double best = d == 1 ? HH(d1, 0, sh + 1) : LL(d1, 0, sh + 1), mfe = r > 0 ? (best - main.EntryPrice) * d / r : 0;
            if (sh >= 10 && mfe < 0.5) { CloseLabel(s, L1); CloseLabel(s, L1A); return; }
            double trail = 0;
            if (Plan1Exit == P1Exit.Chandelier) { trail = (d == 1 ? HH(d1, 1, Math.Max(sh, 1)) : LL(d1, 1, Math.Max(sh, 1))) - d * 3 * N; if (mfe >= 1) ModifySL(s, L1, main.EntryPrice, d); }
            else
            {
                double tp1 = Get(s.Name + "_tp1"), px = d == 1 ? s.Bid : s.Ask;
                if (Get(s.Name + "_tp1done") == 0 && (px - tp1) * d >= 0)
                {
                    double half = s.NormalizeVolumeInUnits(main.VolumeInUnits / 2, RoundingMode.Down);
                    if (half >= s.VolumeInUnitsMin) ModifyPosition(main, main.VolumeInUnits - half);
                    Set(s.Name + "_tp1done", 1);
                }
                if (Get(s.Name + "_tp1done") > 0) { ModifySL(s, L1, main.EntryPrice, d); trail = d == 1 ? LL(d1, 1, 55) : HH(d1, 1, 55); }
            }
            if (trail > 0) { ModifySL(s, L1, trail, d); ModifySL(s, L1A, trail, d); }
            int units = Mine(s, L1).Count() + Mine(s, L1A).Count();
            double last = Get(s.Name + "_last"), nxt = last + d * 0.5 * N, ask = d == 1 ? s.Ask : s.Bid;
            if (units < 4 && N > 0 && (ask - nxt) * d >= 0)
            {
                double vol = SizeTrade(s, P1Risk(EdgeMode()), 2 * N);
                if (vol > 0)
                {
                    var res = ExecuteMarketOrder(d == 1 ? TradeType.Buy : TradeType.Sell, s.Name, vol, L1A, 2 * N / s.PipSize, null, "FP1+");
                    if (res.IsSuccessful) Set(s.Name + "_last", nxt);
                }
            }
        }

        // ---------------------------------------------------------------- PLAN 3
        void Plan3NewHour(Symbol s, int fam)
        {
            int barHour = (NYHour() + 23) % 24;
            if (barHour == 12 || barHour == 13) return;
            if (KillZonesOnly && !KZ.Contains(barHour)) return;
            var w1 = MarketData.GetBars(TimeFrame.Weekly, s.Name); var h1 = MarketData.GetBars(TimeFrame.Hour, s.Name); var d1 = MarketData.GetBars(TimeFrame.Daily, s.Name);
            int dir = Bias(w1, 4); if (dir == 0) return;
            var first = Mine(s, L3).FirstOrDefault(); int adds = Mine(s, L3A).Count();
            if (first != null)
            {
                int fd = first.TradeType == TradeType.Buy ? 1 : -1; double r1 = Get(s.Name + "_p3r");
                double px0 = fd == 1 ? s.Bid : s.Ask;
                if (fd != dir || 1 + adds >= 5 || r1 <= 0 || (px0 - first.EntryPrice) * dir / r1 < 1.0) return;   // threshold = the open trade
            }
            double o = Os(h1, 1), h = Hs(h1, 1), l = Ls(h1, 1), c = Cs(h1, 1), u = Unit(fam), bse = Math.Floor(c / u) * u;
            bool hit = false; double lvl = 0;
            for (int b = -1; b <= 1; b++) foreach (var f in FR)
            {
                double Lv = bse + b * u + f * u;
                if (dir == 1 && l <= Lv && o > Lv && c > Lv && Lv > lvl) { hit = true; lvl = Lv; }
                if (dir == -1 && h >= Lv && o < Lv && c < Lv && (lvl == 0 || Lv < lvl)) { hit = true; lvl = Lv; }
            }
            if (!hit) return;
            double datr = ATRw(d1, 14, 1), px = dir == 1 ? s.Ask : s.Bid;
            if (datr < 3 * s.Spread) return;
            double sl = px - dir * datr; if (first != null) sl = dir == 1 ? Math.Max(sl, first.EntryPrice) : Math.Min(sl, first.EntryPrice);
            double vol = SizeTrade(s, P3Risk(EdgeMode()), Math.Abs(px - sl)); if (vol <= 0) return;
            string cm = "FP3 r=" + (vol * datr * MoneyPerPrice(s)).ToString("F2", System.Globalization.CultureInfo.InvariantCulture);
            var res = ExecuteMarketOrder(dir == 1 ? TradeType.Buy : TradeType.Sell, s.Name, vol, first == null ? L3 : L3A, Math.Abs(px - sl) / s.PipSize, null, cm);
            if (!res.IsSuccessful) return;
            if (first == null) Set(s.Name + "_p3r", datr); else ModifySL(s, L3, first.EntryPrice, dir);
        }
        void Plan3Manage(Symbol s)
        {
            var first = Mine(s, L3).FirstOrDefault();
            if (first == null) { CloseLabel(s, L3A); return; }
            int d = first.TradeType == TradeType.Buy ? 1 : -1;
            var h1 = MarketData.GetBars(TimeFrame.Hour, s.Name); var d1 = MarketData.GetBars(TimeFrame.Daily, s.Name);
            double r = Get(s.Name + "_p3r"); if (r <= 0 && first.StopLoss.HasValue) r = Math.Abs(first.EntryPrice - first.StopLoss.Value);
            int sh = 0; for (int i = h1.Count - 1; i >= 0 && h1.OpenTimes[i] > first.EntryTime; i--) sh++;
            double best = d == 1 ? HH(h1, 0, sh + 1) : LL(h1, 0, sh + 1), mfe = r > 0 ? (best - first.EntryPrice) * d / r : 0;
            if (sh >= 120 && mfe < 0.5) { CloseLabel(s, L3); CloseLabel(s, L3A); return; }
            if (mfe >= 1.0) { ModifySL(s, L3, first.EntryPrice, d); ModifySL(s, L3A, first.EntryPrice, d); }
            if (mfe >= 2.0) { double tr = d == 1 ? LL(d1, 1, 5) : HH(d1, 1, 5); ModifySL(s, L3, tr, d); ModifySL(s, L3A, tr, d); }
        }

        protected override void OnTimer()
        {
            bool ok = Guard();
            foreach (var (s, fam) in markets)
            {
                if (UsePlan1) Plan1Manage(s);
                if (UsePlan3) Plan3Manage(s);
                if (!ok) continue;
                var d1 = MarketData.GetBars(TimeFrame.Daily, s.Name); var h1 = MarketData.GetBars(TimeFrame.Hour, s.Name);
                DateTime td = d1.OpenTimes.LastValue, th = h1.OpenTimes.LastValue;
                if (!lastD1.TryGetValue(s.Name, out var pd) || pd != td) { lastD1[s.Name] = td; if (UsePlan1) Plan1NewDay(s); }
                if (!lastH1.TryGetValue(s.Name, out var ph)) lastH1[s.Name] = th;
                else if (ph != th) { lastH1[s.Name] = th; if (UsePlan3) Plan3NewHour(s, fam); }
            }
            var m = EdgeMode(); double room = Room();
            string t = $"FibFVG Pro | {PresetSel} | mode {m} | start {startBal:F2} equity {Account.Equity:F2} peak {Peak:F2} | open risk {OpenRisk():F2} | room {(room == double.MaxValue ? "no limit" : room.ToString("F2"))}{(halted ? " | HALTED" : "")}\nwithdrawable now {Withdrawable():F2} (balance - start - open stop-risk)\n";
            foreach (var (s, fam) in markets)
            {
                var d1 = MarketData.GetBars(TimeFrame.Daily, s.Name);
                double l1 = SizeTrade(s, P1Risk(m), 1.2 * ATRw(d1, 20, 1)), l3 = SizeTrade(s, P3Risk(m), ATRw(d1, 14, 1));
                t += $"{s.Name}  P1 lots {(l1 > 0 ? s.VolumeInUnitsToQuantity(l1).ToString("F2") : "below min")}  P3 lots {(l3 > 0 ? s.VolumeInUnitsToQuantity(l3).ToString("F2") : "below min")}\n";
            }
            Chart.DrawStaticText("fibpro", t, VerticalAlignment.Top, HorizontalAlignment.Left, Color.White);
        }
    }
}

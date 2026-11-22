//+------------------------------------------------------------------+
//|                                                 FibFVG_Pro.mq4    |
//|  MT4 port of FibFVG_Pro.mq5 - same rules, same presets.          |
//|  Drop on ANY chart; trades the 5 markets it finds.               |
//+------------------------------------------------------------------+
#property copyright "FibFVG Pro"
#property version   "2.00"
#property strict

enum ENUM_PRESET { PRESET_FUNDEDNEXT_STELLAR_INSTANT = 0, PRESET_INSTANT_PREMIUM = 1, PRESET_PERSONAL = 2, PRESET_CUSTOM = 3 };
enum ENUM_RISKMODE { MODE_CONSERVATIVE = 0, MODE_NORMAL = 1, MODE_AGGRESSIVE = 2, MODE_EDGE_GATE = 3 };
enum ENUM_P1EXIT { P1_CHANDELIER = 0, P1_MONTHLY = 1 };

input ENUM_PRESET   Preset          = PRESET_FUNDEDNEXT_STELLAR_INSTANT;
input ENUM_RISKMODE RiskMode        = MODE_NORMAL;
input string        SymbolsToTrade  = "AUTO";
input bool          UsePlan1        = true;
input bool          UsePlan3        = true;
input ENUM_P1EXIT   Plan1Exit       = P1_CHANDELIER;
input bool          KillZonesOnly   = false;
input bool          Plan3Bank2R     = true;     // Plan 3B: close half of each levels unit at +2R
input double        StartBalance    = 0;
input bool          ShowPayoutPlan  = true;
input double        AccountFee      = 740;
input double        CustomDailyLossPct = 0;
input double        CustomMaxLossPct   = 6;
input bool          CustomTrailing     = true;
input bool          ShowPanel       = true;
input int           Magic           = 7706180;

#define MAXS 8
double OTE = 0.705, EXT1 = 0.272;
int    BRK = 20;
int    KZ[] = {20, 0, 2, 6, 7, 9, 10, 15};
string Sym[MAXS]; int Fam[MAXS]; int NS = 0;
datetime lastD1[MAXS], lastH1[MAXS];
double dailyLim = 0, maxLim = 0; bool trailingDD = true; double startBal = 0; bool halted = false;
string GV(string k) { return "FibPro4_" + IntegerToString(Magic) + "_" + k; }
double P1Risk(int m) { return m == MODE_CONSERVATIVE ? 0.0015 : m == MODE_NORMAL ? 0.0025 : 0.0050; }
double P3Risk(int m) { return m == MODE_CONSERVATIVE ? 0.0005 : m == MODE_NORMAL ? 0.0010 : 0.0025; }
double LevelUnit(int f) { return f == 0 ? 100 : f == 1 ? 1 : f == 2 ? 10000 : f == 3 ? 100 : 1000; }

int OnInit()
{
   if(Preset == PRESET_FUNDEDNEXT_STELLAR_INSTANT) { dailyLim = 0;    maxLim = 0.06; trailingDD = true; }
   if(Preset == PRESET_INSTANT_PREMIUM)            { dailyLim = 0.03; maxLim = 0.06; trailingDD = true; }
   if(Preset == PRESET_PERSONAL)                   { dailyLim = 0;    maxLim = 0;    trailingDD = false; }
   if(Preset == PRESET_CUSTOM) { dailyLim = CustomDailyLossPct / 100; maxLim = CustomMaxLossPct / 100; trailingDD = CustomTrailing; }
   startBal = StartBalance > 0 ? StartBalance : (GlobalVariableCheck(GV("start")) ? GlobalVariableGet(GV("start")) : AccountBalance());
   GlobalVariableSet(GV("start"), startBal);
   if(!GlobalVariableCheck(GV("peak"))) GlobalVariableSet(GV("peak"), startBal);
   halted = GlobalVariableCheck(GV("halt")) && GlobalVariableGet(GV("halt")) > 0;
   ResolveSymbols();
   EventSetTimer(5);
   return(INIT_SUCCEEDED);
}
void OnDeinit(const int r) { EventKillTimer(); Comment(""); }

bool Match(string n, string pat) { string u = n; StringToUpper(u); return StringFind(u, pat) == 0; }
int FamilyOf(string n)
{
   if(Match(n, "XAUUSD") || Match(n, "GOLD")) return 0;
   if(Match(n, "XAGUSD") || Match(n, "SILVER")) return 1;
   if(Match(n, "BTCUSD") || Match(n, "BITCOIN")) return 2;
   if(Match(n, "US500") || Match(n, "SPX500") || Match(n, "SP500") || Match(n, "USA500") || Match(n, "SPX")) return 3;
   if(Match(n, "NAS100") || Match(n, "USTEC") || Match(n, "US100") || Match(n, "NDX100") || Match(n, "NAS")) return 4;
   return -1;
}
void AddSym(string n)
{
   int f = FamilyOf(n); if(f < 0 || NS >= MAXS) return;
   for(int i = 0; i < NS; i++) if(Fam[i] == f) return;
   if(MarketInfo(n, MODE_TRADEALLOWED) == 0 && MarketInfo(n, MODE_BID) == 0) return;
   SymbolSelect(n, true);
   Sym[NS] = n; Fam[NS] = f; lastD1[NS] = 0; lastH1[NS] = 0; NS++;
}
void ResolveSymbols()
{
   NS = 0;
   if(SymbolsToTrade != "AUTO")
   {
      string parts[]; int k = StringSplit(SymbolsToTrade, ',', parts);
      for(int i = 0; i < k; i++) { parts[i] = StringTrimLeft(StringTrimRight(parts[i])); AddSym(parts[i]); }
      return;
   }
   AddSym(Symbol());
   for(int i = 0; i < SymbolsTotal(false) && NS < 5; i++) AddSym(SymbolName(i, false));
}

double H(string s, int tf, int i) { return iHigh(s, tf, i); }
double L(string s, int tf, int i) { return iLow(s, tf, i); }
double O(string s, int tf, int i) { return iOpen(s, tf, i); }
double C(string s, int tf, int i) { return iClose(s, tf, i); }
double HH(string s, int tf, int from, int n) { int i = iHighest(s, tf, MODE_HIGH, n, from); return i < 0 ? 0 : H(s, tf, i); }
double LL(string s, int tf, int from, int n) { int i = iLowest(s, tf, MODE_LOW, n, from); return i < 0 ? 0 : L(s, tf, i); }
double ATRw(string s, int tf, int len, int shift)
{
   double a = 0; bool init = false;
   for(int k = shift + len * 5; k >= shift; k--)
   {
      double tr = MathMax(H(s, tf, k), C(s, tf, k + 1)) - MathMin(L(s, tf, k), C(s, tf, k + 1));
      if(!init) { a = tr; init = true; } else a += (tr - a) / len;
   }
   return a;
}
int Bias(string s, int tf, int look) { double mid = (HH(s, tf, 1, look) + LL(s, tf, 1, look)) / 2, c = C(s, tf, 1); return c > mid ? 1 : c < mid ? -1 : 0; }
double Norm(string s, double p) { return NormalizeDouble(p, (int)MarketInfo(s, MODE_DIGITS)); }
double MoneyPerPrice(string s) { double tv = MarketInfo(s, MODE_TICKVALUE), ts = MarketInfo(s, MODE_TICKSIZE); return ts > 0 ? tv / ts : 0; }
double LotsFor(string s, double riskMoney, double dist)
{
   double mpp = MoneyPerPrice(s), step = MarketInfo(s, MODE_LOTSTEP), vmin = MarketInfo(s, MODE_MINLOT), vmax = MarketInfo(s, MODE_MAXLOT);
   if(mpp <= 0 || dist <= 0 || step <= 0) return 0;
   double lots = MathFloor(riskMoney / (dist * mpp) / step) * step;
   if(lots < vmin) return 0;
   return MathMin(lots, vmax);
}
datetime NthSunday(int year, int mon, int n)
{
   datetime d = StringToTime(StringFormat("%04d.%02d.01 00:00", year, mon));
   int add = (7 - TimeDayOfWeek(d)) % 7 + 7 * (n - 1);
   return d + add * 86400;
}
int NYHour()
{
   datetime g = TimeGMT(); int y = TimeYear(g);
   datetime ds = NthSunday(y, 3, 2) + 7 * 3600, de = NthSunday(y, 11, 1) + 6 * 3600;
   return TimeHour(g + ((g >= ds && g < de) ? -4 : -5) * 3600);
}
bool Ours(int mg) { return mg >= Magic && mg <= Magic + 9; }
double OpenRisk()
{
   double tot = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES) || !Ours(OrderMagicNumber()) || OrderType() > OP_SELL) continue;
      int d = OrderType() == OP_BUY ? 1 : -1; double dist = (OrderOpenPrice() - OrderStopLoss()) * d;
      if(OrderStopLoss() <= 0 || dist <= 0) continue;
      tot += dist * MoneyPerPrice(OrderSymbol()) * OrderLots();
   }
   return tot;
}
double Peak() { return GlobalVariableGet(GV("peak")); }
double DayStart() { return GlobalVariableCheck(GV("day")) ? GlobalVariableGet(GV("day")) : AccountBalance(); }
void UpdateDay()
{
   int key = TimeYear(TimeCurrent()) * 1000 + TimeDayOfYear(TimeCurrent());
   if((int)GlobalVariableGet(GV("daykey")) != key) { GlobalVariableSet(GV("daykey"), key); GlobalVariableSet(GV("day"), MathMax(AccountBalance(), AccountEquity())); }
}
double Room()
{
   double eq = AccountEquity(), room = 1e18;
   if(maxLim > 0) room = MathMin(room, (maxLim - 0.01) * startBal - ((trailingDD ? Peak() : startBal) - eq) - OpenRisk());
   if(dailyLim > 0) room = MathMin(room, (dailyLim - 0.005) * startBal - (DayStart() - eq) - OpenRisk());
   return room;
}
void CloseTicket(int tk)
{
   if(!OrderSelect(tk, SELECT_BY_TICKET)) return;
   if(OrderType() <= OP_SELL) { RefreshRates(); double px = OrderType() == OP_BUY ? MarketInfo(OrderSymbol(), MODE_BID) : MarketInfo(OrderSymbol(), MODE_ASK); bool r = OrderClose(tk, OrderLots(), px, 50); }
   else { bool r = OrderDelete(tk); }
}
void CloseAll(string why)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--) if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES) && Ours(OrderMagicNumber())) CloseTicket(OrderTicket());
   Print("FibFVG Pro guard: ", why);
}
void SyncBalanceOps()
{
   datetime from = (datetime)GlobalVariableGet(GV("opsync"));
   if(from == 0) { GlobalVariableSet(GV("opsync"), (double)TimeCurrent()); return; }
   double moved = 0; datetime last = from;
   for(int i = 0; i < OrdersHistoryTotal(); i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
      if(OrderType() != 6 && OrderType() != 7) continue;          // balance / credit operations
      if(OrderOpenTime() <= from) continue;
      moved += OrderProfit(); if(OrderOpenTime() > last) last = OrderOpenTime();
   }
   if(moved != 0)
   {
      GlobalVariableSet(GV("peak"), MathMax(startBal, Peak() + moved)); GlobalVariableSet(GV("day"), DayStart() + moved);
      if(GlobalVariableCheck(GV("mbal"))) GlobalVariableSet(GV("mbal"), GlobalVariableGet(GV("mbal")) + moved);
      if(moved < 0) GlobalVariableSet(GV("qpaid"), GlobalVariableGet(GV("qpaid")) - moved);
   }
   GlobalVariableSet(GV("opsync"), (double)last);
}
string PayoutPlanText()
{
   if(!GlobalVariableCheck(GV("plan0"))) GlobalVariableSet(GV("plan0"), (double)TimeCurrent());
   datetime p0 = (datetime)GlobalVariableGet(GV("plan0"));
   int m = (int)((TimeCurrent() - p0) / (30.44 * 86400)) + 1;
   if((int)GlobalVariableGet(GV("pmonth")) != m)
   {
      int q = (m - 1) / 3, qOld = ((int)GlobalVariableGet(GV("pmonth")) - 1) / 3;
      GlobalVariableSet(GV("pmonth"), m); GlobalVariableSet(GV("mbal"), AccountBalance());
      if(q != qOld) GlobalVariableSet(GV("qpaid"), 0);
   }
   double mtd = AccountBalance() - GlobalVariableGet(GV("mbal")), qtd = GlobalVariableGet(GV("qpaid")) + MathMax(0, mtd);
   int qEnd = ((m - 1) / 3 + 1) * 3;
   string dest = m == 1 ? "founder's private account" : StringFormat("quarter pot -> Cueto & Co at end of month %d", qEnd);
   return StringFormat("PLAN month %d | month-to-date %.2f -> withdraw at month end (restarts at %.0f) -> %s\nquarter-to-date %.2f -> buys %d new $100K account(s) at %.0f\n",
                       m, mtd, startBal, dest, qtd, AccountFee > 0 ? (int)MathFloor(qtd * 0.8 / AccountFee) : 0, AccountFee);
}
double Withdrawable() { return MathMax(0, AccountBalance() - startBal - OpenRisk()); }
bool Guard()
{
   SyncBalanceOps();
   UpdateDay();
   if(AccountBalance() > Peak()) GlobalVariableSet(GV("peak"), AccountBalance());
   if(halted) return false;
   double eq = AccountEquity();
   if(maxLim > 0 && (trailingDD ? Peak() : startBal) - eq >= (maxLim - 0.005) * startBal) { CloseAll("max-loss emergency line"); halted = true; GlobalVariableSet(GV("halt"), 1); return false; }
   if(dailyLim > 0 && DayStart() - eq >= (dailyLim - 0.003) * startBal) { CloseAll("daily emergency line"); return false; }
   return true;
}
int EdgeMode()
{
   if(RiskMode != MODE_EDGE_GATE) return RiskMode;
   double dd = ((trailingDD ? Peak() : startBal) - AccountEquity()) / startBal;
   if(dd >= 0.03) return MODE_CONSERVATIVE;
   double rs[]; int k = 0; ArrayResize(rs, 0);
   for(int i = 0; i < OrdersHistoryTotal(); i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
      if((OrderMagicNumber() != Magic && OrderMagicNumber() != Magic + 2) || OrderType() > OP_SELL) continue;
      int p = StringFind(OrderComment(), "r="); if(p < 0) continue;
      double risk = StringToDouble(StringSubstr(OrderComment(), p + 2)); if(risk <= 0) continue;
      ArrayResize(rs, k + 1); rs[k++] = (OrderProfit() + OrderSwap() + OrderCommission()) / risk;
   }
   if(k < 20) return MODE_CONSERVATIVE;
   double s20 = 0, g20 = 0, l20 = 0, s40 = 0, g40 = 0, l40 = 0;
   for(int i = k - 1; i >= 0 && i >= k - 40; i--)
   {
      if(i >= k - 20) { s20 += rs[i]; if(rs[i] > 0) g20 += rs[i]; else l20 -= rs[i]; }
      s40 += rs[i]; if(rs[i] > 0) g40 += rs[i]; else l40 -= rs[i];
   }
   double pf20 = l20 > 0 ? g20 / l20 : 9.9, pf40 = l40 > 0 ? g40 / l40 : 9.9;
   if(k >= 40 && s40 >= 8 && pf40 >= 1.5 && dd <= 0.015) return MODE_AGGRESSIVE;
   if(s20 >= 3 && pf20 >= 1.3 && dd <= 0.02) return MODE_NORMAL;
   return MODE_CONSERVATIVE;
}
double SizeTrade(string s, double pct, double dist)
{
   double riskMoney = startBal * pct, room = Room();
   if(riskMoney > 0.5 * room) riskMoney = MathMax(0, 0.5 * room);
   return LotsFor(s, riskMoney, dist);
}
int Count(string s, int mg, int &dir, double &op, double &sl, datetime &ot, bool pending = false)
{
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES) || OrderSymbol() != s || OrderMagicNumber() != mg) continue;
      if(!pending && OrderType() > OP_SELL) continue;
      if(pending && OrderType() <= OP_SELL) continue;
      n++; dir = (OrderType() == OP_BUY || OrderType() == OP_BUYLIMIT) ? 1 : -1;
      op = OrderOpenPrice(); sl = OrderStopLoss(); ot = OrderOpenTime();
   }
   return n;
}
void CloseMagic(string s, int mg) { for(int i = OrdersTotal() - 1; i >= 0; i--) if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES) && OrderSymbol() == s && OrderMagicNumber() == mg && OrderType() <= OP_SELL) CloseTicket(OrderTicket()); }
void DeletePending(string s, int mg) { for(int i = OrdersTotal() - 1; i >= 0; i--) if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES) && OrderSymbol() == s && OrderMagicNumber() == mg && OrderType() > OP_SELL) CloseTicket(OrderTicket()); }
void ModifySL(string s, int mg, double nsl, int d)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES) || OrderSymbol() != s || OrderMagicNumber() != mg || OrderType() > OP_SELL) continue;
      double sl = OrderStopLoss(), px = d == 1 ? MarketInfo(s, MODE_BID) : MarketInfo(s, MODE_ASK);
      double want = d == 1 ? MathMax(sl, nsl) : (sl == 0 ? nsl : MathMin(sl, nsl));
      if(MathAbs(want - sl) > MarketInfo(s, MODE_POINT) && (d == 1 ? want < px : want > px)) { bool r = OrderModify(OrderTicket(), OrderOpenPrice(), Norm(s, want), OrderTakeProfit(), 0); }
   }
}
int Send(string s, int type, double lots, double price, double sl, string cm, int mg, datetime exp = 0)
{ return OrderSend(s, type, lots, Norm(s, price), 50, Norm(s, sl), 0, cm, mg, exp, clrNONE); }

//------------------------------------------------------------ PLAN 1
void Plan1NewDay(int k)
{
   string s = Sym[k]; int d_; double a_, b_; datetime t_;
   if(Count(s, Magic, d_, a_, b_, t_) + Count(s, Magic + 1, d_, a_, b_, t_) > 0) return;
   int dir = Bias(s, PERIOD_W1, 4); if(dir == 0 || dir != Bias(s, PERIOD_MN1, 6)) return;
   double N = ATRw(s, PERIOD_D1, 20, 1);
   bool brk = dir == 1 ? H(s, PERIOD_D1, 1) >= HH(s, PERIOD_D1, 2, BRK) : L(s, PERIOD_D1, 1) <= LL(s, PERIOD_D1, 2, BRK);
   if(!brk) return;
   int ext = dir == 1 ? iLowest(s, PERIOD_D1, MODE_LOW, BRK, 1) : iHighest(s, PERIOD_D1, MODE_HIGH, BRK, 1);
   double origin = dir == 1 ? L(s, PERIOD_D1, ext) : H(s, PERIOD_D1, ext), extreme = dir == 1 ? H(s, PERIOD_D1, 1) : L(s, PERIOD_D1, 1);
   double rng = MathAbs(extreme - origin); bool fvg = false;
   for(int j = ext - 2; j >= 1 && !fvg; j--) fvg = dir == 1 ? L(s, PERIOD_D1, j) > H(s, PERIOD_D1, j + 2) : H(s, PERIOD_D1, j) < L(s, PERIOD_D1, j + 2);
   if(!fvg || rng < 1.5 * N) return;
   double entry = extreme - dir * OTE * rng, sl = origin - dir * 0.25 * N;
   double lots = SizeTrade(s, P1Risk(EdgeMode()), MathAbs(entry - sl)); if(lots <= 0) return;
   DeletePending(s, Magic);
   GlobalVariableSet(GV(s + "_N"), N); GlobalVariableSet(GV(s + "_tp1"), extreme + dir * EXT1 * rng);
   GlobalVariableSet(GV(s + "_tp1done"), 0); GlobalVariableSet(GV(s + "_last"), entry); GlobalVariableSet(GV(s + "_risk"), MathAbs(entry - sl));
   string cm = "FP1 r=" + DoubleToString(lots * MathAbs(entry - sl) * MoneyPerPrice(s), 2);
   Send(s, dir == 1 ? OP_BUYLIMIT : OP_SELLLIMIT, lots, entry, sl, cm, Magic, TimeCurrent() + 15 * 86400);
}
void Plan1Manage(int k)
{
   string s = Sym[k]; int d = 0, d2 = 0; double op = 0, sl = 0, o2, s2; datetime ot = 0, t2;
   int n0 = Count(s, Magic, d, op, sl, ot), n1 = Count(s, Magic + 1, d2, o2, s2, t2);
   if(n0 == 0) { if(n1 > 0) CloseMagic(s, Magic + 1); return; }
   double N = GlobalVariableGet(GV(s + "_N")), r = GlobalVariableGet(GV(s + "_risk")); if(r <= 0) r = MathAbs(op - sl);
   int sh = iBarShift(s, PERIOD_D1, ot);
   double best = d == 1 ? HH(s, PERIOD_D1, 0, sh + 1) : LL(s, PERIOD_D1, 0, sh + 1), mfe = r > 0 ? (best - op) * d / r : 0;
   if(sh >= 10 && mfe < 0.5) { CloseMagic(s, Magic); CloseMagic(s, Magic + 1); return; }
   double trail = 0;
   if(Plan1Exit == P1_CHANDELIER) { trail = (d == 1 ? HH(s, PERIOD_D1, 1, MathMax(sh, 1)) : LL(s, PERIOD_D1, 1, MathMax(sh, 1))) - d * 3 * N; if(mfe >= 1) ModifySL(s, Magic, op, d); }
   else
   {
      double tp1 = GlobalVariableGet(GV(s + "_tp1")), px = d == 1 ? MarketInfo(s, MODE_BID) : MarketInfo(s, MODE_ASK);
      if(GlobalVariableGet(GV(s + "_tp1done")) == 0 && (px - tp1) * d >= 0)
      {
         for(int i = OrdersTotal() - 1; i >= 0; i--)
            if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES) && OrderSymbol() == s && OrderMagicNumber() == Magic && OrderType() <= OP_SELL)
            { double st = MarketInfo(s, MODE_LOTSTEP), half = MathFloor(OrderLots() / 2 / st) * st;
              if(half >= MarketInfo(s, MODE_MINLOT)) { bool rr = OrderClose(OrderTicket(), half, px, 50); } }
         GlobalVariableSet(GV(s + "_tp1done"), 1);
      }
      if(GlobalVariableGet(GV(s + "_tp1done")) > 0) { ModifySL(s, Magic, op, d); trail = d == 1 ? LL(s, PERIOD_D1, 1, 55) : HH(s, PERIOD_D1, 1, 55); }
   }
   if(trail > 0) { ModifySL(s, Magic, trail, d); ModifySL(s, Magic + 1, trail, d); }
   double last = GlobalVariableGet(GV(s + "_last")), nxt = last + d * 0.5 * N, px = d == 1 ? MarketInfo(s, MODE_ASK) : MarketInfo(s, MODE_BID);
   if(n0 + n1 < 4 && N > 0 && (px - nxt) * d >= 0)
   {
      double lots = SizeTrade(s, P1Risk(EdgeMode()), 2 * N);
      if(lots > 0 && Send(s, d == 1 ? OP_BUY : OP_SELL, lots, px, px - d * 2 * N, "FP1+", Magic + 1) > 0) GlobalVariableSet(GV(s + "_last"), nxt);
   }
}
//------------------------------------------------------------ PLAN 3
bool InKZ(int h) { for(int i = 0; i < ArraySize(KZ); i++) if(KZ[i] == h) return true; return false; }
void Plan3NewHour(int k)
{
   string s = Sym[k]; int barHour = (NYHour() + 23) % 24;
   if(barHour == 12 || barHour == 13) return;
   if(KillZonesOnly && !InKZ(barHour)) return;
   int dir = Bias(s, PERIOD_W1, 4); if(dir == 0) return;
   int d0 = 0, d1; double fo = 0, fs, ao, as_; datetime ft, at;
   int n2 = Count(s, Magic + 2, d0, fo, fs, ft), n3 = Count(s, Magic + 3, d1, ao, as_, at);
   if(n2 > 0)
   {
      if(d0 != dir || n2 + n3 >= 5) return;
      double r1 = GlobalVariableGet(GV(s + "_p3r")), px = dir == 1 ? MarketInfo(s, MODE_BID) : MarketInfo(s, MODE_ASK);
      if(r1 <= 0 || (px - fo) * dir / r1 < 1.0) return;
   }
   double o = O(s, PERIOD_H1, 1), h = H(s, PERIOD_H1, 1), l = L(s, PERIOD_H1, 1), c = C(s, PERIOD_H1, 1);
   double fr[] = {0, 0.2, 0.5, 0.6, 0.8};
   double u = LevelUnit(Fam[k]), base = MathFloor(c / u) * u; bool hit = false; double lvl = 0;
   for(int b = -1; b <= 1; b++) for(int j = 0; j < 5; j++)
   {
      double Lv = base + b * u + fr[j] * u;
      if(dir == 1 && l <= Lv && o > Lv && c > Lv && Lv > lvl) { hit = true; lvl = Lv; }
      if(dir == -1 && h >= Lv && o < Lv && c < Lv && (lvl == 0 || Lv < lvl)) { hit = true; lvl = Lv; }
   }
   if(!hit) return;
   double datr = ATRw(s, PERIOD_D1, 14, 1), px = dir == 1 ? MarketInfo(s, MODE_ASK) : MarketInfo(s, MODE_BID);
   if(datr < 3 * (MarketInfo(s, MODE_ASK) - MarketInfo(s, MODE_BID))) return;
   double sl = px - dir * datr; if(n2 > 0) sl = dir == 1 ? MathMax(sl, fo) : MathMin(sl, fo);
   double lots = SizeTrade(s, P3Risk(EdgeMode()), MathAbs(px - sl)); if(lots <= 0) return;
   string cm = "FP3 r=" + DoubleToString(lots * datr * MoneyPerPrice(s), 2);
   int tk = Send(s, dir == 1 ? OP_BUY : OP_SELL, lots, px, sl, cm, n2 > 0 ? Magic + 3 : Magic + 2);
   if(tk > 0 && n2 == 0) GlobalVariableSet(GV(s + "_p3r"), datr);
   if(tk > 0 && n2 > 0) ModifySL(s, Magic + 2, fo, dir);
}
void BankHalf(string s, int mg, int d, double r)
{
   if(r <= 0) return;
   double px = d == 1 ? MarketInfo(s, MODE_BID) : MarketInfo(s, MODE_ASK);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES) || OrderSymbol() != s || OrderMagicNumber() != mg || OrderType() > OP_SELL) continue;
      if(StringFind(OrderComment(), "from #") >= 0) continue;        // remainder of an already-split order
      string key = GV("bank_" + IntegerToString(OrderTicket()));
      if(GlobalVariableCheck(key) || (px - OrderOpenPrice()) * d < 2.0 * r) continue;
      double st = MarketInfo(s, MODE_LOTSTEP), half = MathFloor(OrderLots() / 2 / st) * st;
      GlobalVariableSet(key, 1);
      if(half >= MarketInfo(s, MODE_MINLOT)) { bool ok = OrderClose(OrderTicket(), half, px, 50); }
   }
}
void Plan3Manage(int k)
{
   string s = Sym[k]; int d = 0, d2; double op = 0, sl = 0, o2, s2; datetime ot = 0, t2;
   int n2 = Count(s, Magic + 2, d, op, sl, ot), n3 = Count(s, Magic + 3, d2, o2, s2, t2);
   if(n2 == 0) { if(n3 > 0) CloseMagic(s, Magic + 3); return; }
   double r = GlobalVariableGet(GV(s + "_p3r")); if(r <= 0) r = MathAbs(op - sl);
   int sh = iBarShift(s, PERIOD_H1, ot);
   double best = d == 1 ? HH(s, PERIOD_H1, 0, sh + 1) : LL(s, PERIOD_H1, 0, sh + 1), mfe = r > 0 ? (best - op) * d / r : 0;
   if(sh >= 120 && mfe < 0.5) { CloseMagic(s, Magic + 2); CloseMagic(s, Magic + 3); return; }
   if(Plan3Bank2R) { BankHalf(s, Magic + 2, d, r); BankHalf(s, Magic + 3, d, r); }
   if(mfe >= 1.0) { ModifySL(s, Magic + 2, op, d); ModifySL(s, Magic + 3, op, d); }
   if(mfe >= 2.0) { double tr = d == 1 ? LL(s, PERIOD_D1, 1, 5) : HH(s, PERIOD_D1, 1, 5); ModifySL(s, Magic + 2, tr, d); ModifySL(s, Magic + 3, tr, d); }
}
void OnTimer()
{
   bool ok = Guard();
   for(int k = 0; k < NS; k++)
   {
      RefreshRates();
      if(UsePlan1) Plan1Manage(k);
      if(UsePlan3) Plan3Manage(k);
      if(!ok) continue;
      datetime d1 = iTime(Sym[k], PERIOD_D1, 0), h1 = iTime(Sym[k], PERIOD_H1, 0);
      if(d1 != lastD1[k]) { lastD1[k] = d1; if(UsePlan1) Plan1NewDay(k); }
      if(h1 != lastH1[k]) { bool first = lastH1[k] == 0; lastH1[k] = h1; if(UsePlan3 && !first) Plan3NewHour(k); }
   }
   if(ShowPanel)
   {
      int m = EdgeMode();
      string t = StringFormat("FibFVG Pro (MT4) | mode %s | start %.2f equity %.2f peak %.2f | open risk %.2f | room %.2f%s\n",
         m == 0 ? "Conservative" : m == 1 ? "Normal" : "Aggressive", startBal, AccountEquity(), Peak(), OpenRisk(), Room(), halted ? " | HALTED" : "");
      t += StringFormat("withdrawable now %.2f (balance - start - open stop-risk)\n", Withdrawable());
      if(ShowPayoutPlan) t += PayoutPlanText();
      for(int k = 0; k < NS; k++)
      {
         double l1 = SizeTrade(Sym[k], P1Risk(m), 1.2 * ATRw(Sym[k], PERIOD_D1, 20, 1)), l3 = SizeTrade(Sym[k], P3Risk(m), ATRw(Sym[k], PERIOD_D1, 14, 1));
         t += StringFormat("%s  P1 lots %s  P3 lots %s\n", Sym[k], l1 > 0 ? DoubleToString(l1, 2) : "below min", l3 > 0 ? DoubleToString(l3, 2) : "below min");
      }
      Comment(t);
   }
}
void OnTick() {}
//+------------------------------------------------------------------+

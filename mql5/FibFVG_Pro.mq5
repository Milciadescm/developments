//+------------------------------------------------------------------+
//|                                                 FibFVG_Pro.mq5    |
//|  Drop on ANY chart. Trades XAUUSD, XAGUSD, BTCUSD, US500, NAS100 |
//|  from this one chart (broker symbol names found automatically).  |
//|                                                                  |
//|  Plan 1  Position  : MN1+W1 bias, D1 Turtle breakout leg with FVG,|
//|                      limit at 0.705 OTE, stop beyond leg origin, |
//|                      Turtle adds every 0.5N (max 4), chandelier  |
//|                      or monthly exit, 10-day time stop.          |
//|  Plan 3  Levels    : W1 bias, H1 reaction at 00/20/50/60/80      |
//|                      levels, stop 1 daily ATR, BE at +1R, trail  |
//|                      5-day low from +2R, adds only while the     |
//|                      first unit is >= +1R, no NY-lunch trades.   |
//|  Guard             : never lets drawdown + open stop-risk exceed |
//|                      the firm limit minus a buffer; trades are   |
//|                      shrunk near the limit instead of stopped.   |
//|  Edge gate         : risk mode steps up only after the last 20/40|
//|                      closed positions prove the edge (see docs). |
//+------------------------------------------------------------------+
#property copyright "FibFVG Pro"
#property version   "2.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

enum ENUM_PRESET { PRESET_FUNDEDNEXT_STELLAR_INSTANT = 0, // FundedNext Stellar Instant (6% trailing, no daily)
                   PRESET_INSTANT_PREMIUM = 1,            // Instant Premium (3% daily, 6% max)
                   PRESET_PERSONAL = 2,                   // Personal / real money (no firm limits)
                   PRESET_CUSTOM = 3 };                   // use the Custom* inputs
enum ENUM_RISKMODE { MODE_CONSERVATIVE = 0, MODE_NORMAL = 1, MODE_AGGRESSIVE = 2, MODE_EDGE_GATE = 3 };
enum ENUM_P1EXIT { P1_CHANDELIER = 0, P1_MONTHLY = 1 };

input ENUM_PRESET   Preset          = PRESET_FUNDEDNEXT_STELLAR_INSTANT;
input ENUM_RISKMODE RiskMode        = MODE_NORMAL;
input string        SymbolsToTrade  = "AUTO";   // AUTO or a comma list of your broker's names
input bool          UsePlan1        = true;
input bool          UsePlan3        = true;
input ENUM_P1EXIT   Plan1Exit       = P1_CHANDELIER;  // chandelier for prop, monthly for personal
input bool          KillZonesOnly   = false;    // tested: no gain 2024-26, fewer trades
input double        StartBalance    = 0;        // 0 = balance when first attached (remembered)
input double        CustomDailyLossPct = 0;     // PRESET_CUSTOM only (0 = none)
input double        CustomMaxLossPct   = 6;
input bool          CustomTrailing     = true;
input bool          ShowPanel       = true;
input long          Magic           = 7706180;

// ------------------------------------------------------------- constants (match the backtest)
#define MAXS 8
const double OTE = 0.705, EXT1 = 0.272;
const int    BRK = 20;
const double KZ[] = {20, 0, 2, 6, 7, 9, 10, 15};

string Sym[MAXS]; int Fam[MAXS]; int NS = 0;          // family 0 XAU 1 XAG 2 BTC 3 US500 4 NAS100
datetime lastD1[MAXS], lastH1[MAXS];
double  dailyLim = 0, maxLim = 0; bool trailingDD = true;
double  startBal = 0;
bool    halted = false;
string  GV(string k) { return "FibPro_" + IntegerToString(Magic) + "_" + k; }

//--------------------------------------------------------------- risk modes (fraction of start balance)
double P1Risk(int m) { return m == MODE_CONSERVATIVE ? 0.0015 : m == MODE_NORMAL ? 0.0025 : 0.0050; }
double P3Risk(int m) { return m == MODE_CONSERVATIVE ? 0.0005 : m == MODE_NORMAL ? 0.0010 : 0.0025; }
double LevelUnit(int f) { return f == 0 ? 100 : f == 1 ? 1 : f == 2 ? 10000 : f == 3 ? 100 : 1000; }

//--------------------------------------------------------------- init: presets + symbol discovery
int OnInit()
{
   if(Preset == PRESET_FUNDEDNEXT_STELLAR_INSTANT) { dailyLim = 0;    maxLim = 0.06; trailingDD = true; }
   if(Preset == PRESET_INSTANT_PREMIUM)            { dailyLim = 0.03; maxLim = 0.06; trailingDD = true; }
   if(Preset == PRESET_PERSONAL)                   { dailyLim = 0;    maxLim = 0;    trailingDD = false; }
   if(Preset == PRESET_CUSTOM) { dailyLim = CustomDailyLossPct / 100; maxLim = CustomMaxLossPct / 100; trailingDD = CustomTrailing; }
   startBal = StartBalance > 0 ? StartBalance : (GlobalVariableCheck(GV("start")) ? GlobalVariableGet(GV("start")) : AccountInfoDouble(ACCOUNT_BALANCE));
   GlobalVariableSet(GV("start"), startBal);
   if(!GlobalVariableCheck(GV("peak"))) GlobalVariableSet(GV("peak"), startBal);
   halted = GlobalVariableCheck(GV("halt")) && GlobalVariableGet(GV("halt")) > 0;
   ResolveSymbols();
   trade.SetDeviationInPoints(50);
   EventSetTimer(5);
   PrintFormat("FibFVG Pro: preset %d, mode %d, start %.2f, %d symbols", Preset, RiskMode, startBal, NS);
   return(INIT_SUCCEEDED);
}
void OnDeinit(const int r) { EventKillTimer(); Comment(""); }

bool Match(string name, string pat) { string u = name; StringToUpper(u); return StringFind(u, pat) == 0; }
int FamilyOf(string n)
{
   string pats0[] = {"XAUUSD", "GOLD"};
   string pats1[] = {"XAGUSD", "SILVER"};
   string pats2[] = {"BTCUSD", "BITCOIN", "BTCUSDT"};
   string pats3[] = {"US500", "SPX500", "SP500", "USA500", "US.500", "SPX"};
   string pats4[] = {"NAS100", "USTEC", "US100", "NDX100", "USTECH", "NAS"};
   for(int i = 0; i < ArraySize(pats0); i++) if(Match(n, pats0[i])) return 0;
   for(int i = 0; i < ArraySize(pats1); i++) if(Match(n, pats1[i])) return 1;
   for(int i = 0; i < ArraySize(pats2); i++) if(Match(n, pats2[i])) return 2;
   for(int i = 0; i < ArraySize(pats3); i++) if(Match(n, pats3[i])) return 3;
   for(int i = 0; i < ArraySize(pats4); i++) if(Match(n, pats4[i])) return 4;
   return -1;
}
void AddSym(string n)
{
   int f = FamilyOf(n); if(f < 0 || NS >= MAXS) return;
   for(int i = 0; i < NS; i++) if(Fam[i] == f) return;                 // one symbol per market
   if(SymbolInfoInteger(n, SYMBOL_TRADE_MODE) == SYMBOL_TRADE_MODE_DISABLED) return;
   SymbolSelect(n, true);
   Sym[NS] = n; Fam[NS] = f; lastD1[NS] = 0; lastH1[NS] = 0; NS++;
}
void ResolveSymbols()
{
   NS = 0;
   if(SymbolsToTrade != "AUTO")
   {
      string parts[]; int k = StringSplit(SymbolsToTrade, ',', parts);
      for(int i = 0; i < k; i++) { StringTrimLeft(parts[i]); StringTrimRight(parts[i]); AddSym(parts[i]); }
      return;
   }
   AddSym(_Symbol);
   for(int i = 0; i < SymbolsTotal(false) && NS < 5; i++) AddSym(SymbolName(i, false));
}

//--------------------------------------------------------------- price helpers
double H(string s, ENUM_TIMEFRAMES tf, int i) { return iHigh(s, tf, i); }
double L(string s, ENUM_TIMEFRAMES tf, int i) { return iLow(s, tf, i); }
double O(string s, ENUM_TIMEFRAMES tf, int i) { return iOpen(s, tf, i); }
double C(string s, ENUM_TIMEFRAMES tf, int i) { return iClose(s, tf, i); }
double HH(string s, ENUM_TIMEFRAMES tf, int from, int n) { int i = iHighest(s, tf, MODE_HIGH, n, from); return i < 0 ? 0 : H(s, tf, i); }
double LL(string s, ENUM_TIMEFRAMES tf, int from, int n) { int i = iLowest(s, tf, MODE_LOW, n, from); return i < 0 ? 0 : L(s, tf, i); }
double ATRw(string s, ENUM_TIMEFRAMES tf, int len, int shift)
{
   double a = 0; bool init = false;
   for(int k = shift + len * 5; k >= shift; k--)
   {
      double tr = MathMax(H(s, tf, k), C(s, tf, k + 1)) - MathMin(L(s, tf, k), C(s, tf, k + 1));
      if(!init) { a = tr; init = true; } else a += (tr - a) / len;
   }
   return a;
}
int Bias(string s, ENUM_TIMEFRAMES tf, int look)
{
   double mid = (HH(s, tf, 1, look) + LL(s, tf, 1, look)) / 2, c = C(s, tf, 1);
   return c > mid ? 1 : c < mid ? -1 : 0;
}
double Norm(string s, double p) { return NormalizeDouble(p, (int)SymbolInfoInteger(s, SYMBOL_DIGITS)); }
double MoneyPerPrice(string s)   // USD per 1.0 price move per 1.00 lot
{
   double tv = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE_LOSS), ts = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE);
   return ts > 0 ? tv / ts : 0;
}
double LotsFor(string s, double riskMoney, double dist)
{
   double mpp = MoneyPerPrice(s), step = SymbolInfoDouble(s, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(s, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(s, SYMBOL_VOLUME_MAX);
   if(mpp <= 0 || dist <= 0 || step <= 0) return 0;
   double lots = MathFloor(riskMoney / (dist * mpp) / step) * step;
   if(lots < vmin) return 0;                     // never oversize to reach the minimum lot
   return MathMin(lots, vmax);
}

//--------------------------------------------------------------- New York time (US DST)
datetime NthSunday(int year, int mon, int n)
{
   MqlDateTime t; t.year = year; t.mon = mon; t.day = 1; t.hour = 0; t.min = 0; t.sec = 0;
   datetime d = StructToTime(t); TimeToStruct(d, t);
   int add = (7 - t.day_of_week) % 7 + 7 * (n - 1);
   return d + add * 86400;
}
int NYHour()
{
   datetime g = TimeGMT(); MqlDateTime t; TimeToStruct(g, t);
   datetime ds = NthSunday(t.year, 3, 2) + 7 * 3600, de = NthSunday(t.year, 11, 1) + 6 * 3600;
   int off = (g >= ds && g < de) ? -4 : -5;
   MqlDateTime n; TimeToStruct(g + off * 3600, n);
   return n.hour;
}

//--------------------------------------------------------------- account state, guard, edge gate
double OpenRisk()
{
   double tot = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      long mg = PositionGetInteger(POSITION_MAGIC); if(mg < Magic || mg > Magic + 9) continue;
      string s = PositionGetString(POSITION_SYMBOL);
      double sl = PositionGetDouble(POSITION_SL), op = PositionGetDouble(POSITION_PRICE_OPEN);
      if(sl <= 0) continue;
      int d = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      double dist = (op - sl) * d; if(dist <= 0) continue;   // stops at/above entry carry no risk
      tot += dist * MoneyPerPrice(s) * PositionGetDouble(POSITION_VOLUME);
   }
   return tot;
}
double Peak() { return GlobalVariableGet(GV("peak")); }
double DayStart() { return GlobalVariableCheck(GV("day")) ? GlobalVariableGet(GV("day")) : AccountInfoDouble(ACCOUNT_BALANCE); }
void UpdateDay()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   int key = t.year * 1000 + t.day_of_year;
   if((int)GlobalVariableGet(GV("daykey")) != key)
   { GlobalVariableSet(GV("daykey"), key); GlobalVariableSet(GV("day"), MathMax(AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY))); }
}
// room left before the bot's own line (firm limit minus buffer)
double Room()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY), room = DBL_MAX;
   if(maxLim > 0)
   {
      double ref = trailingDD ? Peak() : startBal;
      room = MathMin(room, (maxLim - 0.01) * startBal - (ref - eq) - OpenRisk());
   }
   if(dailyLim > 0) room = MathMin(room, (dailyLim - 0.005) * startBal - (DayStart() - eq) - OpenRisk());
   return room;
}
void CloseAll(string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk)) { long mg = PositionGetInteger(POSITION_MAGIC); if(mg >= Magic && mg <= Magic + 9) trade.PositionClose(tk); } }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   { ulong tk = OrderGetTicket(i); if(OrderSelect(tk)) { long mg = OrderGetInteger(ORDER_MAGIC); if(mg >= Magic && mg <= Magic + 9) trade.OrderDelete(tk); } }
   Print("FibFVG Pro guard: ", why);
}
bool Guard()
{
   UpdateDay();
   double eq = AccountInfoDouble(ACCOUNT_EQUITY), bal = AccountInfoDouble(ACCOUNT_BALANCE);
   if(bal > Peak()) GlobalVariableSet(GV("peak"), bal);
   if(halted) return false;
   if(maxLim > 0)
   {
      double ref = trailingDD ? Peak() : startBal;
      if(ref - eq >= (maxLim - 0.005) * startBal) { CloseAll("max-loss emergency line"); halted = true; GlobalVariableSet(GV("halt"), 1); return false; }
   }
   if(dailyLim > 0 && DayStart() - eq >= (dailyLim - 0.003) * startBal) { CloseAll("daily emergency line - flat until tomorrow"); return false; }
   return true;
}
// EDGE GATE: closed positions' net R from history (risk stored in the entry comment "r=<money>")
int EdgeMode()
{
   if(RiskMode != MODE_EDGE_GATE) return RiskMode;
   double ref = trailingDD ? Peak() : startBal, dd = (ref - AccountInfoDouble(ACCOUNT_EQUITY)) / startBal;
   if(dd >= 0.03) return MODE_CONSERVATIVE;
   HistorySelect(TimeCurrent() - 400 * 86400, TimeCurrent());
   double rs[]; ArrayResize(rs, 0);
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
   {
      ulong d = HistoryDealGetTicket(i);
      long mg = HistoryDealGetInteger(d, DEAL_MAGIC);
      if((mg != Magic && mg != Magic + 2) || HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;   // first units only
      string cm = HistoryDealGetString(d, DEAL_COMMENT); int p = StringFind(cm, "r="); if(p < 0) continue;
      double risk = StringToDouble(StringSubstr(cm, p + 2)); if(risk <= 0) continue;
      long pid = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      if(PositionSelectByTicket(pid)) continue;   // still open
      double prof = 0;
      for(int j = 0; j < n; j++) { ulong e = HistoryDealGetTicket(j); if(HistoryDealGetInteger(e, DEAL_POSITION_ID) == pid) prof += HistoryDealGetDouble(e, DEAL_PROFIT) + HistoryDealGetDouble(e, DEAL_SWAP) + HistoryDealGetDouble(e, DEAL_COMMISSION); }
      int k = ArraySize(rs); ArrayResize(rs, k + 1); rs[k] = prof / risk;
   }
   int k = ArraySize(rs);
   if(k < 20) return MODE_CONSERVATIVE;
   double s20 = 0, g20 = 0, l20 = 0, s40 = 0, g40 = 0, l40 = 0;
   for(int i = k - 1; i >= 0 && i >= k - 40; i--)
   {
      if(i >= k - 20) { s20 += rs[i]; if(rs[i] > 0) g20 += rs[i]; else l20 -= rs[i]; }
      s40 += rs[i]; if(rs[i] > 0) g40 += rs[i]; else l40 -= rs[i];
   }
   double pf20 = l20 > 0 ? g20 / l20 : 9.9, pf40 = l40 > 0 ? g40 / l40 : 9.9;
   if(k >= 40 && s40 >= 8 && pf40 >= 1.5 && dd <= 0.015) return MODE_AGGRESSIVE;   // STRONG_EDGE
   if(s20 >= 3 && pf20 >= 1.3 && dd <= 0.02) return MODE_NORMAL;                    // EDGE_CONFIRMED
   return MODE_CONSERVATIVE;
}
// size a new trade: mode risk, shrunk to half the remaining room near the limit
double SizeTrade(string s, double pct, double dist, double &riskMoney)
{
   riskMoney = startBal * pct;
   double room = Room();
   if(room < DBL_MAX && riskMoney > 0.5 * room) riskMoney = MathMax(0, 0.5 * room);
   return LotsFor(s, riskMoney, dist);
}

//--------------------------------------------------------------- position helpers
int Count(string s, long mg, int &dir, double &firstOpen, double &firstSL, datetime &firstT)
{
   int n = 0; dir = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != s || PositionGetInteger(POSITION_MAGIC) != mg) continue;
      n++; dir = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      firstOpen = PositionGetDouble(POSITION_PRICE_OPEN); firstSL = PositionGetDouble(POSITION_SL); firstT = (datetime)PositionGetInteger(POSITION_TIME);
   }
   return n;
}
void CloseMagic(string s, long mg)
{ for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL) == s && PositionGetInteger(POSITION_MAGIC) == mg) trade.PositionClose(tk); } }
void ModifySL(string s, long mg, double nsl, int d)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != s || PositionGetInteger(POSITION_MAGIC) != mg) continue;
      double sl = PositionGetDouble(POSITION_SL), px = d == 1 ? SymbolInfoDouble(s, SYMBOL_BID) : SymbolInfoDouble(s, SYMBOL_ASK);
      double want = d == 1 ? MathMax(sl, nsl) : (sl == 0 ? nsl : MathMin(sl, nsl));
      if(MathAbs(want - sl) > SymbolInfoDouble(s, SYMBOL_POINT) && (d == 1 ? want < px : want > px)) trade.PositionModify(tk, Norm(s, want), PositionGetDouble(POSITION_TP));
   }
}
bool HasOrder(string s, long mg)
{ for(int i = OrdersTotal() - 1; i >= 0; i--) { ulong tk = OrderGetTicket(i); if(OrderSelect(tk) && OrderGetString(ORDER_SYMBOL) == s && OrderGetInteger(ORDER_MAGIC) == mg) return true; } return false; }
void DeleteOrders(string s, long mg)
{ for(int i = OrdersTotal() - 1; i >= 0; i--) { ulong tk = OrderGetTicket(i); if(OrderSelect(tk) && OrderGetString(ORDER_SYMBOL) == s && OrderGetInteger(ORDER_MAGIC) == mg) trade.OrderDelete(tk); } }

//=============================================================== PLAN 1 (magic+0 first, +1 adds)
void Plan1NewDay(int k)
{
   string s = Sym[k]; long M0 = Magic, M1 = Magic + 1;
   int dd_; double fo, fs; datetime ft;
   if(Count(s, M0, dd_, fo, fs, ft) + Count(s, M1, dd_, fo, fs, ft) > 0) return;
   int dir = Bias(s, PERIOD_W1, 4); if(dir == 0 || dir != Bias(s, PERIOD_MN1, 6)) return;
   double N = ATRw(s, PERIOD_D1, 20, 1);
   bool brk = dir == 1 ? H(s, PERIOD_D1, 1) >= HH(s, PERIOD_D1, 2, BRK) : L(s, PERIOD_D1, 1) <= LL(s, PERIOD_D1, 2, BRK);
   if(!brk) return;
   int ext = dir == 1 ? iLowest(s, PERIOD_D1, MODE_LOW, BRK, 1) : iHighest(s, PERIOD_D1, MODE_HIGH, BRK, 1);
   double origin = dir == 1 ? L(s, PERIOD_D1, ext) : H(s, PERIOD_D1, ext), extreme = dir == 1 ? H(s, PERIOD_D1, 1) : L(s, PERIOD_D1, 1);
   double rng = MathAbs(extreme - origin);
   bool fvg = false;
   for(int j = ext - 2; j >= 1 && !fvg; j--) fvg = dir == 1 ? L(s, PERIOD_D1, j) > H(s, PERIOD_D1, j + 2) : H(s, PERIOD_D1, j) < L(s, PERIOD_D1, j + 2);
   if(!fvg || rng < 1.5 * N) return;
   double entry = extreme - dir * OTE * rng, sl = origin - dir * 0.25 * N, risk;
   double lots = SizeTrade(s, P1Risk(EdgeMode()), MathAbs(entry - sl), risk);
   if(lots <= 0) return;
   DeleteOrders(s, M0);
   GlobalVariableSet(GV(s + "_N"), N); GlobalVariableSet(GV(s + "_tp1"), extreme + dir * EXT1 * rng);
   GlobalVariableSet(GV(s + "_tp1done"), 0); GlobalVariableSet(GV(s + "_last"), entry); GlobalVariableSet(GV(s + "_risk"), MathAbs(entry - sl));
   trade.SetExpertMagicNumber(M0);
   string cm = "FP1 r=" + DoubleToString(lots * MathAbs(entry - sl) * MoneyPerPrice(s), 2);
   datetime exp = TimeCurrent() + 15 * 86400;
   if(dir == 1) trade.BuyLimit(lots, Norm(s, entry), s, Norm(s, sl), 0, ORDER_TIME_SPECIFIED, exp, cm);
   else         trade.SellLimit(lots, Norm(s, entry), s, Norm(s, sl), 0, ORDER_TIME_SPECIFIED, exp, cm);
}
void Plan1Manage(int k)
{
   string s = Sym[k]; long M0 = Magic, M1 = Magic + 1;
   int d, d2; double op, sl; datetime ot;
   int n0 = Count(s, M0, d, op, sl, ot); double o2, s2; datetime t2;
   int n1 = Count(s, M1, d2, o2, s2, t2);
   if(n0 == 0) { if(n1 > 0) CloseMagic(s, M1); return; }          // adds never outlive the first unit
   double N = GlobalVariableGet(GV(s + "_N")), r = GlobalVariableGet(GV(s + "_risk"));
   if(r <= 0) r = MathAbs(op - sl);
   int sh = iBarShift(s, PERIOD_D1, ot);
   double best = d == 1 ? HH(s, PERIOD_D1, 0, sh + 1) : LL(s, PERIOD_D1, 0, sh + 1);
   double mfe = r > 0 ? (best - op) * d / r : 0;
   if(sh >= 10 && mfe < 0.5) { CloseMagic(s, M0); CloseMagic(s, M1); return; }   // cut losers short
   double trail = 0;
   if(Plan1Exit == P1_CHANDELIER)
   {
      double ex = d == 1 ? HH(s, PERIOD_D1, 1, MathMax(sh, 1)) : LL(s, PERIOD_D1, 1, MathMax(sh, 1));
      trail = ex - d * 3 * N;
      if(mfe >= 1.0) ModifySL(s, M0, op, d);
   }
   else
   {
      double tp1 = GlobalVariableGet(GV(s + "_tp1"));
      double px = d == 1 ? SymbolInfoDouble(s, SYMBOL_BID) : SymbolInfoDouble(s, SYMBOL_ASK);
      if(GlobalVariableGet(GV(s + "_tp1done")) == 0 && (px - tp1) * d >= 0)
      {
         for(int i = PositionsTotal() - 1; i >= 0; i--)
         {
            ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
            if(PositionGetString(POSITION_SYMBOL) != s || PositionGetInteger(POSITION_MAGIC) != M0) continue;
            double st = SymbolInfoDouble(s, SYMBOL_VOLUME_STEP), half = MathFloor(PositionGetDouble(POSITION_VOLUME) / 2 / st) * st;
            if(half >= SymbolInfoDouble(s, SYMBOL_VOLUME_MIN)) trade.PositionClosePartial(tk, half);
         }
         GlobalVariableSet(GV(s + "_tp1done"), 1);
      }
      if(GlobalVariableGet(GV(s + "_tp1done")) > 0) { ModifySL(s, M0, op, d); trail = d == 1 ? LL(s, PERIOD_D1, 1, 55) : HH(s, PERIOD_D1, 1, 55); }
   }
   if(trail > 0) { ModifySL(s, M0, trail, d); ModifySL(s, M1, trail, d); }
   // Turtle adds: +1 unit every 0.5N, max 4 units, 2N stop
   double last = GlobalVariableGet(GV(s + "_last")), nxt = last + d * 0.5 * N;
   double px = d == 1 ? SymbolInfoDouble(s, SYMBOL_ASK) : SymbolInfoDouble(s, SYMBOL_BID);
   if(n0 + n1 < 4 && N > 0 && (px - nxt) * d >= 0)
   {
      double risk, lots = SizeTrade(s, P1Risk(EdgeMode()), 2 * N, risk);
      if(lots > 0)
      {
         trade.SetExpertMagicNumber(M1);
         bool ok = d == 1 ? trade.Buy(lots, s, 0, Norm(s, px - 2 * N), 0, "FP1+") : trade.Sell(lots, s, 0, Norm(s, px + 2 * N), 0, "FP1+");
         if(ok) GlobalVariableSet(GV(s + "_last"), nxt);
      }
   }
}

//=============================================================== PLAN 3 (magic+2 first, +3 adds)
bool InKillZone(int h) { for(int i = 0; i < ArraySize(KZ); i++) if((int)KZ[i] == h) return true; return false; }
void Plan3NewHour(int k)
{
   string s = Sym[k]; long M2 = Magic + 2, M3 = Magic + 3;
   int ny = NYHour(); int barHour = (ny + 23) % 24;   // the bar that just closed started one hour ago
   if(barHour == 12 || barHour == 13) return;           // no NY lunch
   if(KillZonesOnly && !InKillZone(barHour)) return;
   int dir = Bias(s, PERIOD_W1, 4); if(dir == 0) return;
   int d0, d1; double fo, fs, ao, as_; datetime ft, at;
   int n2 = Count(s, M2, d0, fo, fs, ft), n3 = Count(s, M3, d1, ao, as_, at);
   if(n2 > 0)
   {
      if(d0 != dir || n2 + n3 >= 5) return;
      double r1 = GlobalVariableGet(GV(s + "_p3r")); if(r1 <= 0) return;
      double px = dir == 1 ? SymbolInfoDouble(s, SYMBOL_BID) : SymbolInfoDouble(s, SYMBOL_ASK);
      if((px - fo) * dir / r1 < 1.0) return;              // the open trade is the threshold: adds only at >= +1R
   }
   double o = O(s, PERIOD_H1, 1), h = H(s, PERIOD_H1, 1), l = L(s, PERIOD_H1, 1), c = C(s, PERIOD_H1, 1);
   double fr[] = {0, 0.2, 0.5, 0.6, 0.8};
   double u = LevelUnit(Fam[k]), base = MathFloor(c / u) * u;
   bool hit = false; double lvl = 0;
   for(int b = -1; b <= 1; b++) for(int j = 0; j < 5; j++)
   {
      double Lv = base + b * u + fr[j] * u;
      if(dir == 1 && l <= Lv && o > Lv && c > Lv && Lv > lvl) { hit = true; lvl = Lv; }
      if(dir == -1 && h >= Lv && o < Lv && c < Lv && (lvl == 0 || Lv < lvl)) { hit = true; lvl = Lv; }
   }
   if(!hit) return;
   double datr = ATRw(s, PERIOD_D1, 14, 1);
   double px = dir == 1 ? SymbolInfoDouble(s, SYMBOL_ASK) : SymbolInfoDouble(s, SYMBOL_BID);
   double sl = px - dir * datr, spread = SymbolInfoDouble(s, SYMBOL_ASK) - SymbolInfoDouble(s, SYMBOL_BID);
   if(datr < 3 * spread) return;
   if(n2 > 0) sl = dir == 1 ? MathMax(sl, fo) : MathMin(sl, fo);   // adds' stops at least at the first entry
   double risk, lots = SizeTrade(s, P3Risk(EdgeMode()), MathAbs(px - sl), risk);
   if(lots <= 0) return;
   long mg = n2 > 0 ? M3 : M2;
   trade.SetExpertMagicNumber(mg);
   string cm = "FP3 r=" + DoubleToString(lots * datr * MoneyPerPrice(s), 2);
   bool ok = dir == 1 ? trade.Buy(lots, s, 0, Norm(s, sl), 0, cm) : trade.Sell(lots, s, 0, Norm(s, sl), 0, cm);
   if(ok && n2 == 0) GlobalVariableSet(GV(s + "_p3r"), datr);
   if(ok && n2 > 0) ModifySL(s, M2, fo, dir);
}
void Plan3Manage(int k)
{
   string s = Sym[k]; long M2 = Magic + 2, M3 = Magic + 3;
   int d, d2; double op, sl, o2, s2; datetime ot, t2;
   int n2 = Count(s, M2, d, op, sl, ot), n3 = Count(s, M3, d2, o2, s2, t2);
   if(n2 == 0) { if(n3 > 0) CloseMagic(s, M3); return; }
   double r = GlobalVariableGet(GV(s + "_p3r")); if(r <= 0) r = MathAbs(op - sl);
   int sh = iBarShift(s, PERIOD_H1, ot);
   double best = d == 1 ? HH(s, PERIOD_H1, 0, sh + 1) : LL(s, PERIOD_H1, 0, sh + 1);
   double mfe = r > 0 ? (best - op) * d / r : 0;
   if(sh >= 120 && mfe < 0.5) { CloseMagic(s, M2); CloseMagic(s, M3); return; }   // cut losers short
   if(mfe >= 1.0) { ModifySL(s, M2, op, d); ModifySL(s, M3, op, d); }             // breakeven
   if(mfe >= 2.0)                                                                 // let winners run: 5-day low
   {
      double tr = d == 1 ? LL(s, PERIOD_D1, 1, 5) : HH(s, PERIOD_D1, 1, 5);
      ModifySL(s, M2, tr, d); ModifySL(s, M3, tr, d);
   }
}

//=============================================================== loop + panel
void OnTimer()
{
   bool ok = Guard();
   for(int k = 0; k < NS; k++)
   {
      if(UsePlan1) Plan1Manage(k);
      if(UsePlan3) Plan3Manage(k);
      if(!ok) continue;
      datetime d1 = iTime(Sym[k], PERIOD_D1, 0), h1 = iTime(Sym[k], PERIOD_H1, 0);
      if(d1 != lastD1[k]) { lastD1[k] = d1; if(UsePlan1) Plan1NewDay(k); }
      if(h1 != lastH1[k]) { lastH1[k] = h1; if(UsePlan3 && lastH1[k] != 0) Plan3NewHour(k); }
   }
   if(ShowPanel) Panel();
}
void OnTick() {}

void Panel()
{
   int m = EdgeMode();
   string mn = m == 0 ? "Conservative" : m == 1 ? "Normal" : "Aggressive";
   double room = Room();
   string t = StringFormat("FibFVG Pro | preset %s | mode %s%s\nstart %.2f  equity %.2f  peak %.2f\nopen stop-risk %.2f  room to bot line %s%s\n",
      Preset == 0 ? "FundedNext Instant" : Preset == 1 ? "Instant Premium" : Preset == 2 ? "Personal" : "Custom",
      mn, RiskMode == MODE_EDGE_GATE ? " (edge gate)" : "", startBal, AccountInfoDouble(ACCOUNT_EQUITY), Peak(), OpenRisk(),
      room == DBL_MAX ? "no limit" : DoubleToString(room, 2), halted ? "\nHALTED by guard" : "");
   t += "symbol      | P1 lots (rec) | P3 lots (rec) | open lots\n";
   for(int k = 0; k < NS; k++)
   {
      string s = Sym[k]; double r1, r3;
      double N = ATRw(s, PERIOD_D1, 20, 1), datr = ATRw(s, PERIOD_D1, 14, 1);
      double l1 = SizeTrade(s, P1Risk(m), 1.2 * N, r1), l3 = SizeTrade(s, P3Risk(m), datr, r3);
      double open = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL) == s && PositionGetInteger(POSITION_MAGIC) >= Magic && PositionGetInteger(POSITION_MAGIC) <= Magic + 9) open += PositionGetDouble(POSITION_VOLUME); }
      t += StringFormat("%-11s | %s | %s | %.2f\n", s, l1 > 0 ? DoubleToString(l1, 2) : "below min", l3 > 0 ? DoubleToString(l3, 2) : "below min", open);
   }
   Comment(t);
}
//+------------------------------------------------------------------+

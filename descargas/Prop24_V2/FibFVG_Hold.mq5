//+------------------------------------------------------------------+
//|                                                FibFVG_Hold.mq5    |
//|  Cueto & Co. - Wallet 2 bot (Cueto & Co. real funds).            |
//|  Drop on ONE chart. Trades gold and silver from it.              |
//|                                                                  |
//|  Direction : monthly + weekly ranges agree.                      |
//|  Setup     : daily 20-day breakout leg >= 1.5 N with a fair      |
//|              value gap; limit at the 0.705 Fibonacci level (live |
//|              15 days); stop 0.25 N beyond the leg origin.        |
//|  Adds      : one more unit every 0.5 N in profit (max 4 units),  |
//|              each with a 2 N stop; adds close with the first.    |
//|  Exit      : YEAR mode (default) - breakeven at +1R, then trail  |
//|              the 120-day low/high: holds can last months to a    |
//|              year or more.  CHANDELIER mode - breakeven at +1R,  |
//|              trail 3 N from the best price, out after 10 days if |
//|              never +0.5R (holds days to weeks).                  |
//|  Hard stop : if the bot's equity falls HardStopPct below its     |
//|              peak, everything closes and the bot halts.          |
//|  Score     : its OWN virtual account by magic number, so it can  |
//|              share a demo account with the Prop24 bot.           |
//|  Log       : MQL5\Files\FibFVG_Hold_<account>.csv                |
//+------------------------------------------------------------------+
#property copyright "Cueto & Co."
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

enum ENUM_EXIT { EXIT_YEAR = 0,        // Year holds: trail the 120-day low (best over 2006-2026)
                 EXIT_CHANDELIER = 1 };// Days-weeks: chandelier 3N + 10-day time stop (bot v3)

input string    RiskProfile    = "Normal";    // label in the log: Normal (Exness) or Aggressive (Vantage)
input double    RiskPctPerUnit = 0.5;         // % of the bot's balance per unit: Normal 0.5, Aggressive 1.0
input double    StartBalance   = 50000;       // the virtual account (plan: 20% of Wallet 2 once it holds $250K)
input ENUM_EXIT ExitMode       = EXIT_YEAR;
input int       MaxUnits       = 4;
input double    HardStopPct    = 30;          // halt if equity falls this % below its peak
input double    MaxLossPct     = 0;           // prop max loss (0 = none). FundedNext 2-Step: 10, Lite: 8, 1-Step: 6
input bool      TrailingMaxLoss = false;      // false = static (2-Step, Lite, 1-Step); true = trailing, locked at the start balance (Instant)
input double    DailyLossPct   = 0;           // prop daily loss (0 = none). FundedNext 2-Step: 5, Lite: 4, 1-Step: 3
input double    GuardBufferPct = 1;           // bot line = MaxLoss - buffer; trades shrink near it
input bool      SizeOnStartBalance = false;   // true on prop accounts (risk on the start balance, as the backtest)
input int       KeepAliveDays  = 50;          // FundedNext 60-day inactivity rule: tiny open/close trade after this many idle days (0 = off)
input bool      AllFiveMarkets = false;       // true = also BTC, S&P 500, Nasdaq 100 (static-limit prop: 44% wins, RR 3.6 in 2024-26)
input string    SymbolsToTrade = "AUTO";      // AUTO or your broker's names, e.g. XAUUSDm,XAGUSDm
input bool      WriteLog       = true;
input bool      ShowPanel      = true;
input bool      ResetHalt      = false;       // set true once to clear a halt after review
input long      Magic          = 7712500;     // first unit = Magic, adds = Magic + 1

#define MAXS 6
const string BOT = "Hold";
const double OTE = 0.705;
const int    BRK = 20;

string   Sym[MAXS]; int Fam[MAXS]; int NS = 0;        // family 0 gold, 1 silver, 2 BTC, 3 S&P 500, 4 Nasdaq 100
datetime lastD1[MAXS];
double   startBal = 0, closedPnL = 0;
datetime t0 = 0;
bool     halted = false;
int      lastDayKey = 0;

string GV(string k) { return "FFH_" + IntegerToString(Magic) + "_" + k; }
bool   Ours(long mg) { return mg == Magic || mg == Magic + 1 || mg == Magic + 9; }
string UnitName(long mg) { return mg == Magic ? "first" : mg == Magic + 9 ? "keep-alive" : "add"; }

//=============================================================== market data helpers
double H(string s, ENUM_TIMEFRAMES tf, int i) { return iHigh(s, tf, i); }
double L(string s, ENUM_TIMEFRAMES tf, int i) { return iLow(s, tf, i); }
double C(string s, ENUM_TIMEFRAMES tf, int i) { return iClose(s, tf, i); }
double HH(string s, ENUM_TIMEFRAMES tf, int from, int n) { int i = iHighest(s, tf, MODE_HIGH, n, from); return i < 0 ? 0 : H(s, tf, i); }
double LL(string s, ENUM_TIMEFRAMES tf, int from, int n) { int i = iLowest(s, tf, MODE_LOW, n, from); return i < 0 ? 0 : L(s, tf, i); }
double ATRw(string s, ENUM_TIMEFRAMES tf, int len, int shift)
{
   double a = 0; bool init = false;
   for(int k = shift + len * 5; k >= shift; k--)
   {
      double c1 = C(s, tf, k + 1); if(c1 <= 0) continue;
      double tr = MathMax(H(s, tf, k), c1) - MathMin(L(s, tf, k), c1);
      if(!init) { a = tr; init = true; } else a += (tr - a) / len;
   }
   return a;
}
int Bias(string s, ENUM_TIMEFRAMES tf, int look)
{
   double hi = HH(s, tf, 1, look), lo = LL(s, tf, 1, look), c = C(s, tf, 1);
   if(hi <= 0 || lo <= 0 || c <= 0) return 0;
   double mid = (hi + lo) / 2;
   return c > mid ? 1 : c < mid ? -1 : 0;
}
double Norm(string s, double p) { return NormalizeDouble(p, (int)SymbolInfoInteger(s, SYMBOL_DIGITS)); }
int    Dg(string s) { return (int)SymbolInfoInteger(s, SYMBOL_DIGITS); }
double MoneyPerPrice(string s)
{
   double tv = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE_LOSS), ts = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0) tv = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE);
   return ts > 0 ? tv / ts : 0;
}
double LotsFor(string s, double riskMoney, double dist)
{
   double mpp = MoneyPerPrice(s), step = SymbolInfoDouble(s, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(s, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(s, SYMBOL_VOLUME_MAX);
   if(mpp <= 0 || dist <= 0 || step <= 0 || riskMoney <= 0) return 0;
   double lots = MathFloor(riskMoney / (dist * mpp) / step) * step;
   if(lots < vmin) return 0;
   return NormalizeDouble(MathMin(lots, vmax), 2);
}
bool MarketOpen(string s)
{
   if(!TerminalInfoInteger(TERMINAL_CONNECTED) || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return false;
   long mode = SymbolInfoInteger(s, SYMBOL_TRADE_MODE);
   if(mode == SYMBOL_TRADE_MODE_DISABLED || mode == SYMBOL_TRADE_MODE_CLOSEONLY) return false;
   datetime now = TimeTradeServer();
   if(now - (datetime)SymbolInfoInteger(s, SYMBOL_TIME) > 600) return false;
   MqlDateTime t; TimeToStruct(now, t);
   int sec = t.hour * 3600 + t.min * 60 + t.sec;
   datetime from, to;
   for(int i = 0; i < 10; i++)
   {
      if(!SymbolInfoSessionTrade(s, (ENUM_DAY_OF_WEEK)t.day_of_week, i, from, to)) break;
      int f = (int)((long)from % 86400), e = (int)((long)to % 86400);
      if(e == 0) e = 86400;
      if(sec >= f && sec < e) return true;
   }
   return false;
}

//=============================================================== symbols
bool Match(string name, string pat) { string u = name; StringToUpper(u); return StringFind(u, pat) == 0; }
int FamilyOf(string n)
{
   if(Match(n, "XAUUSD")) return 0;
   if(Match(n, "XAGUSD")) return 1;
   if(!AllFiveMarkets) return -1;
   if(Match(n, "BTCUSD")) return 2;
   string p3[] = {"US500", "SPX500", "SP500", "USA500", "US.500"};
   string p4[] = {"NAS100", "USTEC", "US100", "NDX100", "USTECH"};
   for(int i = 0; i < ArraySize(p3); i++) if(Match(n, p3[i])) return 3;
   for(int i = 0; i < ArraySize(p4); i++) if(Match(n, p4[i])) return 4;
   return -1;
}
void AddSym(string n)
{
   int f = FamilyOf(n); if(f < 0 || NS >= MAXS) return;
   for(int i = 0; i < NS; i++) if(Fam[i] == f) return;
   if(!SymbolSelect(n, true)) return;
   if(SymbolInfoInteger(n, SYMBOL_TRADE_MODE) == SYMBOL_TRADE_MODE_DISABLED) return;
   Sym[NS] = n; Fam[NS] = f; lastD1[NS] = 0; NS++;
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
   for(int i = 0; i < SymbolsTotal(true) && NS < (AllFiveMarkets ? 5 : 2); i++) AddSym(SymbolName(i, true));
   for(int i = 0; i < SymbolsTotal(false) && NS < (AllFiveMarkets ? 5 : 2); i++) AddSym(SymbolName(i, false));
}

//=============================================================== the bot's own (virtual) account
void CalcClosed()
{
   if(!HistorySelect(t0, TimeCurrent() + 86400)) return;
   double s = 0;
   for(int i = 0; i < HistoryDealsTotal(); i++)
   {
      ulong d = HistoryDealGetTicket(i);
      if(!Ours(HistoryDealGetInteger(d, DEAL_MAGIC))) continue;
      s += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
   }
   closedPnL = s;
}
double Floating()
{
   double s = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      if(!Ours(PositionGetInteger(POSITION_MAGIC))) continue;
      s += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }
   return s;
}
double VBal() { return startBal + closedPnL; }
double VEq()  { return VBal() + Floating(); }
double Peak() { return GlobalVariableCheck(GV("peak")) ? GlobalVariableGet(GV("peak")) : startBal; }
double DDpct() { double p = Peak(); return p > 0 ? (p - VEq()) / p * 100 : 0; }
double OpenRisk()
{
   double tot = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      if(!Ours(PositionGetInteger(POSITION_MAGIC))) continue;
      string s = PositionGetString(POSITION_SYMBOL);
      double sl = PositionGetDouble(POSITION_SL), op = PositionGetDouble(POSITION_PRICE_OPEN);
      if(sl <= 0) continue;
      int d = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      double dist = (op - sl) * d; if(dist <= 0) continue;
      tot += dist * MoneyPerPrice(s) * PositionGetDouble(POSITION_VOLUME);
   }
   return tot;
}

//=============================================================== log
string LogName() { return "FibFVG_" + BOT + "_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".csv"; }
void Log(string ev, string s, string detail)
{
   if(!WriteLog) return;
   int h = FileOpen(LogName(), FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
   if(h == INVALID_HANDLE) return;
   bool fresh = FileSize(h) == 0;
   FileSeek(h, 0, SEEK_END);
   string broker = AccountInfoString(ACCOUNT_COMPANY); StringReplace(broker, ",", " ");
   StringReplace(detail, ",", ";");
   if(fresh) FileWrite(h, "server_time", "utc_time", "bot", "profile", "broker", "account", "event", "symbol", "detail",
                       "v_balance", "v_equity", "v_peak", "drawdown_pct", "open_risk");
   FileWrite(h, TimeToString(TimeTradeServer(), TIME_DATE | TIME_SECONDS), TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS), BOT, RiskProfile,
             broker, IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)), ev, s, detail, DoubleToString(VBal(), 2), DoubleToString(VEq(), 2),
             DoubleToString(Peak(), 2), DoubleToString(DDpct(), 2), DoubleToString(OpenRisk(), 2));
   FileClose(h);
}
string Stats()
{
   double n = GlobalVariableGet(GV("n")), w = GlobalVariableGet(GV("w")), sr = GlobalVariableGet(GV("sr")), sw = GlobalVariableGet(GV("sw")), sl = GlobalVariableGet(GV("sl"));
   double aw = w > 0 ? sw / w : 0, al = n - w > 0 ? sl / (n - w) : 0;
   return StringFormat("closed_units=%.0f; win_rate=%.1f%%; avg_win_R=%.2f; avg_loss_R=%.2f; RR=%.2f; avg_R=%.3f",
                       n, n > 0 ? w / n * 100 : 0, aw, al, al < 0 ? aw / -al : 0, n > 0 ? sr / n : 0);
}

//=============================================================== position helpers
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
void CloseMagic(string s, long mg, int code)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk) || PositionGetString(POSITION_SYMBOL) != s || PositionGetInteger(POSITION_MAGIC) != mg) continue;
      GlobalVariableSet(GV("why_" + IntegerToString(PositionGetInteger(POSITION_IDENTIFIER))), code);
      if(!trade.PositionClose(tk)) Log("ERROR", s, StringFormat("close failed: %d", trade.ResultRetcode()));
   }
}
void ModifySL(string s, long mg, double nsl, int d, string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != s || PositionGetInteger(POSITION_MAGIC) != mg) continue;
      double sl = PositionGetDouble(POSITION_SL), px = d == 1 ? SymbolInfoDouble(s, SYMBOL_BID) : SymbolInfoDouble(s, SYMBOL_ASK);
      double want = d == 1 ? MathMax(sl, nsl) : (sl == 0 ? nsl : MathMin(sl, nsl));
      double gap = SymbolInfoInteger(s, SYMBOL_TRADE_STOPS_LEVEL) * SymbolInfoDouble(s, SYMBOL_POINT);
      if(MathAbs(want - sl) > SymbolInfoDouble(s, SYMBOL_POINT) && (d == 1 ? want < px - gap : want > px + gap))
         if(trade.PositionModify(tk, Norm(s, want), PositionGetDouble(POSITION_TP)))
            Log("STOP", s, StringFormat("unit=%s; stop %s -> %s; reason=%s", UnitName(mg), DoubleToString(sl, Dg(s)), DoubleToString(want, Dg(s)), why));
   }
}
void DeleteOrders(string s, long mg, string why)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(OrderSelect(tk) && OrderGetString(ORDER_SYMBOL) == s && OrderGetInteger(ORDER_MAGIC) == mg)
         if(trade.OrderDelete(tk)) Log("CANCEL", s, StringFormat("order=%I64u; reason=%s", tk, why));
   }
}

//=============================================================== hard stop and prop limits
double BPeak() { return GlobalVariableCheck(GV("bpeak")) ? GlobalVariableGet(GV("bpeak")) : startBal; }
double DayStart() { return GlobalVariableCheck(GV("day")) ? GlobalVariableGet(GV("day")) : VEq(); }
// the firm's loss line: static = start - MaxLoss; trailing = balance peak - MaxLoss, never above the start balance
double Floor() { double f = startBal - MaxLossPct / 100.0 * startBal; if(TrailingMaxLoss) f = MathMin(BPeak() - MaxLossPct / 100.0 * startBal, startBal); return f; }
double Room()
{
   double room = DBL_MAX;
   if(MaxLossPct > 0) room = VEq() - Floor() - GuardBufferPct / 100.0 * startBal - OpenRisk();
   if(DailyLossPct > 0) room = MathMin(room, VEq() - (DayStart() - DailyLossPct / 100.0 * startBal) - 0.5 / 100.0 * startBal - OpenRisk());
   return room;
}
double UnitRisk()
{
   double base = SizeOnStartBalance ? startBal : VBal(), r = base * RiskPctPerUnit / 100.0, room = Room();
   if(room < DBL_MAX && r > 0.5 * room) r = MathMax(0, 0.5 * room);     // shrink near the firm's line
   return r;
}
void CloseEverything(int code, string why)
{
   for(int k = 0; k < NS; k++) { CloseMagic(Sym[k], Magic + 1, code); CloseMagic(Sym[k], Magic, code); CloseMagic(Sym[k], Magic + 9, code); DeleteOrders(Sym[k], Magic, why); }
}
bool Guard()
{
   CalcClosed();
   if(VEq() > Peak()) GlobalVariableSet(GV("peak"), VEq());
   if(VBal() > BPeak()) GlobalVariableSet(GV("bpeak"), VBal());
   MqlDateTime t; TimeToStruct(TimeTradeServer(), t);
   int key = t.year * 1000 + t.day_of_year;
   if(key != lastDayKey) { if(lastDayKey != 0) Log("DAY", "", Stats()); lastDayKey = key; GlobalVariableSet(GV("day"), VEq()); }
   if(halted) return false;
   if(MaxLossPct > 0 && VEq() - Floor() <= 0.5 / 100.0 * startBal)
   {
      CloseEverything(4, "max-loss emergency line"); halted = true; GlobalVariableSet(GV("halt"), 1);
      Log("HALT", "", StringFormat("equity %.2f is 0.5%% from the firm's line %.2f", VEq(), Floor())); return false;
   }
   if(DailyLossPct > 0 && DayStart() - VEq() >= (DailyLossPct - 0.3) / 100.0 * startBal)
   {
      if((int)GlobalVariableGet(GV("dayhalt")) != key) { CloseEverything(7, "daily emergency line"); GlobalVariableSet(GV("dayhalt"), key); Log("DAYSTOP", "", "daily loss line close: flat until tomorrow"); }
      return false;
   }
   if((int)GlobalVariableGet(GV("dayhalt")) == key) return false;
   if(DDpct() >= HardStopPct)
   {
      CloseEverything(5, "hard stop");
      halted = true; GlobalVariableSet(GV("halt"), 1);
      Log("HALT", "", StringFormat("equity %.2f%% below its peak - hard stop", DDpct()));
      return false;
   }
   return true;
}
// FundedNext deactivates an account after 60 days without a trade: open and close the smallest position
void KeepAlive()
{
   if(KeepAliveDays <= 0 || NS == 0) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionSelectByTicket(tk) && PositionGetInteger(POSITION_MAGIC) == Magic + 9 && TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) >= 60)
      { GlobalVariableSet(GV("why_" + IntegerToString(PositionGetInteger(POSITION_IDENTIFIER))), 8); trade.PositionClose(tk); }
   }
   if(TimeCurrent() - (datetime)GlobalVariableGet(GV("last_open")) < KeepAliveDays * 86400) return;
   for(int k = 0; k < NS; k++)
   {
      string s = Sym[k]; if(!MarketOpen(s)) continue;
      trade.SetExpertMagicNumber(Magic + 9); trade.SetTypeFillingBySymbol(s);
      if(trade.Buy(SymbolInfoDouble(s, SYMBOL_VOLUME_MIN), s, 0, 0, 0, "keep-alive"))
      { GlobalVariableSet(GV("last_open"), (double)TimeCurrent()); Log("KEEPALIVE", s, StringFormat("no trade for %d days: minimum position opened, closed after 1 minute", KeepAliveDays)); }
      return;
   }
}

//=============================================================== setup and management
void NewDay(int k)
{
   string s = Sym[k];
   int d_; double fo, fs; datetime ft;
   if(Count(s, Magic, d_, fo, fs, ft) + Count(s, Magic + 1, d_, fo, fs, ft) > 0) return;   // one position per market
   // pending order expiry (15 days) and gap through the stop
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i); if(!OrderSelect(tk) || OrderGetString(ORDER_SYMBOL) != s || OrderGetInteger(ORDER_MAGIC) != Magic) continue;
      if(TimeTradeServer() >= (datetime)GlobalVariableGet(GV("exp_" + s)) && trade.OrderDelete(tk)) Log("CANCEL", s, "reason=expired after 15 days");
   }
   int dir = Bias(s, PERIOD_W1, 4); if(dir == 0 || dir != Bias(s, PERIOD_MN1, 6)) return;
   double N = ATRw(s, PERIOD_D1, 20, 2); if(N <= 0) return;
   bool brk = dir == 1 ? H(s, PERIOD_D1, 1) >= HH(s, PERIOD_D1, 2, BRK) : L(s, PERIOD_D1, 1) <= LL(s, PERIOD_D1, 2, BRK);
   if(!brk) return;
   int ext = dir == 1 ? iLowest(s, PERIOD_D1, MODE_LOW, BRK, 1) : iHighest(s, PERIOD_D1, MODE_HIGH, BRK, 1);
   if(ext < 1) return;
   double origin = dir == 1 ? L(s, PERIOD_D1, ext) : H(s, PERIOD_D1, ext), extreme = dir == 1 ? H(s, PERIOD_D1, 1) : L(s, PERIOD_D1, 1);
   double rng = MathAbs(extreme - origin);
   bool fvg = false;
   for(int j = ext - 2; j >= 1 && !fvg; j--) fvg = dir == 1 ? L(s, PERIOD_D1, j) > H(s, PERIOD_D1, j + 2) : H(s, PERIOD_D1, j) < L(s, PERIOD_D1, j + 2);
   if(!fvg || rng < 1.5 * N) return;
   double entry = extreme - dir * OTE * rng, sl = origin - dir * 0.25 * N, dist = MathAbs(entry - sl);
   double ask = SymbolInfoDouble(s, SYMBOL_ASK), bid = SymbolInfoDouble(s, SYMBOL_BID), px = dir == 1 ? ask : bid;
   if((px - sl) * dir <= 0) return;
   double lots = LotsFor(s, UnitRisk(), dist);
   if(lots <= 0) { Log("SKIP", s, StringFormat("dir=%d; reason=lot below minimum or no room for %.2f risk", dir, UnitRisk())); return; }
   DeleteOrders(s, Magic, "replaced by a newer setup");
   GlobalVariableSet(GV(s + "_N"), N); GlobalVariableSet(GV(s + "_last"), entry); GlobalVariableSet(GV(s + "_risk"), dist);
   trade.SetExpertMagicNumber(Magic);
   trade.SetTypeFillingBySymbol(s);
   string cm = StringFormat("HOLD r=%.0f", lots * dist * MoneyPerPrice(s));
   bool ok; string how;
   if((px - entry) * dir <= 0)
   {
      ok = dir == 1 ? trade.Buy(lots, s, 0, Norm(s, sl), 0, cm) : trade.Sell(lots, s, 0, Norm(s, sl), 0, cm);
      how = "market";
   }
   else
   {
      ok = dir == 1 ? trade.BuyLimit(lots, Norm(s, entry), s, Norm(s, sl), 0, ORDER_TIME_GTC, 0, cm)
                    : trade.SellLimit(lots, Norm(s, entry), s, Norm(s, sl), 0, ORDER_TIME_GTC, 0, cm);
      how = "limit";
      if(ok) GlobalVariableSet(GV("exp_" + s), (double)(TimeTradeServer() + 15 * 86400));
   }
   if(ok) Log("ORDER", s, StringFormat("type=%s; dir=%s; entry=%s; sl=%s; lots=%.2f; risk_usd=%.2f; N=%s; leg=%s-%s; exit=%s", how,
                                       dir == 1 ? "buy" : "sell", DoubleToString(entry, Dg(s)), DoubleToString(sl, Dg(s)), lots,
                                       lots * dist * MoneyPerPrice(s), DoubleToString(N, Dg(s)), DoubleToString(origin, Dg(s)),
                                       DoubleToString(extreme, Dg(s)), ExitMode == EXIT_YEAR ? "year" : "chandelier"));
   else Log("ERROR", s, StringFormat("order rejected: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()));
}
void Manage(int k)
{
   string s = Sym[k]; long M0 = Magic, M1 = Magic + 1;
   int d, d2; double op, sl, o2, s2; datetime ot, t2;
   int n0 = Count(s, M0, d, op, sl, ot), n1 = Count(s, M1, d2, o2, s2, t2);
   // pending order: cancel if price went through its stop
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i); if(!OrderSelect(tk) || OrderGetString(ORDER_SYMBOL) != s || OrderGetInteger(ORDER_MAGIC) != M0) continue;
      bool buy = OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_LIMIT; double osl = OrderGetDouble(ORDER_SL);
      double px = buy ? SymbolInfoDouble(s, SYMBOL_BID) : SymbolInfoDouble(s, SYMBOL_ASK);
      if(osl > 0 && (buy ? px <= osl : px >= osl) && trade.OrderDelete(tk)) Log("CANCEL", s, "reason=price went through the stop");
   }
   if(n0 == 0) { if(n1 > 0) CloseMagic(s, M1, 6); return; }               // adds never outlive the first unit
   double N = GlobalVariableGet(GV(s + "_N")), r = GlobalVariableGet(GV(s + "_risk"));
   if(r <= 0) r = MathAbs(op - sl);
   int sh = iBarShift(s, PERIOD_D1, ot);
   double best = d == 1 ? HH(s, PERIOD_D1, 0, sh + 1) : LL(s, PERIOD_D1, 0, sh + 1);
   double mfe = r > 0 ? (best - op) * d / r : 0;
   if(ExitMode == EXIT_CHANDELIER && sh >= 10 && mfe < 0.5) { CloseMagic(s, M1, 3); CloseMagic(s, M0, 3); return; }
   if(mfe >= 1.0) ModifySL(s, M0, op, d, "breakeven at +1R");
   double trail = 0;
   if(ExitMode == EXIT_CHANDELIER)
   {
      if(sh >= 1) { double ex = d == 1 ? HH(s, PERIOD_D1, 1, sh) : LL(s, PERIOD_D1, 1, sh); trail = ex - d * 3 * N; }
   }
   else trail = d == 1 ? LL(s, PERIOD_D1, 1, 120) : HH(s, PERIOD_D1, 1, 120);
   if(trail > 0) { ModifySL(s, M0, trail, d, ExitMode == EXIT_YEAR ? "120-day trail" : "chandelier 3N"); ModifySL(s, M1, trail, d, ExitMode == EXIT_YEAR ? "120-day trail" : "chandelier 3N"); }
   // adds: one unit every 0.5 N in profit
   double last = GlobalVariableGet(GV(s + "_last")), nxt = last + d * 0.5 * N;
   double px = d == 1 ? SymbolInfoDouble(s, SYMBOL_ASK) : SymbolInfoDouble(s, SYMBOL_BID);
   if(n0 + n1 < MaxUnits && N > 0 && (px - nxt) * d >= 0)
   {
      double lots = LotsFor(s, UnitRisk(), 2 * N);
      if(lots > 0)
      {
         trade.SetExpertMagicNumber(M1);
         trade.SetTypeFillingBySymbol(s);
         bool ok = d == 1 ? trade.Buy(lots, s, 0, Norm(s, px - 2 * N), 0, "HOLD+") : trade.Sell(lots, s, 0, Norm(s, px + 2 * N), 0, "HOLD+");
         if(ok) GlobalVariableSet(GV(s + "_last"), nxt);
         else Log("ERROR", s, StringFormat("add rejected: %d", trade.ResultRetcode()));
      }
      else GlobalVariableSet(GV(s + "_last"), nxt);                         // too small: skip this step
   }
}

//=============================================================== events
int OnInit()
{
   startBal = StartBalance > 0 ? StartBalance : AccountInfoDouble(ACCOUNT_BALANCE);
   if(!GlobalVariableCheck(GV("t0"))) GlobalVariableSet(GV("t0"), (double)TimeCurrent());
   t0 = (datetime)GlobalVariableGet(GV("t0"));
   if(ResetHalt) GlobalVariableSet(GV("halt"), 0);
   halted = GlobalVariableCheck(GV("halt")) && GlobalVariableGet(GV("halt")) > 0;
   ResolveSymbols();
   trade.SetDeviationInPoints(100);
   CalcClosed();
   if(!GlobalVariableCheck(GV("peak"))) GlobalVariableSet(GV("peak"), startBal);
   if(!GlobalVariableCheck(GV("last_open"))) GlobalVariableSet(GV("last_open"), (double)TimeCurrent());
   EventSetTimer(5);
   string list = ""; for(int k = 0; k < NS; k++) list += (k ? " " : "") + Sym[k];
   Log("START", "", StringFormat("profile=%s; risk_per_unit=%.2f%%; start=%.0f; exit=%s; hard_stop=%.0f%%; symbols=%s", RiskProfile, RiskPctPerUnit, startBal,
                                 ExitMode == EXIT_YEAR ? "year" : "chandelier", HardStopPct, list));
   if(NS < (AllFiveMarkets ? 5 : 2)) Print("FibFVG Hold: only ", NS, " markets found. Set SymbolsToTrade to your broker's names.");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { EventKillTimer(); Comment(""); Log("STOP", "", StringFormat("reason=%d; %s", r, Stats())); }
void OnTick() {}
void OnTimer()
{
   bool ok = Guard();
   KeepAlive();
   for(int k = 0; k < NS; k++)
   {
      if(!MarketOpen(Sym[k])) continue;
      Manage(k);
      if(!ok) continue;
      datetime d1 = iTime(Sym[k], PERIOD_D1, 0);
      if(d1 == 0) continue;
      if(d1 != lastD1[k]) { bool first = lastD1[k] == 0; lastD1[k] = d1; if(!first) NewDay(k); }
   }
   if(ShowPanel) Panel();
}
void OnTradeTransaction(const MqlTradeTransaction &tr, const MqlTradeRequest &rq, const MqlTradeResult &rs)
{
   if(tr.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(tr.deal)) return;
   long mg = HistoryDealGetInteger(tr.deal, DEAL_MAGIC); if(!Ours(mg)) return;
   string s = HistoryDealGetString(tr.deal, DEAL_SYMBOL);
   long entry = HistoryDealGetInteger(tr.deal, DEAL_ENTRY), pid = HistoryDealGetInteger(tr.deal, DEAL_POSITION_ID);
   double px = HistoryDealGetDouble(tr.deal, DEAL_PRICE), vol = HistoryDealGetDouble(tr.deal, DEAL_VOLUME);
   string id = IntegerToString(pid);
   if(entry == DEAL_ENTRY_IN)
   {
      double sl = 0, risk = 0;
      if(PositionSelectByTicket((ulong)pid)) { sl = PositionGetDouble(POSITION_SL); risk = MathAbs(px - sl) * MoneyPerPrice(s) * vol; }
      GlobalVariableSet(GV("risk_" + id), risk);
      GlobalVariableSet(GV("last_open"), (double)TimeCurrent());
      Log("FILL", s, StringFormat("unit=%s; dir=%s; price=%s; lots=%.2f; sl=%s; risk_usd=%.2f; position=%s", UnitName(mg),
                                  HistoryDealGetInteger(tr.deal, DEAL_TYPE) == DEAL_TYPE_BUY ? "buy" : "sell", DoubleToString(px, Dg(s)), vol,
                                  DoubleToString(sl, Dg(s)), risk, id));
   }
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
   {
      double pnl = HistoryDealGetDouble(tr.deal, DEAL_PROFIT) + HistoryDealGetDouble(tr.deal, DEAL_SWAP) + HistoryDealGetDouble(tr.deal, DEAL_COMMISSION);
      double swap = HistoryDealGetDouble(tr.deal, DEAL_SWAP);
      double risk = GlobalVariableGet(GV("risk_" + id)), R = risk > 0 ? pnl / risk : 0;
      int code = (int)GlobalVariableGet(GV("why_" + id));
      long rsn = HistoryDealGetInteger(tr.deal, DEAL_REASON);
      string why = code == 3 ? "10-day time stop" : code == 5 ? "hard stop" : code == 6 ? "closed with the first unit" :
                   code == 4 ? "max-loss emergency line" : code == 7 ? "daily loss line" : code == 8 ? "keep-alive" :
                   rsn == DEAL_REASON_SL ? "stop / trail" : rsn == DEAL_REASON_SO ? "stop out" : "other";
      GlobalVariableSet(GV("n"), GlobalVariableGet(GV("n")) + 1); GlobalVariableSet(GV("sr"), GlobalVariableGet(GV("sr")) + R);
      if(pnl > 0) { GlobalVariableSet(GV("w"), GlobalVariableGet(GV("w")) + 1); GlobalVariableSet(GV("sw"), GlobalVariableGet(GV("sw")) + R); }
      else GlobalVariableSet(GV("sl"), GlobalVariableGet(GV("sl")) + R);
      CalcClosed();
      Log("EXIT", s, StringFormat("unit=%s; price=%s; lots=%.2f; pnl=%.2f; swap=%.2f; R=%.2f; reason=%s; position=%s", UnitName(mg),
                                  DoubleToString(px, Dg(s)), vol, pnl, swap, R, why, id));
      GlobalVariableDel(GV("why_" + id));
   }
}

//=============================================================== panel
void Panel()
{
   string t = StringFormat("FibFVG Hold (Wallet 2) | %s | %.2f%% per unit | exit %s%s\n", RiskProfile, RiskPctPerUnit,
                           ExitMode == EXIT_YEAR ? "YEAR (120-day trail)" : "CHANDELIER", halted ? " | HALTED (set ResetHalt after review)" : "");
   t += StringFormat("virtual balance %.2f  equity %.2f  peak %.2f  drawdown %.2f%% (hard stop %.0f%%)\n", VBal(), VEq(), Peak(), DDpct(), HardStopPct);
   t += StringFormat("open stop-risk %.2f\n%s\n", OpenRisk(), Stats());
   for(int k = 0; k < NS; k++)
   {
      string s = Sym[k]; int d; double op, sl; datetime ot;
      int n = Count(s, Magic, d, op, sl, ot); int d2; double o2, s2; datetime t2; int m = Count(s, Magic + 1, d2, o2, s2, t2);
      t += StringFormat("%-10s %s  units %d  bias W %d / M %d%s\n", s, MarketOpen(s) ? "open  " : "closed", n + m, Bias(s, PERIOD_W1, 4), Bias(s, PERIOD_MN1, 6),
                        n > 0 ? StringFormat("  held %d days", (int)((TimeTradeServer() - ot) / 86400)) : "");
   }
   t += "log: MQL5\\Files\\" + LogName();
   Comment(t);
}
//+------------------------------------------------------------------+

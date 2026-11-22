//+------------------------------------------------------------------+
//|                                              FibFVG_Prop24.mq5    |
//|  Cueto & Co. - Wallet 1 bot (prop accounts).                     |
//|  Drop on ONE chart. Trades BTC, S&P 500 and Nasdaq 100 from it.  |
//|                                                                  |
//|  Direction : monthly + weekly ranges agree (premium/discount).   |
//|  Setup A   : daily chart - 20-day breakout leg >= 1.5 ATR with a |
//|              fair value gap; limit at the 0.705 Fibonacci level; |
//|              stop at the leg origin; take profit +1R.            |
//|  Setup B   : same pattern on the 4-hour chart; no target.        |
//|  Exit      : every trade closed 24 h after the fill or at the    |
//|              Friday 16:00 New York close, whichever is first.    |
//|  Guard     : drawdown + open stop-risk kept under MaxLoss-1%     |
//|              (6% firm line -> 5%); trades shrink near the line.  |
//|  Score     : the bot keeps its OWN virtual account (StartBalance |
//|              + its own closed and open P&L, by magic number), so |
//|              it can share a demo account with the Hold bot.      |
//|  Log       : MQL5\Files\FibFVG_Prop24_<account>.csv              |
//+------------------------------------------------------------------+
#property copyright "Cueto & Co."
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

input string RiskProfile       = "Normal";   // label in the log: Normal (Exness) or Aggressive (Vantage)
input double RiskPct           = 0.5;        // % of StartBalance per trade: Normal 0.5, Aggressive 0.75
input double StartBalance      = 100000;     // the virtual account this bot trades and is judged on
input double MaxLossPct        = 6;          // firm max loss
input bool   TrailingMaxLoss   = true;       // FundedNext instant: trailing
input double GuardBufferPct    = 1;          // bot line = MaxLoss - buffer (5% of start)
input double DailyLossPct      = 0;          // firm daily loss limit (0 = none)
input string SymbolsToTrade    = "AUTO";     // AUTO or your broker's names, e.g. BTCUSDm,US500m,USTECm
input bool   UseDailySetups    = true;       // setup A
input bool   UseH4Setups       = true;       // setup B
input int    MaxHoldHours      = 24;         // prop rule
input int    FridayCloseHourNY = 16;         // flat before the weekend (New York time)
input bool   WriteLog          = true;
input bool   ShowPanel         = true;
input long   Magic             = 7712400;    // A = Magic, B = Magic + 1

#define MAXS 6
const string BOT = "Prop24";
const double OTE = 0.705;
const int    BRK = 20;

string   Sym[MAXS]; int Fam[MAXS]; int NS = 0;       // family 2 BTC, 3 S&P 500, 4 Nasdaq 100
datetime lastD1[MAXS], lastH4[MAXS];
double   startBal = 0, closedPnL = 0;
datetime t0 = 0;
bool     halted = false;
int      lastDayKey = 0;

string GV(string k) { return "FFP24_" + IntegerToString(Magic) + "_" + k; }
bool   Ours(long mg) { return mg == Magic || mg == Magic + 1; }
string SetupName(long mg) { return mg == Magic ? "A-daily" : "B-4h"; }

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
   if(lots < vmin) return 0;                      // never oversize to reach the minimum lot
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

//=============================================================== New York time
datetime NthSunday(int year, int mon, int n)
{
   MqlDateTime t; t.year = year; t.mon = mon; t.day = 1; t.hour = 0; t.min = 0; t.sec = 0;
   datetime d = StructToTime(t); TimeToStruct(d, t);
   return d + ((7 - t.day_of_week) % 7 + 7 * (n - 1)) * 86400;
}
int NYOffset(datetime gmt)
{
   MqlDateTime t; TimeToStruct(gmt, t);
   datetime ds = NthSunday(t.year, 3, 2) + 7 * 3600, de = NthSunday(t.year, 11, 1) + 6 * 3600;
   return (gmt >= ds && gmt < de) ? -4 : -5;
}
int ServerOffset() { return (int)(MathRound((double)(TimeTradeServer() - TimeGMT()) / 900.0) * 900); }
// the first Friday 16:00 New York after a server time, returned as server time
datetime FridayCloseAfter(datetime server)
{
   int so = ServerOffset();
   datetime g = server - so; int off = NYOffset(g);
   datetime ny = g + off * 3600;
   MqlDateTime t; TimeToStruct(ny, t);
   datetime day0 = ny - (t.hour * 3600 + t.min * 60 + t.sec);
   datetime fri = day0 + ((5 - t.day_of_week + 7) % 7) * 86400 + FridayCloseHourNY * 3600;
   if(fri <= ny) fri += 7 * 86400;
   return fri - off * 3600 + so;
}

//=============================================================== symbols
bool Match(string name, string pat) { string u = name; StringToUpper(u); return StringFind(u, pat) == 0; }
int FamilyOf(string n)
{
   string p2[] = {"BTCUSD"};
   string p3[] = {"US500", "SPX500", "SP500", "USA500", "US.500"};
   string p4[] = {"NAS100", "USTEC", "US100", "NDX100", "USTECH"};
   for(int i = 0; i < ArraySize(p2); i++) if(Match(n, p2[i])) return 2;
   for(int i = 0; i < ArraySize(p3); i++) if(Match(n, p3[i])) return 3;
   for(int i = 0; i < ArraySize(p4); i++) if(Match(n, p4[i])) return 4;
   return -1;
}
void AddSym(string n)
{
   int f = FamilyOf(n); if(f < 0 || NS >= MAXS) return;
   for(int i = 0; i < NS; i++) if(Fam[i] == f) return;                  // one symbol per market
   if(!SymbolSelect(n, true)) return;
   if(SymbolInfoInteger(n, SYMBOL_TRADE_MODE) == SYMBOL_TRADE_MODE_DISABLED) return;
   Sym[NS] = n; Fam[NS] = f; lastD1[NS] = 0; lastH4[NS] = 0; NS++;
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
   for(int i = 0; i < SymbolsTotal(true) && NS < 3; i++) AddSym(SymbolName(i, true));     // Market Watch first
   for(int i = 0; i < SymbolsTotal(false) && NS < 3; i++) AddSym(SymbolName(i, false));
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
double DDpct() { double ref = TrailingMaxLoss ? Peak() : startBal; return startBal > 0 ? (ref - VEq()) / startBal * 100 : 0; }
double DayStart() { return GlobalVariableCheck(GV("day")) ? GlobalVariableGet(GV("day")) : VBal(); }
double Room()
{
   double ref = TrailingMaxLoss ? Peak() : startBal;
   double room = (MaxLossPct - GuardBufferPct) / 100.0 * startBal - (ref - VEq()) - OpenRisk();
   if(DailyLossPct > 0) room = MathMin(room, (DailyLossPct - 0.5) / 100.0 * startBal - (DayStart() - VEq()) - OpenRisk());
   return room;
}

//=============================================================== log (CSV, one row per event)
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
   return StringFormat("closed=%.0f; win_rate=%.1f%%; avg_win_R=%.2f; avg_loss_R=%.2f; RR=%.2f; avg_R=%.3f",
                       n, n > 0 ? w / n * 100 : 0, aw, al, al < 0 ? aw / -al : 0, n > 0 ? sr / n : 0);
}

//=============================================================== orders and positions
int PosCount(string s, long mg)
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL) == s && PositionGetInteger(POSITION_MAGIC) == mg) n++; }
   return n;
}
void DeleteOrders(string s, long mg, string why)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(OrderSelect(tk) && OrderGetString(ORDER_SYMBOL) == s && OrderGetInteger(ORDER_MAGIC) == mg)
         if(trade.OrderDelete(tk)) Log("CANCEL", s, StringFormat("setup=%s; order=%I64u; reason=%s", SetupName(mg), tk, why));
   }
}
void ClosePos(ulong tk, int code, string why)
{
   if(!PositionSelectByTicket(tk)) return;
   GlobalVariableSet(GV("why_" + IntegerToString(PositionGetInteger(POSITION_IDENTIFIER))), code);
   if(!trade.PositionClose(tk)) Log("ERROR", PositionGetString(POSITION_SYMBOL), StringFormat("close failed (%s): %d", why, trade.ResultRetcode()));
}
void CloseAll(string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk) && Ours(PositionGetInteger(POSITION_MAGIC))) ClosePos(tk, 4, why); }
   for(int k = 0; k < NS; k++) { DeleteOrders(Sym[k], Magic, why); DeleteOrders(Sym[k], Magic + 1, why); }
}

//=============================================================== guard
bool Guard()
{
   CalcClosed();
   if(VBal() > Peak()) GlobalVariableSet(GV("peak"), VBal());
   MqlDateTime t; TimeToStruct(TimeTradeServer(), t);
   int key = t.year * 1000 + t.day_of_year;
   if(key != lastDayKey)
   {
      if(lastDayKey != 0) Log("DAY", "", Stats());
      lastDayKey = key; GlobalVariableSet(GV("day"), VEq());
   }
   if(halted) return false;
   double ref = TrailingMaxLoss ? Peak() : startBal;
   if(ref - VEq() >= (MaxLossPct - 0.5) / 100.0 * startBal)
   {
      CloseAll("max-loss emergency line"); halted = true; GlobalVariableSet(GV("halt"), 1);
      Log("HALT", "", StringFormat("drawdown %.2f%% reached the emergency line", DDpct())); return false;
   }
   if(DailyLossPct > 0 && DayStart() - VEq() >= (DailyLossPct - 0.3) / 100.0 * startBal) { CloseAll("daily emergency line"); return false; }
   return true;
}

//=============================================================== setups A (D1) and B (H4)
void NewBar(int k, ENUM_TIMEFRAMES tf, long mg)
{
   string s = Sym[k];
   if(PosCount(s, mg) > 0) return;                                         // one trade per setup and market
   int dir = Bias(s, PERIOD_W1, 4); if(dir == 0 || dir != Bias(s, PERIOD_MN1, 6)) return;
   double N = ATRw(s, tf, 20, 2); if(N <= 0) return;
   bool brk = dir == 1 ? H(s, tf, 1) >= HH(s, tf, 2, BRK) : L(s, tf, 1) <= LL(s, tf, 2, BRK);
   if(!brk) return;
   int ext = dir == 1 ? iLowest(s, tf, MODE_LOW, BRK, 1) : iHighest(s, tf, MODE_HIGH, BRK, 1);
   if(ext < 1) return;
   double origin = dir == 1 ? L(s, tf, ext) : H(s, tf, ext), extreme = dir == 1 ? H(s, tf, 1) : L(s, tf, 1);
   double rng = MathAbs(extreme - origin);
   if(rng < 1.5 * N) return;
   bool fvg = false;
   for(int j = ext - 2; j >= 1 && !fvg; j--) fvg = dir == 1 ? L(s, tf, j) > H(s, tf, j + 2) : H(s, tf, j) < L(s, tf, j + 2);
   if(!fvg) return;
   double entry = extreme - dir * OTE * rng, sl = origin, dist = MathAbs(entry - sl);
   double ask = SymbolInfoDouble(s, SYMBOL_ASK), bid = SymbolInfoDouble(s, SYMBOL_BID);
   if(dist < 3 * (ask - bid)) return;
   double px = dir == 1 ? ask : bid;
   if((px - sl) * dir <= 0) return;                                        // already through the stop
   double riskMoney = startBal * RiskPct / 100.0, room = Room();
   if(riskMoney > 0.5 * room) riskMoney = MathMax(0, 0.5 * room);         // shrink near the line
   double lots = LotsFor(s, riskMoney, dist);
   string tag = SetupName(mg);
   if(lots <= 0) { Log("SKIP", s, StringFormat("setup=%s; dir=%d; reason=lot below minimum or no room; room=%.2f", tag, dir, room)); return; }
   double tp = (tf == PERIOD_D1) ? entry + dir * dist : 0;
   DeleteOrders(s, mg, "replaced by a newer setup");
   trade.SetExpertMagicNumber(mg);
   trade.SetTypeFillingBySymbol(s);
   string cm = StringFormat("P24%s r=%.0f", mg == Magic ? "A" : "B", lots * dist * MoneyPerPrice(s));
   bool ok;
   string how;
   if((px - entry) * dir <= 0)                                             // price already at the 0.705 level: enter now
   {
      ok = dir == 1 ? trade.Buy(lots, s, 0, Norm(s, sl), tp > 0 ? Norm(s, tp) : 0, cm) : trade.Sell(lots, s, 0, Norm(s, sl), tp > 0 ? Norm(s, tp) : 0, cm);
      how = "market";
   }
   else
   {
      ok = dir == 1 ? trade.BuyLimit(lots, Norm(s, entry), s, Norm(s, sl), tp > 0 ? Norm(s, tp) : 0, ORDER_TIME_GTC, 0, cm)
                    : trade.SellLimit(lots, Norm(s, entry), s, Norm(s, sl), tp > 0 ? Norm(s, tp) : 0, ORDER_TIME_GTC, 0, cm);
      how = "limit";
      datetime exp = TimeTradeServer() + (tf == PERIOD_D1 ? 15 * 86400 : 24 * 3600);
      if(ok) GlobalVariableSet(GV("exp_" + s + "_" + IntegerToString(mg)), (double)exp);
   }
   int dg = (int)SymbolInfoInteger(s, SYMBOL_DIGITS);
   if(ok) Log("ORDER", s, StringFormat("setup=%s; type=%s; dir=%s; entry=%s; sl=%s; tp=%s; lots=%.2f; risk_usd=%.2f; leg=%s-%s",
                                       tag, how, dir == 1 ? "buy" : "sell", DoubleToString(entry, dg), DoubleToString(sl, dg),
                                       tp > 0 ? DoubleToString(tp, dg) : "none", lots, lots * dist * MoneyPerPrice(s),
                                       DoubleToString(origin, dg), DoubleToString(extreme, dg)));
   else Log("ERROR", s, StringFormat("setup=%s; order rejected: %d %s", tag, trade.ResultRetcode(), trade.ResultRetcodeDescription()));
}

void Manage(int k)
{
   string s = Sym[k];
   // pending orders: expiry and price through the stop
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i); if(!OrderSelect(tk)) continue;
      long mg = OrderGetInteger(ORDER_MAGIC);
      if(OrderGetString(ORDER_SYMBOL) != s || !Ours(mg)) continue;
      datetime exp = (datetime)GlobalVariableGet(GV("exp_" + s + "_" + IntegerToString(mg)));
      double sl = OrderGetDouble(ORDER_SL);
      bool buy = OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_LIMIT;
      double px = buy ? SymbolInfoDouble(s, SYMBOL_BID) : SymbolInfoDouble(s, SYMBOL_ASK);
      string why = "";
      if(exp > 0 && TimeTradeServer() >= exp) why = "expired";
      else if(sl > 0 && (buy ? px <= sl : px >= sl)) why = "price went through the stop";
      if(why != "" && trade.OrderDelete(tk)) Log("CANCEL", s, StringFormat("setup=%s; order=%I64u; reason=%s", SetupName(mg), tk, why));
   }
   // open trades: 24 h and Friday close
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != s || !Ours(PositionGetInteger(POSITION_MAGIC))) continue;
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      if(TimeTradeServer() - ot >= MaxHoldHours * 3600) ClosePos(tk, 1, "24 hours");
      else if(TimeTradeServer() >= FridayCloseAfter(ot)) ClosePos(tk, 2, "Friday close");
   }
}

//=============================================================== events
int OnInit()
{
   startBal = StartBalance > 0 ? StartBalance : AccountInfoDouble(ACCOUNT_BALANCE);
   if(!GlobalVariableCheck(GV("t0"))) GlobalVariableSet(GV("t0"), (double)TimeCurrent());
   t0 = (datetime)GlobalVariableGet(GV("t0"));
   halted = GlobalVariableCheck(GV("halt")) && GlobalVariableGet(GV("halt")) > 0;
   ResolveSymbols();
   trade.SetDeviationInPoints(100);
   CalcClosed();
   if(!GlobalVariableCheck(GV("peak"))) GlobalVariableSet(GV("peak"), startBal);
   EventSetTimer(5);
   string list = ""; for(int k = 0; k < NS; k++) list += (k ? " " : "") + Sym[k];
   Log("START", "", StringFormat("profile=%s; risk=%.2f%%; start=%.0f; symbols=%s; server_offset_h=%.1f", RiskProfile, RiskPct, startBal, list, ServerOffset() / 3600.0));
   if(NS < 3) Print("FibFVG Prop24: only ", NS, " of 3 markets found. Set SymbolsToTrade to your broker's names.");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { EventKillTimer(); Comment(""); Log("STOP", "", StringFormat("reason=%d; %s", r, Stats())); }
void OnTick() {}
void OnTimer()
{
   bool ok = Guard();
   for(int k = 0; k < NS; k++)
   {
      if(!MarketOpen(Sym[k])) continue;
      Manage(k);
      if(!ok) continue;
      datetime d1 = iTime(Sym[k], PERIOD_D1, 0), h4 = iTime(Sym[k], PERIOD_H4, 0);
      if(d1 == 0 || h4 == 0) continue;                                     // history still loading
      if(d1 != lastD1[k]) { bool first = lastD1[k] == 0; lastD1[k] = d1; if(UseDailySetups && !first) NewBar(k, PERIOD_D1, Magic); }
      if(h4 != lastH4[k]) { bool first = lastH4[k] == 0; lastH4[k] = h4; if(UseH4Setups && !first) NewBar(k, PERIOD_H4, Magic + 1); }
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
      Log("FILL", s, StringFormat("setup=%s; dir=%s; price=%s; lots=%.2f; sl=%s; risk_usd=%.2f; position=%s", SetupName(mg),
                                  HistoryDealGetInteger(tr.deal, DEAL_TYPE) == DEAL_TYPE_BUY ? "buy" : "sell", DoubleToString(px, (int)SymbolInfoInteger(s, SYMBOL_DIGITS)),
                                  vol, DoubleToString(sl, (int)SymbolInfoInteger(s, SYMBOL_DIGITS)), risk, id));
   }
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
   {
      double pnl = HistoryDealGetDouble(tr.deal, DEAL_PROFIT) + HistoryDealGetDouble(tr.deal, DEAL_SWAP) + HistoryDealGetDouble(tr.deal, DEAL_COMMISSION);
      double risk = GlobalVariableGet(GV("risk_" + id)), R = risk > 0 ? pnl / risk : 0;
      int code = (int)GlobalVariableGet(GV("why_" + id));
      long rsn = HistoryDealGetInteger(tr.deal, DEAL_REASON);
      string why = code == 1 ? "24 hours" : code == 2 ? "Friday close" : code == 4 ? "guard" :
                   rsn == DEAL_REASON_SL ? "stop loss" : rsn == DEAL_REASON_TP ? "take profit +1R" : rsn == DEAL_REASON_SO ? "stop out" : "other";
      GlobalVariableSet(GV("n"), GlobalVariableGet(GV("n")) + 1); GlobalVariableSet(GV("sr"), GlobalVariableGet(GV("sr")) + R);
      if(pnl > 0) { GlobalVariableSet(GV("w"), GlobalVariableGet(GV("w")) + 1); GlobalVariableSet(GV("sw"), GlobalVariableGet(GV("sw")) + R); }
      else GlobalVariableSet(GV("sl"), GlobalVariableGet(GV("sl")) + R);
      CalcClosed();
      Log("EXIT", s, StringFormat("setup=%s; price=%s; lots=%.2f; pnl=%.2f; R=%.2f; reason=%s; position=%s", SetupName(mg),
                                  DoubleToString(px, (int)SymbolInfoInteger(s, SYMBOL_DIGITS)), vol, pnl, R, why, id));
      GlobalVariableDel(GV("why_" + id));
   }
}

//=============================================================== panel
void Panel()
{
   string t = StringFormat("FibFVG Prop24 (Wallet 1) | %s | risk %.2f%% per trade%s\n", RiskProfile, RiskPct, halted ? " | HALTED" : "");
   t += StringFormat("virtual balance %.2f  equity %.2f  peak %.2f  drawdown %.2f%% (bot line %.1f%%)\n", VBal(), VEq(), Peak(), DDpct(), MaxLossPct - GuardBufferPct);
   t += StringFormat("open stop-risk %.2f  room %.2f\n%s\n", OpenRisk(), Room(), Stats());
   for(int k = 0; k < NS; k++)
   {
      string s = Sym[k]; int a = PosCount(s, Magic), b = PosCount(s, Magic + 1);
      t += StringFormat("%-10s %s  open A:%d B:%d  bias W %d / M %d\n", s, MarketOpen(s) ? "open  " : "closed", a, b, Bias(s, PERIOD_W1, 4), Bias(s, PERIOD_MN1, 6));
   }
   t += "log: MQL5\\Files\\" + LogName();
   Comment(t);
}
//+------------------------------------------------------------------+

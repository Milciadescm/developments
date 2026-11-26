//+------------------------------------------------------------------+
//|                                           FibFVG_Prop24_V2.mq5    |
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
//|  Log       : MQL5\Files\FibFVG_Prop24V2_<account>.csv            |
//|  V2 (26 nov 2026): entradas solo 08:00-18:00 hora de Nueva York  |
//|     (fuera de horario la orden se estaciona); freno opcional     |
//|     para cuentas reales: riesgo a la mitad tras N pérdidas       |
//|     seguidas y riesgo mínimo si el saldo cae X % desde su máximo. |
//+------------------------------------------------------------------+
#property copyright "Cueto & Co."
#property version   "2.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

input string RiskProfile       = "Normal";   // label in the log: Normal (Exness) or Aggressive (Vantage)
input double RiskPct           = 0.5;        // % of StartBalance per trade: Normal 0.5, Aggressive 0.75
input double StartBalance      = 100000;     // the virtual account this bot trades and is judged on
input double MaxLossPct        = 6;          // firm max loss
input bool   TrailingMaxLoss   = true;       // FundedNext Instant: trailing, stops rising once it reaches the start balance
input double GuardBufferPct    = 1;          // bot line = MaxLoss - buffer (5% of start)
input double DailyLossPct      = 0;          // firm daily loss limit (0 = none)
input double MaxOpenRiskPct    = 0;          // floating-loss limit of all open trades (0 = none). Goat Funded Instant Premium: 1
input bool   TrailOnEquity     = false;      // true = the trailing line follows the equity peak (Goat Funded "intraday trailing")
input string SymbolsToTrade    = "AUTO";     // AUTO or your broker's names, e.g. BTCUSDm,US500m,USTECm
input bool   UseDailySetups    = true;       // setup A
input bool   UseH4Setups       = true;       // setup B
input int    MaxHoldHours      = 24;         // prop rule
input int    FridayCloseHourNY = 16;         // flat before the weekend (New York time)
input int    KeepAliveDays     = 50;         // FundedNext 60-day inactivity rule: tiny open/close trade after this many idle days (0 = off)
input bool   WriteLog          = true;
input bool   ShowPanel         = true;
input long   Magic             = 7712400;    // A = Magic, B = Magic + 1
input bool   CompoundOnBalance = false;      // real money: risk is a % of the CURRENT account balance (deposits and profits count)
input bool   MinLotIfBelow     = false;      // small accounts: open at the broker minimum lot when the % size is smaller...
input double MaxRiskPctAtMinLot = 3;         // ...but only if that minimum lot risks at most this % of the balance
input int    EntryFromHourNY   = 8;          // entradas solo desde esta hora de Nueva York (0 y 24 = todo el día)
input int    EntryToHourNY     = 18;         // ...hasta esta hora (sin incluir). GFT 26 nov 2026: 8 a 18 (pasó los 4 controles)
input int    BrakeAfterLosses  = 0;          // cuenta real: tras esta cantidad de pérdidas seguidas, riesgo x BrakeFactor (0 = apagado; GFT: 0)
input double BrakeFactor       = 0.5;        // ...multiplicador del riesgo durante el freno
input double DDBrakePct        = 0;          // cuenta real: si el saldo cae este % desde su máximo, riesgo = DDBrakeRiskPct (0 = apagado)
input double DDBrakeRiskPct    = 1;          // ...riesgo % durante esa caída

#define MAXS 6
const string BOT = "Prop24V2";
const double OTE = 0.705;
const int    BRK = 20;

string   Sym[MAXS]; int Fam[MAXS]; int NS = 0;       // family 2 BTC, 3 S&P 500, 4 Nasdaq 100
datetime lastD1[MAXS], lastH4[MAXS];
double   startBal = 0, closedPnL = 0;
datetime t0 = 0;
bool     halted = false;
int      lastDayKey = 0;
// órdenes "estacionadas" fuera del horario de entrada: se vuelven a poner al abrir el horario
#define MAXP 20
string pSym[MAXP]; long pMg[MAXP]; int pDir[MAXP]; double pEntry[MAXP], pSl[MAXP], pTp[MAXP], pLots[MAXP]; datetime pExp[MAXP]; string pCm[MAXP]; int NP = 0;
bool guardOk = true;

string GV(string k) { return "FFP24_" + IntegerToString(Magic) + "_" + k; }
bool   Ours(long mg) { return mg == Magic || mg == Magic + 1 || mg == Magic + 9; }
string SetupName(long mg) { return mg == Magic ? "A-daily" : mg == Magic + 9 ? "keep-alive" : "B-4h"; }

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
   if(lots < vmin)
   {
      double base = CompoundOnBalance ? AccountInfoDouble(ACCOUNT_BALANCE) : startBal;
      if(!MinLotIfBelow || vmin * dist * mpp > MaxRiskPctAtMinLot / 100.0 * base) return 0;   // never oversize past the cap
      lots = vmin;
   }
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

bool InEntryWindow()
{
   if(EntryFromHourNY <= 0 && EntryToHourNY >= 24) return true;
   datetime g = TimeGMT(); MqlDateTime t; TimeToStruct(g + NYOffset(g) * 3600, t);
   return t.hour >= EntryFromHourNY && t.hour < EntryToHourNY;
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
// riesgo % efectivo (V2): freno por racha de pérdidas y por caída desde el máximo del saldo
double EffRiskPct()
{
   double r = RiskPct;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double pk = MathMax(GlobalVariableCheck(GV("bpeak")) ? GlobalVariableGet(GV("bpeak")) : bal, bal);
   GlobalVariableSet(GV("bpeak"), pk);
   if(DDBrakePct > 0 && bal < (1 - DDBrakePct / 100.0) * pk) return MathMin(r, DDBrakeRiskPct);
   if(BrakeAfterLosses > 0 && GlobalVariableGet(GV("streak")) >= BrakeAfterLosses) r *= BrakeFactor;
   return r;
}
double DDpct() { double ref = TrailingMaxLoss ? Peak() : startBal; return startBal > 0 ? (ref - VEq()) / startBal * 100 : 0; }
// the firm's loss line: static = start - MaxLoss; trailing = balance peak - MaxLoss, never above the start balance (FundedNext)
double Floor() { double f = startBal - MaxLossPct / 100.0 * startBal; if(TrailingMaxLoss) f = MathMin(Peak() - MaxLossPct / 100.0 * startBal, startBal); return f; }
double DayStart() { return GlobalVariableCheck(GV("day")) ? GlobalVariableGet(GV("day")) : VBal(); }
double Room()
{
   double room = VEq() - Floor() - GuardBufferPct / 100.0 * startBal - OpenRisk();
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
   NP = 0;                                                                 // las órdenes estacionadas también se descartan
   for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk) && Ours(PositionGetInteger(POSITION_MAGIC))) ClosePos(tk, 4, why); }
   for(int k = 0; k < NS; k++) { DeleteOrders(Sym[k], Magic, why); DeleteOrders(Sym[k], Magic + 1, why); }
}

//=============================================================== guard
bool Guard()
{
   CalcClosed();
   if(VBal() > Peak()) GlobalVariableSet(GV("peak"), VBal());
   if(TrailOnEquity && VEq() > Peak()) GlobalVariableSet(GV("peak"), VEq());
   MqlDateTime t; TimeToStruct(TimeTradeServer(), t);
   int key = t.year * 1000 + t.day_of_year;
   if(key != lastDayKey)
   {
      if(lastDayKey != 0) Log("DAY", "", Stats());
      lastDayKey = key; GlobalVariableSet(GV("day"), VEq());
   }
   if(halted) return false;
   if(VEq() - Floor() <= 0.5 / 100.0 * startBal)
   {
      CloseAll("max-loss emergency line"); halted = true; GlobalVariableSet(GV("halt"), 1);
      Log("HALT", "", StringFormat("drawdown %.2f%% reached the emergency line", DDpct())); return false;
   }
   if(DailyLossPct > 0 && DayStart() - VEq() >= (DailyLossPct - 0.3) / 100.0 * startBal) { CloseAll("daily emergency line"); return false; }
   return true;
}

//=============================================================== horario de entrada (órdenes estacionadas)
void Unpark(int i) { for(int j = i; j < NP - 1; j++) { pSym[j] = pSym[j + 1]; pMg[j] = pMg[j + 1]; pDir[j] = pDir[j + 1]; pEntry[j] = pEntry[j + 1]; pSl[j] = pSl[j + 1]; pTp[j] = pTp[j + 1]; pLots[j] = pLots[j + 1]; pExp[j] = pExp[j + 1]; pCm[j] = pCm[j + 1]; } NP--; }
void DropParked(string s, long mg) { for(int i = NP - 1; i >= 0; i--) if(pSym[i] == s && pMg[i] == mg) Unpark(i); }
void Park(string s, long mg, int dir, double entry, double sl, double tp, double lots, datetime exp, string cm)
{
   DropParked(s, mg);
   if(NP >= MAXP) return;
   pSym[NP] = s; pMg[NP] = mg; pDir[NP] = dir; pEntry[NP] = entry; pSl[NP] = sl; pTp[NP] = tp; pLots[NP] = lots; pExp[NP] = exp; pCm[NP] = cm; NP++;
   Log("PARK", s, StringFormat("setup=%s; reason=outside entry hours %d-%d NY; entry=%s; sl=%s", SetupName(mg), EntryFromHourNY, EntryToHourNY,
                               DoubleToString(entry, (int)SymbolInfoInteger(s, SYMBOL_DIGITS)), DoubleToString(sl, (int)SymbolInfoInteger(s, SYMBOL_DIGITS))));
}
// fuera del horario: las órdenes límite pendientes se quitan y se guardan
void ParkPending(string s)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i); if(!OrderSelect(tk)) continue;
      long mg = OrderGetInteger(ORDER_MAGIC);
      if(OrderGetString(ORDER_SYMBOL) != s || !Ours(mg)) continue;
      int dir = OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_LIMIT ? 1 : -1;
      double e = OrderGetDouble(ORDER_PRICE_OPEN), sl = OrderGetDouble(ORDER_SL), tp = OrderGetDouble(ORDER_TP), lots = OrderGetDouble(ORDER_VOLUME_CURRENT);
      string cm = OrderGetString(ORDER_COMMENT);
      datetime exp = (datetime)GlobalVariableGet(GV("exp_" + s + "_" + IntegerToString(mg)));
      if(trade.OrderDelete(tk)) Park(s, mg, dir, e, sl, tp, lots, exp, cm);
   }
}
// dentro del horario: volver a poner lo estacionado si sigue vigente
void ReleaseParked(string s)
{
   for(int i = NP - 1; i >= 0; i--)
   {
      if(pSym[i] != s) continue;
      string tag = SetupName(pMg[i]);
      double ask = SymbolInfoDouble(s, SYMBOL_ASK), bid = SymbolInfoDouble(s, SYMBOL_BID), px = pDir[i] == 1 ? ask : bid;
      string why = "";
      if(pExp[i] > 0 && TimeTradeServer() >= pExp[i]) why = "expired";
      else if((px - pSl[i]) * pDir[i] <= 0) why = "price went through the stop";
      else if(PosCount(s, pMg[i]) > 0) why = "a trade of this setup is already open";
      else if(MaxOpenRiskPct > 0 && pLots[i] * MathAbs(pEntry[i] - pSl[i]) * MoneyPerPrice(s) > (MaxOpenRiskPct - 0.1) / 100.0 * startBal - OpenRisk()) why = "floating-loss limit";
      if(why != "") { Log("CANCEL", s, StringFormat("setup=%s; parked order; reason=%s", tag, why)); Unpark(i); continue; }
      trade.SetExpertMagicNumber(pMg[i]); trade.SetTypeFillingBySymbol(s);
      bool ok; string how;
      if((px - pEntry[i]) * pDir[i] <= 0)
      { ok = pDir[i] == 1 ? trade.Buy(pLots[i], s, 0, Norm(s, pSl[i]), pTp[i] > 0 ? Norm(s, pTp[i]) : 0, pCm[i]) : trade.Sell(pLots[i], s, 0, Norm(s, pSl[i]), pTp[i] > 0 ? Norm(s, pTp[i]) : 0, pCm[i]); how = "market"; }
      else
      {
         ok = pDir[i] == 1 ? trade.BuyLimit(pLots[i], Norm(s, pEntry[i]), s, Norm(s, pSl[i]), pTp[i] > 0 ? Norm(s, pTp[i]) : 0, ORDER_TIME_GTC, 0, pCm[i])
                           : trade.SellLimit(pLots[i], Norm(s, pEntry[i]), s, Norm(s, pSl[i]), pTp[i] > 0 ? Norm(s, pTp[i]) : 0, ORDER_TIME_GTC, 0, pCm[i]);
         how = "limit";
         if(ok) GlobalVariableSet(GV("exp_" + s + "_" + IntegerToString(pMg[i])), (double)pExp[i]);
      }
      if(ok) Log("ORDER", s, StringFormat("setup=%s; type=%s; parked order released (entry hours %d-%d NY)", tag, how, EntryFromHourNY, EntryToHourNY));
      else Log("ERROR", s, StringFormat("setup=%s; parked order rejected: %d %s", tag, trade.ResultRetcode(), trade.ResultRetcodeDescription()));
      Unpark(i);
   }
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
   double riskPct = EffRiskPct();
   double riskMoney = (CompoundOnBalance ? AccountInfoDouble(ACCOUNT_BALANCE) : startBal) * riskPct / 100.0, room = Room();
   if(riskPct < RiskPct) Log("BRAKE", s, StringFormat("setup=%s; risk %.2f%% instead of %.2f%% (losses in a row %.0f)", SetupName(mg), riskPct, RiskPct, GlobalVariableGet(GV("streak"))));
   if(MaxOpenRiskPct > 0)                                                  // floating-loss limit: all open stops together
   {
      double left = (MaxOpenRiskPct - 0.1) / 100.0 * startBal - OpenRisk();
      if(riskMoney > left) { Log("SKIP", s, StringFormat("setup=%s; reason=floating-loss limit (open risk %.2f)", SetupName(mg), OpenRisk())); return; }
   }
   if(riskMoney > 0.5 * room) riskMoney = MathMax(0, 0.5 * room);         // shrink near the line
   double lots = LotsFor(s, riskMoney, dist);
   string tag = SetupName(mg);
   if(lots <= 0) { Log("SKIP", s, StringFormat("setup=%s; dir=%d; reason=lot below minimum or no room; room=%.2f", tag, dir, room)); return; }
   double tp = (tf == PERIOD_D1) ? entry + dir * dist : 0;
   DeleteOrders(s, mg, "replaced by a newer setup");
   DropParked(s, mg);
   if(!InEntryWindow())
   {
      Park(s, mg, dir, entry, sl, tp, lots, TimeTradeServer() + (tf == PERIOD_D1 ? 15 * 86400 : 24 * 3600),
           StringFormat("P24%s r=%.0f", mg == Magic ? "A" : "B", lots * dist * MoneyPerPrice(s)));
      return;
   }
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
   if(!InEntryWindow()) ParkPending(s); else if(guardOk && !halted) ReleaseParked(s);
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

// FundedNext deactivates an account after 60 days without a trade: open and close the smallest position
void KeepAlive()
{
   if(KeepAliveDays <= 0 || NS == 0) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionSelectByTicket(tk) && PositionGetInteger(POSITION_MAGIC) == Magic + 9 && TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) >= 60) ClosePos(tk, 8, "keep-alive");
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
   if(!GlobalVariableCheck(GV("last_open"))) GlobalVariableSet(GV("last_open"), (double)TimeCurrent());
   EventSetTimer(5);
   string list = ""; for(int k = 0; k < NS; k++) list += (k ? " " : "") + Sym[k];
   Log("START", "", StringFormat("profile=%s; risk=%.2f%%; start=%.0f; symbols=%s; server_offset_h=%.1f; entry_hours_NY=%d-%d; brake=%d losses x%.2f, dd %.0f%% -> %.2f%%; version=2", RiskProfile, RiskPct, startBal, list, ServerOffset() / 3600.0, EntryFromHourNY, EntryToHourNY, BrakeAfterLosses, BrakeFactor, DDBrakePct, DDBrakeRiskPct));
   if(NS < 3) Print("FibFVG Prop24: only ", NS, " of 3 markets found. Set SymbolsToTrade to your broker's names.");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { EventKillTimer(); Comment(""); Log("STOP", "", StringFormat("reason=%d; %s", r, Stats())); }
void OnTick() {}
void OnTimer()
{
   bool ok = Guard(); guardOk = ok;
   KeepAlive();
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
      GlobalVariableSet(GV("last_open"), (double)TimeCurrent());
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
      string why = code == 1 ? "24 hours" : code == 2 ? "Friday close" : code == 4 ? "guard" : code == 8 ? "keep-alive" :
                   rsn == DEAL_REASON_SL ? "stop loss" : rsn == DEAL_REASON_TP ? "take profit +1R" : rsn == DEAL_REASON_SO ? "stop out" : "other";
      GlobalVariableSet(GV("n"), GlobalVariableGet(GV("n")) + 1); GlobalVariableSet(GV("sr"), GlobalVariableGet(GV("sr")) + R);
      if(pnl > 0) { GlobalVariableSet(GV("w"), GlobalVariableGet(GV("w")) + 1); GlobalVariableSet(GV("sw"), GlobalVariableGet(GV("sw")) + R); }
      if(code != 8) GlobalVariableSet(GV("streak"), pnl < 0 ? GlobalVariableGet(GV("streak")) + 1 : 0);   // racha de pérdidas (freno V2)
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
   string t = StringFormat("FibFVG Prop24 V2 | %s | risk %.2f%% (now %.2f%%) | entries %02d-%02d NY%s\n", RiskProfile, RiskPct, EffRiskPct(), EntryFromHourNY, EntryToHourNY, halted ? " | HALTED" : "");
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

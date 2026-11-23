"""Generates the two Goat Funded Trader EAs from one shared MQL5 core (risk guard, New York clock, log, panel).
    python tools/build_gft_eas.py -> mql5/FibFVG_NY10.mq5, mql5/FibFVG_GoldMidnight.mq5
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORE = r'''
#include <Trade/Trade.mqh>
CTrade trade;

input double StartBalance    = 5000;   // the account's starting balance ($5K, $50K, $100K ...)
input double RiskPct         = RISKDEFAULT;   // % of StartBalance lost if the stop is hit
input double MaxLossPct      = 6;      // GFT Instant Premium: 6% trailing (locks at the start balance)
input bool   TrailOnEquity   = true;   // GFT "intraday trailing": the line follows the highest equity
input double DailyLossPct    = 3;      // GFT daily loss (day starts 17:00 New York)
input double MaxOpenRiskPct  = 1;      // GFT floating-loss limit of ALL open trades (1% for accounts bought after 2 Sep 2026)
input double GuardBufferPct  = 1;      // the bot stops trading this far before the 6% line
input string SymbolToTrade   = "AUTO"; // AUTO or your broker's exact name
input bool   WriteLog        = true;
input bool   ShowPanel       = true;
input long   Magic           = MAGICDEFAULT;

string Sym = ""; bool halted = false;
string GV(string k) { return BOTNAME + "_" + IntegerToString(Magic) + "_" + k; }
bool Ours(long mg) { return mg == Magic; }

//=============================================================== time: server -> New York
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
datetime ToNY(datetime server) { datetime g = server - ServerOffset(); return g + NYOffset(g) * 3600; }
datetime NYNow() { return ToNY(TimeTradeServer()); }
int NYHour(datetime ny) { MqlDateTime t; TimeToStruct(ny, t); return t.hour; }
int NYDow(datetime ny) { MqlDateTime t; TimeToStruct(ny, t); return t.day_of_week; }
datetime NYDate(datetime ny) { long x = (long)ny; return (datetime)(x - x % 86400); }

//=============================================================== market helpers
double MoneyPerPrice(string s)
{
   double tv = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE_LOSS), ts = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0) tv = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE);
   return ts > 0 ? tv / ts : 0;
}
double Norm(double p) { return NormalizeDouble(p, (int)SymbolInfoInteger(Sym, SYMBOL_DIGITS)); }
string P(double p) { return DoubleToString(p, (int)SymbolInfoInteger(Sym, SYMBOL_DIGITS)); }
double LotsFor(double riskMoney, double dist)
{
   double mpp = MoneyPerPrice(Sym), step = SymbolInfoDouble(Sym, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(Sym, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(Sym, SYMBOL_VOLUME_MAX);
   if(mpp <= 0 || dist <= 0 || step <= 0 || riskMoney <= 0) return 0;
   double lots = MathFloor(riskMoney / (dist * mpp) / step) * step;
   if(lots < vmin) return 0;                       // never oversize to reach the minimum lot
   return NormalizeDouble(MathMin(lots, vmax), 2);
}
bool MarketOpen()
{
   if(!TerminalInfoInteger(TERMINAL_CONNECTED) || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return false;
   long mode = SymbolInfoInteger(Sym, SYMBOL_TRADE_MODE);
   if(mode == SYMBOL_TRADE_MODE_DISABLED || mode == SYMBOL_TRADE_MODE_CLOSEONLY) return false;
   return TimeTradeServer() - (datetime)SymbolInfoInteger(Sym, SYMBOL_TIME) <= 600;
}
int Bias(ENUM_TIMEFRAMES tf, int look)
{
   int ih = iHighest(Sym, tf, MODE_HIGH, look, 1), il = iLowest(Sym, tf, MODE_LOW, look, 1);
   if(ih < 0 || il < 0) return 0;
   double mid = (iHigh(Sym, tf, ih) + iLow(Sym, tf, il)) / 2, c = iClose(Sym, tf, 1);
   return c > mid ? 1 : c < mid ? -1 : 0;
}
int TrendBias() { int w = Bias(PERIOD_W1, 4); return (w != 0 && w == Bias(PERIOD_MN1, 6)) ? w : 0; }   // monthly + weekly agree
bool FindSymbol()
{
   if(SymbolToTrade != "AUTO") { Sym = SymbolToTrade; return SymbolSelect(Sym, true); }
   string pats[] = PATTERNS;
   for(int pass = 0; pass < 2; pass++)
      for(int i = 0; i < SymbolsTotal(pass == 0); i++)
      {
         string n = SymbolName(i, pass == 0), u = n; StringToUpper(u);
         for(int j = 0; j < ArraySize(pats); j++)
            if(StringFind(u, pats[j]) == 0 && SymbolInfoInteger(n, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_DISABLED) { Sym = n; return SymbolSelect(n, true); }
      }
   return false;
}

//=============================================================== account guard (GFT Instant Premium rules)
double Eq() { return AccountInfoDouble(ACCOUNT_EQUITY); }
double Bal() { return AccountInfoDouble(ACCOUNT_BALANCE); }
double Peak() { return GlobalVariableCheck(GV("peak")) ? GlobalVariableGet(GV("peak")) : StartBalance; }
// the firm's line: highest equity (or balance) minus 6%, but never above the starting balance
double Floor() { return MathMin(Peak() - MaxLossPct / 100.0 * StartBalance, StartBalance); }
int GftDayKey() { datetime ny = NYNow() - 17 * 3600; MqlDateTime t; TimeToStruct(ny, t); return t.year * 1000 + t.day_of_year; }
double DayStart() { return GlobalVariableCheck(GV("day")) ? GlobalVariableGet(GV("day")) : MathMax(Bal(), Eq()); }
double OpenRisk()                                   // stops of ALL open trades on the account (any EA)
{
   double tot = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      string s = PositionGetString(POSITION_SYMBOL);
      double sl = PositionGetDouble(POSITION_SL), op = PositionGetDouble(POSITION_PRICE_OPEN), v = PositionGetDouble(POSITION_VOLUME);
      int d = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      if(sl <= 0) { tot += StartBalance; continue; }   // a trade without a stop counts as unlimited risk
      double dist = (op - sl) * d; if(dist > 0) tot += dist * MoneyPerPrice(s) * v;
   }
   return tot;
}
double RiskRoom()
{
   double room = Eq() - Floor() - GuardBufferPct / 100.0 * StartBalance - OpenRisk();
   room = MathMin(room, Eq() - (DayStart() - DailyLossPct / 100.0 * StartBalance) - 0.5 / 100.0 * StartBalance - OpenRisk());
   if(MaxOpenRiskPct > 0) room = MathMin(room, (MaxOpenRiskPct - 0.1) / 100.0 * StartBalance - OpenRisk());
   return room;
}
void CloseOurs(string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk) && Ours(PositionGetInteger(POSITION_MAGIC))) { GlobalVariableSet(GV("why_" + IntegerToString(PositionGetInteger(POSITION_IDENTIFIER))), 1); trade.PositionClose(tk); } }
   for(int i = OrdersTotal() - 1; i >= 0; i--) { ulong tk = OrderGetTicket(i); if(OrderSelect(tk) && Ours(OrderGetInteger(ORDER_MAGIC))) trade.OrderDelete(tk); }
   Log("CLOSEALL", Sym, why);
}
int lastKey = 0;
bool Guard()
{
   double hi = TrailOnEquity ? MathMax(Eq(), Bal()) : Bal();
   if(hi > Peak()) GlobalVariableSet(GV("peak"), hi);
   int key = GftDayKey();
   if(key != lastKey)
   {
      if(lastKey != 0)
      {
         double dayPnl = Bal() - GlobalVariableGet(GV("daybal"));
         if(dayPnl >= 0.005 * StartBalance) GlobalVariableSet(GV("pdays"), GlobalVariableGet(GV("pdays")) + 1);
         Log("DAY", Sym, StringFormat("closed_pnl=%.2f; profitable_days_since_payout=%.0f; %s", dayPnl, GlobalVariableGet(GV("pdays")), Stats()));
      }
      lastKey = key; GlobalVariableSet(GV("day"), MathMax(Bal(), Eq())); GlobalVariableSet(GV("daybal"), Bal());
   }
   if(halted) return false;
   if(Eq() - Floor() <= 0.5 / 100.0 * StartBalance) { CloseOurs("max-loss emergency line"); halted = true; GlobalVariableSet(GV("halt"), 1); Log("HALT", Sym, "0.5% from the firm's line"); return false; }
   if(DayStart() - Eq() >= (DailyLossPct - 0.3) / 100.0 * StartBalance) { CloseOurs("daily emergency line"); return false; }
   return true;
}

//=============================================================== log
string LogName() { return "FibFVG_" + BOTNAME + "_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".csv"; }
void Log(string ev, string s, string detail)
{
   if(!WriteLog) return;
   int h = FileOpen(LogName(), FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
   if(h == INVALID_HANDLE) return;
   bool fresh = FileSize(h) == 0; FileSeek(h, 0, SEEK_END);
   StringReplace(detail, ",", ";");
   if(fresh) FileWrite(h, "server_time", "new_york_time", "bot", "account", "event", "symbol", "detail", "balance", "equity", "peak", "firm_line", "open_risk");
   FileWrite(h, TimeToString(TimeTradeServer(), TIME_DATE | TIME_SECONDS), TimeToString(NYNow(), TIME_DATE | TIME_SECONDS), BOTNAME,
             IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)), ev, s, detail, DoubleToString(Bal(), 2), DoubleToString(Eq(), 2),
             DoubleToString(Peak(), 2), DoubleToString(Floor(), 2), DoubleToString(OpenRisk(), 2));
   FileClose(h);
}
string Stats()
{
   double n = GlobalVariableGet(GV("n")), w = GlobalVariableGet(GV("w")), sr = GlobalVariableGet(GV("sr")), gw = GlobalVariableGet(GV("gw")), gl = GlobalVariableGet(GV("gl"));
   return StringFormat("trades=%.0f; win_rate=%.1f%%; profit_factor=%.2f; avg_R=%.3f", n, n > 0 ? w / n * 100 : 0, gl > 0 ? gw / gl : 0, n > 0 ? sr / n : 0);
}

//=============================================================== trade events: fills, exits, payouts
void OnTradeTransaction(const MqlTradeTransaction &tr, const MqlTradeRequest &rq, const MqlTradeResult &rs)
{
   if(tr.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(tr.deal)) return;
   long type = HistoryDealGetInteger(tr.deal, DEAL_TYPE);
   if(type == DEAL_TYPE_BALANCE && HistoryDealGetDouble(tr.deal, DEAL_PROFIT) < 0)
   {                                                   // payout taken: the count of profitable days restarts
      GlobalVariableSet(GV("pdays"), 0); GlobalVariableSet(GV("peak"), MathMax(Bal(), StartBalance));
      GlobalVariableSet(GV("daybal"), Bal()); GlobalVariableSet(GV("day"), MathMax(Bal(), Eq()));
      Log("PAYOUT", "", StringFormat("withdrawn=%.2f", -HistoryDealGetDouble(tr.deal, DEAL_PROFIT))); return;
   }
   if(!Ours(HistoryDealGetInteger(tr.deal, DEAL_MAGIC))) return;
   long entry = HistoryDealGetInteger(tr.deal, DEAL_ENTRY), pid = HistoryDealGetInteger(tr.deal, DEAL_POSITION_ID);
   double px = HistoryDealGetDouble(tr.deal, DEAL_PRICE), vol = HistoryDealGetDouble(tr.deal, DEAL_VOLUME);
   string id = IntegerToString(pid);
   if(entry == DEAL_ENTRY_IN)
   {
      double sl = 0, risk = 0;
      if(PositionSelectByTicket((ulong)pid)) { sl = PositionGetDouble(POSITION_SL); risk = MathAbs(px - sl) * MoneyPerPrice(Sym) * vol; }
      GlobalVariableSet(GV("risk_" + id), RISKSTORE);
      Log("FILL", Sym, StringFormat("dir=%s; price=%s; lots=%.2f; stop=%s; risk_usd=%.2f; position=%s", type == DEAL_TYPE_BUY ? "buy" : "sell", P(px), vol, P(sl), risk, id));
   }
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
   {
      double pnl = HistoryDealGetDouble(tr.deal, DEAL_PROFIT) + HistoryDealGetDouble(tr.deal, DEAL_SWAP) + HistoryDealGetDouble(tr.deal, DEAL_COMMISSION);
      double risk = GlobalVariableGet(GV("risk_" + id)), R = risk > 0 ? pnl / risk : 0;
      long rsn = HistoryDealGetInteger(tr.deal, DEAL_REASON);
      string why = GlobalVariableGet(GV("why_" + id)) > 0 ? "time exit / guard" : rsn == DEAL_REASON_SL ? "stop (or breakeven)" : rsn == DEAL_REASON_TP ? "target" : "other";
      GlobalVariableSet(GV("n"), GlobalVariableGet(GV("n")) + 1); GlobalVariableSet(GV("sr"), GlobalVariableGet(GV("sr")) + R);
      if(pnl > 0) { GlobalVariableSet(GV("w"), GlobalVariableGet(GV("w")) + 1); GlobalVariableSet(GV("gw"), GlobalVariableGet(GV("gw")) + pnl); }
      else GlobalVariableSet(GV("gl"), GlobalVariableGet(GV("gl")) - pnl);
      Log("EXIT", Sym, StringFormat("price=%s; lots=%.2f; pnl=%.2f; R=%.2f; reason=%s; position=%s", P(px), vol, pnl, R, why, id));
   }
}
int CountOurs() { int n = 0; for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk) && Ours(PositionGetInteger(POSITION_MAGIC))) n++; } return n; }
int CountOrders() { int n = 0; for(int i = OrdersTotal() - 1; i >= 0; i--) { ulong tk = OrderGetTicket(i); if(OrderSelect(tk) && Ours(OrderGetInteger(ORDER_MAGIC))) n++; } return n; }
void CloseTimed(string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionSelectByTicket(tk) && Ours(PositionGetInteger(POSITION_MAGIC)))
      { GlobalVariableSet(GV("why_" + IntegerToString(PositionGetInteger(POSITION_IDENTIFIER))), 1); if(trade.PositionClose(tk)) Log("TIMEEXIT", Sym, why); }
   }
}
string PanelCommon()
{
   return StringFormat("%s on %s | risk %.2f%% of %.0f%s\nbalance %.2f  equity %.2f  firm line %.2f  (room %.2f)\nopen risk %.2f (limit %.0f%%)  profitable days since payout %.0f / 5\n%s\nNew York time %s\nlog: MQL5\\Files\\%s",
                       BOTNAME, Sym, RiskPct, StartBalance, halted ? " | HALTED" : "", Bal(), Eq(), Floor(), RiskRoom(), OpenRisk(), MaxOpenRiskPct,
                       GlobalVariableGet(GV("pdays")), Stats(), TimeToString(NYNow(), TIME_DATE | TIME_MINUTES), LogName());
}
'''

NY10 = r'''//+------------------------------------------------------------------+
//|                                                 FibFVG_NY10.mq5   |
//|  Cueto & Co. - Nasdaq 100, one trade a day in the 10:00-14:00     |
//|  New York 4-hour candle. Built for Goat Funded Trader Instant     |
//|  Premium (6% intraday trailing, 3% daily, 1% floating limit).     |
//|                                                                  |
//|  Direction : monthly + weekly ranges agree.                      |
//|  Range     : A = average high-low of the 10:00-14:00 NY candle    |
//|              over the last 20 days.                              |
//|  Entry     : at 10:00 NY a limit 0.25 A back from the 10:00 open  |
//|              (buy below / sell above). Cancelled at 11:00 NY.    |
//|  Stop      : 0.5 A from the entry = 1R. Target: 2R.              |
//|  Breakeven : stop to entry once the trade is +0.5R.              |
//|  Time exit : everything closed at 14:00 NY. Nothing overnight.   |
//|  Backtest Jul 2024 - Nov 2026 (hourly data, not proven, t 1.4):  |
//|  182 trades, 25% wins, profit factor 1.37 (R) / 1.53 (pips).     |
//|  Run it on your own PC: GFT bans VPS, VPN and proxies.           |
//+------------------------------------------------------------------+
#property copyright "Cueto & Co."
#property version   "1.00"
#property strict
#define BOTNAME "NY10"
#define RISKDEFAULT 0.6
#define MAGICDEFAULT 7713000
#define PATTERNS {"NAS100", "USTEC", "US100", "NDX100", "USTECH", "NASDAQ"}
#define RISKSTORE risk
''' + CORE + r'''
input int    RangeDays       = 20;     // days in the average 10:00-14:00 range

datetime doneDay = 0;
double AvgRange()
{
   double sum = 0; int n = 0; datetime cur = 0; double hi = 0, lo = 0; int bars = 0;
   datetime today = NYDate(NYNow());
   for(int i = 1; i < 24 * 45 && n < RangeDays; i++)
   {
      datetime t = iTime(Sym, PERIOD_H1, i); if(t == 0) break;
      datetime ny = ToNY(t); int h = NYHour(ny); datetime d = NYDate(ny);
      if(d >= today) continue;
      if(d != cur) { if(cur != 0 && bars == 4) { sum += hi - lo; n++; } cur = d; hi = 0; lo = DBL_MAX; bars = 0; }
      if(h >= 10 && h <= 13) { hi = MathMax(hi, iHigh(Sym, PERIOD_H1, i)); lo = MathMin(lo, iLow(Sym, PERIOD_H1, i)); bars++; }
   }
   return n >= 10 ? sum / n : 0;
}
void Setup()
{
   datetime ny = NYNow(); datetime d = NYDate(ny);
   if(doneDay == d) return;
   doneDay = d; GlobalVariableSet(GV("done"), (double)d);
   int dw = NYDow(ny); if(dw == 0 || dw == 6) return;
   int dir = TrendBias(); if(dir == 0) { Log("SKIP", Sym, "monthly and weekly bias disagree"); return; }
   double A = AvgRange(); if(A <= 0) { Log("SKIP", Sym, "not enough history for the average range"); return; }
   double o10 = iOpen(Sym, PERIOD_H1, 0), entry = o10 - dir * 0.25 * A, r = 0.5 * A, sl = entry - dir * r, tp = entry + dir * 2 * r;
   double ask = SymbolInfoDouble(Sym, SYMBOL_ASK), bid = SymbolInfoDouble(Sym, SYMBOL_BID), px = dir == 1 ? ask : bid;
   if(r <= 3 * (ask - bid)) { Log("SKIP", Sym, "range too small for the spread"); return; }
   double riskMoney = MathMin(StartBalance * RiskPct / 100.0, RiskRoom());
   double lots = LotsFor(riskMoney, r);
   if(lots <= 0) { Log("SKIP", Sym, StringFormat("no room or below minimum lot (room %.2f)", RiskRoom())); return; }
   trade.SetExpertMagicNumber(Magic); trade.SetTypeFillingBySymbol(Sym);
   bool ok; string how;
   if((px - entry) * dir <= 0) { ok = dir == 1 ? trade.Buy(lots, Sym, 0, Norm(sl), Norm(tp), "NY10") : trade.Sell(lots, Sym, 0, Norm(sl), Norm(tp), "NY10"); how = "market (already at the entry)"; }
   else { ok = dir == 1 ? trade.BuyLimit(lots, Norm(entry), Sym, Norm(sl), Norm(tp), ORDER_TIME_GTC, 0, "NY10") : trade.SellLimit(lots, Norm(entry), Sym, Norm(sl), Norm(tp), ORDER_TIME_GTC, 0, "NY10"); how = "limit"; }
   GlobalVariableSet(GV("entry"), entry); GlobalVariableSet(GV("r"), r); GlobalVariableSet(GV("dir"), dir);
   if(ok) Log("ORDER", Sym, StringFormat("%s; dir=%s; open10=%s; avg_range=%s; entry=%s; stop=%s; target=%s; lots=%.2f; risk_usd=%.2f", how, dir == 1 ? "buy" : "sell", P(o10), P(A), P(entry), P(sl), P(tp), lots, lots * r * MoneyPerPrice(Sym)));
   else Log("ERROR", Sym, StringFormat("order rejected: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()));
}
void Manage()
{
   datetime ny = NYNow(); int h = NYHour(ny);
   if(h >= 11) for(int i = OrdersTotal() - 1; i >= 0; i--) { ulong tk = OrderGetTicket(i); if(OrderSelect(tk) && Ours(OrderGetInteger(ORDER_MAGIC)) && trade.OrderDelete(tk)) Log("CANCEL", Sym, "not filled by 11:00 New York"); }
   if(h >= 14 || h < 10) { if(CountOurs() > 0) CloseTimed("14:00 New York time exit"); return; }
   double e = GlobalVariableGet(GV("entry")), r = GlobalVariableGet(GV("r"));
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk) || !Ours(PositionGetInteger(POSITION_MAGIC))) continue;
      int d = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      double op = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), px = d == 1 ? SymbolInfoDouble(Sym, SYMBOL_BID) : SymbolInfoDouble(Sym, SYMBOL_ASK);
      if(r > 0 && (px - op) * d >= 0.5 * r && (sl - op) * d < 0)
         if(trade.PositionModify(tk, Norm(op), PositionGetDouble(POSITION_TP))) Log("BREAKEVEN", Sym, "+0.5R reached: stop moved to the entry");
   }
}
int OnInit()
{
   if(!FindSymbol()) { Print("NY10: Nasdaq symbol not found. Set SymbolToTrade."); return INIT_FAILED; }
   halted = GlobalVariableCheck(GV("halt")) && GlobalVariableGet(GV("halt")) > 0;
   doneDay = (datetime)GlobalVariableGet(GV("done"));
   trade.SetDeviationInPoints(50);
   EventSetTimer(5);
   Log("START", Sym, StringFormat("start=%.0f; risk=%.2f%%; server_offset_h=%.1f", StartBalance, RiskPct, ServerOffset() / 3600.0));
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { EventKillTimer(); Comment(""); Log("STOP", Sym, Stats()); }
void OnTick() {}
void OnTimer()
{
   bool ok = Guard();
   if(MarketOpen())
   {
      Manage();
      if(ok && NYHour(NYNow()) == 10 && iTime(Sym, PERIOD_H1, 0) != 0 && NYHour(ToNY(iTime(Sym, PERIOD_H1, 0))) == 10) Setup();
   }
   if(ShowPanel) Comment(PanelCommon() + StringFormat("\nbias %d | today: %s", TrendBias(), doneDay == NYDate(NYNow()) ? "checked" : "waiting for 10:00 New York"));
}
//+------------------------------------------------------------------+
'''

GOLD = r'''//+------------------------------------------------------------------+
//|                                          FibFVG_GoldMidnight.mq5  |
//|  Cueto & Co. - Gold, one trade a day from the midnight New York   |
//|  open to 14:00 NY. Built for Goat Funded Trader Instant Premium.  |
//|                                                                  |
//|  Direction : monthly + weekly ranges agree AND yesterday's New    |
//|              York candle closed the same way. Otherwise no trade.|
//|  Entry     : market at 00:00 New York (Monday-Friday).           |
//|  Stop      : StopATR x daily ATR(14) (default 0.75), breakeven   |
//|              once the trade gains half the stop.                 |
//|  Exit      : time only, at 14:00 New York.                       |
//|  Size      : RiskPct is what the full stop costs; 0.9% stays      |
//|              inside GFT's 1% floating-loss limit.                |
//|  Also for silver: set SymbolToTrade (preset GFT_100K_Silver).    |
//|  Backtest Jul 2024 - Nov 2026, gold, 0.75 ATR + breakeven, 0.9%: |
//|  $8,451 paid on $100K in 5 payouts, no breach (not proven).      |
//|  Needs $10K+ (gold) / $15K+ (silver) for the 0.01-lot minimum.   |
//|  Run it on your own PC: GFT bans VPS, VPN and proxies.           |
//+------------------------------------------------------------------+
#property copyright "Cueto & Co."
#property version   "1.00"
#property strict
#define BOTNAME "GoldMidnight"
#define RISKDEFAULT 0.9
#define MAGICDEFAULT 7713100
#define PATTERNS {"XAUUSD", "GOLD."}
#define RISKSTORE risk
''' + CORE + r'''
input double StopATR     = 0.75;   // stop = this x daily ATR(14). Best on GFT rules 2024-26: gold 0.75, silver 0.75
input double BreakevenAt = 0.5;    // move the stop to entry once the trade gains this x the stop (0 = off)
datetime doneDay = 0;
double ATRd(int len)
{
   double a = 0; bool init = false;
   for(int k = len * 5 + 1; k >= 1; k--)
   {
      double c1 = iClose(Sym, PERIOD_D1, k + 1); if(c1 <= 0) continue;
      double tr = MathMax(iHigh(Sym, PERIOD_D1, k), c1) - MathMin(iLow(Sym, PERIOD_D1, k), c1);
      if(!init) { a = tr; init = true; } else a += (tr - a) / len;
   }
   return a;
}
int YesterdayDir()           // the last New York day before today that has candles (Sunday evening for Monday)
{
   datetime today = NYDate(NYNow()), dy = 0; double o = 0, c = 0;
   for(int i = 1; i < 24 * 5; i++)
   {
      datetime t = iTime(Sym, PERIOD_H1, i); if(t == 0) break;
      datetime d = NYDate(ToNY(t)); if(d >= today) continue;
      if(dy == 0) { dy = d; c = iClose(Sym, PERIOD_H1, i); }
      if(d != dy) break;
      o = iOpen(Sym, PERIOD_H1, i);
   }
   return c > o ? 1 : c < o ? -1 : 0;
}
void Setup()
{
   datetime ny = NYNow(); datetime d = NYDate(ny);
   if(doneDay == d) return;
   doneDay = d; GlobalVariableSet(GV("done"), (double)d);
   int dw = NYDow(ny); if(dw == 0 || dw == 6) return;
   int b = TrendBias(), y = YesterdayDir();
   if(b == 0 || b != y) { Log("SKIP", Sym, StringFormat("bias %d and yesterday %d do not agree", b, y)); return; }
   double A = ATRd(14); if(A <= 0) return;
   double ask = SymbolInfoDouble(Sym, SYMBOL_ASK), bid = SymbolInfoDouble(Sym, SYMBOL_BID), px = b == 1 ? ask : bid;
   if(0.5 * A <= 3 * (ask - bid)) { Log("SKIP", Sym, "spread too wide at midnight"); return; }
   double dist = StopATR * A, sl = px - b * dist;
   double riskMoney = MathMin(StartBalance * RiskPct / 100.0, RiskRoom());
   double lots = LotsFor(riskMoney, dist);
   if(lots <= 0) { Log("SKIP", Sym, StringFormat("no room or the 0.01-lot minimum risks more than %.2f (stop = %s)", riskMoney, P(dist))); return; }
   GlobalVariableSet(GV("r"), dist);
   trade.SetExpertMagicNumber(Magic); trade.SetTypeFillingBySymbol(Sym);
   bool ok = b == 1 ? trade.Buy(lots, Sym, 0, Norm(sl), 0, "GoldMidnight") : trade.Sell(lots, Sym, 0, Norm(sl), 0, "GoldMidnight");
   if(ok) Log("ORDER", Sym, StringFormat("market; dir=%s; atr=%s; stop=%s; lots=%.2f; stop_risk_usd=%.2f", b == 1 ? "buy" : "sell", P(A), P(sl), lots, lots * dist * MoneyPerPrice(Sym)));
   else Log("ERROR", Sym, StringFormat("order rejected: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()));
}
int OnInit()
{
   if(!FindSymbol()) { Print("GoldMidnight: gold symbol not found. Set SymbolToTrade."); return INIT_FAILED; }
   halted = GlobalVariableCheck(GV("halt")) && GlobalVariableGet(GV("halt")) > 0;
   doneDay = (datetime)GlobalVariableGet(GV("done"));
   trade.SetDeviationInPoints(50);
   EventSetTimer(5);
   Log("START", Sym, StringFormat("start=%.0f; risk=%.2f%%; server_offset_h=%.1f", StartBalance, RiskPct, ServerOffset() / 3600.0));
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { EventKillTimer(); Comment(""); Log("STOP", Sym, Stats()); }
void OnTick() {}
void OnTimer()
{
   bool ok = Guard();
   if(MarketOpen())
   {
      int h = NYHour(NYNow());
      if(h >= 14 && CountOurs() > 0) CloseTimed("14:00 New York time exit");
      double r = GlobalVariableGet(GV("r"));
      if(BreakevenAt > 0 && r > 0)
         for(int i = PositionsTotal() - 1; i >= 0; i--)
         {
            ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk) || !Ours(PositionGetInteger(POSITION_MAGIC))) continue;
            int d = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
            double op = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), px = d == 1 ? SymbolInfoDouble(Sym, SYMBOL_BID) : SymbolInfoDouble(Sym, SYMBOL_ASK);
            if((px - op) * d >= BreakevenAt * r && (sl - op) * d < 0 && trade.PositionModify(tk, Norm(op), 0)) Log("BREAKEVEN", Sym, "stop moved to the entry");
         }
      if(ok && h == 0) Setup();
   }
   if(ShowPanel) Comment(PanelCommon() + StringFormat("\nbias %d, yesterday %d | today: %s", TrendBias(), YesterdayDir(), doneDay == NYDate(NYNow()) ? "checked" : "waiting for 00:00 New York"));
}
//+------------------------------------------------------------------+
'''

# FibFVG_NY10 withdrawn 23 Nov 2026: its backtest edge came from a fill-candle bug (see fibfvg/falsify.py); not generated.
open(os.path.join(ROOT, "mql5", "FibFVG_GoldMidnight.mq5"), "w").write(GOLD)

PRESETS = {
    "GFT_50K_GoldMidnight.set": ("GoldMidnight - gold 00:00-14:00 NY, Goat Funded Trader Instant Premium $50K", 50000, 0.9, 7713100),
    "GFT_100K_GoldMidnight.set": ("GoldMidnight - gold 00:00-14:00 NY, Goat Funded Trader Instant Premium $100K", 100000, 0.9, 7713100),
    "GFT_100K_SilverMidnight.set": ("GoldMidnight EA on SILVER 00:00-14:00 NY, Goat Funded Trader Instant Premium $100K", 100000, 0.6, 7713200),
}
os.makedirs(os.path.join(ROOT, "presets", "gft"), exist_ok=True)
for name, (title, size, risk, magic) in PRESETS.items():
    lines = [f"; {title}", "; 6% intraday trailing (locks at the start), 3% daily from 17:00 New York, 1% floating limit, own PC only.",
             f"StartBalance={size}", f"RiskPct={risk}", "MaxLossPct=6", "TrailOnEquity=true", "DailyLossPct=3", "MaxOpenRiskPct=1",
             "GuardBufferPct=1", "SymbolToTrade=" + ("XAGUSD" if "Silver" in name else "AUTO"), "WriteLog=true", "ShowPanel=true", f"Magic={magic}"]
    if "Midnight" in name:
        lines += ["StopATR=0.75", "BreakevenAt=0.5"]
    open(os.path.join(ROOT, "presets", "gft", name), "w").write("\n".join(lines) + "\n")
print("written")

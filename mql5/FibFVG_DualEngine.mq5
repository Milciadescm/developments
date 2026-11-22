//+------------------------------------------------------------------+
//|                                          FibFVG_DualEngine.mq5   |
//|  Weekly swing engine  : MN1+W1 bias -> D1 Turtle breakout leg ->  |
//|                         OTE (0.705) limit, needs a D1 FVG in leg, |
//|                         TP1 -0.272 ext (50% off + BE),            |
//|                         TP2 -0.618 ext, runner trails Turtle 20d, |
//|                         Turtle pyramid +1 unit / 0.5N, max 4.     |
//|  Micro engine         : W1 bias -> H4 FVG + displacement ->       |
//|                         OTE limit (<= FVG top), TP -0.618 ext.    |
//|  Optional experimental: seconds-bar FVG scalper for US500 built   |
//|                         from ticks (15/30/45s). NOT backtested.   |
//|  Attach ONE chart per symbol (any timeframe). Unique MagicBase.   |
//+------------------------------------------------------------------+
#property copyright "FibFVG Dual Engine"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//--- engines
input bool   UseWeeklyEngine     = true;
input bool   UseMicroEngine      = true;
input bool   UseSecondsScalper   = false;   // EXPERIMENTAL, forward-test on demo only
//--- money management (fraction of equity at risk per trade / unit)
input double WeeklyUnitRiskPct   = 0.50;    // % per Turtle unit (personal acct). Prop: 0.10-0.25
input double MicroRiskPct        = 0.25;    // % per 4H micro trade.              Prop: 0.10
input double ScalpRiskPct        = 0.10;    // % per seconds scalp
input double MaxOpenRiskPct      = 6.0;     // cap on sum of open stop-risk
input int    MaxUnitsPerSymbol   = 4;       // Turtle
input bool   SkipIfBelowMinLot   = true;    // never oversize to reach min lot
//--- prop-firm guard (set to your account's real rules; 0 = off)
input double DailyLossLimitPct   = 3.0;
input double MaxLossLimitPct     = 6.0;
input bool   TrailingMaxLoss     = true;
//--- Fibonacci / Turtle parameters
input double OTE_Entry           = 0.705;
input double Ext_TP1             = 0.272;
input double Ext_TP2             = 0.618;
input int    BreakoutLen         = 20;
input int    ExitLen             = 20;
input int    AtrLen              = 20;
input double PyramidStepN        = 0.5;
input double AddStopN            = 2.0;
input int    SetupExpiryDays     = 15;
input double MicroDispATR        = 0.8;
input int    MicroExpiryBars     = 6;
input int    MicroMaxHoldBars    = 30;
input double MicroMinRR          = 1.0;
//--- seconds scalper
input int    ScalpSeconds        = 30;      // 15, 30 or 45
input double ScalpRR             = 1.618;
input int    ScalpExpirySec      = 180;
//--- misc
input long   MagicBase           = 7705618;

long MW, MWA, MM, MS;                       // magics: weekly, weekly add, micro, scalp
datetime lastD1 = 0, lastH4 = 0;
double   g_tp1 = 0, g_entryW = 0, g_lastAdd = 0, g_N = 0;  bool g_tp1Done = false;
double   dayStartEq = 0, peakEq = 0, startBal = 0; int curDay = -1; bool halted = false;

//+------------------------------------------------------------------+
int OnInit()
{
   MW = MagicBase; MWA = MagicBase + 1; MM = MagicBase + 2; MS = MagicBase + 3;
   startBal = AccountInfoDouble(ACCOUNT_BALANCE);
   peakEq = AccountInfoDouble(ACCOUNT_EQUITY);
   dayStartEq = peakEq;
   trade.SetDeviationInPoints(30);
   return(INIT_SUCCEEDED);
}

//------------------------------------------------------------------ utils
double Hi(ENUM_TIMEFRAMES tf, int s) { return iHigh(_Symbol, tf, s); }
double Lo(ENUM_TIMEFRAMES tf, int s) { return iLow(_Symbol, tf, s); }
double Op(ENUM_TIMEFRAMES tf, int s) { return iOpen(_Symbol, tf, s); }
double Cl(ENUM_TIMEFRAMES tf, int s) { return iClose(_Symbol, tf, s); }

double HighestH(ENUM_TIMEFRAMES tf, int from, int count)
{ int i = iHighest(_Symbol, tf, MODE_HIGH, count, from); return i < 0 ? 0 : Hi(tf, i); }
double LowestL(ENUM_TIMEFRAMES tf, int from, int count)
{ int i = iLowest(_Symbol, tf, MODE_LOW, count, from); return i < 0 ? 0 : Lo(tf, i); }

double WilderATR(ENUM_TIMEFRAMES tf, int len, int shift)
{
   int bars = len * 5;
   double a = 0; bool init = false;
   for(int s = shift + bars; s >= shift; s--)
   {
      double tr = MathMax(Hi(tf, s), Cl(tf, s + 1)) - MathMin(Lo(tf, s), Cl(tf, s + 1));
      if(!init) { a = tr; init = true; } else a = a + (tr - a) / len;
   }
   return a;
}

// premium / discount bias of a dealing range using completed bars only
int RangeBias(ENUM_TIMEFRAMES tf, int lookback)
{
   double mid = (HighestH(tf, 1, lookback) + LowestL(tf, 1, lookback)) / 2.0;
   double c = Cl(tf, 1);
   return c > mid ? 1 : (c < mid ? -1 : 0);
}
int WeeklyBias()  { return RangeBias(PERIOD_W1, 4); }
int MonthlyBias() { return RangeBias(PERIOD_MN1, 6); }

double NormPrice(double p) { return NormalizeDouble(p, _Digits); }

double LotsForRisk(double riskPct, double stopDist)
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(tv <= 0 || ts <= 0 || stopDist <= 0) return 0;
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * riskPct / 100.0;
   double perLot = stopDist / ts * tv;
   double lots = MathFloor(riskMoney / perLot / step) * step;
   if(lots < vmin) return SkipIfBelowMinLot ? 0 : vmin;
   return MathMin(lots, vmax);
}

double OpenRiskMoney()
{
   double total = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      long mg = PositionGetInteger(POSITION_MAGIC); if(mg < MagicBase || mg > MagicBase + 3) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      double sl = PositionGetDouble(POSITION_SL), op = PositionGetDouble(POSITION_PRICE_OPEN);
      if(sl <= 0) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      double dist = (type == POSITION_TYPE_BUY) ? op - sl : sl - op;
      if(dist <= 0) continue;
      double tv = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE_LOSS), ts = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
      total += dist / ts * tv * PositionGetDouble(POSITION_VOLUME);
   }
   return total;
}

bool RiskAllows(double lots, double stopDist)
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double newRisk = stopDist / ts * tv * lots;
   return OpenRiskMoney() + newRisk <= AccountInfoDouble(ACCOUNT_EQUITY) * MaxOpenRiskPct / 100.0;
}

int CountPositions(long magic)
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic) n++; }
   return n;
}
int CountOrders(long magic)
{
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   { ulong tk = OrderGetTicket(i); if(OrderSelect(tk) && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == magic) n++; }
   return n;
}
void DeleteOrders(long magic)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   { ulong tk = OrderGetTicket(i); if(OrderSelect(tk) && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == magic) trade.OrderDelete(tk); }
}
void CloseAll()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   { ulong tk = PositionGetTicket(i); if(PositionSelectByTicket(tk)) { long mg = PositionGetInteger(POSITION_MAGIC); if(mg >= MagicBase && mg <= MagicBase + 3) trade.PositionClose(tk); } }
   for(long m = MagicBase; m <= MagicBase + 3; m++) DeleteOrders(m);
}

//------------------------------------------------------------------ prop guard
bool GuardOK()
{
   if(halted) return false;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(t.day_of_year != curDay) { curDay = t.day_of_year; dayStartEq = MathMax(eq, AccountInfoDouble(ACCOUNT_BALANCE)); }
   peakEq = MathMax(peakEq, eq);
   if(DailyLossLimitPct > 0 && dayStartEq - eq >= startBal * DailyLossLimitPct / 100.0 * 0.9)
   { CloseAll(); Print("Guard: daily loss buffer reached - flat until tomorrow"); return false; }
   double ref = TrailingMaxLoss ? peakEq : startBal;
   if(MaxLossLimitPct > 0 && ref - eq >= startBal * MaxLossLimitPct / 100.0 * 0.9)
   { CloseAll(); halted = true; Print("Guard: max-loss buffer reached - EA halted"); return false; }
   return true;
}

//------------------------------------------------------------------ weekly engine
bool LegHasFVG(int dir, int fromShift, int toShift)   // shifts on D1, fromShift > toShift
{
   for(int s = fromShift - 2; s >= toShift; s--)
   {
      if(dir == 1  && Lo(PERIOD_D1, s) > Hi(PERIOD_D1, s + 2)) return true;
      if(dir == -1 && Hi(PERIOD_D1, s) < Lo(PERIOD_D1, s + 2)) return true;
   }
   return false;
}

void WeeklyNewBar()
{
   int dir = WeeklyBias();
   if(dir == 0 || dir != MonthlyBias()) return;
   if(CountPositions(MW) + CountPositions(MWA) > 0) return;
   double N = WilderATR(PERIOD_D1, AtrLen, 1);
   int L = BreakoutLen;
   bool brk = dir == 1 ? Hi(PERIOD_D1, 1) >= HighestH(PERIOD_D1, 2, L)
                       : Lo(PERIOD_D1, 1) <= LowestL(PERIOD_D1, 2, L);
   if(!brk) return;
   int ext = dir == 1 ? iLowest(_Symbol, PERIOD_D1, MODE_LOW, L, 1) : iHighest(_Symbol, PERIOD_D1, MODE_HIGH, L, 1);
   double origin = dir == 1 ? Lo(PERIOD_D1, ext) : Hi(PERIOD_D1, ext);
   double extreme = dir == 1 ? Hi(PERIOD_D1, 1) : Lo(PERIOD_D1, 1);
   double rng = MathAbs(extreme - origin);
   if(rng < 1.5 * N || !LegHasFVG(dir, ext, 1)) return;
   double entry = extreme - dir * OTE_Entry * rng;
   double sl    = origin - dir * 0.25 * N;
   double tp2   = extreme + dir * Ext_TP2 * rng;
   g_tp1 = extreme + dir * Ext_TP1 * rng; g_entryW = entry; g_N = N; g_tp1Done = false; g_lastAdd = entry;
   double lots = LotsForRisk(WeeklyUnitRiskPct, MathAbs(entry - sl));
   if(lots <= 0 || !RiskAllows(lots, MathAbs(entry - sl))) return;
   DeleteOrders(MW);   // a fresh breakout replaces the older setup (leg extended)
   trade.SetExpertMagicNumber(MW);
   datetime exp = TimeCurrent() + SetupExpiryDays * 86400;
   if(dir == 1) trade.BuyLimit(lots, NormPrice(entry), _Symbol, NormPrice(sl), NormPrice(tp2), ORDER_TIME_SPECIFIED, exp, "FibW");
   else         trade.SellLimit(lots, NormPrice(entry), _Symbol, NormPrice(sl), NormPrice(tp2), ORDER_TIME_SPECIFIED, exp, "FibW");
}

void WeeklyManage()
{
   double trailL = LowestL(PERIOD_D1, 1, ExitLen), trailH = HighestH(PERIOD_D1, 1, ExitLen);
   int mainDir = 0; double mainTP = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      long mg = PositionGetInteger(POSITION_MAGIC); if(mg != MW && mg != MWA) continue;
      int d = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      double sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP), op = PositionGetDouble(POSITION_PRICE_OPEN);
      double px = d == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(mg == MW)
      {
         mainDir = d; mainTP = tp;
         if(!g_tp1Done && g_tp1 > 0 && (d == 1 ? px >= g_tp1 : px <= g_tp1))
         {
            double half = MathFloor(PositionGetDouble(POSITION_VOLUME) / 2 / SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)) * SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
            if(half >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)) trade.PositionClosePartial(tk, half);
            g_tp1Done = true;
            sl = d == 1 ? MathMax(sl, op) : MathMin(sl, op);
         }
      }
      double nsl = d == 1 ? MathMax(sl, trailL) : MathMin(sl == 0 ? DBL_MAX : sl, trailH);  // Turtle 20-day exit
      if(MathAbs(nsl - sl) > _Point && (d == 1 ? nsl < px : nsl > px)) trade.PositionModify(tk, NormPrice(nsl), tp);
   }
   // Turtle pyramid: +1 unit every 0.5N, max units, adds use 2N stop and share TP2
   if(mainDir != 0 && g_N > 0)
   {
      int units = CountPositions(MW) + CountPositions(MWA);
      double px = mainDir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double nxt = g_lastAdd + mainDir * PyramidStepN * g_N;
      if(units < MaxUnitsPerSymbol && (mainDir == 1 ? px >= nxt : px <= nxt) && (mainDir == 1 ? px < mainTP : px > mainTP))
      {
         double sl = px - mainDir * AddStopN * g_N;
         double lots = LotsForRisk(WeeklyUnitRiskPct, AddStopN * g_N);
         if(lots > 0 && RiskAllows(lots, AddStopN * g_N))
         {
            trade.SetExpertMagicNumber(MWA);
            bool ok = mainDir == 1 ? trade.Buy(lots, _Symbol, 0, NormPrice(sl), mainTP, "FibW+")
                                   : trade.Sell(lots, _Symbol, 0, NormPrice(sl), mainTP, "FibW+");
            if(ok) g_lastAdd = nxt;
         }
      }
   }
   else if(CountPositions(MWA) > 0 && CountPositions(MW) == 0) { /* adds keep their own 2N / 20d stops */ }
}

//------------------------------------------------------------------ micro engine (H4)
void MicroNewBar()
{
   // time exit
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i); if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != MM) continue;
      if(TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) >= MicroMaxHoldBars * 4 * 3600) trade.PositionClose(tk);
   }
   if(CountPositions(MM) > 0 || CountOrders(MM) > 0) return;
   int dir = WeeklyBias(); if(dir == 0) return;
   double a = WilderATR(PERIOD_H4, 14, 2);
   double h1 = Hi(PERIOD_H4, 1), l1 = Lo(PERIOD_H4, 1), h3 = Hi(PERIOD_H4, 3), l3 = Lo(PERIOD_H4, 3);
   bool disp = (Hi(PERIOD_H4, 2) - Lo(PERIOD_H4, 2)) > MicroDispATR * a && (Cl(PERIOD_H4, 2) - Op(PERIOD_H4, 2)) * dir > 0;
   bool fvg = dir == 1 ? l1 > h3 : h1 < l3;
   if(!disp || !fvg) return;
   double origin = dir == 1 ? LowestL(PERIOD_H4, 2, 5) : HighestH(PERIOD_H4, 2, 5);
   double extreme = dir == 1 ? h1 : l1;
   double rng = MathAbs(extreme - origin);
   double entry = extreme - dir * OTE_Entry * rng;
   entry = dir == 1 ? MathMin(entry, l1) : MathMax(entry, h1);
   double sl = origin - dir * 0.1 * a;
   double tp = extreme + dir * Ext_TP2 * rng;
   double risk = MathAbs(entry - sl);
   if(risk <= 0 || MathAbs(tp - entry) / risk < MicroMinRR) return;
   double lots = LotsForRisk(MicroRiskPct, risk);
   if(lots <= 0 || !RiskAllows(lots, risk)) return;
   trade.SetExpertMagicNumber(MM);
   datetime exp = TimeCurrent() + MicroExpiryBars * 4 * 3600;
   if(dir == 1) trade.BuyLimit(lots, NormPrice(entry), _Symbol, NormPrice(sl), NormPrice(tp), ORDER_TIME_SPECIFIED, exp, "FibM");
   else         trade.SellLimit(lots, NormPrice(entry), _Symbol, NormPrice(sl), NormPrice(tp), ORDER_TIME_SPECIFIED, exp, "FibM");
}

//------------------------------------------------------------------ seconds scalper (experimental)
struct SBar { double o, h, l, c; datetime t; };
SBar sb[3]; SBar cur; int sbCount = 0; datetime curStart = 0;

void ScalperTick()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   datetime now = TimeCurrent();
   datetime slot = now - (now % ScalpSeconds);
   if(curStart == 0) { curStart = slot; cur.o = cur.h = cur.l = cur.c = bid; cur.t = slot; return; }
   if(slot != curStart)
   {
      sb[0] = sb[1]; sb[1] = sb[2]; sb[2] = cur; sbCount++;
      curStart = slot; cur.o = cur.h = cur.l = cur.c = bid; cur.t = slot;
      if(sbCount >= 3) ScalperSignal();
   }
   else { cur.h = MathMax(cur.h, bid); cur.l = MathMin(cur.l, bid); cur.c = bid; }
}

void ScalperSignal()
{
   if(CountPositions(MS) > 0 || CountOrders(MS) > 0) return;
   int dir = WeeklyBias(); if(dir == 0) return;
   // FVG among the last 3 completed seconds-bars, aligned with weekly bias
   bool bull = sb[2].l > sb[0].h && sb[1].c > sb[1].o;
   bool bear = sb[2].h < sb[0].l && sb[1].c < sb[1].o;
   if(!((dir == 1 && bull) || (dir == -1 && bear))) return;
   double entry = dir == 1 ? (sb[2].l + sb[0].h) / 2 : (sb[2].h + sb[0].l) / 2;   // consequent encroachment
   double sl = dir == 1 ? sb[0].l : sb[0].h;
   double risk = MathAbs(entry - sl);
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(risk <= 3 * spread) return;     // gap too small vs costs
   double tp = entry + dir * ScalpRR * risk;
   double lots = LotsForRisk(ScalpRiskPct, risk);
   if(lots <= 0 || !RiskAllows(lots, risk)) return;
   trade.SetExpertMagicNumber(MS);
   datetime exp = TimeCurrent() + ScalpExpirySec;
   if(dir == 1) trade.BuyLimit(lots, NormPrice(entry), _Symbol, NormPrice(sl), NormPrice(tp), ORDER_TIME_SPECIFIED, exp, "FibS");
   else         trade.SellLimit(lots, NormPrice(entry), _Symbol, NormPrice(sl), NormPrice(tp), ORDER_TIME_SPECIFIED, exp, "FibS");
}

//------------------------------------------------------------------ main
void OnTick()
{
   if(!GuardOK()) return;
   if(UseWeeklyEngine) WeeklyManage();
   datetime d1 = iTime(_Symbol, PERIOD_D1, 0);
   if(d1 != lastD1) { lastD1 = d1; if(UseWeeklyEngine) WeeklyNewBar(); }
   datetime h4 = iTime(_Symbol, PERIOD_H4, 0);
   if(h4 != lastH4) { lastH4 = h4; if(UseMicroEngine) MicroNewBar(); }
   if(UseSecondsScalper) ScalperTick();
}
//+------------------------------------------------------------------+

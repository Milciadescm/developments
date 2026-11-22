"""Configuration for the Fib-FVG Dual Engine.

Contract specs are typical MT5 CFD specs (FundedNext-style). VERIFY them in
your broker's Market Watch -> Symbol -> Specification before going live:
contract size, min lot and lot step differ between brokers and change the
small-account results a lot.
"""
from dataclasses import dataclass, field

# Fibonacci ratios. 0.618 is the limit of F(n-1)/F(n) -- the same recursion the
# 1s-and-2s video shows (13 = 8 + 5, "21212212" = "21212" + "212").
FIB_OTE_LOW = 0.618      # shallow edge of the Optimal Trade Entry zone
FIB_OTE_MID = 0.705      # entry level (ICT "sweet spot")
FIB_OTE_HIGH = 0.786     # deep edge of the OTE zone
FIB_EXT_1 = 0.272        # TP1 = leg extreme + 0.272 * leg  (the -0.272 extension)
FIB_EXT_2 = 0.618        # TP2 = leg extreme + 0.618 * leg  (the -0.618 extension)


@dataclass
class SymbolSpec:
    name: str
    contract: float      # P&L in USD per 1.0 price move per 1.00 lot
    min_lot: float
    lot_step: float
    max_lot: float       # per-order cap (liquidity / broker limit)
    spread: float        # round-trip cost in price units (spread + slippage)
    group: str           # correlation group for Turtle portfolio caps


SYMBOLS = {
    "XAUUSD": SymbolSpec("XAUUSD", 100.0, 0.01, 0.01, 50.0, 0.35, "metals"),
    "XAGUSD": SymbolSpec("XAGUSD", 5000.0, 0.01, 0.01, 50.0, 0.035, "metals"),
    "BTCUSD": SymbolSpec("BTCUSD", 1.0, 0.01, 0.01, 50.0, 40.0, "crypto"),
    "US500":  SymbolSpec("US500", 1.0, 0.01, 0.01, 500.0, 0.7, "indices"),
    "NAS100": SymbolSpec("NAS100", 1.0, 0.01, 0.01, 500.0, 2.0, "indices"),
}


@dataclass
class RiskConfig:
    weekly_unit_risk: float = 0.005   # 0.5% of equity per Turtle unit (swing engine)
    micro_risk: float = 0.010         # 1.0% per micro trade ("higher lot size")
    max_units_per_symbol: int = 4     # Turtle rule
    max_units_per_group: int = 6      # Turtle rule: closely correlated markets
    max_open_risk: float = 0.06       # total open risk cap (sum of stop distances)
    skip_if_below_min_lot: bool = True  # sound MM: never oversize to reach min lot
    # Prop-firm guard (set for the $50k account). Values are CONFIGURABLE --
    # check FundedNext's current rules for your exact account type.
    daily_loss_limit: float | None = None
    max_loss_limit: float | None = None
    trailing_max_loss: bool = True


@dataclass
class EngineConfig:
    # Weekly (swing) engine -- Monthly/Weekly bias, Daily execution, Turtle rules
    breakout_len: int = 20         # Turtle System 1 breakout defines the impulse leg
    exit_len: int = 20             # Turtle System 2 exit (opposite 20-day extreme)
    atr_len: int = 20              # Turtle "N"
    pyramid_step_n: float = 0.5    # add a unit every 0.5N in favour
    add_stop_n: float = 2.0        # 2N stop on adds
    setup_expiry_bars: int = 15    # cancel unfilled OTE order after 15 days
    # Micro (intraday) engine -- Daily bias, 4H FVG execution
    micro_expiry_bars: int = 6     # 6 x 4H = 1 day
    micro_max_hold_bars: int = 30  # 5 days
    micro_min_rr: float = 1.0
    micro_disp_atr: float = 0.8   # displacement candle range >= 0.8 x ATR(14, 4H)
    weekly_trade_start: str = "2005-01-01"
    extra: dict = field(default_factory=dict)


CAPITAL_TIERS = [50, 100, 150, 200, 300, 500, 1000, 2500, 50000]

"""
Pydantic 请求/响应模型
"""

from pydantic import BaseModel
from typing import Optional


# ==================== Overview ====================

class PositionInfo(BaseModel):
    symbol: str
    side: str
    amount: float
    entry_price: float
    unrealized_pnl: float
    mark_price: float


class RiskStatusResponse(BaseModel):
    current_equity: float
    peak_equity: float
    drawdown_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    trades_today: int
    consecutive_losses: int
    is_halted: bool
    halt_reason: str


class OverviewResponse(BaseModel):
    equity: float
    free_usdt: float
    positions: list[PositionInfo]
    daily_pnl: float
    daily_pnl_pct: float
    risk_status: Optional[RiskStatusResponse] = None


# ==================== Market ====================

class OHLCVBar(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorData(BaseModel):
    atr: list[Optional[float]]
    rsi: list[Optional[float]]
    macd_line: list[Optional[float]]
    signal_line: list[Optional[float]]
    histogram: list[Optional[float]]
    bb_upper: list[Optional[float]]
    bb_middle: list[Optional[float]]
    bb_lower: list[Optional[float]]


class OHLCVResponse(BaseModel):
    symbol: str
    timeframe: str
    candles: list[OHLCVBar]
    indicators: Optional[IndicatorData] = None


class TickerResponse(BaseModel):
    symbol: str
    last: float
    bid: float
    ask: float
    volume_24h: float
    change_24h_pct: float


class OrderBookResponse(BaseModel):
    bids: list[list[float]]
    asks: list[list[float]]
    spread: float
    mid_price: float


# ==================== Strategy ====================

class StrategyInfo(BaseModel):
    name: str
    description: str
    default_params: dict
    is_active: bool


class SignalPoint(BaseModel):
    timestamp: int
    signal: int
    price: float


class StrategySignalsResponse(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str
    signals: list[SignalPoint]


# ==================== Backtest ====================

class BacktestRequest(BaseModel):
    strategy_name: str
    symbol: str = "BTC/USDT"
    timeframe: str = "4h"
    initial_capital: float = 100000.0
    maker_fee: float = 0.001
    taker_fee: float = 0.001
    slippage_pct: float = 0.0001
    stop_loss_atr_mult: float = 2.0
    take_profit_atr_mult: float = 4.0
    strategy_params: dict = {}
    since: Optional[str] = None
    until: Optional[str] = None


class BacktestSummary(BaseModel):
    initial_capital: float
    final_equity: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate_pct: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    total_fees: float


class EquityCurvePoint(BaseModel):
    timestamp: int
    equity: float
    cash: float
    position_value: float


class TradeLogEntry(BaseModel):
    timestamp: int
    side: str
    price: float
    amount: float
    fee: float
    pnl: float


class BacktestResponse(BaseModel):
    summary: BacktestSummary
    equity_curve: list[EquityCurvePoint]
    trade_log: list[TradeLogEntry]


# ==================== Risk ====================

class RiskConfigResponse(BaseModel):
    max_daily_loss_pct: float
    max_drawdown_pct: float
    max_position_pct: float
    max_single_loss_pct: float
    max_trades_per_day: int
    max_consecutive_losses: int


# ==================== Settings ====================

class SettingsResponse(BaseModel):
    exchange: dict
    strategy: dict
    risk: dict
    fees: dict
    logging: dict


class SettingsUpdateRequest(BaseModel):
    strategy: Optional[dict] = None
    risk: Optional[dict] = None
    fees: Optional[dict] = None
    logging: Optional[dict] = None


# ==================== Environment Config ====================


class EnvConfigResponse(BaseModel):
    api_key_configured: bool
    api_key_masked: str
    api_secret_configured: bool
    api_secret_masked: str
    use_testnet: bool
    connection_status: str
    connection_error: Optional[str] = None


class EnvConfigUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    use_testnet: Optional[bool] = None

/* ── Risk ── */

export interface RiskStatusResponse {
  current_equity: number;
  peak_equity: number;
  drawdown_pct: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  trades_today: number;
  consecutive_losses: number;
  is_halted: boolean;
  halt_reason: string | null;
}

export interface RiskConfigResponse {
  max_daily_loss_pct: number;
  max_drawdown_pct: number;
  max_position_pct: number;
  max_single_loss_pct: number;
  max_trades_per_day: number;
  max_consecutive_losses: number;
}

/* ── Positions / Overview ── */

export interface PositionInfo {
  symbol: string;
  side: string;
  amount: number;
  entry_price: number;
  unrealized_pnl: number;
  mark_price: number;
}

export interface OverviewResponse {
  equity: number;
  free_usdt: number;
  positions: PositionInfo[];
  daily_pnl: number;
  daily_pnl_pct: number;
  risk_status: RiskStatusResponse | null;
}

/* ── Market ── */

export interface OHLCVBar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface IndicatorData {
  atr: (number | null)[];
  rsi: (number | null)[];
  macd_line: (number | null)[];
  signal_line: (number | null)[];
  histogram: (number | null)[];
  bb_upper: (number | null)[];
  bb_middle: (number | null)[];
  bb_lower: (number | null)[];
}

export interface OHLCVResponse {
  symbol: string;
  timeframe: string;
  candles: OHLCVBar[];
  indicators: IndicatorData | null;
}

export interface TickerResponse {
  symbol: string;
  last: number;
  bid: number;
  ask: number;
  volume_24h: number;
  change_24h_pct: number;
}

export interface OrderBookResponse {
  bids: number[][];
  asks: number[][];
  spread: number;
  mid_price: number;
}

/* ── Strategies ── */

export interface StrategyInfo {
  name: string;
  description: string;
  default_params: Record<string, unknown>;
  is_active: boolean;
}

export interface SignalPoint {
  timestamp: number;
  signal: string;
  price: number;
}

export interface StrategySignalsResponse {
  strategy_name: string;
  symbol: string;
  timeframe: string;
  signals: SignalPoint[];
}

/* ── Backtest ── */

export interface BacktestRequest {
  strategy_name: string;
  symbol: string;
  timeframe: string;
  initial_capital: number;
  maker_fee: number;
  taker_fee: number;
  slippage_pct: number;
  stop_loss_atr_mult: number;
  take_profit_atr_mult: number;
  strategy_params: Record<string, unknown>;
  since?: string;
  until?: string;
}

export interface BacktestSummary {
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
  win_rate_pct: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  total_fees: number;
}

export interface EquityCurvePoint {
  timestamp: number;
  equity: number;
  cash: number;
  position_value: number;
}

export interface TradeLogEntry {
  timestamp: number;
  side: string;
  price: number;
  amount: number;
  fee: number;
  pnl: number;
}

export interface BacktestResponse {
  summary: BacktestSummary;
  equity_curve: EquityCurvePoint[];
  trade_log: TradeLogEntry[];
}

/* ── Settings ── */

export interface SettingsResponse {
  exchange: Record<string, unknown>;
  strategy: Record<string, unknown>;
  risk: Record<string, unknown>;
  fees: Record<string, unknown>;
  logging: Record<string, unknown>;
}

/* ── Environment Config ── */

export interface EnvConfigResponse {
  api_key_configured: boolean;
  api_key_masked: string;
  api_secret_configured: boolean;
  api_secret_masked: string;
  use_testnet: boolean;
  connection_status: "connected" | "disconnected" | "error";
  connection_error: string | null;
}

export interface EnvConfigUpdateRequest {
  api_key?: string;
  api_secret?: string;
  use_testnet?: boolean;
}

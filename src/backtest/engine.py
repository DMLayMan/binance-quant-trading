"""
回测引擎

事件驱动的回测框架，支持：
- 多策略回测
- 滑点和手续费模拟
- 逐K线交易模拟
- 详细的绩效报告
"""

import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """单笔交易记录"""
    timestamp: pd.Timestamp
    side: str           # 'buy' or 'sell'
    price: float
    amount: float
    fee: float
    pnl: float = 0.0    # 平仓时填入


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 100_000.0
    maker_fee: float = 0.001       # 0.1%
    taker_fee: float = 0.001       # 0.1%
    slippage_pct: float = 0.0001   # 0.01%
    max_position_pct: float = 0.3  # 最大仓位占比
    risk_per_trade_pct: float = 0.01


class BacktestEngine:
    """
    回测引擎

    用法:
        engine = BacktestEngine(config)
        result = engine.run(df, signal_func, **signal_params)
        result.summary()
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        df: pd.DataFrame,
        signal_func: Callable[..., pd.Series],
        stop_loss_atr_mult: float = 2.0,
        take_profit_atr_mult: float = 4.0,
        **signal_kwargs,
    ) -> "BacktestResult":
        """
        执行回测

        Args:
            df: OHLCV DataFrame（需要 open/high/low/close/volume 列）
            signal_func: 信号生成函数，接收 df 和 **kwargs，返回 pd.Series
            stop_loss_atr_mult: 止损 ATR 倍数
            take_profit_atr_mult: 止盈 ATR 倍数
            **signal_kwargs: 传给 signal_func 的额外参数

        Returns:
            BacktestResult
        """
        cfg = self.config
        capital = cfg.initial_capital
        position = 0.0
        entry_price = 0.0
        trades: list[Trade] = []
        equity_curve = []

        # 计算 ATR
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        # 生成信号
        signals = signal_func(df, **signal_kwargs)

        for i in range(1, len(df)):
            ts = df.index[i]
            price = float(df["close"].iloc[i])
            high = float(df["high"].iloc[i])
            low = float(df["low"].iloc[i])
            current_atr = float(atr.iloc[i]) if not np.isnan(atr.iloc[i]) else 0
            signal = int(signals.iloc[i]) if i < len(signals) else 0

            # 检查止损止盈 (用 high/low 模拟盘中触发)
            if position > 0 and entry_price > 0 and current_atr > 0:
                sl = entry_price - stop_loss_atr_mult * current_atr
                tp = entry_price + take_profit_atr_mult * current_atr
                if low <= sl:
                    exit_price = self._apply_slippage(sl, is_buy=False)
                    fee = exit_price * position * cfg.taker_fee
                    pnl = (exit_price - entry_price) * position - fee
                    trades.append(Trade(ts, "sell", exit_price, position, fee, pnl))
                    capital += exit_price * position - fee
                    position = 0.0
                    entry_price = 0.0
                elif high >= tp:
                    exit_price = self._apply_slippage(tp, is_buy=False)
                    fee = exit_price * position * cfg.taker_fee
                    pnl = (exit_price - entry_price) * position - fee
                    trades.append(Trade(ts, "sell", exit_price, position, fee, pnl))
                    capital += exit_price * position - fee
                    position = 0.0
                    entry_price = 0.0

            elif position < 0 and entry_price > 0 and current_atr > 0:
                sl = entry_price + stop_loss_atr_mult * current_atr
                tp = entry_price - take_profit_atr_mult * current_atr
                if high >= sl:
                    exit_price = self._apply_slippage(sl, is_buy=True)
                    fee = exit_price * abs(position) * cfg.taker_fee
                    pnl = (entry_price - exit_price) * abs(position) - fee
                    trades.append(Trade(ts, "buy", exit_price, abs(position), fee, pnl))
                    capital += pnl
                    position = 0.0
                    entry_price = 0.0
                elif low <= tp:
                    exit_price = self._apply_slippage(tp, is_buy=True)
                    fee = exit_price * abs(position) * cfg.taker_fee
                    pnl = (entry_price - exit_price) * abs(position) - fee
                    trades.append(Trade(ts, "buy", exit_price, abs(position), fee, pnl))
                    capital += pnl
                    position = 0.0
                    entry_price = 0.0

            # 根据信号开仓
            if signal == 1 and position <= 0:
                # 先平空仓
                if position < 0:
                    cover_price = self._apply_slippage(price, is_buy=True)
                    fee = cover_price * abs(position) * cfg.taker_fee
                    pnl = (entry_price - cover_price) * abs(position) - fee
                    trades.append(Trade(ts, "buy", cover_price, abs(position), fee, pnl))
                    capital += pnl
                    position = 0.0

                # 计算仓位
                if current_atr > 0:
                    risk_amount = capital * cfg.risk_per_trade_pct
                    stop_distance = stop_loss_atr_mult * current_atr
                    risk_size = risk_amount / stop_distance
                    max_size = (capital * cfg.max_position_pct) / price
                    size = min(risk_size, max_size)
                else:
                    size = (capital * cfg.max_position_pct) / price

                buy_price = self._apply_slippage(price, is_buy=True)
                fee = buy_price * size * cfg.taker_fee
                cost = buy_price * size + fee
                if cost <= capital:
                    trades.append(Trade(ts, "buy", buy_price, size, fee))
                    capital -= cost
                    position = size
                    entry_price = buy_price

            elif signal == -1 and position > 0:
                sell_price = self._apply_slippage(price, is_buy=False)
                fee = sell_price * position * cfg.taker_fee
                pnl = (sell_price - entry_price) * position - fee
                trades.append(Trade(ts, "sell", sell_price, position, fee, pnl))
                capital += sell_price * position - fee
                position = 0.0
                entry_price = 0.0

            # 记录权益
            mark_value = position * price if position > 0 else 0
            equity_curve.append({
                "timestamp": ts,
                "equity": capital + mark_value,
                "cash": capital,
                "position_value": mark_value,
            })

        return BacktestResult(
            config=cfg,
            trades=trades,
            equity_curve=pd.DataFrame(equity_curve).set_index("timestamp"),
        )

    def _apply_slippage(self, price: float, is_buy: bool) -> float:
        """应用滑点"""
        slip = self.config.slippage_pct
        return price * (1 + slip) if is_buy else price * (1 - slip)


@dataclass
class BacktestResult:
    """回测结果"""
    config: BacktestConfig
    trades: list[Trade]
    equity_curve: pd.DataFrame

    def summary(self) -> dict:
        """计算回测绩效指标"""
        if self.equity_curve.empty:
            return {"error": "No data"}

        eq = self.equity_curve["equity"]
        initial = self.config.initial_capital
        final = float(eq.iloc[-1])

        total_return = (final - initial) / initial
        days = (eq.index[-1] - eq.index[0]).days
        ann_return = (1 + total_return) ** (365 / max(days, 1)) - 1

        # 日收益率 (按K线间隔)
        returns = eq.pct_change().dropna()
        periods_per_year = max(len(returns) / max(days, 1) * 365, 1)

        # 夏普比率
        if returns.std() > 0:
            sharpe = (returns.mean() * periods_per_year - 0.02) / (
                returns.std() * np.sqrt(periods_per_year)
            )
        else:
            sharpe = 0.0

        # 最大回撤
        peak = eq.cummax()
        drawdown = (eq - peak) / peak
        max_dd = float(drawdown.min())

        # 索提诺比率
        neg_returns = returns[returns < 0]
        downside_std = neg_returns.std() * np.sqrt(periods_per_year)
        sortino = ((returns.mean() * periods_per_year - 0.02) / downside_std
                   if downside_std > 0 else 0.0)

        # 卡尔马比率
        calmar = ann_return / abs(max_dd) if max_dd != 0 else 0.0

        # 交易统计
        closing_trades = [t for t in self.trades if t.pnl != 0]
        n_trades = len(closing_trades)
        if n_trades > 0:
            wins = [t for t in closing_trades if t.pnl > 0]
            losses = [t for t in closing_trades if t.pnl < 0]
            win_rate = len(wins) / n_trades
            avg_win = np.mean([t.pnl for t in wins]) if wins else 0
            avg_loss = abs(np.mean([t.pnl for t in losses])) if losses else 1
            profit_factor = (sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses))
                            if losses else float("inf"))
            total_fees = sum(t.fee for t in self.trades)
        else:
            win_rate = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            profit_factor = 0.0
            total_fees = 0.0

        result = {
            "initial_capital": initial,
            "final_equity": round(final, 2),
            "total_return_pct": round(total_return * 100, 2),
            "annualized_return_pct": round(ann_return * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "total_trades": n_trades,
            "win_rate_pct": round(win_rate * 100, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "total_fees": round(total_fees, 2),
        }

        logger.info("=== Backtest Summary ===")
        for k, v in result.items():
            logger.info(f"  {k}: {v}")
        return result

    def trade_log(self) -> pd.DataFrame:
        """返回交易日志 DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "timestamp": t.timestamp,
                "side": t.side,
                "price": t.price,
                "amount": t.amount,
                "fee": t.fee,
                "pnl": t.pnl,
            }
            for t in self.trades
        ])

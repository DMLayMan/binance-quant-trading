"""
风控引擎

负责仓位管理、风险指标计算、异常检测。
包含：每日亏损限制、最大回撤熔断、预交易检查。
"""

import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ==================== 仓位计算 ====================


def kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    kelly_factor: float = 0.5,
) -> float:
    """
    Kelly 公式计算最优仓位

    Args:
        win_rate: 历史胜率
        avg_win: 平均盈利
        avg_loss: 平均亏损
        kelly_factor: Kelly 系数（通常取半 Kelly = 0.5）

    Returns:
        最优仓位比例
    """
    b = avg_win / avg_loss  # 盈亏比
    p = win_rate
    q = 1 - p

    f = (p * b - q) / b
    f = max(0, f)  # 负值意味着不应该交易

    return f * kelly_factor


# ==================== 绩效指标 ====================


def compute_metrics(
    equity_curve: pd.Series, risk_free_rate: float = 0.02
) -> dict:
    """
    计算策略评估指标

    Args:
        equity_curve: 权益曲线（时间序列）
        risk_free_rate: 无风险利率（年化）

    Returns:
        指标字典
    """
    returns = equity_curve.pct_change().dropna()

    # 年化收益
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0] - 1
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    annualized_return = (1 + total_return) ** (365 / max(days, 1)) - 1

    # 夏普比率
    excess_returns = returns.mean() * 365 - risk_free_rate
    sharpe = excess_returns / (returns.std() * np.sqrt(365)) if returns.std() > 0 else 0

    # 最大回撤
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak
    max_drawdown = drawdown.min()

    # 索提诺比率
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() * np.sqrt(365)
    sortino = excess_returns / downside_std if downside_std > 0 else 0

    # 卡尔马比率
    calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

    # 胜率和盈亏比
    trades = returns[returns != 0]
    win_rate = float((trades > 0).mean()) if len(trades) > 0 else 0
    avg_win = float(trades[trades > 0].mean()) if (trades > 0).any() else 0
    avg_loss = float(abs(trades[trades < 0].mean())) if (trades < 0).any() else 1
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

    return {
        "annualized_return_pct": round(annualized_return * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
        "win_rate_pct": round(win_rate * 100, 2),
        "profit_loss_ratio": round(profit_loss_ratio, 2),
    }


# ==================== 蒙特卡洛模拟 ====================


def monte_carlo_simulation(
    trade_returns: np.ndarray, n_simulations: int = 1000
) -> dict:
    """
    蒙特卡洛模拟

    Args:
        trade_returns: 交易收益率数组
        n_simulations: 模拟次数

    Returns:
        模拟结果统计
    """
    results_returns = []
    results_drawdowns = []

    for _ in range(n_simulations):
        shuffled = np.random.choice(
            trade_returns, size=len(trade_returns), replace=True
        )
        equity = np.cumprod(1 + shuffled)
        total_return = equity[-1] - 1
        max_dd = np.min(equity / np.maximum.accumulate(equity) - 1)
        results_returns.append(total_return)
        results_drawdowns.append(max_dd)

    return {
        "return_5th_pct": np.percentile(results_returns, 5),
        "return_median": np.median(results_returns),
        "return_95th_pct": np.percentile(results_returns, 95),
        "max_dd_5th_pct": np.percentile(results_drawdowns, 5),
        "max_dd_median": np.median(results_drawdowns),
    }


# ==================== 滑点模拟 ====================


def simulate_slippage(
    price: float, volume: float, order_size: float, is_buy: bool
) -> float:
    """
    滑点模拟（固定 + 成交量冲击）

    Args:
        price: 当前价格
        volume: 市场成交量
        order_size: 订单数量
        is_buy: 是否买单

    Returns:
        滑点后的实际成交价
    """
    fixed_slippage = 0.0001  # 0.01%
    volume_impact = (order_size / volume) * 0.1 if volume > 0 else 0
    total_slippage = fixed_slippage + volume_impact

    if is_buy:
        return price * (1 + total_slippage)
    else:
        return price * (1 - total_slippage)


# ==================== 实时风控引擎 ====================


@dataclass
class RiskState:
    """风控状态追踪"""
    initial_equity: float = 0.0
    peak_equity: float = 0.0
    daily_start_equity: float = 0.0
    current_equity: float = 0.0
    current_date: Optional[str] = None
    total_trades_today: int = 0
    consecutive_losses: int = 0
    is_halted: bool = False
    halt_reason: str = ""


class RiskController:
    """
    实时风控引擎

    提供：
    - 每日最大亏损限制
    - 最大回撤熔断
    - 单笔仓位限制
    - 连续亏损暂停
    - 每日最大交易次数限制
    - 预交易检查
    """

    def __init__(
        self,
        initial_equity: float,
        max_daily_loss_pct: float = 0.05,
        max_drawdown_pct: float = 0.15,
        max_position_pct: float = 0.30,
        max_single_loss_pct: float = 0.02,
        max_trades_per_day: int = 50,
        max_consecutive_losses: int = 5,
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_position_pct = max_position_pct
        self.max_single_loss_pct = max_single_loss_pct
        self.max_trades_per_day = max_trades_per_day
        self.max_consecutive_losses = max_consecutive_losses

        self.state = RiskState(
            initial_equity=initial_equity,
            peak_equity=initial_equity,
            daily_start_equity=initial_equity,
            current_equity=initial_equity,
        )

    def update_equity(self, equity: float, date_str: Optional[str] = None):
        """更新当前权益，触发日期变更时重置日内统计"""
        self.state.current_equity = equity
        self.state.peak_equity = max(self.state.peak_equity, equity)

        if date_str and date_str != self.state.current_date:
            self.state.current_date = date_str
            self.state.daily_start_equity = equity
            self.state.total_trades_today = 0
            # 新的一天，如果是日内亏损熔断则解除
            if self.state.is_halted and "daily" in self.state.halt_reason:
                self.state.is_halted = False
                self.state.halt_reason = ""
                logger.info("Daily loss halt lifted on new trading day")

    def record_trade(self, pnl: float):
        """记录一笔交易的盈亏"""
        self.state.total_trades_today += 1

        if pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0

    def pre_trade_check(
        self,
        order_value: float,
        current_price: float,
        atr: float,
        stop_loss_mult: float = 2.0,
    ) -> tuple[bool, str]:
        """
        预交易风控检查

        Args:
            order_value: 拟下单金额 (USDT)
            current_price: 当前价格
            atr: 当前 ATR
            stop_loss_mult: 止损 ATR 倍数

        Returns:
            (是否允许, 原因)
        """
        equity = self.state.current_equity

        # 0. 检查是否已熔断
        if self.state.is_halted:
            return False, f"Trading halted: {self.state.halt_reason}"

        # 1. 每日最大亏损检查
        daily_pnl = equity - self.state.daily_start_equity
        daily_loss_pct = daily_pnl / self.state.daily_start_equity
        if daily_loss_pct <= -self.max_daily_loss_pct:
            self.state.is_halted = True
            self.state.halt_reason = f"daily loss limit ({daily_loss_pct:.2%})"
            logger.warning(f"HALT: Daily loss limit reached: {daily_loss_pct:.2%}")
            return False, self.state.halt_reason

        # 2. 最大回撤检查
        drawdown = (equity - self.state.peak_equity) / self.state.peak_equity
        if drawdown <= -self.max_drawdown_pct:
            self.state.is_halted = True
            self.state.halt_reason = f"max drawdown limit ({drawdown:.2%})"
            logger.warning(f"HALT: Max drawdown limit reached: {drawdown:.2%}")
            return False, self.state.halt_reason

        # 3. 仓位占比检查
        position_pct = order_value / equity if equity > 0 else 1
        if position_pct > self.max_position_pct:
            return False, (
                f"Position too large: {position_pct:.2%} > {self.max_position_pct:.2%}"
            )

        # 4. 单笔最大亏损检查
        if atr > 0:
            potential_loss = (atr * stop_loss_mult) * (order_value / current_price)
            loss_pct = potential_loss / equity
            if loss_pct > self.max_single_loss_pct:
                return False, (
                    f"Single trade risk too high: {loss_pct:.2%} > "
                    f"{self.max_single_loss_pct:.2%}"
                )

        # 5. 日内交易次数检查
        if self.state.total_trades_today >= self.max_trades_per_day:
            return False, (
                f"Daily trade limit reached: {self.state.total_trades_today}"
            )

        # 6. 连续亏损检查
        if self.state.consecutive_losses >= self.max_consecutive_losses:
            self.state.is_halted = True
            self.state.halt_reason = (
                f"consecutive losses ({self.state.consecutive_losses})"
            )
            logger.warning(
                f"HALT: {self.state.consecutive_losses} consecutive losses"
            )
            return False, self.state.halt_reason

        return True, "OK"

    def get_status(self) -> dict:
        """获取当前风控状态"""
        equity = self.state.current_equity
        return {
            "current_equity": round(equity, 2),
            "peak_equity": round(self.state.peak_equity, 2),
            "drawdown_pct": round(
                (equity - self.state.peak_equity) / self.state.peak_equity * 100, 2
            ) if self.state.peak_equity > 0 else 0,
            "daily_pnl": round(equity - self.state.daily_start_equity, 2),
            "daily_pnl_pct": round(
                (equity - self.state.daily_start_equity)
                / self.state.daily_start_equity * 100, 2
            ) if self.state.daily_start_equity > 0 else 0,
            "trades_today": self.state.total_trades_today,
            "consecutive_losses": self.state.consecutive_losses,
            "is_halted": self.state.is_halted,
            "halt_reason": self.state.halt_reason,
        }

    def reset_halt(self):
        """手动解除熔断（需人工确认后调用）"""
        logger.info(
            f"Manual halt reset (was: {self.state.halt_reason})"
        )
        self.state.is_halted = False
        self.state.halt_reason = ""
        self.state.consecutive_losses = 0

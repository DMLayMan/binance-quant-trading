"""
风控引擎

负责仓位管理、风险指标计算、异常检测。
"""

import numpy as np
import pandas as pd


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

"""
改良海龟交易法则 (Modified Turtle Trading)

原理：经典海龟法则使用 N 日最高/最低价突破入场，
用 ATR 管理仓位和止损。加密市场使用 4H K线适配。

适用场景：强趋势行情
预期表现：夏普比率 0.9-1.8，最大回撤 25-40%
"""

import pandas as pd


def turtle_signal(
    df: pd.DataFrame, entry_period: int = 120, exit_period: int = 60
) -> pd.Series:
    """
    改良海龟突破信号（4H K线，120根 ≈ 20天）

    Args:
        df: 包含 'high', 'low', 'close' 列的 DataFrame
        entry_period: 入场突破周期
        exit_period: 出场突破周期

    Returns:
        信号序列: 1=买入, -1=卖出, 0=持有
    """
    high_entry = df["high"].rolling(entry_period).max()
    low_entry = df["low"].rolling(entry_period).min()

    signal = pd.Series(0, index=df.index)
    signal[df["close"] > high_entry.shift(1)] = 1  # 突破做多
    signal[df["close"] < low_entry.shift(1)] = -1  # 突破做空

    return signal


def turtle_position_size(
    capital: float, atr: float, risk_pct: float = 0.01
) -> float:
    """
    海龟仓位计算：每笔交易风险不超过总资金的 risk_pct

    Args:
        capital: 总资金
        atr: 当前 ATR 值
        risk_pct: 单笔风险占比

    Returns:
        建议仓位数量
    """
    dollar_risk = capital * risk_pct
    stop_distance = 2 * atr  # 止损 = 2 × ATR
    position_size = dollar_risk / stop_distance
    return position_size

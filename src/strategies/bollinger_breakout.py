"""
布林带突破策略 (Bollinger Bands Breakout)

原理：布林带 = MA(20) +/- 2σ。价格突破上轨为强势信号，
布林带收窄（squeeze）后的突破往往预示大行情。

适用场景：Squeeze 后的趋势行情
预期表现：夏普比率 0.8-1.6，最大回撤 20-35%
"""

import pandas as pd


def bollinger_breakout_signal(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
) -> pd.Series:
    """
    布林带突破信号

    Args:
        df: 包含 'close', 'high', 'low' 列的 DataFrame
        period: 均线周期
        std_dev: 标准差倍数

    Returns:
        信号序列: 1=买入, -1=卖出, 0=持有
    """
    sma = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    bandwidth = (upper - lower) / sma

    signal = pd.Series(0, index=df.index)
    # Squeeze 后突破（带宽处于历史低位 → 突破）
    squeeze = bandwidth < bandwidth.rolling(120).quantile(0.2)
    signal[(df["close"] > upper) & squeeze.shift(1)] = 1  # 向上突破
    signal[(df["close"] < lower) & squeeze.shift(1)] = -1  # 向下突破

    return signal

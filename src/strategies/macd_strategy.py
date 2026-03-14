"""
MACD 趋势策略

原理：MACD = EMA(fast) - EMA(slow)，信号线 = EMA(MACD, signal)
MACD 上穿信号线为买入信号，下穿为卖出信号。

适用场景：趋势行情
预期表现：夏普比率 0.7-1.3，最大回撤 15-30%
"""

import pandas as pd


def macd_signal(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal_period: int = 9
) -> pd.Series:
    """
    MACD 交叉信号

    Args:
        df: 包含 'close' 列的 DataFrame
        fast: 快速 EMA 周期
        slow: 慢速 EMA 周期
        signal_period: 信号线 EMA 周期

    Returns:
        信号序列: 1=买入, -1=卖出, 0=持有
    """
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

    signal = pd.Series(0, index=df.index)
    buy = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    sell = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
    signal[buy] = 1
    signal[sell] = -1

    return signal

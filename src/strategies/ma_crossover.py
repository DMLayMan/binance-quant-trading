"""
双均线交叉策略 (Moving Average Crossover)

原理：短期均线上穿长期均线（Golden Cross）产生买入信号，
下穿（Death Cross）产生卖出信号。

适用场景：单边趋势行情（BTC 大牛/大熊市）
预期表现：夏普比率 0.8-1.5，最大回撤 15-25%，胜率约 35-45%
"""

import pandas as pd


def ma_crossover_signal(
    df: pd.DataFrame, fast: int = 7, slow: int = 25
) -> pd.Series:
    """
    双均线交叉信号生成

    Args:
        df: 包含 'close' 列的 DataFrame
        fast: 快速均线周期
        slow: 慢速均线周期

    Returns:
        信号序列: 1=买入, -1=卖出, 0=持有
    """
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()

    signal = pd.Series(0, index=df.index)
    # Golden Cross: 快线从下方穿越慢线
    signal[(ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))] = 1
    # Death Cross: 快线从上方穿越慢线
    signal[(ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))] = -1

    return signal

"""
RSI 动量策略

原理：RSI = 100 - 100/(1 + RS)，RS = 平均涨幅/平均跌幅。
RSI > 70 超买，RSI < 30 超卖。

适用场景：震荡 + 趋势行情
预期表现：夏普比率 0.6-1.2，最大回撤 10-20%
"""

import pandas as pd


def rsi_signal(
    df: pd.DataFrame,
    period: int = 14,
    overbought: float = 70,
    oversold: float = 30,
) -> pd.Series:
    """
    RSI 超买超卖信号

    Args:
        df: 包含 'close' 列的 DataFrame
        period: RSI 计算周期
        overbought: 超买阈值
        oversold: 超卖阈值

    Returns:
        信号序列: 1=买入, -1=卖出, 0=持有
    """
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    signal = pd.Series(0, index=df.index)
    # 从超卖区回升
    signal[(rsi > oversold) & (rsi.shift(1) <= oversold)] = 1
    # 从超买区回落
    signal[(rsi < overbought) & (rsi.shift(1) >= overbought)] = -1

    return signal

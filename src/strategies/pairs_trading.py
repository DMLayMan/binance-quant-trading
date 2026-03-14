"""
配对交易 / 统计套利 (Pairs Trading)

原理：找到两个高度相关的资产，当价差偏离历史均值时，
做多低估品种、做空高估品种。

适用场景：震荡行情
预期表现：夏普比率 1.0-2.0，最大回撤 5-15%
"""

import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import coint


def find_cointegrated_pairs(
    prices: pd.DataFrame, significance: float = 0.05
) -> list[tuple]:
    """
    在多个币对中寻找协整配对

    Args:
        prices: 列为币对名称，行为价格的 DataFrame
        significance: 显著性水平

    Returns:
        协整配对列表 [(coin_a, coin_b, p_value), ...]
    """
    n = prices.shape[1]
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            score, pvalue, _ = coint(prices.iloc[:, i], prices.iloc[:, j])
            if pvalue < significance:
                pairs.append((prices.columns[i], prices.columns[j], pvalue))
    return sorted(pairs, key=lambda x: x[2])


def pairs_trading_signal(
    spread: pd.Series,
    window: int = 60,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
) -> pd.Series:
    """
    配对交易信号

    Args:
        spread: 价差序列
        window: 滚动窗口
        entry_z: 入场 Z-Score 阈值
        exit_z: 平仓 Z-Score 阈值

    Returns:
        信号序列: 1=做多价差, -1=做空价差, 0=平仓
    """
    mean = spread.rolling(window).mean()
    std = spread.rolling(window).std()
    z_score = (spread - mean) / std

    signal = pd.Series(0, index=spread.index)
    signal[z_score > entry_z] = -1  # 价差过高，做空价差
    signal[z_score < -entry_z] = 1  # 价差过低，做多价差
    signal[z_score.abs() < exit_z] = 0  # 回归均值，平仓

    return signal

"""
技术指标计算工具
"""

import pandas as pd
import numpy as np


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算 ATR (Average True Range)"""
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """计算 RSI (Relative Strength Index)"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def compute_bollinger_bands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """计算布林带 (upper, middle, lower)"""
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """计算 MACD (macd_line, signal_line, histogram)"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """构建 ML 特征"""
    features = pd.DataFrame(index=df.index)

    # 价格变化特征
    features["returns"] = df["close"].pct_change()
    features["log_returns"] = np.log(df["close"] / df["close"].shift(1))

    # 技术指标
    features["rsi_14"] = compute_rsi(df["close"], 14)
    features["macd"], _, _ = compute_macd(df["close"])
    upper, middle, lower = compute_bollinger_bands(df["close"])
    features["bb_position"] = (df["close"] - middle) / ((upper - lower) / 2)
    features["atr_14"] = compute_atr(df, 14)

    # 成交量特征
    features["volume_ma_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    features["obv"] = (np.sign(df["close"].diff()) * df["volume"]).cumsum()

    # 时间特征
    if hasattr(df.index, "hour"):
        features["hour"] = df.index.hour
        features["day_of_week"] = df.index.dayofweek

    return features.dropna()

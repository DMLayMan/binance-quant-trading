"""技术指标单元测试"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.indicators import (
    compute_atr,
    compute_rsi,
    compute_bollinger_bands,
    compute_macd,
    create_features,
)


@pytest.fixture
def sample_ohlcv():
    """生成模拟 OHLCV 数据"""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")
    close = 40000 + np.cumsum(np.random.randn(n) * 200)
    high = close + np.random.uniform(50, 300, n)
    low = close - np.random.uniform(50, 300, n)
    open_ = close + np.random.randn(n) * 100
    volume = np.random.uniform(100, 1000, n)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


class TestATR:
    def test_atr_length(self, sample_ohlcv):
        atr = compute_atr(sample_ohlcv)
        assert len(atr) == len(sample_ohlcv)

    def test_atr_positive(self, sample_ohlcv):
        atr = compute_atr(sample_ohlcv).dropna()
        assert (atr > 0).all()

    def test_atr_nan_start(self, sample_ohlcv):
        atr = compute_atr(sample_ohlcv, period=14)
        # 前 14 根K线由于 rolling 窗口不足，应该有 NaN
        assert atr.iloc[:13].isna().any()
        assert not atr.iloc[14:].isna().any()

    def test_atr_custom_period(self, sample_ohlcv):
        atr_7 = compute_atr(sample_ohlcv, period=7)
        atr_21 = compute_atr(sample_ohlcv, period=21)
        assert not atr_7.dropna().equals(atr_21.dropna())


class TestRSI:
    def test_rsi_range(self, sample_ohlcv):
        rsi = compute_rsi(sample_ohlcv["close"]).dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_rsi_length(self, sample_ohlcv):
        rsi = compute_rsi(sample_ohlcv["close"])
        assert len(rsi) == len(sample_ohlcv)


class TestBollingerBands:
    def test_bollinger_structure(self, sample_ohlcv):
        upper, middle, lower = compute_bollinger_bands(sample_ohlcv["close"])
        valid = ~upper.isna() & ~middle.isna() & ~lower.isna()
        assert (upper[valid] >= middle[valid]).all()
        assert (middle[valid] >= lower[valid]).all()

    def test_bollinger_width(self, sample_ohlcv):
        upper, middle, lower = compute_bollinger_bands(
            sample_ohlcv["close"], std_dev=2.0
        )
        width = (upper - lower).dropna()
        assert (width > 0).all()


class TestMACD:
    def test_macd_structure(self, sample_ohlcv):
        macd_line, signal_line, histogram = compute_macd(sample_ohlcv["close"])
        assert len(macd_line) == len(sample_ohlcv)
        assert len(signal_line) == len(sample_ohlcv)
        assert len(histogram) == len(sample_ohlcv)

    def test_macd_histogram_consistency(self, sample_ohlcv):
        macd_line, signal_line, histogram = compute_macd(sample_ohlcv["close"])
        diff = (macd_line - signal_line).dropna()
        hist_valid = histogram.dropna()
        np.testing.assert_array_almost_equal(
            diff.values[-len(hist_valid):],
            hist_valid.values[-len(diff):],
        )


class TestFeatures:
    def test_feature_columns(self, sample_ohlcv):
        features = create_features(sample_ohlcv)
        expected_cols = [
            "returns", "log_returns", "rsi_14", "macd",
            "bb_position", "atr_14", "volume_ma_ratio", "obv",
        ]
        for col in expected_cols:
            assert col in features.columns, f"Missing column: {col}"

    def test_no_nan_after_warmup(self, sample_ohlcv):
        features = create_features(sample_ohlcv)
        assert not features.isnull().any().any()

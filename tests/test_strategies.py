"""策略信号生成单元测试"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from strategies.ma_crossover import ma_crossover_signal
from strategies.macd_strategy import macd_signal
from strategies.bollinger_breakout import bollinger_breakout_signal
from strategies.rsi_momentum import rsi_signal
from strategies.turtle_trading import turtle_signal, turtle_position_size


@pytest.fixture
def trending_up_data():
    """生成上升趋势数据"""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")
    close = 40000 + np.arange(n) * 50 + np.random.randn(n) * 30
    high = close + np.random.uniform(20, 100, n)
    low = close - np.random.uniform(20, 100, n)
    volume = np.random.uniform(100, 500, n)
    return pd.DataFrame(
        {"open": close - 10, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def oscillating_data():
    """生成震荡数据"""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")
    close = 40000 + 2000 * np.sin(np.linspace(0, 8 * np.pi, n)) + np.random.randn(n) * 50
    high = close + np.random.uniform(20, 100, n)
    low = close - np.random.uniform(20, 100, n)
    volume = np.random.uniform(100, 500, n)
    return pd.DataFrame(
        {"open": close - 10, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


class TestMACrossover:
    def test_signal_values(self, trending_up_data):
        signals = ma_crossover_signal(trending_up_data, fast=7, slow=25)
        unique_values = set(signals.unique())
        assert unique_values.issubset({-1, 0, 1})

    def test_signal_length(self, trending_up_data):
        signals = ma_crossover_signal(trending_up_data)
        assert len(signals) == len(trending_up_data)

    def test_trending_up_has_buy(self, trending_up_data):
        signals = ma_crossover_signal(trending_up_data, fast=7, slow=25)
        assert (signals == 1).any(), "Should detect buy signal in uptrend"


class TestMACDSignal:
    def test_signal_values(self, trending_up_data):
        signals = macd_signal(trending_up_data)
        unique_values = set(signals.unique())
        assert unique_values.issubset({-1, 0, 1})

    def test_signal_length(self, trending_up_data):
        signals = macd_signal(trending_up_data)
        assert len(signals) == len(trending_up_data)


class TestBollingerBreakout:
    def test_signal_values(self, oscillating_data):
        signals = bollinger_breakout_signal(oscillating_data)
        unique_values = set(signals.unique())
        assert unique_values.issubset({-1, 0, 1})

    def test_signal_length(self, oscillating_data):
        signals = bollinger_breakout_signal(oscillating_data)
        assert len(signals) == len(oscillating_data)


class TestRSISignal:
    def test_signal_values(self, oscillating_data):
        signals = rsi_signal(oscillating_data)
        unique_values = set(signals.unique())
        assert unique_values.issubset({-1, 0, 1})

    def test_oscillating_generates_signals(self, oscillating_data):
        signals = rsi_signal(oscillating_data, overbought=70, oversold=30)
        total_signals = (signals != 0).sum()
        assert total_signals > 0, "RSI should generate signals in oscillating data"


class TestTurtleTrading:
    def test_signal_values(self, trending_up_data):
        signals = turtle_signal(trending_up_data, entry_period=120, exit_period=60)
        unique_values = set(signals.unique())
        assert unique_values.issubset({-1, 0, 1})

    def test_position_size(self):
        size = turtle_position_size(capital=100000, atr=500, risk_pct=0.01)
        assert size == pytest.approx(1.0)

    def test_position_size_lower_risk(self):
        size = turtle_position_size(capital=100000, atr=1000, risk_pct=0.005)
        expected = (100000 * 0.005) / (2 * 1000)
        assert size == pytest.approx(expected)

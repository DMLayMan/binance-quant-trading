"""风控引擎单元测试"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from risk.risk_manager import (
    kelly_fraction,
    compute_metrics,
    monte_carlo_simulation,
    simulate_slippage,
    RiskController,
)


class TestKellyFraction:
    def test_positive_edge(self):
        # 60% 胜率，盈亏比 1.5
        f = kelly_fraction(win_rate=0.6, avg_win=1.5, avg_loss=1.0)
        assert f > 0

    def test_no_edge(self):
        # 50% 胜率，盈亏比 1.0 → 零预期
        f = kelly_fraction(win_rate=0.5, avg_win=1.0, avg_loss=1.0)
        assert f == 0

    def test_negative_edge(self):
        # 30% 胜率，盈亏比 1.0 → 不应交易
        f = kelly_fraction(win_rate=0.3, avg_win=1.0, avg_loss=1.0)
        assert f == 0

    def test_half_kelly(self):
        full = kelly_fraction(win_rate=0.6, avg_win=2.0, avg_loss=1.0, kelly_factor=1.0)
        half = kelly_fraction(win_rate=0.6, avg_win=2.0, avg_loss=1.0, kelly_factor=0.5)
        assert half == pytest.approx(full * 0.5)


class TestComputeMetrics:
    def test_positive_equity(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="1d")
        equity = pd.Series(np.linspace(10000, 15000, 100), index=dates)
        metrics = compute_metrics(equity)
        assert metrics["annualized_return_pct"] > 0
        assert metrics["sharpe_ratio"] > 0
        assert metrics["max_drawdown_pct"] <= 0  # 单调增无回撤或 ≤ 0

    def test_negative_equity(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="1d")
        equity = pd.Series(np.linspace(10000, 5000, 100), index=dates)
        metrics = compute_metrics(equity)
        assert metrics["annualized_return_pct"] < 0
        assert metrics["max_drawdown_pct"] < 0


class TestMonteCarloSimulation:
    def test_output_keys(self):
        returns = np.random.randn(50) * 0.02
        result = monte_carlo_simulation(returns, n_simulations=100)
        assert "return_5th_pct" in result
        assert "return_median" in result
        assert "return_95th_pct" in result
        assert "max_dd_5th_pct" in result

    def test_percentile_order(self):
        returns = np.random.randn(50) * 0.02
        result = monte_carlo_simulation(returns, n_simulations=500)
        assert result["return_5th_pct"] <= result["return_median"]
        assert result["return_median"] <= result["return_95th_pct"]


class TestSlippage:
    def test_buy_slippage_higher(self):
        result = simulate_slippage(price=50000, volume=100, order_size=1, is_buy=True)
        assert result > 50000

    def test_sell_slippage_lower(self):
        result = simulate_slippage(price=50000, volume=100, order_size=1, is_buy=False)
        assert result < 50000

    def test_large_order_more_slippage(self):
        small = simulate_slippage(price=50000, volume=100, order_size=1, is_buy=True)
        large = simulate_slippage(price=50000, volume=100, order_size=50, is_buy=True)
        assert large > small


class TestRiskController:
    def test_init(self):
        rc = RiskController(initial_equity=100000)
        status = rc.get_status()
        assert status["current_equity"] == 100000
        assert status["is_halted"] is False

    def test_pre_trade_allowed(self):
        rc = RiskController(initial_equity=100000)
        allowed, reason = rc.pre_trade_check(
            order_value=10000, current_price=50000, atr=500
        )
        assert allowed is True
        assert reason == "OK"

    def test_position_too_large(self):
        rc = RiskController(initial_equity=100000, max_position_pct=0.3)
        allowed, reason = rc.pre_trade_check(
            order_value=50000, current_price=50000, atr=500
        )
        assert allowed is False
        assert "Position too large" in reason

    def test_daily_loss_halt(self):
        rc = RiskController(initial_equity=100000, max_daily_loss_pct=0.05)
        # 先设定当天开盘权益
        rc.update_equity(100000, "2024-01-01")
        # 盘中亏损 6%
        rc.update_equity(94000)
        allowed, reason = rc.pre_trade_check(
            order_value=5000, current_price=50000, atr=500
        )
        assert allowed is False
        assert "daily loss limit" in reason
        assert rc.state.is_halted is True

    def test_daily_loss_reset_next_day(self):
        rc = RiskController(initial_equity=100000, max_daily_loss_pct=0.05)
        rc.update_equity(100000, "2024-01-01")
        rc.update_equity(94000)
        # 触发熔断
        rc.pre_trade_check(order_value=5000, current_price=50000, atr=500)
        assert rc.state.is_halted is True
        # 新的一天
        rc.update_equity(94000, "2024-01-02")
        assert rc.state.is_halted is False

    def test_max_drawdown_halt(self):
        rc = RiskController(initial_equity=100000, max_drawdown_pct=0.15)
        rc.update_equity(110000, "2024-01-01")  # 新高峰
        rc.update_equity(90000, "2024-01-02")   # 从 110k 跌到 90k = -18.2%
        allowed, reason = rc.pre_trade_check(
            order_value=5000, current_price=50000, atr=500
        )
        assert allowed is False
        assert "max drawdown" in reason

    def test_consecutive_losses_halt(self):
        rc = RiskController(initial_equity=100000, max_consecutive_losses=3)
        rc.record_trade(-100)
        rc.record_trade(-200)
        rc.record_trade(-150)
        allowed, reason = rc.pre_trade_check(
            order_value=5000, current_price=50000, atr=500
        )
        assert allowed is False
        assert "consecutive losses" in reason

    def test_consecutive_losses_reset_on_win(self):
        rc = RiskController(initial_equity=100000, max_consecutive_losses=5)
        rc.record_trade(-100)
        rc.record_trade(-200)
        rc.record_trade(300)  # 赢了一次
        assert rc.state.consecutive_losses == 0

    def test_daily_trade_limit(self):
        rc = RiskController(initial_equity=100000, max_trades_per_day=3)
        rc.record_trade(100)
        rc.record_trade(100)
        rc.record_trade(100)
        allowed, reason = rc.pre_trade_check(
            order_value=5000, current_price=50000, atr=500
        )
        assert allowed is False
        assert "Daily trade limit" in reason

    def test_manual_reset(self):
        rc = RiskController(initial_equity=100000, max_consecutive_losses=2)
        rc.record_trade(-100)
        rc.record_trade(-100)
        rc.pre_trade_check(order_value=5000, current_price=50000, atr=500)
        assert rc.state.is_halted is True
        rc.reset_halt()
        assert rc.state.is_halted is False
        assert rc.state.consecutive_losses == 0

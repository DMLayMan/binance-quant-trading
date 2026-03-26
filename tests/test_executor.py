"""执行引擎单元测试"""

import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    """每个测试使用独立的临时数据库"""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("BQT_DB_PATH", db_path)
    import core.database
    monkeypatch.setattr(core.database, "DB_PATH", db_path)
    core.database.init_db()
    yield db_path


@pytest.fixture
def pool_and_instance():
    """创建测试用的资金池和策略实例"""
    from core.models import create_fund_pool, create_strategy_instance, update_strategy_instance
    pool = create_fund_pool(name="Test Pool", allocated_amount=10000)
    inst = create_strategy_instance(
        fund_pool_id=pool.id,
        strategy_name="ma_crossover",
        symbol="BTC/USDT",
        timeframe="4h",
        stop_loss_atr_mult=2.0,
        take_profit_atr_mult=4.0,
        max_position_pct=0.30,
        risk_per_trade_pct=0.01,
    )
    update_strategy_instance(inst.id, status="running")
    inst.status = "running"
    return pool, inst


@pytest.fixture
def mock_df():
    """创建模拟行情数据"""
    dates = pd.date_range("2024-01-01", periods=100, freq="4h")
    np.random.seed(42)
    close = 50000 + np.cumsum(np.random.randn(100) * 200)
    df = pd.DataFrame({
        "open": close - 50,
        "high": close + 100,
        "low": close - 100,
        "close": close,
        "volume": np.random.uniform(100, 1000, 100),
    }, index=dates)
    return df


# ==================== Risk Check ====================


class TestStrategyRisk:
    def test_strategy_risk_pass(self, pool_and_instance):
        from core.executor import _check_strategy_risk
        pool, inst = pool_and_instance
        ok, reason = _check_strategy_risk(inst, 2000, pool)
        assert ok is True
        assert reason == ""

    def test_strategy_risk_position_too_large(self, pool_and_instance):
        from core.executor import _check_strategy_risk
        pool, inst = pool_and_instance
        # Order value > 30% of equity
        ok, reason = _check_strategy_risk(inst, 5000, pool)
        assert ok is False
        assert "Position size" in reason

    def test_strategy_risk_consecutive_losses(self, pool_and_instance):
        from core.executor import _check_strategy_risk
        from core.models import update_strategy_instance
        pool, inst = pool_and_instance
        update_strategy_instance(inst.id, consecutive_losses=5)
        inst.consecutive_losses = 5
        ok, reason = _check_strategy_risk(inst, 1000, pool)
        assert ok is False
        assert "Consecutive losses" in reason

    def test_strategy_risk_daily_trade_limit(self, pool_and_instance):
        from core.executor import _check_strategy_risk
        from core.models import update_strategy_instance
        from core.database import today_str
        pool, inst = pool_and_instance
        td = today_str()
        update_strategy_instance(inst.id, trades_today=50, trades_today_date=td)
        inst.trades_today = 50
        inst.trades_today_date = td
        ok, reason = _check_strategy_risk(inst, 1000, pool)
        assert ok is False
        assert "Daily trade count" in reason


class TestPoolRisk:
    def test_pool_risk_pass(self, pool_and_instance):
        from core.executor import _check_pool_risk
        pool, _ = pool_and_instance
        ok, reason = _check_pool_risk(pool)
        assert ok is True

    def test_pool_risk_daily_loss(self, pool_and_instance):
        from core.executor import _check_pool_risk
        from core.models import update_fund_pool
        pool, _ = pool_and_instance
        # Simulate 6% daily loss
        update_fund_pool(pool.id, current_equity=9400,
                         daily_start_equity=10000)
        pool.current_equity = 9400
        pool.daily_start_equity = 10000
        ok, reason = _check_pool_risk(pool)
        assert ok is False
        assert "Daily loss" in reason

    def test_pool_risk_max_drawdown(self, pool_and_instance):
        from core.executor import _check_pool_risk
        pool, _ = pool_and_instance
        # Peak was 12000, now at 10000 → 16.7% drawdown > 15%
        pool.peak_equity = 12000
        pool.current_equity = 10000
        ok, reason = _check_pool_risk(pool)
        assert ok is False
        assert "Drawdown" in reason

    def test_pool_risk_stop_loss(self, pool_and_instance):
        from core.executor import _check_pool_risk
        pool, _ = pool_and_instance
        pool.stop_loss_pct = 0.10
        pool.current_equity = 8800  # 12% loss from 10000
        # daily_start_equity also needs to be high to avoid daily loss triggering first
        pool.daily_start_equity = 8800
        ok, reason = _check_pool_risk(pool)
        assert ok is False
        assert "stop-loss" in reason


class TestPoolTakeProfit:
    def test_take_profit_not_reached(self, pool_and_instance):
        from core.executor import _check_pool_take_profit
        pool, _ = pool_and_instance
        pool.take_profit_pct = 0.20
        pool.current_equity = 11000  # 10% gain, target is 20%
        assert _check_pool_take_profit(pool) is False

    def test_take_profit_reached(self, pool_and_instance):
        from core.executor import _check_pool_take_profit
        pool, _ = pool_and_instance
        pool.take_profit_pct = 0.20
        pool.current_equity = 12500  # 25% gain
        assert _check_pool_take_profit(pool) is True

    def test_take_profit_none(self, pool_and_instance):
        from core.executor import _check_pool_take_profit
        pool, _ = pool_and_instance
        pool.take_profit_pct = None
        assert _check_pool_take_profit(pool) is False


# ==================== Execution ====================


class TestExecuteStrategyTick:
    @patch("core.executor._get_ohlcv_cached")
    @patch("core.executor.STRATEGY_REGISTRY", {
        "ma_crossover": {
            "func": lambda df, **kw: pd.Series([0] * (len(df) - 1) + [1], index=df.index),
            "default_params": {},
        }
    })
    def test_buy_signal_opens_position(self, mock_ohlcv, pool_and_instance, mock_df):
        from core.executor import execute_strategy_tick
        from core.models import get_strategy_instance
        mock_ohlcv.return_value = mock_df
        pool, inst = pool_and_instance

        result = execute_strategy_tick(inst, exchange=None)
        assert result["action"] == "open"
        assert result["signal"] == 1

        # Check position was recorded
        updated = get_strategy_instance(inst.id)
        assert updated.current_position > 0
        assert updated.entry_price > 0

    @patch("core.executor._get_ohlcv_cached")
    @patch("core.executor.STRATEGY_REGISTRY", {
        "ma_crossover": {
            "func": lambda df, **kw: pd.Series([0] * len(df), index=df.index),
            "default_params": {},
        }
    })
    def test_no_signal_no_action(self, mock_ohlcv, pool_and_instance, mock_df):
        from core.executor import execute_strategy_tick
        mock_ohlcv.return_value = mock_df
        _, inst = pool_and_instance

        result = execute_strategy_tick(inst, exchange=None)
        assert result["action"] == "none"
        assert result["signal"] == 0

    @patch("core.executor._get_ohlcv_cached")
    @patch("core.executor.STRATEGY_REGISTRY", {
        "ma_crossover": {
            "func": lambda df, **kw: pd.Series([0] * len(df), index=df.index),
            "default_params": {},
        }
    })
    def test_stop_loss_trigger(self, mock_ohlcv, pool_and_instance, mock_df):
        from core.executor import execute_strategy_tick
        from core.models import update_strategy_instance, get_strategy_instance

        mock_ohlcv.return_value = mock_df
        pool, inst = pool_and_instance

        # Set up an existing position with entry price much higher than current
        current_price = float(mock_df["close"].iloc[-1])
        entry_price = current_price + 5000  # Entry was much higher
        update_strategy_instance(inst.id,
                                 current_position=0.1,
                                 entry_price=entry_price,
                                 last_signal_time="2024-01-01T00:00:00")
        inst.current_position = 0.1
        inst.entry_price = entry_price
        inst.last_signal_time = "2024-01-01T00:00:00"

        result = execute_strategy_tick(inst, exchange=None)
        assert result["action"] == "close"
        assert "stop_loss" in result.get("message", "")

    @patch("core.executor._get_ohlcv_cached")
    @patch("core.executor.STRATEGY_REGISTRY", {
        "ma_crossover": {
            "func": lambda df, **kw: pd.Series([0] * len(df), index=df.index),
            "default_params": {},
        }
    })
    def test_take_profit_trigger(self, mock_ohlcv, pool_and_instance, mock_df):
        from core.executor import execute_strategy_tick
        from core.models import update_strategy_instance

        mock_ohlcv.return_value = mock_df
        pool, inst = pool_and_instance

        # Set up position with entry price much lower than current
        current_price = float(mock_df["close"].iloc[-1])
        entry_price = current_price - 5000
        update_strategy_instance(inst.id,
                                 current_position=0.1,
                                 entry_price=entry_price,
                                 last_signal_time="2024-01-01T00:00:00")
        inst.current_position = 0.1
        inst.entry_price = entry_price
        inst.last_signal_time = "2024-01-01T00:00:00"

        result = execute_strategy_tick(inst, exchange=None)
        assert result["action"] == "close"
        assert "take_profit" in result.get("message", "")

    @patch("core.executor._get_ohlcv_cached")
    def test_inactive_pool_skips(self, mock_ohlcv, pool_and_instance, mock_df):
        from core.executor import execute_strategy_tick
        from core.models import update_fund_pool

        mock_ohlcv.return_value = mock_df
        pool, inst = pool_and_instance
        update_fund_pool(pool.id, status="paused")

        result = execute_strategy_tick(inst, exchange=None)
        assert result["action"] == "skip"

    @patch("core.executor._get_ohlcv_cached")
    def test_insufficient_data(self, mock_ohlcv, pool_and_instance):
        from core.executor import execute_strategy_tick

        # Only 10 candles (need at least 30)
        dates = pd.date_range("2024-01-01", periods=10, freq="4h")
        short_df = pd.DataFrame({
            "open": [50000] * 10,
            "high": [50100] * 10,
            "low": [49900] * 10,
            "close": [50000] * 10,
            "volume": [100] * 10,
        }, index=dates)
        mock_ohlcv.return_value = short_df
        _, inst = pool_and_instance

        result = execute_strategy_tick(inst, exchange=None)
        assert result["action"] == "none"
        assert "Insufficient" in result["message"]

    @patch("core.executor._get_ohlcv_cached")
    @patch("core.executor.STRATEGY_REGISTRY", {})
    def test_unknown_strategy(self, mock_ohlcv, pool_and_instance, mock_df):
        from core.executor import execute_strategy_tick
        mock_ohlcv.return_value = mock_df
        _, inst = pool_and_instance

        result = execute_strategy_tick(inst, exchange=None)
        assert result["action"] == "error"
        assert "Unknown strategy" in result["message"]


# ==================== Open/Close Position ====================


class TestPositionManagement:
    @patch("core.executor._get_ohlcv_cached")
    @patch("core.executor.STRATEGY_REGISTRY", {
        "ma_crossover": {
            "func": lambda df, **kw: pd.Series([0] * (len(df) - 1) + [-1], index=df.index),
            "default_params": {},
        }
    })
    def test_sell_signal_closes_position(self, mock_ohlcv, pool_and_instance, mock_df):
        from core.executor import execute_strategy_tick
        from core.models import update_strategy_instance, get_strategy_instance, list_trades

        mock_ohlcv.return_value = mock_df
        pool, inst = pool_and_instance

        # Set up existing long position
        current_price = float(mock_df["close"].iloc[-1])
        update_strategy_instance(inst.id,
                                 current_position=0.1,
                                 entry_price=current_price - 100,
                                 last_signal_time="2024-01-01T00:00:00")
        inst.current_position = 0.1
        inst.entry_price = current_price - 100
        inst.last_signal_time = "2024-01-01T00:00:00"

        result = execute_strategy_tick(inst, exchange=None)
        assert result["action"] == "close"

        # Check position was cleared
        updated = get_strategy_instance(inst.id)
        assert updated.current_position == 0.0

        # Check trade was recorded
        trades = list_trades(strategy_instance_id=inst.id)
        assert len(trades) >= 1

    def test_open_position_with_exchange(self, pool_and_instance):
        from core.executor import _open_position
        from core.models import get_strategy_instance

        pool, inst = pool_and_instance
        mock_exchange = MagicMock()
        mock_exchange.create_market_order.return_value = {
            "id": "EX123",
            "average": 50100,
            "filled": 0.1,
            "fee": {"cost": 5.0},
        }

        result = _open_position(inst, pool, mock_exchange, "buy", 0.1, 50000, "test")
        assert result["action"] == "open"
        mock_exchange.create_market_order.assert_called_once()

        updated = get_strategy_instance(inst.id)
        assert updated.current_position == 0.1

    def test_close_position_records_trade(self, pool_and_instance):
        from core.executor import _close_position
        from core.models import update_strategy_instance, list_trades, get_fund_pool

        pool, inst = pool_and_instance
        update_strategy_instance(inst.id,
                                 current_position=0.1,
                                 entry_price=50000,
                                 last_signal_time="2024-01-01T00:00:00")
        inst.current_position = 0.1
        inst.entry_price = 50000
        inst.last_signal_time = "2024-01-01T00:00:00"

        result = _close_position(inst, pool, exchange=None, price=51000, reason="test_close")
        assert result["action"] == "close"

        trades = list_trades(strategy_instance_id=inst.id)
        assert len(trades) == 1
        assert trades[0].exit_reason == "test_close"
        assert trades[0].pnl > 0  # Profit trade

        # Check pool equity was updated
        updated_pool = get_fund_pool(pool.id)
        assert updated_pool.current_equity > pool.current_equity

    def test_close_no_position(self, pool_and_instance):
        from core.executor import _close_position
        pool, inst = pool_and_instance
        result = _close_position(inst, pool, exchange=None, price=50000, reason="test")
        assert result["action"] == "none"
        assert "No position" in result["message"]

    def test_open_position_exchange_error(self, pool_and_instance):
        from core.executor import _open_position
        pool, inst = pool_and_instance
        mock_exchange = MagicMock()
        mock_exchange.create_market_order.side_effect = Exception("API Error")

        result = _open_position(inst, pool, mock_exchange, "buy", 0.1, 50000, "test")
        assert result["action"] == "error"
        assert "Order failed" in result["message"]


# ==================== OHLCV Cache ====================


class TestOHLCVCache:
    def test_cache_returns_same_data(self, mock_df):
        from core.executor import _get_ohlcv_cached, _ohlcv_cache
        _ohlcv_cache.clear()

        mock_exchange = MagicMock()
        mock_exchange_calls = [0]

        def mock_fetch(ex, sym, tf, limit=500):
            mock_exchange_calls[0] += 1
            return mock_df

        with patch("core.executor.fetch_ohlcv", mock_fetch):
            df1 = _get_ohlcv_cached(mock_exchange, "BTC/USDT", "4h")
            df2 = _get_ohlcv_cached(mock_exchange, "BTC/USDT", "4h")
            # Should only call fetch once due to cache
            assert mock_exchange_calls[0] == 1
            assert df1.equals(df2)

        _ohlcv_cache.clear()

    def test_cache_different_symbols(self, mock_df):
        from core.executor import _get_ohlcv_cached, _ohlcv_cache
        _ohlcv_cache.clear()

        call_count = [0]

        def mock_fetch(ex, sym, tf, limit=500):
            call_count[0] += 1
            return mock_df

        with patch("core.executor.fetch_ohlcv", mock_fetch):
            _get_ohlcv_cached(None, "BTC/USDT", "4h")
            _get_ohlcv_cached(None, "ETH/USDT", "4h")
            assert call_count[0] == 2

        _ohlcv_cache.clear()


# ==================== Force Close ====================


class TestForceClose:
    @patch("core.executor._get_ohlcv_cached")
    def test_force_close_position(self, mock_ohlcv, pool_and_instance, mock_df):
        from core.executor import force_close_position
        from core.models import update_strategy_instance, get_strategy_instance

        mock_ohlcv.return_value = mock_df
        pool, inst = pool_and_instance
        update_strategy_instance(inst.id,
                                 current_position=0.1,
                                 entry_price=50000,
                                 last_signal_time="2024-01-01T00:00:00")

        result = force_close_position(inst.id, exchange=None)
        assert result["success"] is True

        updated = get_strategy_instance(inst.id)
        assert updated.current_position == 0.0

    def test_force_close_no_instance(self):
        from core.executor import force_close_position
        result = force_close_position("nonexistent-id", exchange=None)
        assert result["success"] is False

    def test_force_close_no_position(self, pool_and_instance):
        from core.executor import force_close_position
        _, inst = pool_and_instance
        result = force_close_position(inst.id, exchange=None)
        assert result["success"] is False
        assert "No position" in result["message"]

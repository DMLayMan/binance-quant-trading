"""数据库和模型层单元测试"""

import pytest
import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    """每个测试使用独立的临时数据库"""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("BQT_DB_PATH", db_path)

    # 重新加载模块以使用新路径
    import core.database
    monkeypatch.setattr(core.database, "DB_PATH", db_path)
    core.database.init_db()

    yield db_path


# ==================== Database ====================


class TestDatabase:
    def test_init_db_creates_tables(self, temp_db):
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "fund_pools" in table_names
        assert "strategy_instances" in table_names
        assert "orders" in table_names
        assert "trades" in table_names
        assert "equity_snapshots" in table_names
        assert "risk_events" in table_names
        conn.close()

    def test_wal_mode(self, temp_db):
        from core.database import get_connection
        conn = get_connection()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_foreign_keys_enabled(self, temp_db):
        from core.database import get_connection
        conn = get_connection()
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_now_iso_format(self):
        from core.database import now_iso
        iso = now_iso()
        assert len(iso) == 19  # YYYY-MM-DDTHH:MM:SS
        assert "T" in iso

    def test_today_str_format(self):
        from core.database import today_str
        td = today_str()
        assert len(td) == 10  # YYYY-MM-DD
        assert td.count("-") == 2

    def test_get_db_path_creates_directory(self, tmp_path, monkeypatch):
        import core.database
        nested = str(tmp_path / "a" / "b" / "c" / "test.db")
        monkeypatch.setattr(core.database, "DB_PATH", nested)
        path = core.database.get_db_path()
        assert os.path.isdir(os.path.dirname(path))


# ==================== FundPool ====================


class TestFundPool:
    def test_create_fund_pool(self):
        from core.models import create_fund_pool
        pool = create_fund_pool(name="Test Pool", allocated_amount=10000)
        assert pool.name == "Test Pool"
        assert pool.allocated_amount == 10000
        assert pool.current_equity == 10000
        assert pool.peak_equity == 10000
        assert pool.status == "active"
        assert pool.id is not None

    def test_create_fund_pool_with_risk_params(self):
        from core.models import create_fund_pool
        pool = create_fund_pool(
            name="Risk Pool",
            allocated_amount=50000,
            max_daily_loss_pct=0.03,
            max_drawdown_pct=0.10,
            take_profit_pct=0.20,
            stop_loss_pct=0.15,
        )
        assert pool.max_daily_loss_pct == 0.03
        assert pool.max_drawdown_pct == 0.10
        assert pool.take_profit_pct == 0.20
        assert pool.stop_loss_pct == 0.15

    def test_get_fund_pool(self):
        from core.models import create_fund_pool, get_fund_pool
        pool = create_fund_pool(name="Fetch Test", allocated_amount=5000)
        fetched = get_fund_pool(pool.id)
        assert fetched is not None
        assert fetched.name == "Fetch Test"
        assert fetched.allocated_amount == 5000

    def test_get_fund_pool_not_found(self):
        from core.models import get_fund_pool
        result = get_fund_pool("nonexistent-id")
        assert result is None

    def test_list_fund_pools(self):
        from core.models import create_fund_pool, list_fund_pools
        create_fund_pool(name="Pool A", allocated_amount=1000)
        create_fund_pool(name="Pool B", allocated_amount=2000)
        pools = list_fund_pools()
        assert len(pools) >= 2
        names = [p.name for p in pools]
        assert "Pool A" in names
        assert "Pool B" in names

    def test_list_fund_pools_filter_status(self):
        from core.models import create_fund_pool, list_fund_pools, update_fund_pool
        p1 = create_fund_pool(name="Active Pool", allocated_amount=1000)
        p2 = create_fund_pool(name="Paused Pool", allocated_amount=2000)
        update_fund_pool(p2.id, status="paused")

        active = list_fund_pools(status="active")
        paused = list_fund_pools(status="paused")
        assert any(p.id == p1.id for p in active)
        assert any(p.id == p2.id for p in paused)

    def test_update_fund_pool(self):
        from core.models import create_fund_pool, update_fund_pool, get_fund_pool
        pool = create_fund_pool(name="Update Test", allocated_amount=10000)
        update_fund_pool(pool.id, current_equity=9500, status="paused")
        updated = get_fund_pool(pool.id)
        assert updated.current_equity == 9500
        assert updated.status == "paused"

    def test_update_fund_pool_returns_updated(self):
        from core.models import create_fund_pool, update_fund_pool
        pool = create_fund_pool(name="Return Test", allocated_amount=10000)
        result = update_fund_pool(pool.id, name="Updated Name")
        assert result.name == "Updated Name"


# ==================== StrategyInstance ====================


class TestStrategyInstance:
    def _create_pool(self):
        from core.models import create_fund_pool
        return create_fund_pool(name="Test Pool", allocated_amount=10000)

    def test_create_strategy_instance(self):
        from core.models import create_strategy_instance
        pool = self._create_pool()
        inst = create_strategy_instance(
            fund_pool_id=pool.id,
            strategy_name="ma_crossover",
            symbol="ETH/USDT",
            timeframe="1h",
        )
        assert inst.fund_pool_id == pool.id
        assert inst.strategy_name == "ma_crossover"
        assert inst.symbol == "ETH/USDT"
        assert inst.timeframe == "1h"
        assert inst.status == "pending"
        assert inst.current_position == 0.0
        assert inst.total_pnl == 0.0

    def test_create_with_params(self):
        from core.models import create_strategy_instance
        pool = self._create_pool()
        params = {"fast_period": 10, "slow_period": 30}
        inst = create_strategy_instance(
            fund_pool_id=pool.id,
            strategy_name="ma_crossover",
            params=params,
        )
        assert inst.get_params() == params

    def test_get_strategy_instance(self):
        from core.models import create_strategy_instance, get_strategy_instance
        pool = self._create_pool()
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        fetched = get_strategy_instance(inst.id)
        assert fetched is not None
        assert fetched.strategy_name == "rsi"

    def test_get_strategy_instance_not_found(self):
        from core.models import get_strategy_instance
        result = get_strategy_instance("nonexistent")
        assert result is None

    def test_list_strategy_instances(self):
        from core.models import create_strategy_instance, list_strategy_instances
        pool = self._create_pool()
        create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        create_strategy_instance(fund_pool_id=pool.id, strategy_name="macd")
        instances = list_strategy_instances(fund_pool_id=pool.id)
        assert len(instances) >= 2

    def test_list_instances_filter_status(self):
        from core.models import create_strategy_instance, list_strategy_instances, update_strategy_instance
        pool = self._create_pool()
        i1 = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        i2 = create_strategy_instance(fund_pool_id=pool.id, strategy_name="macd")
        update_strategy_instance(i1.id, status="running")

        running = list_strategy_instances(fund_pool_id=pool.id, status="running")
        pending = list_strategy_instances(fund_pool_id=pool.id, status="pending")
        assert any(i.id == i1.id for i in running)
        assert any(i.id == i2.id for i in pending)

    def test_get_runnable_instances(self):
        from core.models import (
            create_strategy_instance, update_strategy_instance,
            get_runnable_instances,
        )
        pool = self._create_pool()
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        # 设置为 running 且 next_check_time 在过去
        update_strategy_instance(inst.id, status="running",
                                 next_check_time="2020-01-01T00:00:00")
        runnable = get_runnable_instances("2025-01-01T00:00:00")
        assert any(i.id == inst.id for i in runnable)

    def test_runnable_excludes_paused(self):
        from core.models import (
            create_strategy_instance, update_strategy_instance,
            get_runnable_instances,
        )
        pool = self._create_pool()
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        update_strategy_instance(inst.id, status="paused",
                                 next_check_time="2020-01-01T00:00:00")
        runnable = get_runnable_instances("2025-01-01T00:00:00")
        assert not any(i.id == inst.id for i in runnable)

    def test_update_strategy_instance(self):
        from core.models import create_strategy_instance, update_strategy_instance, get_strategy_instance
        pool = self._create_pool()
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        update_strategy_instance(inst.id, total_pnl=150.50, trade_count=5)
        updated = get_strategy_instance(inst.id)
        assert updated.total_pnl == 150.50
        assert updated.trade_count == 5

    def test_update_params_as_dict(self):
        from core.models import create_strategy_instance, update_strategy_instance, get_strategy_instance
        pool = self._create_pool()
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        update_strategy_instance(inst.id, params={"rsi_period": 21})
        updated = get_strategy_instance(inst.id)
        assert updated.get_params() == {"rsi_period": 21}

    def test_win_rate_property(self):
        from core.models import create_strategy_instance, update_strategy_instance, get_strategy_instance
        pool = self._create_pool()
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        update_strategy_instance(inst.id, trade_count=10, win_count=6)
        updated = get_strategy_instance(inst.id)
        assert updated.win_rate == 60.0

    def test_win_rate_zero_trades(self):
        from core.models import create_strategy_instance
        pool = self._create_pool()
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        assert inst.win_rate == 0.0


# ==================== Order ====================


class TestOrder:
    def _create_instance(self):
        from core.models import create_fund_pool, create_strategy_instance
        pool = create_fund_pool(name="Order Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        return inst

    def test_create_order(self):
        from core.models import create_order
        inst = self._create_instance()
        order = create_order(
            strategy_instance_id=inst.id,
            symbol="BTC/USDT",
            side="buy",
            amount=0.01,
            reason="signal_buy",
        )
        assert order.strategy_instance_id == inst.id
        assert order.symbol == "BTC/USDT"
        assert order.side == "buy"
        assert order.amount == 0.01
        assert order.status == "pending"
        assert order.filled_amount == 0.0

    def test_update_order(self):
        from core.models import create_order, update_order, list_orders
        inst = self._create_instance()
        order = create_order(
            strategy_instance_id=inst.id, symbol="BTC/USDT",
            side="buy", amount=0.01, reason="test",
        )
        update_order(order.id, status="filled", filled_amount=0.01, price=50000.0)
        orders = list_orders(strategy_instance_id=inst.id)
        filled = [o for o in orders if o.id == order.id][0]
        assert filled.status == "filled"
        assert filled.filled_amount == 0.01
        assert filled.price == 50000.0

    def test_list_orders(self):
        from core.models import create_order, list_orders
        inst = self._create_instance()
        create_order(strategy_instance_id=inst.id, symbol="BTC/USDT",
                     side="buy", amount=0.01, reason="test1")
        create_order(strategy_instance_id=inst.id, symbol="BTC/USDT",
                     side="sell", amount=0.01, reason="test2")
        orders = list_orders(strategy_instance_id=inst.id)
        assert len(orders) == 2

    def test_list_orders_filter_status(self):
        from core.models import create_order, update_order, list_orders
        inst = self._create_instance()
        o1 = create_order(strategy_instance_id=inst.id, symbol="BTC/USDT",
                          side="buy", amount=0.01, reason="test")
        create_order(strategy_instance_id=inst.id, symbol="BTC/USDT",
                     side="sell", amount=0.01, reason="test")
        update_order(o1.id, status="filled")

        filled = list_orders(strategy_instance_id=inst.id, status="filled")
        pending = list_orders(strategy_instance_id=inst.id, status="pending")
        assert len(filled) == 1
        assert len(pending) == 1

    def test_list_orders_limit(self):
        from core.models import create_order, list_orders
        inst = self._create_instance()
        for i in range(10):
            create_order(strategy_instance_id=inst.id, symbol="BTC/USDT",
                         side="buy", amount=0.01, reason=f"test_{i}")
        orders = list_orders(strategy_instance_id=inst.id, limit=5)
        assert len(orders) == 5


# ==================== Trade ====================


class TestTrade:
    def _create_instance(self):
        from core.models import create_fund_pool, create_strategy_instance
        pool = create_fund_pool(name="Trade Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        return pool, inst

    def test_create_trade(self):
        from core.models import create_trade
        pool, inst = self._create_instance()
        trade = create_trade(
            strategy_instance_id=inst.id,
            fund_pool_id=pool.id,
            symbol="BTC/USDT",
            side="long",
            entry_price=50000,
            exit_price=51000,
            amount=0.1,
            pnl=100,
            total_fee=5,
            exit_reason="take_profit",
            entry_time="2024-01-01T10:00:00",
            exit_time="2024-01-01T14:00:00",
        )
        assert trade.pnl == 100
        assert trade.exit_reason == "take_profit"
        assert trade.holding_seconds == 14400  # 4 hours

    def test_trade_pnl_pct_long(self):
        from core.models import create_trade
        pool, inst = self._create_instance()
        trade = create_trade(
            strategy_instance_id=inst.id, fund_pool_id=pool.id,
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            amount=0.1, pnl=100, total_fee=5,
            exit_reason="tp",
            entry_time="2024-01-01T10:00:00",
            exit_time="2024-01-01T14:00:00",
        )
        assert trade.pnl_pct == pytest.approx(2.0)  # (51000-50000)/50000 * 100

    def test_trade_pnl_pct_short(self):
        from core.models import create_trade
        pool, inst = self._create_instance()
        trade = create_trade(
            strategy_instance_id=inst.id, fund_pool_id=pool.id,
            symbol="BTC/USDT", side="short",
            entry_price=50000, exit_price=49000,
            amount=0.1, pnl=100, total_fee=5,
            exit_reason="tp",
            entry_time="2024-01-01T10:00:00",
            exit_time="2024-01-01T14:00:00",
        )
        # short side: -(49000-50000)/50000 * 100 = 2.0
        assert trade.pnl_pct == pytest.approx(2.0)

    def test_list_trades(self):
        from core.models import create_trade, list_trades
        pool, inst = self._create_instance()
        for i in range(5):
            create_trade(
                strategy_instance_id=inst.id, fund_pool_id=pool.id,
                symbol="BTC/USDT", side="long",
                entry_price=50000, exit_price=50100 + i * 100,
                amount=0.1, pnl=10 + i * 10, total_fee=1,
                exit_reason="tp",
                entry_time=f"2024-01-0{i+1}T10:00:00",
                exit_time=f"2024-01-0{i+1}T14:00:00",
            )
        trades = list_trades(strategy_instance_id=inst.id)
        assert len(trades) == 5

    def test_list_trades_by_pool(self):
        from core.models import create_trade, list_trades
        pool, inst = self._create_instance()
        create_trade(
            strategy_instance_id=inst.id, fund_pool_id=pool.id,
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            amount=0.1, pnl=100, total_fee=1,
            exit_reason="tp",
            entry_time="2024-01-01T10:00:00",
            exit_time="2024-01-01T14:00:00",
        )
        trades = list_trades(fund_pool_id=pool.id)
        assert len(trades) >= 1


# ==================== Equity Snapshot ====================


class TestEquitySnapshot:
    def test_record_and_get_equity(self):
        from core.models import create_fund_pool, record_equity_snapshot, get_equity_history
        pool = create_fund_pool(name="Equity Test", allocated_amount=10000)
        record_equity_snapshot(pool.id, 10100)
        record_equity_snapshot(pool.id, 10200)
        record_equity_snapshot(pool.id, 10150)

        history = get_equity_history(pool.id)
        assert len(history) == 3
        # Should be in chronological order (oldest first)
        equities = [h["equity"] for h in history]
        assert equities == [10100, 10200, 10150]

    def test_equity_history_limit(self):
        from core.models import create_fund_pool, record_equity_snapshot, get_equity_history
        pool = create_fund_pool(name="Limit Test", allocated_amount=10000)
        for i in range(10):
            record_equity_snapshot(pool.id, 10000 + i * 10)
        history = get_equity_history(pool.id, limit=5)
        assert len(history) == 5


# ==================== Risk Event ====================


class TestRiskEvent:
    def test_record_risk_event(self):
        from core.models import create_fund_pool, record_risk_event
        from core.database import get_connection
        pool = create_fund_pool(name="Risk Event Test", allocated_amount=10000)
        record_risk_event("daily_loss_halt", "Daily loss exceeded 5%", fund_pool_id=pool.id)

        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM risk_events WHERE fund_pool_id=?", (pool.id,)
            ).fetchall()
            assert len(rows) == 1
            assert dict(rows[0])["event_type"] == "daily_loss_halt"
        finally:
            conn.close()

    def test_risk_event_with_instance(self):
        from core.models import create_fund_pool, create_strategy_instance, record_risk_event
        from core.database import get_connection
        pool = create_fund_pool(name="Risk Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        record_risk_event("strategy_risk_block", "Too many losses",
                          strategy_instance_id=inst.id, fund_pool_id=pool.id)

        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM risk_events WHERE strategy_instance_id=?", (inst.id,)
            ).fetchall()
            assert len(rows) == 1
        finally:
            conn.close()


# ==================== next_check_time ====================


class TestNextCheckTime:
    def test_next_check_time_format(self):
        from core.models import next_check_time
        nct = next_check_time("4h")
        assert len(nct) == 19
        assert "T" in nct

    def test_next_check_time_future(self):
        from core.models import next_check_time
        from core.database import now_iso
        nct = next_check_time("1m")
        now = now_iso()
        # next_check_time should be in the future
        assert nct >= now

    def test_next_check_time_default(self):
        from core.models import next_check_time
        # Unknown timeframe defaults to 4h interval
        nct = next_check_time("unknown")
        assert len(nct) == 19

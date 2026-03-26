"""托管交易 API 路由测试 — funds, instances, orders_trades"""

import pytest
import os
import sys
import json

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
def client(monkeypatch):
    """创建 FastAPI TestClient"""
    from unittest.mock import MagicMock, AsyncMock, patch

    # Mock exchange and config
    mock_exchange = MagicMock()
    mock_config = {
        "api_key": "",
        "api_secret": "",
        "sandbox": True,
        "strategy_name": "ma_crossover",
        "risk": {},
    }

    # Patch dependencies before importing server
    import api.dependencies as deps
    monkeypatch.setattr(deps, "_exchange", None)
    monkeypatch.setattr(deps, "_config", mock_config)

    from fastapi.testclient import TestClient
    from api.server import app

    # Override lifespan to avoid startup logic
    @pytest.fixture
    def no_lifespan():
        pass

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ==================== Fund Pool API ====================


class TestFundPoolAPI:
    def test_create_fund_pool(self, client):
        resp = client.post("/api/funds", json={
            "name": "Test Pool",
            "allocated_amount": 10000,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Pool"
        assert data["allocated_amount"] == 10000
        assert data["status"] == "active"
        assert data["pnl"] == 0
        assert data["pnl_pct"] == 0

    def test_create_fund_pool_with_risk_params(self, client):
        resp = client.post("/api/funds", json={
            "name": "Risk Pool",
            "allocated_amount": 50000,
            "max_daily_loss_pct": 0.03,
            "max_drawdown_pct": 0.10,
            "take_profit_pct": 0.25,
            "stop_loss_pct": 0.15,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["max_daily_loss_pct"] == 0.03
        assert data["take_profit_pct"] == 0.25

    def test_create_fund_pool_invalid_amount(self, client):
        resp = client.post("/api/funds", json={
            "name": "Bad Pool",
            "allocated_amount": -100,
        })
        assert resp.status_code == 400

    def test_list_fund_pools(self, client):
        client.post("/api/funds", json={"name": "A", "allocated_amount": 1000})
        client.post("/api/funds", json={"name": "B", "allocated_amount": 2000})
        resp = client.get("/api/funds")
        assert resp.status_code == 200
        pools = resp.json()
        assert len(pools) >= 2

    def test_list_fund_pools_filter_status(self, client):
        r1 = client.post("/api/funds", json={"name": "Active", "allocated_amount": 1000})
        pool_id = r1.json()["id"]
        client.post(f"/api/funds/{pool_id}/pause")

        resp = client.get("/api/funds?status=paused")
        assert resp.status_code == 200
        pools = resp.json()
        assert any(p["id"] == pool_id for p in pools)

    def test_get_fund_pool(self, client):
        r = client.post("/api/funds", json={"name": "Detail", "allocated_amount": 5000})
        pool_id = r.json()["id"]

        resp = client.get(f"/api/funds/{pool_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Detail"
        assert "equity_history" in data

    def test_get_fund_pool_not_found(self, client):
        resp = client.get("/api/funds/nonexistent-id")
        assert resp.status_code == 404

    def test_update_fund_pool(self, client):
        r = client.post("/api/funds", json={"name": "Update", "allocated_amount": 5000})
        pool_id = r.json()["id"]

        resp = client.put(f"/api/funds/{pool_id}", json={
            "name": "Updated Name",
            "max_daily_loss_pct": 0.08,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["max_daily_loss_pct"] == 0.08

    def test_update_fund_pool_empty(self, client):
        r = client.post("/api/funds", json={"name": "Empty", "allocated_amount": 5000})
        pool_id = r.json()["id"]

        resp = client.put(f"/api/funds/{pool_id}", json={})
        assert resp.status_code == 400

    def test_pause_fund_pool(self, client):
        r = client.post("/api/funds", json={"name": "Pause", "allocated_amount": 5000})
        pool_id = r.json()["id"]

        resp = client.post(f"/api/funds/{pool_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_pause_non_active_pool(self, client):
        r = client.post("/api/funds", json={"name": "Pause2", "allocated_amount": 5000})
        pool_id = r.json()["id"]
        client.post(f"/api/funds/{pool_id}/pause")

        resp = client.post(f"/api/funds/{pool_id}/pause")
        assert resp.status_code == 400

    def test_resume_fund_pool(self, client):
        r = client.post("/api/funds", json={"name": "Resume", "allocated_amount": 5000})
        pool_id = r.json()["id"]
        client.post(f"/api/funds/{pool_id}/pause")

        resp = client.post(f"/api/funds/{pool_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_resume_non_paused_pool(self, client):
        r = client.post("/api/funds", json={"name": "Resume2", "allocated_amount": 5000})
        pool_id = r.json()["id"]

        resp = client.post(f"/api/funds/{pool_id}/resume")
        assert resp.status_code == 400

    def test_stop_fund_pool(self, client):
        r = client.post("/api/funds", json={"name": "Stop", "allocated_amount": 5000})
        pool_id = r.json()["id"]

        resp = client.post(f"/api/funds/{pool_id}/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_stop_already_stopped(self, client):
        r = client.post("/api/funds", json={"name": "Stop2", "allocated_amount": 5000})
        pool_id = r.json()["id"]
        client.post(f"/api/funds/{pool_id}/stop")

        resp = client.post(f"/api/funds/{pool_id}/stop")
        assert resp.status_code == 400


# ==================== Strategy Instance API ====================


class TestInstanceAPI:
    def _create_pool(self, client):
        r = client.post("/api/funds", json={"name": "Inst Pool", "allocated_amount": 10000})
        return r.json()["id"]

    def test_create_instance(self, client):
        pool_id = self._create_pool(client)
        resp = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
            "symbol": "ETH/USDT",
            "timeframe": "1h",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["strategy_name"] == "ma_crossover"
        assert data["symbol"] == "ETH/USDT"
        assert data["status"] == "pending"

    def test_create_instance_invalid_strategy(self, client):
        pool_id = self._create_pool(client)
        resp = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "nonexistent_strategy",
        })
        assert resp.status_code == 400

    def test_create_instance_pool_not_found(self, client):
        resp = client.post("/api/instances", json={
            "fund_pool_id": "nonexistent",
            "strategy_name": "ma_crossover",
        })
        assert resp.status_code == 404

    def test_create_instance_invalid_timeframe(self, client):
        pool_id = self._create_pool(client)
        resp = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
            "timeframe": "3h",
        })
        assert resp.status_code == 400

    def test_list_instances(self, client):
        pool_id = self._create_pool(client)
        client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "rsi",
        })

        resp = client.get("/api/instances")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_list_instances_filter_pool(self, client):
        pool_id = self._create_pool(client)
        client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })

        resp = client.get(f"/api/instances?fund_pool_id={pool_id}")
        assert resp.status_code == 200
        for inst in resp.json():
            assert inst["fund_pool_id"] == pool_id

    def test_get_instance_detail(self, client):
        pool_id = self._create_pool(client)
        r = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        inst_id = r.json()["id"]

        resp = client.get(f"/api/instances/{inst_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "recent_orders" in data
        assert "recent_trades" in data

    def test_get_instance_not_found(self, client):
        resp = client.get("/api/instances/nonexistent")
        assert resp.status_code == 404

    def test_update_instance(self, client):
        pool_id = self._create_pool(client)
        r = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        inst_id = r.json()["id"]

        resp = client.put(f"/api/instances/{inst_id}", json={
            "stop_loss_atr_mult": 3.0,
            "take_profit_atr_mult": 6.0,
        })
        assert resp.status_code == 200
        assert resp.json()["stop_loss_atr_mult"] == 3.0
        assert resp.json()["take_profit_atr_mult"] == 6.0

    def test_update_running_instance_blocked(self, client):
        pool_id = self._create_pool(client)
        r = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        inst_id = r.json()["id"]
        client.post(f"/api/instances/{inst_id}/start")

        resp = client.put(f"/api/instances/{inst_id}", json={
            "stop_loss_atr_mult": 3.0,
        })
        assert resp.status_code == 400

    def test_start_instance(self, client):
        pool_id = self._create_pool(client)
        r = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        inst_id = r.json()["id"]

        resp = client.post(f"/api/instances/{inst_id}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_start_already_running(self, client):
        pool_id = self._create_pool(client)
        r = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        inst_id = r.json()["id"]
        client.post(f"/api/instances/{inst_id}/start")

        resp = client.post(f"/api/instances/{inst_id}/start")
        assert resp.status_code == 400

    def test_pause_instance(self, client):
        pool_id = self._create_pool(client)
        r = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        inst_id = r.json()["id"]
        client.post(f"/api/instances/{inst_id}/start")

        resp = client.post(f"/api/instances/{inst_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_stop_instance(self, client):
        pool_id = self._create_pool(client)
        r = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        inst_id = r.json()["id"]

        resp = client.post(f"/api/instances/{inst_id}/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_instance_lifecycle(self, client):
        """完整生命周期: pending → running → paused → running → stopped"""
        pool_id = self._create_pool(client)
        r = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        })
        inst_id = r.json()["id"]
        assert r.json()["status"] == "pending"

        # Start
        r = client.post(f"/api/instances/{inst_id}/start")
        assert r.json()["status"] == "running"

        # Pause
        r = client.post(f"/api/instances/{inst_id}/pause")
        assert r.json()["status"] == "paused"

        # Resume (start again)
        r = client.post(f"/api/instances/{inst_id}/start")
        assert r.json()["status"] == "running"

        # Stop
        r = client.post(f"/api/instances/{inst_id}/stop")
        assert r.json()["status"] == "stopped"


# ==================== Orders & Trades API ====================


class TestOrdersTradesAPI:
    def test_get_orders_empty(self, client):
        resp = client.get("/api/orders")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_trades_empty(self, client):
        resp = client.get("/api/trades")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_trade_stats_empty(self, client):
        resp = client.get("/api/trades/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 0
        assert data["win_rate"] == 0

    def test_get_orders_with_data(self, client):
        # Create some order data directly
        from core.models import create_fund_pool, create_strategy_instance, create_order
        pool = create_fund_pool(name="Order Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        create_order(strategy_instance_id=inst.id, symbol="BTC/USDT",
                     side="buy", amount=0.01, reason="test")
        create_order(strategy_instance_id=inst.id, symbol="BTC/USDT",
                     side="sell", amount=0.01, reason="test")

        resp = client.get(f"/api/orders?strategy_instance_id={inst.id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_trades_with_data(self, client):
        from core.models import create_fund_pool, create_strategy_instance, create_trade
        pool = create_fund_pool(name="Trade Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        create_trade(
            strategy_instance_id=inst.id, fund_pool_id=pool.id,
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            amount=0.1, pnl=100, total_fee=5,
            exit_reason="tp",
            entry_time="2024-01-01T10:00:00",
            exit_time="2024-01-01T14:00:00",
        )

        resp = client.get(f"/api/trades?fund_pool_id={pool.id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_trade_stats_with_data(self, client):
        from core.models import create_fund_pool, create_strategy_instance, create_trade
        pool = create_fund_pool(name="Stats Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")

        # 3 trades: 2 wins, 1 loss
        create_trade(
            strategy_instance_id=inst.id, fund_pool_id=pool.id,
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            amount=0.1, pnl=100, total_fee=5,
            exit_reason="tp",
            entry_time="2024-01-01T10:00:00",
            exit_time="2024-01-01T14:00:00",
        )
        create_trade(
            strategy_instance_id=inst.id, fund_pool_id=pool.id,
            symbol="BTC/USDT", side="long",
            entry_price=51000, exit_price=52000,
            amount=0.1, pnl=100, total_fee=5,
            exit_reason="tp",
            entry_time="2024-01-02T10:00:00",
            exit_time="2024-01-02T14:00:00",
        )
        create_trade(
            strategy_instance_id=inst.id, fund_pool_id=pool.id,
            symbol="BTC/USDT", side="long",
            entry_price=52000, exit_price=51000,
            amount=0.1, pnl=-100, total_fee=5,
            exit_reason="sl",
            entry_time="2024-01-03T10:00:00",
            exit_time="2024-01-03T14:00:00",
        )

        resp = client.get(f"/api/trades/stats?fund_pool_id={pool.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 3
        assert data["winning_trades"] == 2
        assert data["losing_trades"] == 1
        assert data["win_rate"] == pytest.approx(66.67, abs=0.1)
        assert data["total_pnl"] == 100  # 100 + 100 - 100
        assert data["total_fees"] == 15

    def test_get_risk_events(self, client):
        from core.models import create_fund_pool, record_risk_event
        pool = create_fund_pool(name="Risk Event Test", allocated_amount=10000)
        record_risk_event("daily_loss_halt", "Daily loss exceeded 5%", fund_pool_id=pool.id)

        resp = client.get(f"/api/risk-events?fund_pool_id={pool.id}")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "daily_loss_halt"

    def test_orders_limit(self, client):
        resp = client.get("/api/orders?limit=10")
        assert resp.status_code == 200

    def test_trades_limit(self, client):
        resp = client.get("/api/trades?limit=10")
        assert resp.status_code == 200


# ==================== Pause Pool Cascading ====================


class TestCascading:
    def test_pause_pool_pauses_instances(self, client):
        """暂停资金池时应该级联暂停其运行中的策略实例"""
        pool_id = client.post("/api/funds", json={
            "name": "Cascade", "allocated_amount": 10000,
        }).json()["id"]

        # Create and start an instance
        inst_id = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        }).json()["id"]
        client.post(f"/api/instances/{inst_id}/start")

        # Pause pool
        client.post(f"/api/funds/{pool_id}/pause")

        # Instance should be paused
        inst = client.get(f"/api/instances/{inst_id}").json()
        assert inst["status"] == "paused"

    def test_stop_pool_stops_instances(self, client):
        """停止资金池时应该级联停止所有策略实例"""
        pool_id = client.post("/api/funds", json={
            "name": "Cascade Stop", "allocated_amount": 10000,
        }).json()["id"]

        inst_id = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        }).json()["id"]
        client.post(f"/api/instances/{inst_id}/start")

        # Stop pool
        client.post(f"/api/funds/{pool_id}/stop")

        # Instance should be stopped
        inst = client.get(f"/api/instances/{inst_id}").json()
        assert inst["status"] == "stopped"

    def test_start_instance_inactive_pool(self, client):
        """不能在非活跃资金池上启动策略实例"""
        pool_id = client.post("/api/funds", json={
            "name": "Inactive", "allocated_amount": 10000,
        }).json()["id"]

        inst_id = client.post("/api/instances", json={
            "fund_pool_id": pool_id,
            "strategy_name": "ma_crossover",
        }).json()["id"]

        # Pause pool first
        client.post(f"/api/funds/{pool_id}/pause")

        # Try to start instance
        resp = client.post(f"/api/instances/{inst_id}/start")
        assert resp.status_code == 400

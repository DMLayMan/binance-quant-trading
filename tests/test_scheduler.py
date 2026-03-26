"""调度引擎单元测试"""

import pytest
import os
import sys
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

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


class TestSchedulerLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        from core.scheduler import Scheduler
        s = Scheduler()
        assert s.is_running is False

        await s.start()
        assert s.is_running is True

        await s.stop()
        assert s.is_running is False

    @pytest.mark.asyncio
    async def test_start_twice(self):
        from core.scheduler import Scheduler
        s = Scheduler()
        await s.start()
        await s.start()  # Should not create duplicate task
        assert s.is_running is True
        await s.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        from core.scheduler import Scheduler
        s = Scheduler()
        await s.stop()  # Should not raise
        assert s.is_running is False


class TestSchedulerExecution:
    @pytest.mark.asyncio
    async def test_scan_no_instances(self):
        from core.scheduler import Scheduler
        s = Scheduler()
        # Should not raise even with no instances
        await s._scan_and_execute()

    @pytest.mark.asyncio
    async def test_scan_finds_runnable(self):
        from core.scheduler import Scheduler
        from core.models import (
            create_fund_pool, create_strategy_instance,
            update_strategy_instance, get_strategy_instance,
        )

        pool = create_fund_pool(name="Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        update_strategy_instance(inst.id, status="running",
                                 next_check_time="2020-01-01T00:00:00")

        s = Scheduler()

        with patch("core.scheduler.execute_strategy_tick") as mock_exec:
            mock_exec.return_value = {"action": "none", "signal": 0, "message": ""}
            await s._scan_and_execute()
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_skips_future(self):
        from core.scheduler import Scheduler
        from core.models import (
            create_fund_pool, create_strategy_instance,
            update_strategy_instance,
        )

        pool = create_fund_pool(name="Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        update_strategy_instance(inst.id, status="running",
                                 next_check_time="2099-01-01T00:00:00")

        s = Scheduler()

        with patch("core.scheduler.execute_strategy_tick") as mock_exec:
            await s._scan_and_execute()
            mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_execution_error_handled(self):
        from core.scheduler import Scheduler
        from core.models import (
            create_fund_pool, create_strategy_instance,
            update_strategy_instance, get_strategy_instance,
        )

        pool = create_fund_pool(name="Test", allocated_amount=10000)
        inst = create_strategy_instance(fund_pool_id=pool.id, strategy_name="rsi")
        update_strategy_instance(inst.id, status="running",
                                 next_check_time="2020-01-01T00:00:00")

        s = Scheduler()

        with patch("core.scheduler.execute_strategy_tick") as mock_exec:
            mock_exec.side_effect = Exception("Test error")
            await s._scan_and_execute()

            # Check error was recorded
            updated = get_strategy_instance(inst.id)
            assert updated.error_message == "Test error"

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        from core.scheduler import Scheduler, MAX_CONCURRENT
        from core.models import (
            create_fund_pool, create_strategy_instance,
            update_strategy_instance,
        )

        pool = create_fund_pool(name="Test", allocated_amount=10000)
        # Create more instances than MAX_CONCURRENT
        for i in range(MAX_CONCURRENT + 3):
            inst = create_strategy_instance(fund_pool_id=pool.id,
                                            strategy_name="rsi",
                                            symbol=f"SYM{i}/USDT")
            update_strategy_instance(inst.id, status="running",
                                     next_check_time="2020-01-01T00:00:00")

        s = Scheduler()
        concurrent_count = [0]
        max_concurrent_seen = [0]

        original_execute = None

        def track_concurrent(inst, exchange):
            concurrent_count[0] += 1
            max_concurrent_seen[0] = max(max_concurrent_seen[0], concurrent_count[0])
            import time
            time.sleep(0.01)  # Small delay
            concurrent_count[0] -= 1
            return {"action": "none", "signal": 0, "message": ""}

        with patch("core.scheduler.execute_strategy_tick", side_effect=track_concurrent):
            await s._scan_and_execute()
            # Due to semaphore, max concurrent should be <= MAX_CONCURRENT
            assert max_concurrent_seen[0] <= MAX_CONCURRENT

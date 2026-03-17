"""
执行引擎 — 单个策略实例的完整执行流程

流程: 获取行情 → 计算指标 → 生成信号 → 持仓检查(SL/TP) → 风控检查 → 下单 → 后处理
"""

import logging
import math
from datetime import datetime
from typing import Optional

from core.models import (
    StrategyInstance, FundPool,
    get_fund_pool, update_fund_pool,
    update_strategy_instance,
    create_order, update_order,
    create_trade,
    record_equity_snapshot,
    record_risk_event,
    next_check_time,
    today_str, now_iso,
)
from data.market_data import fetch_ohlcv
from utils.indicators import compute_atr, compute_rsi
from main import STRATEGY_REGISTRY
from core.notifier import notify, NotifyLevel

logger = logging.getLogger(__name__)


# ==================== 行情缓存 ====================

_ohlcv_cache: dict[str, tuple[str, object]] = {}  # key → (expire_iso, df)


def _get_ohlcv_cached(exchange, symbol: str, timeframe: str, limit: int = 500):
    """带缓存的行情获取，同一根 K 线周期内只请求一次"""
    from core.models import TIMEFRAME_SECONDS
    cache_key = f"{symbol}:{timeframe}"
    now = datetime.utcnow()

    if cache_key in _ohlcv_cache:
        expire_str, df = _ohlcv_cache[cache_key]
        if now.strftime("%Y-%m-%dT%H:%M:%S") < expire_str:
            return df

    df = fetch_ohlcv(exchange, symbol, timeframe, limit=limit)

    interval = TIMEFRAME_SECONDS.get(timeframe, 14400)
    ts = int(now.timestamp())
    expire_ts = ((ts // interval) + 1) * interval
    expire_iso = datetime.utcfromtimestamp(expire_ts).strftime("%Y-%m-%dT%H:%M:%S")
    _ohlcv_cache[cache_key] = (expire_iso, df)

    return df


# ==================== 三层风控 ====================


def _check_strategy_risk(inst: StrategyInstance, order_value: float, pool: FundPool) -> tuple[bool, str]:
    """第 1 层: 策略级风控"""
    equity = pool.current_equity

    # 单笔仓位检查
    if equity > 0 and order_value / equity > inst.max_position_pct:
        return False, f"Position size {order_value:.0f} exceeds {inst.max_position_pct*100:.0f}% of equity"

    # 连续亏损
    if inst.consecutive_losses >= 5:
        return False, f"Consecutive losses ({inst.consecutive_losses}) >= 5"

    # 日交易次数
    td = today_str()
    trades_today = inst.trades_today if inst.trades_today_date == td else 0
    if trades_today >= 50:
        return False, f"Daily trade count ({trades_today}) >= 50"

    return True, ""


def _check_pool_risk(pool: FundPool) -> tuple[bool, str]:
    """第 2 层: 资金池级风控"""
    # 日亏损检查
    if pool.daily_start_equity > 0:
        daily_loss = (pool.current_equity - pool.daily_start_equity) / pool.daily_start_equity
        if daily_loss <= -pool.max_daily_loss_pct:
            return False, f"Daily loss {daily_loss*100:.1f}% exceeds limit {pool.max_daily_loss_pct*100:.0f}%"

    # 最大回撤检查
    if pool.peak_equity > 0:
        drawdown = (pool.current_equity - pool.peak_equity) / pool.peak_equity
        if drawdown <= -pool.max_drawdown_pct:
            return False, f"Drawdown {drawdown*100:.1f}% exceeds limit {pool.max_drawdown_pct*100:.0f}%"

    # 总止损检查
    if pool.stop_loss_pct is not None:
        loss_from_start = (pool.current_equity - pool.allocated_amount) / pool.allocated_amount
        if loss_from_start <= -pool.stop_loss_pct:
            return False, f"Total loss {loss_from_start*100:.1f}% hit stop-loss {pool.stop_loss_pct*100:.0f}%"

    return True, ""


def _check_pool_take_profit(pool: FundPool) -> bool:
    """检查资金池是否达到止盈目标"""
    if pool.take_profit_pct is None:
        return False
    gain = (pool.current_equity - pool.allocated_amount) / pool.allocated_amount
    return gain >= pool.take_profit_pct


# ==================== 核心执行 ====================


def execute_strategy_tick(inst: StrategyInstance, exchange) -> dict:
    """
    执行一次策略 tick（一根 K 线的完整处理）

    Returns:
        执行结果 dict: {action, signal, price, message, ...}
    """
    result = {"action": "none", "signal": 0, "message": "", "instance_id": inst.id}

    try:
        # 0. 获取资金池
        pool = get_fund_pool(inst.fund_pool_id)
        if not pool or pool.status != "active":
            result["action"] = "skip"
            result["message"] = f"Fund pool {inst.fund_pool_id} not active"
            update_strategy_instance(inst.id, status="paused",
                                     error_message="Fund pool not active")
            return result

        # 1. 获取行情 + 指标
        df = _get_ohlcv_cached(exchange, inst.symbol, inst.timeframe)
        if df.empty or len(df) < 30:
            result["message"] = "Insufficient market data"
            _schedule_next(inst)
            return result

        df["atr"] = compute_atr(df)
        df["rsi"] = compute_rsi(df["close"])

        current_price = float(df["close"].iloc[-1])
        current_atr = float(df["atr"].iloc[-1])
        if math.isnan(current_atr) or current_atr <= 0:
            current_atr = current_price * 0.02  # fallback 2%

        # 2. 策略信号
        if inst.strategy_name not in STRATEGY_REGISTRY:
            result["action"] = "error"
            result["message"] = f"Unknown strategy: {inst.strategy_name}"
            update_strategy_instance(inst.id, status="error",
                                     error_message=result["message"])
            return result

        strategy = STRATEGY_REGISTRY[inst.strategy_name]
        signal_func = strategy["func"]
        params = {**strategy["default_params"], **inst.get_params()}
        signals = signal_func(df, **params)
        signal = int(signals.iloc[-1])
        result["signal"] = signal
        result["price"] = current_price

        # 更新日内计数器
        td = today_str()
        if inst.trades_today_date != td:
            update_strategy_instance(inst.id, trades_today=0, trades_today_date=td)
            inst.trades_today = 0
            inst.trades_today_date = td

        # 日期切换时重置资金池日起始权益
        if pool.current_date != td:
            update_fund_pool(pool.id, daily_start_equity=pool.current_equity, current_date=td)
            pool.daily_start_equity = pool.current_equity
            pool.current_date = td

        # 3. 持仓检查 — 止损 / 止盈
        if inst.current_position > 0 and inst.entry_price > 0:
            sl_price = inst.entry_price - inst.stop_loss_atr_mult * current_atr
            tp_price = inst.entry_price + inst.take_profit_atr_mult * current_atr

            if current_price <= sl_price:
                result = _close_position(inst, pool, exchange, current_price, "stop_loss")
                _schedule_next(inst)
                return result

            if current_price >= tp_price:
                result = _close_position(inst, pool, exchange, current_price, "take_profit")
                _schedule_next(inst)
                return result

            # 更新未实现盈亏
            unrealized = (current_price - inst.entry_price) * inst.current_position
            update_strategy_instance(inst.id, unrealized_pnl=round(unrealized, 2))

        # 4. 资金池止盈检查
        if _check_pool_take_profit(pool):
            record_risk_event("take_profit_target", "Fund pool reached take-profit target",
                              fund_pool_id=pool.id)
            notify(NotifyLevel.INFO, f"Pool '{pool.name}' reached take-profit target, stopping.")
            # 平掉持仓并停止
            if inst.current_position > 0:
                _close_position(inst, pool, exchange, current_price, "pool_take_profit")
            update_strategy_instance(inst.id, status="stopped")
            update_fund_pool(pool.id, status="stopped")
            result["action"] = "pool_take_profit"
            result["message"] = "Fund pool reached take-profit target, strategy stopped"
            return result

        # 5. 风控检查 (池级)
        pool_ok, pool_reason = _check_pool_risk(pool)
        if not pool_ok:
            record_risk_event("pool_risk_halt", pool_reason, fund_pool_id=pool.id,
                              strategy_instance_id=inst.id)
            notify(NotifyLevel.CRITICAL, f"Pool '{pool.name}' risk halt: {pool_reason}")
            if "stop-loss" in pool_reason.lower():
                # 总止损触发 → 平仓 + 停止
                if inst.current_position > 0:
                    _close_position(inst, pool, exchange, current_price, "pool_stop_loss")
                update_strategy_instance(inst.id, status="stopped")
                update_fund_pool(pool.id, status="stopped")
            else:
                # 日亏损/回撤 → 暂停
                update_strategy_instance(inst.id, status="paused",
                                         error_message=pool_reason)
            result["action"] = "risk_halt"
            result["message"] = pool_reason
            _schedule_next(inst)
            return result

        # 6. 交易执行
        if signal == 1 and inst.current_position <= 0:
            # 先平空仓 (如果有)
            if inst.current_position < 0:
                _close_position(inst, pool, exchange, current_price, "signal_reverse")

            # 计算仓位
            position_value = pool.current_equity * inst.max_position_pct
            risk_amount = pool.current_equity * inst.risk_per_trade_pct
            stop_distance = current_atr * inst.stop_loss_atr_mult
            if stop_distance > 0:
                risk_based_value = (risk_amount / stop_distance) * current_price
                position_value = min(position_value, risk_based_value)

            # 策略级风控
            strat_ok, strat_reason = _check_strategy_risk(inst, position_value, pool)
            if not strat_ok:
                record_risk_event("strategy_risk_block", strat_reason,
                                  strategy_instance_id=inst.id)
                notify(NotifyLevel.WARNING, f"Strategy risk block on {inst.symbol}: {strat_reason}")
                result["action"] = "risk_blocked"
                result["message"] = strat_reason
                _schedule_next(inst)
                return result

            size = position_value / current_price if current_price > 0 else 0
            if size > 0:
                result = _open_position(inst, pool, exchange, "buy", size,
                                        current_price, "signal_buy")

        elif signal == -1 and inst.current_position > 0:
            result = _close_position(inst, pool, exchange, current_price, "signal_sell")

        # 7. 更新信号 & 下次检查时间
        update_strategy_instance(
            inst.id,
            last_signal=signal,
            last_signal_time=now_iso(),
        )
        _schedule_next(inst)

        return result

    except Exception as e:
        logger.error(f"Strategy tick error [{inst.id}]: {e}", exc_info=True)
        result["action"] = "error"
        result["message"] = str(e)
        update_strategy_instance(inst.id, error_message=str(e))
        _schedule_next(inst)
        return result


# ==================== 开仓 / 平仓 ====================


def _open_position(
    inst: StrategyInstance, pool: FundPool, exchange,
    side: str, size: float, price: float, reason: str,
) -> dict:
    """开仓"""
    result = {"action": "open", "signal": 1, "price": price,
              "instance_id": inst.id, "message": ""}

    # 创建订单记录
    order = create_order(inst.id, inst.symbol, side, size, reason)

    try:
        # 调用交易所
        if exchange is not None:
            ex_order = exchange.create_market_order(inst.symbol, side, size)
            fill_price = ex_order.get("average", ex_order.get("price", price))
            filled = ex_order.get("filled", size)
            fee_cost = 0.0
            if ex_order.get("fee"):
                fee_cost = ex_order["fee"].get("cost", 0.0)
            update_order(order.id,
                         exchange_order_id=str(ex_order.get("id", "")),
                         status="filled",
                         filled_amount=filled,
                         price=fill_price,
                         fee=fee_cost,
                         filled_at=now_iso())
            price = fill_price or price
            size = filled or size
        else:
            # Demo 模式
            update_order(order.id, status="filled", filled_amount=size,
                         price=price, filled_at=now_iso())

        # 更新策略实例
        td = today_str()
        trades_today = inst.trades_today + 1
        update_strategy_instance(
            inst.id,
            current_position=size,
            entry_price=price,
            unrealized_pnl=0.0,
            trades_today=trades_today,
            trades_today_date=td,
        )

        result["message"] = f"Opened {side} {size:.6f} @ {price:.2f}"
        logger.info(f"[{inst.id[:8]}] {result['message']}")

    except Exception as e:
        update_order(order.id, status="failed")
        result["action"] = "error"
        result["message"] = f"Order failed: {e}"
        logger.error(f"[{inst.id[:8]}] Open position failed: {e}")

    return result


def _close_position(
    inst: StrategyInstance, pool: FundPool, exchange,
    price: float, reason: str,
) -> dict:
    """平仓"""
    result = {"action": "close", "signal": -1, "price": price,
              "instance_id": inst.id, "message": ""}

    size = abs(inst.current_position)
    if size <= 0:
        result["action"] = "none"
        result["message"] = "No position to close"
        return result

    side = "sell" if inst.current_position > 0 else "buy"
    order = create_order(inst.id, inst.symbol, side, size, reason)

    try:
        fee_cost = 0.0
        if exchange is not None:
            ex_order = exchange.create_market_order(inst.symbol, side, size)
            fill_price = ex_order.get("average", ex_order.get("price", price))
            filled = ex_order.get("filled", size)
            if ex_order.get("fee"):
                fee_cost = ex_order["fee"].get("cost", 0.0)
            update_order(order.id,
                         exchange_order_id=str(ex_order.get("id", "")),
                         status="filled",
                         filled_amount=filled,
                         price=fill_price,
                         fee=fee_cost,
                         filled_at=now_iso())
            price = fill_price or price
        else:
            # Demo: 模拟手续费 0.1%
            fee_cost = size * price * 0.001
            update_order(order.id, status="filled", filled_amount=size,
                         price=price, fee=fee_cost, filled_at=now_iso())

        # 计算盈亏
        pnl = (price - inst.entry_price) * size - fee_cost
        is_win = pnl > 0

        # 记录成交
        create_trade(
            strategy_instance_id=inst.id,
            fund_pool_id=inst.fund_pool_id,
            symbol=inst.symbol,
            side="long",
            entry_price=inst.entry_price,
            exit_price=price,
            amount=size,
            pnl=round(pnl, 2),
            total_fee=round(fee_cost, 2),
            exit_reason=reason,
            entry_time=inst.last_signal_time or inst.created_at,
            exit_time=now_iso(),
            exit_order_id=order.id,
        )

        # 更新策略实例
        new_total_pnl = inst.total_pnl + pnl
        new_trade_count = inst.trade_count + 1
        new_win_count = inst.win_count + (1 if is_win else 0)
        new_consecutive = 0 if is_win else inst.consecutive_losses + 1
        td = today_str()
        trades_today = inst.trades_today + 1

        update_strategy_instance(
            inst.id,
            current_position=0.0,
            entry_price=0.0,
            unrealized_pnl=0.0,
            total_pnl=round(new_total_pnl, 2),
            trade_count=new_trade_count,
            win_count=new_win_count,
            consecutive_losses=new_consecutive,
            trades_today=trades_today,
            trades_today_date=td,
        )

        # 更新资金池权益
        new_equity = pool.current_equity + pnl
        new_peak = max(pool.peak_equity, new_equity)
        update_fund_pool(pool.id,
                         current_equity=round(new_equity, 2),
                         peak_equity=round(new_peak, 2))

        # 权益快照
        record_equity_snapshot(pool.id, round(new_equity, 2))

        result["message"] = (f"Closed {side} {size:.6f} @ {price:.2f}, "
                             f"PnL: {'+'if pnl>0 else ''}{pnl:.2f} ({reason})")
        logger.info(f"[{inst.id[:8]}] {result['message']}")

    except Exception as e:
        update_order(order.id, status="failed")
        result["action"] = "error"
        result["message"] = f"Close failed: {e}"
        logger.error(f"[{inst.id[:8]}] Close position failed: {e}")

    return result


def _schedule_next(inst: StrategyInstance) -> None:
    """更新下次检查时间"""
    nxt = next_check_time(inst.timeframe)
    update_strategy_instance(inst.id, next_check_time=nxt)


# ==================== 手动平仓 ====================


def force_close_position(instance_id: str, exchange) -> dict:
    """手动强制平仓"""
    inst = get_fund_pool_instance(instance_id)
    if not inst:
        return {"success": False, "message": "Instance not found"}

    pool = get_fund_pool(inst.fund_pool_id)
    if not pool:
        return {"success": False, "message": "Fund pool not found"}

    if inst.current_position <= 0:
        return {"success": False, "message": "No position to close"}

    try:
        df = _get_ohlcv_cached(exchange, inst.symbol, inst.timeframe, limit=10)
        price = float(df["close"].iloc[-1]) if not df.empty else 0
    except Exception:
        price = inst.entry_price  # fallback

    result = _close_position(inst, pool, exchange, price, "manual_close")
    return {"success": result["action"] != "error", "message": result["message"]}


def get_fund_pool_instance(instance_id: str) -> Optional[StrategyInstance]:
    """获取策略实例 (别名, 避免循环导入)"""
    from core.models import get_strategy_instance
    return get_strategy_instance(instance_id)

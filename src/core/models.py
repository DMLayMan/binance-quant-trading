"""
数据模型 — 资金池、策略实例、订单、成交的 CRUD 操作
"""

import json
import uuid
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

from core.database import get_connection, now_iso, today_str


# ==================== 时间工具 ====================

TIMEFRAME_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900,
    "1h": 3600, "4h": 14400, "1d": 86400,
}


def next_check_time(timeframe: str) -> str:
    """计算下一次策略检查时间：对齐到 K 线收盘 + 5 秒"""
    interval = TIMEFRAME_SECONDS.get(timeframe, 14400)
    now = datetime.utcnow()
    ts = int(now.timestamp())
    next_ts = ((ts // interval) + 1) * interval + 5
    return datetime.utcfromtimestamp(next_ts).strftime("%Y-%m-%dT%H:%M:%S")


# ==================== FundPool ====================


@dataclass
class FundPool:
    id: str
    name: str
    allocated_amount: float
    current_equity: float
    peak_equity: float
    status: str  # active / paused / stopped
    max_daily_loss_pct: float
    max_drawdown_pct: float
    take_profit_pct: Optional[float]
    stop_loss_pct: Optional[float]
    daily_start_equity: float
    current_date: str
    created_at: str
    updated_at: str


def create_fund_pool(
    name: str,
    allocated_amount: float,
    max_daily_loss_pct: float = 0.05,
    max_drawdown_pct: float = 0.15,
    take_profit_pct: Optional[float] = None,
    stop_loss_pct: Optional[float] = None,
) -> FundPool:
    pool = FundPool(
        id=str(uuid.uuid4()),
        name=name,
        allocated_amount=allocated_amount,
        current_equity=allocated_amount,
        peak_equity=allocated_amount,
        status="active",
        max_daily_loss_pct=max_daily_loss_pct,
        max_drawdown_pct=max_drawdown_pct,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
        daily_start_equity=allocated_amount,
        current_date=today_str(),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO fund_pools
               (id, name, allocated_amount, current_equity, peak_equity, status,
                max_daily_loss_pct, max_drawdown_pct, take_profit_pct, stop_loss_pct,
                daily_start_equity, current_date, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pool.id, pool.name, pool.allocated_amount, pool.current_equity,
             pool.peak_equity, pool.status, pool.max_daily_loss_pct,
             pool.max_drawdown_pct, pool.take_profit_pct, pool.stop_loss_pct,
             pool.daily_start_equity, pool.current_date,
             pool.created_at, pool.updated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return pool


def get_fund_pool(pool_id: str) -> Optional[FundPool]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM fund_pools WHERE id=?", (pool_id,)).fetchone()
        return FundPool(**dict(row)) if row else None
    finally:
        conn.close()


def list_fund_pools(status: Optional[str] = None) -> list[FundPool]:
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM fund_pools WHERE status=? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM fund_pools ORDER BY created_at DESC"
            ).fetchall()
        return [FundPool(**dict(r)) for r in rows]
    finally:
        conn.close()


def update_fund_pool(pool_id: str, **kwargs) -> Optional[FundPool]:
    kwargs["updated_at"] = now_iso()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [pool_id]
    conn = get_connection()
    try:
        conn.execute(f"UPDATE fund_pools SET {sets} WHERE id=?", vals)
        conn.commit()
    finally:
        conn.close()
    return get_fund_pool(pool_id)


# ==================== StrategyInstance ====================


@dataclass
class StrategyInstance:
    id: str
    fund_pool_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    params: str  # JSON string

    stop_loss_atr_mult: float
    take_profit_atr_mult: float
    max_position_pct: float
    risk_per_trade_pct: float

    status: str  # pending / running / paused / stopped / error
    current_position: float
    entry_price: float
    unrealized_pnl: float
    total_pnl: float
    trade_count: int
    win_count: int
    consecutive_losses: int
    trades_today: int
    trades_today_date: str

    last_signal: int
    last_signal_time: Optional[str]
    next_check_time: str
    error_message: Optional[str]
    created_at: str
    updated_at: str

    def get_params(self) -> dict:
        return json.loads(self.params) if self.params else {}

    @property
    def win_rate(self) -> float:
        return (self.win_count / self.trade_count * 100) if self.trade_count > 0 else 0.0


def create_strategy_instance(
    fund_pool_id: str,
    strategy_name: str,
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    params: Optional[dict] = None,
    stop_loss_atr_mult: float = 2.0,
    take_profit_atr_mult: float = 4.0,
    max_position_pct: float = 0.30,
    risk_per_trade_pct: float = 0.01,
) -> StrategyInstance:
    now = now_iso()
    inst = StrategyInstance(
        id=str(uuid.uuid4()),
        fund_pool_id=fund_pool_id,
        strategy_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        params=json.dumps(params or {}),
        stop_loss_atr_mult=stop_loss_atr_mult,
        take_profit_atr_mult=take_profit_atr_mult,
        max_position_pct=max_position_pct,
        risk_per_trade_pct=risk_per_trade_pct,
        status="pending",
        current_position=0.0,
        entry_price=0.0,
        unrealized_pnl=0.0,
        total_pnl=0.0,
        trade_count=0,
        win_count=0,
        consecutive_losses=0,
        trades_today=0,
        trades_today_date=today_str(),
        last_signal=0,
        last_signal_time=None,
        next_check_time=next_check_time(timeframe),
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO strategy_instances
               (id, fund_pool_id, strategy_name, symbol, timeframe, params,
                stop_loss_atr_mult, take_profit_atr_mult, max_position_pct,
                risk_per_trade_pct, status, current_position, entry_price,
                unrealized_pnl, total_pnl, trade_count, win_count,
                consecutive_losses, trades_today, trades_today_date,
                last_signal, last_signal_time, next_check_time, error_message,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (inst.id, inst.fund_pool_id, inst.strategy_name, inst.symbol,
             inst.timeframe, inst.params, inst.stop_loss_atr_mult,
             inst.take_profit_atr_mult, inst.max_position_pct,
             inst.risk_per_trade_pct, inst.status, inst.current_position,
             inst.entry_price, inst.unrealized_pnl, inst.total_pnl,
             inst.trade_count, inst.win_count, inst.consecutive_losses,
             inst.trades_today, inst.trades_today_date, inst.last_signal,
             inst.last_signal_time, inst.next_check_time, inst.error_message,
             inst.created_at, inst.updated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return inst


def get_strategy_instance(instance_id: str) -> Optional[StrategyInstance]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM strategy_instances WHERE id=?", (instance_id,)
        ).fetchone()
        return StrategyInstance(**dict(row)) if row else None
    finally:
        conn.close()


def list_strategy_instances(
    fund_pool_id: Optional[str] = None,
    status: Optional[str] = None,
) -> list[StrategyInstance]:
    conn = get_connection()
    try:
        where, vals = [], []
        if fund_pool_id:
            where.append("fund_pool_id=?")
            vals.append(fund_pool_id)
        if status:
            where.append("status=?")
            vals.append(status)
        clause = " AND ".join(where) if where else "1=1"
        rows = conn.execute(
            f"SELECT * FROM strategy_instances WHERE {clause} ORDER BY created_at DESC",
            vals,
        ).fetchall()
        return [StrategyInstance(**dict(r)) for r in rows]
    finally:
        conn.close()


def get_runnable_instances(now_str: str) -> list[StrategyInstance]:
    """获取所有 status=running 且到达检查时间的策略实例"""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM strategy_instances
               WHERE status='running' AND next_check_time <= ?
               ORDER BY next_check_time ASC""",
            (now_str,),
        ).fetchall()
        return [StrategyInstance(**dict(r)) for r in rows]
    finally:
        conn.close()


def update_strategy_instance(instance_id: str, **kwargs) -> Optional[StrategyInstance]:
    if "params" in kwargs and isinstance(kwargs["params"], dict):
        kwargs["params"] = json.dumps(kwargs["params"])
    kwargs["updated_at"] = now_iso()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [instance_id]
    conn = get_connection()
    try:
        conn.execute(f"UPDATE strategy_instances SET {sets} WHERE id=?", vals)
        conn.commit()
    finally:
        conn.close()
    return get_strategy_instance(instance_id)


# ==================== Order ====================


@dataclass
class Order:
    id: str
    exchange_order_id: Optional[str]
    strategy_instance_id: str
    symbol: str
    side: str
    order_type: str
    amount: float
    price: Optional[float]
    filled_amount: float
    fee: float
    status: str
    reason: Optional[str]
    created_at: str
    filled_at: Optional[str]


def create_order(
    strategy_instance_id: str,
    symbol: str,
    side: str,
    amount: float,
    reason: str,
    order_type: str = "market",
    price: Optional[float] = None,
) -> Order:
    order = Order(
        id=str(uuid.uuid4()),
        exchange_order_id=None,
        strategy_instance_id=strategy_instance_id,
        symbol=symbol,
        side=side,
        order_type=order_type,
        amount=amount,
        price=price,
        filled_amount=0.0,
        fee=0.0,
        status="pending",
        reason=reason,
        created_at=now_iso(),
        filled_at=None,
    )
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO orders
               (id, exchange_order_id, strategy_instance_id, symbol, side,
                order_type, amount, price, filled_amount, fee, status, reason,
                created_at, filled_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (order.id, order.exchange_order_id, order.strategy_instance_id,
             order.symbol, order.side, order.order_type, order.amount,
             order.price, order.filled_amount, order.fee, order.status,
             order.reason, order.created_at, order.filled_at),
        )
        conn.commit()
    finally:
        conn.close()
    return order


def update_order(order_id: str, **kwargs) -> None:
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [order_id]
    conn = get_connection()
    try:
        conn.execute(f"UPDATE orders SET {sets} WHERE id=?", vals)
        conn.commit()
    finally:
        conn.close()


def list_orders(
    strategy_instance_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[Order]:
    conn = get_connection()
    try:
        where, vals = [], []
        if strategy_instance_id:
            where.append("strategy_instance_id=?")
            vals.append(strategy_instance_id)
        if status:
            where.append("status=?")
            vals.append(status)
        clause = " AND ".join(where) if where else "1=1"
        vals.append(limit)
        rows = conn.execute(
            f"SELECT * FROM orders WHERE {clause} ORDER BY created_at DESC LIMIT ?",
            vals,
        ).fetchall()
        return [Order(**dict(r)) for r in rows]
    finally:
        conn.close()


# ==================== Trade ====================


@dataclass
class TradeRecord:
    id: str
    strategy_instance_id: str
    fund_pool_id: str
    symbol: str
    side: str
    entry_order_id: Optional[str]
    exit_order_id: Optional[str]
    entry_price: float
    exit_price: float
    amount: float
    pnl: float
    pnl_pct: float
    total_fee: float
    holding_seconds: int
    exit_reason: Optional[str]
    entry_time: str
    exit_time: str


def create_trade(
    strategy_instance_id: str,
    fund_pool_id: str,
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float,
    amount: float,
    pnl: float,
    total_fee: float,
    exit_reason: str,
    entry_time: str,
    exit_time: str,
    entry_order_id: Optional[str] = None,
    exit_order_id: Optional[str] = None,
) -> TradeRecord:
    pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
    if side == "short":
        pnl_pct = -pnl_pct
    entry_dt = datetime.fromisoformat(entry_time)
    exit_dt = datetime.fromisoformat(exit_time)
    holding = int((exit_dt - entry_dt).total_seconds())

    trade = TradeRecord(
        id=str(uuid.uuid4()),
        strategy_instance_id=strategy_instance_id,
        fund_pool_id=fund_pool_id,
        symbol=symbol,
        side=side,
        entry_order_id=entry_order_id,
        exit_order_id=exit_order_id,
        entry_price=entry_price,
        exit_price=exit_price,
        amount=amount,
        pnl=pnl,
        pnl_pct=pnl_pct,
        total_fee=total_fee,
        holding_seconds=holding,
        exit_reason=exit_reason,
        entry_time=entry_time,
        exit_time=exit_time,
    )
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO trades
               (id, strategy_instance_id, fund_pool_id, symbol, side,
                entry_order_id, exit_order_id, entry_price, exit_price,
                amount, pnl, pnl_pct, total_fee, holding_seconds,
                exit_reason, entry_time, exit_time)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (trade.id, trade.strategy_instance_id, trade.fund_pool_id,
             trade.symbol, trade.side, trade.entry_order_id,
             trade.exit_order_id, trade.entry_price, trade.exit_price,
             trade.amount, trade.pnl, trade.pnl_pct, trade.total_fee,
             trade.holding_seconds, trade.exit_reason,
             trade.entry_time, trade.exit_time),
        )
        conn.commit()
    finally:
        conn.close()
    return trade


def list_trades(
    strategy_instance_id: Optional[str] = None,
    fund_pool_id: Optional[str] = None,
    limit: int = 100,
) -> list[TradeRecord]:
    conn = get_connection()
    try:
        where, vals = [], []
        if strategy_instance_id:
            where.append("strategy_instance_id=?")
            vals.append(strategy_instance_id)
        if fund_pool_id:
            where.append("fund_pool_id=?")
            vals.append(fund_pool_id)
        clause = " AND ".join(where) if where else "1=1"
        vals.append(limit)
        rows = conn.execute(
            f"SELECT * FROM trades WHERE {clause} ORDER BY exit_time DESC LIMIT ?",
            vals,
        ).fetchall()
        return [TradeRecord(**dict(r)) for r in rows]
    finally:
        conn.close()


# ==================== Equity Snapshot ====================


def record_equity_snapshot(fund_pool_id: str, equity: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO equity_snapshots (fund_pool_id, equity, timestamp) VALUES (?,?,?)",
            (fund_pool_id, equity, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def get_equity_history(fund_pool_id: str, limit: int = 500) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT equity, timestamp FROM equity_snapshots
               WHERE fund_pool_id=? ORDER BY timestamp DESC LIMIT ?""",
            (fund_pool_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()


# ==================== Risk Event ====================


def record_risk_event(
    event_type: str,
    message: str,
    strategy_instance_id: Optional[str] = None,
    fund_pool_id: Optional[str] = None,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO risk_events
               (strategy_instance_id, fund_pool_id, event_type, message, timestamp)
               VALUES (?,?,?,?,?)""",
            (strategy_instance_id, fund_pool_id, event_type, message, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

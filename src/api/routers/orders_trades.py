"""Orders & Trades 路由 — 订单和成交记录查询 + CSV 导出"""

import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from core.models import list_orders, list_trades
from core.database import get_connection

router = APIRouter()


# ==================== 响应模型 ====================


class OrderResponse(BaseModel):
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


class TradeResponse(BaseModel):
    id: str
    strategy_instance_id: str
    fund_pool_id: str
    symbol: str
    side: str
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


class TradeStatsResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    avg_win: float
    avg_loss: float
    max_win: float
    max_loss: float
    total_fees: float
    avg_holding_seconds: int


class RiskEventResponse(BaseModel):
    id: int
    strategy_instance_id: Optional[str]
    fund_pool_id: Optional[str]
    event_type: str
    message: str
    timestamp: str


# ==================== 路由 ====================


@router.get("/orders", response_model=list[OrderResponse])
def get_orders(
    strategy_instance_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """查询订单列表"""
    orders = list_orders(
        strategy_instance_id=strategy_instance_id,
        status=status,
        limit=limit,
    )
    return [_order_to_response(o) for o in orders]


@router.get("/trades", response_model=list[TradeResponse])
def get_trades(
    strategy_instance_id: Optional[str] = Query(None),
    fund_pool_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """查询成交记录"""
    trades = list_trades(
        strategy_instance_id=strategy_instance_id,
        fund_pool_id=fund_pool_id,
        limit=limit,
    )
    return [_trade_to_response(t) for t in trades]


@router.get("/trades/stats", response_model=TradeStatsResponse)
def get_trade_stats(
    fund_pool_id: Optional[str] = Query(None),
    strategy_instance_id: Optional[str] = Query(None),
):
    """获取成交统计"""
    trades = list_trades(
        strategy_instance_id=strategy_instance_id,
        fund_pool_id=fund_pool_id,
        limit=10000,
    )

    if not trades:
        return TradeStatsResponse(
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0, total_pnl=0, avg_pnl=0,
            avg_win=0, avg_loss=0, max_win=0, max_loss=0,
            total_fees=0, avg_holding_seconds=0,
        )

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    total = len(trades)

    return TradeStatsResponse(
        total_trades=total,
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate=round(len(wins) / total * 100, 2) if total > 0 else 0,
        total_pnl=round(sum(t.pnl for t in trades), 2),
        avg_pnl=round(sum(t.pnl for t in trades) / total, 2),
        avg_win=round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0,
        avg_loss=round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0,
        max_win=round(max(t.pnl for t in trades), 2),
        max_loss=round(min(t.pnl for t in trades), 2),
        total_fees=round(sum(t.total_fee for t in trades), 2),
        avg_holding_seconds=int(sum(t.holding_seconds for t in trades) / total),
    )


@router.get("/risk-events", response_model=list[RiskEventResponse])
def get_risk_events(
    fund_pool_id: Optional[str] = Query(None),
    strategy_instance_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """查询风控事件"""
    conn = get_connection()
    try:
        where, vals = [], []
        if fund_pool_id:
            where.append("fund_pool_id=?")
            vals.append(fund_pool_id)
        if strategy_instance_id:
            where.append("strategy_instance_id=?")
            vals.append(strategy_instance_id)
        clause = " AND ".join(where) if where else "1=1"
        vals.append(limit)
        rows = conn.execute(
            f"SELECT * FROM risk_events WHERE {clause} ORDER BY timestamp DESC LIMIT ?",
            vals,
        ).fetchall()
        return [RiskEventResponse(**dict(r)) for r in rows]
    finally:
        conn.close()


@router.get("/trades/export")
def export_trades_csv(
    fund_pool_id: Optional[str] = Query(None),
    strategy_instance_id: Optional[str] = Query(None),
):
    """导出成交记录为 CSV"""
    trades = list_trades(
        strategy_instance_id=strategy_instance_id,
        fund_pool_id=fund_pool_id,
        limit=100000,
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "ID", "Symbol", "Side", "Entry Price", "Exit Price", "Amount",
        "P&L", "P&L %", "Fee", "Holding (s)", "Exit Reason",
        "Entry Time", "Exit Time",
    ])
    for t in trades:
        writer.writerow([
            t.id, t.symbol, t.side, t.entry_price, t.exit_price, t.amount,
            round(t.pnl, 4), round(t.pnl_pct, 4), round(t.total_fee, 4),
            t.holding_seconds, t.exit_reason or "",
            t.entry_time, t.exit_time,
        ])

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )


# ==================== 辅助 ====================


def _order_to_response(order) -> dict:
    return {
        "id": order.id,
        "exchange_order_id": order.exchange_order_id,
        "strategy_instance_id": order.strategy_instance_id,
        "symbol": order.symbol,
        "side": order.side,
        "order_type": order.order_type,
        "amount": order.amount,
        "price": order.price,
        "filled_amount": order.filled_amount,
        "fee": order.fee,
        "status": order.status,
        "reason": order.reason,
        "created_at": order.created_at,
        "filled_at": order.filled_at,
    }


def _trade_to_response(trade) -> dict:
    return {
        "id": trade.id,
        "strategy_instance_id": trade.strategy_instance_id,
        "fund_pool_id": trade.fund_pool_id,
        "symbol": trade.symbol,
        "side": trade.side,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "amount": trade.amount,
        "pnl": trade.pnl,
        "pnl_pct": trade.pnl_pct,
        "total_fee": trade.total_fee,
        "holding_seconds": trade.holding_seconds,
        "exit_reason": trade.exit_reason,
        "entry_time": trade.entry_time,
        "exit_time": trade.exit_time,
    }

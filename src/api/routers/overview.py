"""Overview 路由 — 账户总览 + 管理化交易仪表板"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_exchange, get_risk_controller
from api.schemas import OverviewResponse, PositionInfo, RiskStatusResponse
from core.models import list_fund_pools, list_strategy_instances, list_trades
from core.database import get_connection

router = APIRouter()


# ==================== 仪表板模型 ====================


class PoolSummary(BaseModel):
    id: str
    name: str
    status: str
    current_equity: float
    pnl: float
    pnl_pct: float
    instance_count: int


class InstanceSummary(BaseModel):
    id: str
    strategy_name: str
    symbol: str
    timeframe: str
    status: str
    total_pnl: float
    trade_count: int


class RecentTrade(BaseModel):
    id: str
    symbol: str
    side: str
    pnl: float
    pnl_pct: float
    exit_reason: Optional[str]
    exit_time: str


class DashboardResponse(BaseModel):
    total_allocated: float
    total_equity: float
    total_pnl: float
    total_pnl_pct: float
    active_pools: int
    running_instances: int
    total_trades: int
    pools: list[PoolSummary]
    active_instances: list[InstanceSummary]
    recent_trades: list[RecentTrade]
    recent_risk_events: int


# ==================== 路由 ====================


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    exchange=Depends(get_exchange),
    risk_controller=Depends(get_risk_controller),
):
    if exchange is None:
        return OverviewResponse(
            equity=0, free_usdt=0, positions=[],
            daily_pnl=0, daily_pnl_pct=0, risk_status=None,
        )

    balance = exchange.fetch_balance()
    free_usdt = balance["free"].get("USDT", 0)
    total_usdt = balance["total"].get("USDT", 0)

    positions = []
    for currency, amount in balance["total"].items():
        if currency == "USDT" or amount == 0:
            continue
        symbol = f"{currency}/USDT"
        try:
            ticker = exchange.fetch_ticker(symbol)
            mark_price = ticker["last"] or 0
            positions.append(PositionInfo(
                symbol=symbol, side="long", amount=amount,
                entry_price=0, unrealized_pnl=0, mark_price=mark_price,
            ))
        except Exception:
            continue

    risk_status = None
    if risk_controller:
        status = risk_controller.get_status()
        risk_status = RiskStatusResponse(**status)

    equity = total_usdt + sum(p.amount * p.mark_price for p in positions)

    return OverviewResponse(
        equity=round(equity, 2),
        free_usdt=round(free_usdt, 2),
        positions=positions,
        daily_pnl=risk_status.daily_pnl if risk_status else 0,
        daily_pnl_pct=risk_status.daily_pnl_pct if risk_status else 0,
        risk_status=risk_status,
    )


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard():
    """管理化交易仪表板 — 资金池/实例/交易总览"""
    pools = list_fund_pools()
    all_instances = list_strategy_instances()
    recent = list_trades(limit=10)

    total_allocated = sum(p.allocated_amount for p in pools)
    total_equity = sum(p.current_equity for p in pools)
    total_pnl = total_equity - total_allocated
    total_pnl_pct = round(total_pnl / total_allocated * 100, 2) if total_allocated > 0 else 0

    active_pools = sum(1 for p in pools if p.status == "active")
    running_instances = sum(1 for i in all_instances if i.status == "running")

    all_trades = list_trades(limit=100000)
    total_trades = len(all_trades)

    pool_summaries = []
    for p in pools:
        pnl = p.current_equity - p.allocated_amount
        pnl_pct = round(pnl / p.allocated_amount * 100, 2) if p.allocated_amount > 0 else 0
        inst_count = sum(1 for i in all_instances if i.fund_pool_id == p.id)
        pool_summaries.append(PoolSummary(
            id=p.id, name=p.name, status=p.status,
            current_equity=round(p.current_equity, 2),
            pnl=round(pnl, 2), pnl_pct=pnl_pct,
            instance_count=inst_count,
        ))

    active_inst = [i for i in all_instances if i.status in ("running", "paused")][:20]
    inst_summaries = [
        InstanceSummary(
            id=i.id, strategy_name=i.strategy_name, symbol=i.symbol,
            timeframe=i.timeframe, status=i.status,
            total_pnl=round(i.total_pnl, 2), trade_count=i.trade_count,
        )
        for i in active_inst
    ]

    recent_trades = [
        RecentTrade(
            id=t.id, symbol=t.symbol, side=t.side,
            pnl=round(t.pnl, 2), pnl_pct=round(t.pnl_pct, 2),
            exit_reason=t.exit_reason, exit_time=t.exit_time,
        )
        for t in recent
    ]

    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT COUNT(*) FROM risk_events WHERE timestamp > datetime('now', '-24 hours')"
        ).fetchone()
        recent_risk_events = row[0] if row else 0
        conn.close()
    except Exception:
        recent_risk_events = 0

    return DashboardResponse(
        total_allocated=round(total_allocated, 2),
        total_equity=round(total_equity, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=total_pnl_pct,
        active_pools=active_pools,
        running_instances=running_instances,
        total_trades=total_trades,
        pools=pool_summaries,
        active_instances=inst_summaries,
        recent_trades=recent_trades,
        recent_risk_events=recent_risk_events,
    )

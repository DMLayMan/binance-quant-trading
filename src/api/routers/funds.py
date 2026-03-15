"""Funds 路由 — 资金池 CRUD 与生命周期管理"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from core.models import (
    create_fund_pool, get_fund_pool, list_fund_pools, update_fund_pool,
    list_strategy_instances, get_equity_history,
)

router = APIRouter()


# ==================== 请求/响应 ====================


class CreateFundPoolRequest(BaseModel):
    name: str
    allocated_amount: float
    max_daily_loss_pct: float = 0.05
    max_drawdown_pct: float = 0.15
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None


class UpdateFundPoolRequest(BaseModel):
    name: Optional[str] = None
    max_daily_loss_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None


class FundPoolResponse(BaseModel):
    id: str
    name: str
    allocated_amount: float
    current_equity: float
    peak_equity: float
    status: str
    max_daily_loss_pct: float
    max_drawdown_pct: float
    take_profit_pct: Optional[float]
    stop_loss_pct: Optional[float]
    daily_start_equity: float
    pnl: float
    pnl_pct: float
    drawdown_pct: float
    instance_count: int
    created_at: str
    updated_at: str


class FundPoolDetailResponse(FundPoolResponse):
    equity_history: list[dict]


# ==================== 辅助 ====================


def _pool_to_response(pool, include_instances: bool = True) -> dict:
    pnl = pool.current_equity - pool.allocated_amount
    pnl_pct = (pnl / pool.allocated_amount * 100) if pool.allocated_amount > 0 else 0
    drawdown_pct = 0.0
    if pool.peak_equity > 0:
        drawdown_pct = (pool.peak_equity - pool.current_equity) / pool.peak_equity * 100

    instance_count = 0
    if include_instances:
        instance_count = len(list_strategy_instances(fund_pool_id=pool.id))

    return {
        "id": pool.id,
        "name": pool.name,
        "allocated_amount": pool.allocated_amount,
        "current_equity": pool.current_equity,
        "peak_equity": pool.peak_equity,
        "status": pool.status,
        "max_daily_loss_pct": pool.max_daily_loss_pct,
        "max_drawdown_pct": pool.max_drawdown_pct,
        "take_profit_pct": pool.take_profit_pct,
        "stop_loss_pct": pool.stop_loss_pct,
        "daily_start_equity": pool.daily_start_equity,
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "drawdown_pct": round(drawdown_pct, 2),
        "instance_count": instance_count,
        "created_at": pool.created_at,
        "updated_at": pool.updated_at,
    }


# ==================== 路由 ====================


@router.post("", response_model=FundPoolResponse, status_code=201)
def create_pool(req: CreateFundPoolRequest):
    """创建资金池"""
    if req.allocated_amount <= 0:
        raise HTTPException(400, "allocated_amount must be positive")

    pool = create_fund_pool(
        name=req.name,
        allocated_amount=req.allocated_amount,
        max_daily_loss_pct=req.max_daily_loss_pct,
        max_drawdown_pct=req.max_drawdown_pct,
        take_profit_pct=req.take_profit_pct,
        stop_loss_pct=req.stop_loss_pct,
    )
    return _pool_to_response(pool)


@router.get("", response_model=list[FundPoolResponse])
def list_pools(status: Optional[str] = Query(None)):
    """列出所有资金池"""
    pools = list_fund_pools(status=status)
    return [_pool_to_response(p) for p in pools]


@router.get("/{pool_id}", response_model=FundPoolDetailResponse)
def get_pool(pool_id: str):
    """获取资金池详情 (含权益历史)"""
    pool = get_fund_pool(pool_id)
    if not pool:
        raise HTTPException(404, "Fund pool not found")

    data = _pool_to_response(pool)
    data["equity_history"] = get_equity_history(pool_id, limit=500)
    return data


@router.put("/{pool_id}", response_model=FundPoolResponse)
def update_pool(pool_id: str, req: UpdateFundPoolRequest):
    """更新资金池参数"""
    pool = get_fund_pool(pool_id)
    if not pool:
        raise HTTPException(404, "Fund pool not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    updated = update_fund_pool(pool_id, **updates)
    return _pool_to_response(updated)


@router.post("/{pool_id}/pause", response_model=FundPoolResponse)
def pause_pool(pool_id: str):
    """暂停资金池 (所有策略实例也暂停)"""
    pool = get_fund_pool(pool_id)
    if not pool:
        raise HTTPException(404, "Fund pool not found")
    if pool.status != "active":
        raise HTTPException(400, f"Cannot pause pool with status '{pool.status}'")

    updated = update_fund_pool(pool_id, status="paused")

    # 暂停该资金池下所有运行中的策略实例
    from core.models import update_strategy_instance
    instances = list_strategy_instances(fund_pool_id=pool_id, status="running")
    for inst in instances:
        update_strategy_instance(inst.id, status="paused", error_message="Fund pool paused")

    return _pool_to_response(updated)


@router.post("/{pool_id}/resume", response_model=FundPoolResponse)
def resume_pool(pool_id: str):
    """恢复资金池"""
    pool = get_fund_pool(pool_id)
    if not pool:
        raise HTTPException(404, "Fund pool not found")
    if pool.status != "paused":
        raise HTTPException(400, f"Cannot resume pool with status '{pool.status}'")

    updated = update_fund_pool(pool_id, status="active")
    return _pool_to_response(updated)


@router.post("/{pool_id}/stop", response_model=FundPoolResponse)
def stop_pool(pool_id: str):
    """停止资金池 (永久停止)"""
    pool = get_fund_pool(pool_id)
    if not pool:
        raise HTTPException(404, "Fund pool not found")
    if pool.status == "stopped":
        raise HTTPException(400, "Pool already stopped")

    updated = update_fund_pool(pool_id, status="stopped")

    # 停止该资金池下所有策略实例
    from core.models import update_strategy_instance
    instances = list_strategy_instances(fund_pool_id=pool_id)
    for inst in instances:
        if inst.status in ("running", "paused", "pending"):
            update_strategy_instance(inst.id, status="stopped",
                                     error_message="Fund pool stopped")

    return _pool_to_response(updated)

"""Instances 路由 — 策略实例生命周期管理"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_exchange
from core.models import (
    create_strategy_instance, get_strategy_instance,
    list_strategy_instances, update_strategy_instance,
    get_fund_pool, list_orders, list_trades,
)
from core.executor import force_close_position
from main import STRATEGY_REGISTRY

router = APIRouter()


# ==================== 请求/响应 ====================


class CreateInstanceRequest(BaseModel):
    fund_pool_id: str
    strategy_name: str
    symbol: str = "BTC/USDT"
    timeframe: str = "4h"
    params: Optional[dict] = None
    stop_loss_atr_mult: float = 2.0
    take_profit_atr_mult: float = 4.0
    max_position_pct: float = 0.30
    risk_per_trade_pct: float = 0.01


class UpdateInstanceRequest(BaseModel):
    stop_loss_atr_mult: Optional[float] = None
    take_profit_atr_mult: Optional[float] = None
    max_position_pct: Optional[float] = None
    risk_per_trade_pct: Optional[float] = None
    params: Optional[dict] = None


class InstanceResponse(BaseModel):
    id: str
    fund_pool_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    params: dict
    stop_loss_atr_mult: float
    take_profit_atr_mult: float
    max_position_pct: float
    risk_per_trade_pct: float
    status: str
    current_position: float
    entry_price: float
    unrealized_pnl: float
    total_pnl: float
    trade_count: int
    win_count: int
    win_rate: float
    consecutive_losses: int
    last_signal: int
    last_signal_time: Optional[str]
    next_check_time: str
    error_message: Optional[str]
    created_at: str
    updated_at: str


class InstanceDetailResponse(InstanceResponse):
    recent_orders: list[dict]
    recent_trades: list[dict]


# ==================== 辅助 ====================


def _inst_to_response(inst) -> dict:
    import json
    params = json.loads(inst.params) if isinstance(inst.params, str) else inst.params
    return {
        "id": inst.id,
        "fund_pool_id": inst.fund_pool_id,
        "strategy_name": inst.strategy_name,
        "symbol": inst.symbol,
        "timeframe": inst.timeframe,
        "params": params,
        "stop_loss_atr_mult": inst.stop_loss_atr_mult,
        "take_profit_atr_mult": inst.take_profit_atr_mult,
        "max_position_pct": inst.max_position_pct,
        "risk_per_trade_pct": inst.risk_per_trade_pct,
        "status": inst.status,
        "current_position": inst.current_position,
        "entry_price": inst.entry_price,
        "unrealized_pnl": inst.unrealized_pnl,
        "total_pnl": inst.total_pnl,
        "trade_count": inst.trade_count,
        "win_count": inst.win_count,
        "win_rate": inst.win_rate,
        "consecutive_losses": inst.consecutive_losses,
        "last_signal": inst.last_signal,
        "last_signal_time": inst.last_signal_time,
        "next_check_time": inst.next_check_time,
        "error_message": inst.error_message,
        "created_at": inst.created_at,
        "updated_at": inst.updated_at,
    }


def _order_to_dict(order) -> dict:
    return {
        "id": order.id,
        "exchange_order_id": order.exchange_order_id,
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


def _trade_to_dict(trade) -> dict:
    return {
        "id": trade.id,
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


# ==================== 路由 ====================


@router.post("", response_model=InstanceResponse, status_code=201)
def create_instance(req: CreateInstanceRequest):
    """创建策略实例"""
    # 校验策略名
    if req.strategy_name not in STRATEGY_REGISTRY:
        available = list(STRATEGY_REGISTRY.keys())
        raise HTTPException(400, f"Unknown strategy '{req.strategy_name}'. Available: {available}")

    # 校验资金池
    pool = get_fund_pool(req.fund_pool_id)
    if not pool:
        raise HTTPException(404, "Fund pool not found")
    if pool.status != "active":
        raise HTTPException(400, f"Fund pool status is '{pool.status}', must be 'active'")

    # 校验 timeframe
    valid_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
    if req.timeframe not in valid_timeframes:
        raise HTTPException(400, f"Invalid timeframe. Valid: {valid_timeframes}")

    inst = create_strategy_instance(
        fund_pool_id=req.fund_pool_id,
        strategy_name=req.strategy_name,
        symbol=req.symbol,
        timeframe=req.timeframe,
        params=req.params,
        stop_loss_atr_mult=req.stop_loss_atr_mult,
        take_profit_atr_mult=req.take_profit_atr_mult,
        max_position_pct=req.max_position_pct,
        risk_per_trade_pct=req.risk_per_trade_pct,
    )
    return _inst_to_response(inst)


@router.get("", response_model=list[InstanceResponse])
def list_instances(
    fund_pool_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """列出策略实例"""
    instances = list_strategy_instances(fund_pool_id=fund_pool_id, status=status)
    return [_inst_to_response(inst) for inst in instances]


@router.get("/{instance_id}", response_model=InstanceDetailResponse)
def get_instance(instance_id: str):
    """获取策略实例详情 (含近期订单和成交)"""
    inst = get_strategy_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Strategy instance not found")

    data = _inst_to_response(inst)
    data["recent_orders"] = [_order_to_dict(o) for o in list_orders(strategy_instance_id=instance_id, limit=20)]
    data["recent_trades"] = [_trade_to_dict(t) for t in list_trades(strategy_instance_id=instance_id, limit=20)]
    return data


@router.put("/{instance_id}", response_model=InstanceResponse)
def update_instance(instance_id: str, req: UpdateInstanceRequest):
    """更新策略实例参数 (仅 pending/paused 状态可修改)"""
    inst = get_strategy_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Strategy instance not found")

    if inst.status not in ("pending", "paused"):
        raise HTTPException(400, f"Cannot update instance with status '{inst.status}'. "
                                  "Pause it first.")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    updated = update_strategy_instance(instance_id, **updates)
    return _inst_to_response(updated)


@router.post("/{instance_id}/start", response_model=InstanceResponse)
def start_instance(instance_id: str):
    """启动策略实例"""
    inst = get_strategy_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Strategy instance not found")

    if inst.status not in ("pending", "paused"):
        raise HTTPException(400, f"Cannot start instance with status '{inst.status}'")

    # 检查资金池状态
    pool = get_fund_pool(inst.fund_pool_id)
    if not pool or pool.status != "active":
        raise HTTPException(400, "Fund pool is not active")

    from core.models import next_check_time as calc_next
    updated = update_strategy_instance(
        instance_id,
        status="running",
        error_message=None,
        next_check_time=calc_next(inst.timeframe),
    )
    return _inst_to_response(updated)


@router.post("/{instance_id}/pause", response_model=InstanceResponse)
def pause_instance(instance_id: str):
    """暂停策略实例"""
    inst = get_strategy_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Strategy instance not found")

    if inst.status != "running":
        raise HTTPException(400, f"Cannot pause instance with status '{inst.status}'")

    updated = update_strategy_instance(instance_id, status="paused")
    return _inst_to_response(updated)


@router.post("/{instance_id}/stop", response_model=InstanceResponse)
def stop_instance(instance_id: str):
    """停止策略实例 (永久停止)"""
    inst = get_strategy_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Strategy instance not found")

    if inst.status in ("stopped",):
        raise HTTPException(400, "Instance already stopped")

    updated = update_strategy_instance(instance_id, status="stopped")
    return _inst_to_response(updated)


@router.post("/{instance_id}/close-position")
def close_position(instance_id: str, exchange=Depends(get_exchange)):
    """手动平仓"""
    inst = get_strategy_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Strategy instance not found")

    if inst.current_position <= 0:
        raise HTTPException(400, "No position to close")

    result = force_close_position(instance_id, exchange)
    if not result["success"]:
        raise HTTPException(400, result["message"])

    return result

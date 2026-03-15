"""Overview 路由 — 账户总览"""

from fastapi import APIRouter, Depends
from api.dependencies import get_exchange, get_risk_controller
from api.schemas import OverviewResponse, PositionInfo, RiskStatusResponse

router = APIRouter()


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

    # 构建持仓列表（非零余额的非 USDT 资产）
    positions = []
    for currency, amount in balance["total"].items():
        if currency == "USDT" or amount == 0:
            continue
        symbol = f"{currency}/USDT"
        try:
            ticker = exchange.fetch_ticker(symbol)
            mark_price = ticker["last"] or 0
            value = amount * mark_price
            positions.append(PositionInfo(
                symbol=symbol,
                side="long",
                amount=amount,
                entry_price=0,  # 无法从 exchange 获取入场价
                unrealized_pnl=0,
                mark_price=mark_price,
            ))
        except Exception:
            continue

    risk_status = None
    if risk_controller:
        status = risk_controller.get_status()
        risk_status = RiskStatusResponse(**status)

    equity = total_usdt + sum(
        p.amount * p.mark_price for p in positions
    )

    return OverviewResponse(
        equity=round(equity, 2),
        free_usdt=round(free_usdt, 2),
        positions=positions,
        daily_pnl=risk_status.daily_pnl if risk_status else 0,
        daily_pnl_pct=risk_status.daily_pnl_pct if risk_status else 0,
        risk_status=risk_status,
    )

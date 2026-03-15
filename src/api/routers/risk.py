"""Risk 路由 — 风控状态与控制"""

from fastapi import APIRouter, Depends
from api.dependencies import get_risk_controller
from api.schemas import RiskStatusResponse, RiskConfigResponse

router = APIRouter()


@router.get("/status", response_model=RiskStatusResponse)
def get_risk_status(risk_controller=Depends(get_risk_controller)):
    if risk_controller is None:
        return RiskStatusResponse(
            current_equity=0, peak_equity=0, drawdown_pct=0,
            daily_pnl=0, daily_pnl_pct=0, trades_today=0,
            consecutive_losses=0, is_halted=False, halt_reason="",
        )

    return RiskStatusResponse(**risk_controller.get_status())


@router.get("/config", response_model=RiskConfigResponse)
def get_risk_config(risk_controller=Depends(get_risk_controller)):
    if risk_controller is None:
        return RiskConfigResponse(
            max_daily_loss_pct=0.05, max_drawdown_pct=0.15,
            max_position_pct=0.30, max_single_loss_pct=0.02,
            max_trades_per_day=50, max_consecutive_losses=5,
        )

    return RiskConfigResponse(
        max_daily_loss_pct=risk_controller.max_daily_loss_pct,
        max_drawdown_pct=risk_controller.max_drawdown_pct,
        max_position_pct=risk_controller.max_position_pct,
        max_single_loss_pct=risk_controller.max_single_loss_pct,
        max_trades_per_day=risk_controller.max_trades_per_day,
        max_consecutive_losses=risk_controller.max_consecutive_losses,
    )


@router.post("/reset-halt")
def reset_halt(risk_controller=Depends(get_risk_controller)):
    if risk_controller is None:
        return {"success": False, "message": "Risk controller not initialized"}

    risk_controller.reset_halt()
    return {"success": True, "message": "Halt has been reset"}

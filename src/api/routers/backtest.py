"""Backtest 路由 — 回测执行"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import get_exchange
from api.schemas import (
    BacktestRequest, BacktestResponse, BacktestSummary,
    EquityCurvePoint, TradeLogEntry,
)
from data.market_data import fetch_ohlcv, fetch_ohlcv_history
from backtest.engine import BacktestEngine, BacktestConfig
from main import STRATEGY_REGISTRY

router = APIRouter()


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    req: BacktestRequest,
    exchange=Depends(get_exchange),
):
    if req.strategy_name not in STRATEGY_REGISTRY:
        raise HTTPException(404, f"Unknown strategy: {req.strategy_name}")

    if exchange is None:
        raise HTTPException(503, "Exchange not connected")

    strategy = STRATEGY_REGISTRY[req.strategy_name]
    signal_func = strategy["func"]
    params = {**strategy["default_params"], **req.strategy_params}

    # 获取数据
    if req.since or req.until:
        df = fetch_ohlcv_history(
            exchange, req.symbol, req.timeframe,
            since=req.since, until=req.until,
        )
    else:
        df = fetch_ohlcv(exchange, req.symbol, req.timeframe, limit=500)

    if df.empty or len(df) < 30:
        raise HTTPException(400, "Insufficient data for backtest")

    config = BacktestConfig(
        initial_capital=req.initial_capital,
        maker_fee=req.maker_fee,
        taker_fee=req.taker_fee,
        slippage_pct=req.slippage_pct,
    )
    engine = BacktestEngine(config)

    # CPU 密集型任务在线程池中执行
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: engine.run(
            df, signal_func,
            stop_loss_atr_mult=req.stop_loss_atr_mult,
            take_profit_atr_mult=req.take_profit_atr_mult,
            **params,
        ),
    )

    summary = result.summary()

    equity_curve = [
        EquityCurvePoint(
            timestamp=int(ts.timestamp() * 1000),
            equity=round(row["equity"], 2),
            cash=round(row["cash"], 2),
            position_value=round(row["position_value"], 2),
        )
        for ts, row in result.equity_curve.iterrows()
    ]

    trade_log_df = result.trade_log()
    trade_log = []
    if not trade_log_df.empty:
        trade_log = [
            TradeLogEntry(
                timestamp=int(row["timestamp"].timestamp() * 1000),
                side=row["side"],
                price=round(row["price"], 2),
                amount=round(row["amount"], 6),
                fee=round(row["fee"], 2),
                pnl=round(row["pnl"], 2),
            )
            for _, row in trade_log_df.iterrows()
        ]

    return BacktestResponse(
        summary=BacktestSummary(**summary),
        equity_curve=equity_curve,
        trade_log=trade_log,
    )

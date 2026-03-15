"""Strategies 路由 — 策略信息与信号"""

from fastapi import APIRouter, Depends, Query, HTTPException
from api.dependencies import get_exchange, get_config
from api.schemas import StrategyInfo, StrategySignalsResponse, SignalPoint
from data.market_data import fetch_ohlcv
from main import STRATEGY_REGISTRY

router = APIRouter()

STRATEGY_DESCRIPTIONS = {
    "ma_crossover": "双均线交叉策略：短期EMA上穿长期EMA买入，下穿卖出",
    "macd": "MACD趋势策略：MACD线上穿信号线买入，下穿卖出",
    "bollinger_breakout": "布林带突破策略：Squeeze后价格突破上/下轨",
    "rsi": "RSI动量策略：超卖区回升买入，超买区回落卖出",
    "turtle": "改良海龟交易法则：N日最高价突破入场",
}


@router.get("", response_model=list[StrategyInfo])
def list_strategies(config=Depends(get_config)):
    active_name = config["strategy_name"] if config else ""
    result = []
    for name, info in STRATEGY_REGISTRY.items():
        result.append(StrategyInfo(
            name=name,
            description=STRATEGY_DESCRIPTIONS.get(name, ""),
            default_params=info["default_params"],
            is_active=(name == active_name),
        ))
    return result


@router.get("/{name}/signals", response_model=StrategySignalsResponse)
def get_strategy_signals(
    name: str,
    symbol: str = Query("BTC/USDT"),
    timeframe: str = Query("4h"),
    limit: int = Query(200, ge=50, le=1500),
    exchange=Depends(get_exchange),
):
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(404, f"Unknown strategy: {name}")

    if exchange is None:
        return StrategySignalsResponse(
            strategy_name=name, symbol=symbol, timeframe=timeframe, signals=[],
        )

    strategy = STRATEGY_REGISTRY[name]
    df = fetch_ohlcv(exchange, symbol, timeframe, limit=limit)
    signals_series = strategy["func"](df, **strategy["default_params"])

    signals = []
    for i in range(len(df)):
        sig = int(signals_series.iloc[i])
        if sig != 0:
            signals.append(SignalPoint(
                timestamp=int(df.index[i].timestamp() * 1000),
                signal=sig,
                price=float(df["close"].iloc[i]),
            ))

    return StrategySignalsResponse(
        strategy_name=name, symbol=symbol,
        timeframe=timeframe, signals=signals,
    )

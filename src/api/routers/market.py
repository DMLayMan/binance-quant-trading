"""Market 路由 — 行情数据"""

import math
from fastapi import APIRouter, Depends, Query
from api.dependencies import get_exchange
from api.schemas import OHLCVResponse, OHLCVBar, IndicatorData, TickerResponse, OrderBookResponse
from data.market_data import fetch_ohlcv, fetch_ticker, fetch_order_book
from utils.indicators import compute_atr, compute_rsi, compute_macd, compute_bollinger_bands

router = APIRouter()


def _safe(v):
    """NaN → None for JSON serialization"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


@router.get("/ohlcv", response_model=OHLCVResponse)
def get_ohlcv(
    symbol: str = Query("BTC/USDT"),
    timeframe: str = Query("4h"),
    limit: int = Query(200, ge=10, le=1500),
    indicators: bool = Query(True),
    exchange=Depends(get_exchange),
):
    if exchange is None:
        return OHLCVResponse(symbol=symbol, timeframe=timeframe, candles=[])

    df = fetch_ohlcv(exchange, symbol, timeframe, limit=limit)

    candles = [
        OHLCVBar(
            timestamp=int(ts.timestamp() * 1000),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )
        for ts, row in df.iterrows()
    ]

    indicator_data = None
    if indicators and not df.empty:
        atr = compute_atr(df)
        rsi = compute_rsi(df["close"])
        macd_l, sig_l, hist = compute_macd(df["close"])
        bb_u, bb_m, bb_l = compute_bollinger_bands(df["close"])

        indicator_data = IndicatorData(
            atr=[_safe(v) for v in atr],
            rsi=[_safe(v) for v in rsi],
            macd_line=[_safe(v) for v in macd_l],
            signal_line=[_safe(v) for v in sig_l],
            histogram=[_safe(v) for v in hist],
            bb_upper=[_safe(v) for v in bb_u],
            bb_middle=[_safe(v) for v in bb_m],
            bb_lower=[_safe(v) for v in bb_l],
        )

    return OHLCVResponse(
        symbol=symbol, timeframe=timeframe,
        candles=candles, indicators=indicator_data,
    )


@router.get("/ticker", response_model=TickerResponse)
def get_ticker(
    symbol: str = Query("BTC/USDT"),
    exchange=Depends(get_exchange),
):
    if exchange is None:
        return TickerResponse(
            symbol=symbol, last=0, bid=0, ask=0, volume_24h=0, change_24h_pct=0,
        )

    data = fetch_ticker(exchange, symbol)
    return TickerResponse(**data)


@router.get("/orderbook", response_model=OrderBookResponse)
def get_orderbook(
    symbol: str = Query("BTC/USDT"),
    depth: int = Query(20, ge=5, le=100),
    exchange=Depends(get_exchange),
):
    if exchange is None:
        return OrderBookResponse(bids=[], asks=[], spread=0, mid_price=0)

    data = fetch_order_book(exchange, symbol, depth=depth)
    return OrderBookResponse(**data)

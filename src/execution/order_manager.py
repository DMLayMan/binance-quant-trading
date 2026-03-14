"""
订单管理系统 (OMS)

负责下单执行、止损止盈管理、仓位计算。
"""

import ccxt
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def calculate_position_size(
    exchange: ccxt.binance,
    symbol: str,
    atr: float,
    max_position_pct: float = 0.3,
    risk_per_trade_pct: float = 0.01,
    stop_loss_atr_mult: float = 2.0,
) -> float:
    """
    基于风险的仓位计算

    Args:
        exchange: 交易所实例
        symbol: 交易对
        atr: 当前 ATR 值
        max_position_pct: 最大仓位占比
        risk_per_trade_pct: 单笔风险占比
        stop_loss_atr_mult: 止损 ATR 倍数

    Returns:
        建议仓位数量
    """
    balance = exchange.fetch_balance()
    free_usdt = balance["free"].get("USDT", 0)

    max_position_value = free_usdt * max_position_pct

    risk_amount = free_usdt * risk_per_trade_pct
    stop_distance = atr * stop_loss_atr_mult
    risk_based_size = risk_amount / stop_distance

    ticker = exchange.fetch_ticker(symbol)
    price = ticker["last"]
    risk_based_value = risk_based_size * price

    position_value = min(max_position_value, risk_based_value)
    position_size = position_value / price

    position_size = float(exchange.amount_to_precision(symbol, position_size))

    logger.info(f"Position size: {position_size} ({position_value:.2f} USDT)")
    return position_size


def execute_order(
    exchange: ccxt.binance,
    symbol: str,
    side: str,
    amount: float,
    price: Optional[float] = None,
    max_retries: int = 3,
) -> Optional[dict]:
    """
    执行下单，支持限价单和市价单，失败自动重试

    Args:
        exchange: 交易所实例
        symbol: 交易对
        side: 'buy' 或 'sell'
        amount: 数量
        price: 限价（None 则市价单）
        max_retries: 最大重试次数

    Returns:
        订单信息，失败返回 None
    """
    for attempt in range(max_retries):
        try:
            if price:
                order = exchange.create_limit_order(symbol, side, amount, price)
            else:
                order = exchange.create_market_order(symbol, side, amount)

            logger.info(
                f"Order executed: {side} {amount} {symbol} @ "
                f"{'market' if not price else price}"
            )
            return order

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds: {e}")
            return None
        except ccxt.NetworkError as e:
            logger.warning(f"Network error (attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(2**attempt)
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error: {e}")
            return None

    logger.error(f"Order failed after {max_retries} attempts")
    return None


def compute_stop_take_profit(
    entry_price: float,
    atr: float,
    side: str,
    stop_loss_mult: float = 2.0,
    take_profit_mult: float = 4.0,
) -> tuple[float, float]:
    """
    计算止损止盈价格

    Args:
        entry_price: 入场价格
        atr: 当前 ATR 值
        side: 'buy' 或 'sell'
        stop_loss_mult: 止损 ATR 倍数
        take_profit_mult: 止盈 ATR 倍数

    Returns:
        (止损价, 止盈价)
    """
    if side == "buy":
        stop_price = entry_price - stop_loss_mult * atr
        tp_price = entry_price + take_profit_mult * atr
    else:
        stop_price = entry_price + stop_loss_mult * atr
        tp_price = entry_price - take_profit_mult * atr

    logger.info(f"Stop Loss: {stop_price:.2f}, Take Profit: {tp_price:.2f}")
    return stop_price, tp_price

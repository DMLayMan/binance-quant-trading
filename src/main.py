"""
币安量化交易系统 — 主入口

基于双均线交叉策略的示例运行器。
可替换为其他策略模块。
"""

import os
import time
import logging

from data.market_data import create_exchange, fetch_ohlcv
from strategies.ma_crossover import ma_crossover_signal
from execution.order_manager import (
    calculate_position_size,
    execute_order,
    compute_stop_take_profit,
)
from utils.indicators import compute_atr, compute_rsi

# ==================== 配置 ====================

CONFIG = {
    "symbol": "BTC/USDT",
    "timeframe": "4h",
    "fast_ma": 7,
    "slow_ma": 25,
    "max_position_pct": 0.3,
    "risk_per_trade_pct": 0.01,
    "stop_loss_atr_mult": 2.0,
    "take_profit_atr_mult": 4.0,
    "use_testnet": True,
}

SLEEP_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

# ==================== 日志 ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ==================== 主循环 ====================


def run_strategy(api_key: str, api_secret: str):
    """策略主循环"""
    exchange = create_exchange(api_key, api_secret, sandbox=CONFIG["use_testnet"])
    symbol = CONFIG["symbol"]
    timeframe = CONFIG["timeframe"]
    current_position = 0.0
    entry_price = 0.0

    logger.info(f"Starting strategy: {symbol} {timeframe}")
    logger.info(f"Parameters: MA({CONFIG['fast_ma']}/{CONFIG['slow_ma']})")

    while True:
        try:
            # 1. 获取数据
            df = fetch_ohlcv(exchange, symbol, timeframe)
            df["atr"] = compute_atr(df)
            df["rsi"] = compute_rsi(df["close"])

            # 2. 生成信号
            signals = ma_crossover_signal(df, CONFIG["fast_ma"], CONFIG["slow_ma"])
            signal = int(signals.iloc[-1])
            current_price = float(df["close"].iloc[-1])
            current_atr = float(df["atr"].iloc[-1])

            logger.info(
                f"Price: {current_price:.2f}, ATR: {current_atr:.2f}, "
                f"Signal: {signal}, Position: {current_position}"
            )

            # 3. 检查止损止盈
            if current_position != 0 and entry_price > 0:
                sl, tp = compute_stop_take_profit(
                    entry_price,
                    current_atr,
                    "buy" if current_position > 0 else "sell",
                    CONFIG["stop_loss_atr_mult"],
                    CONFIG["take_profit_atr_mult"],
                )
                if (current_position > 0 and current_price <= sl) or (
                    current_position < 0 and current_price >= sl
                ):
                    logger.info("Stop loss triggered!")
                    execute_order(
                        exchange,
                        symbol,
                        "sell" if current_position > 0 else "buy",
                        abs(current_position),
                    )
                    current_position = 0.0
                    entry_price = 0.0

            # 4. 执行交易
            if signal == 1 and current_position <= 0:
                if current_position < 0:
                    execute_order(exchange, symbol, "buy", abs(current_position))

                size = calculate_position_size(
                    exchange,
                    symbol,
                    current_atr,
                    CONFIG["max_position_pct"],
                    CONFIG["risk_per_trade_pct"],
                    CONFIG["stop_loss_atr_mult"],
                )
                if size > 0:
                    order = execute_order(exchange, symbol, "buy", size)
                    if order:
                        current_position = size
                        entry_price = current_price

            elif signal == -1 and current_position > 0:
                execute_order(exchange, symbol, "sell", current_position)
                current_position = 0.0
                entry_price = 0.0

            # 5. 等待下一根K线
            time.sleep(SLEEP_SECONDS.get(timeframe, 3600))

        except KeyboardInterrupt:
            logger.info("Strategy stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    API_KEY = os.environ.get("BINANCE_API_KEY", "")
    API_SECRET = os.environ.get("BINANCE_API_SECRET", "")

    if not API_KEY or not API_SECRET:
        logger.error("Please set BINANCE_API_KEY and BINANCE_API_SECRET")
        exit(1)

    run_strategy(API_KEY, API_SECRET)

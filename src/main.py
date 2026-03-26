"""
币安量化交易系统 — 主入口

支持多策略切换、YAML 配置加载、实时风控引擎集成。
"""

import os
import sys
import time
import logging

import yaml
from dotenv import load_dotenv

from data.market_data import create_exchange, fetch_ohlcv
from strategies.ma_crossover import ma_crossover_signal
from strategies.macd_strategy import macd_signal
from strategies.bollinger_breakout import bollinger_breakout_signal
from strategies.rsi_momentum import rsi_signal
from strategies.turtle_trading import turtle_signal
from execution.order_manager import (
    calculate_position_size,
    execute_order,
    compute_stop_take_profit,
)
from utils.indicators import compute_atr, compute_rsi
from risk.risk_manager import RiskController

# ==================== 策略注册表 ====================

STRATEGY_REGISTRY = {
    "ma_crossover": {
        "func": ma_crossover_signal,
        "default_params": {"fast": 7, "slow": 25},
    },
    "macd": {
        "func": macd_signal,
        "default_params": {"fast": 12, "slow": 26, "signal_period": 9},
    },
    "bollinger_breakout": {
        "func": bollinger_breakout_signal,
        "default_params": {"period": 20, "std_dev": 2.0},
    },
    "rsi": {
        "func": rsi_signal,
        "default_params": {"period": 14, "overbought": 70, "oversold": 30},
    },
    "turtle": {
        "func": turtle_signal,
        "default_params": {"entry_period": 120, "exit_period": 60},
    },
}

SLEEP_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


# ==================== 配置加载 ====================


def load_config(config_path: str | None = None) -> dict:
    """从 YAML 加载配置，环境变量覆盖"""
    load_dotenv()

    if config_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "settings.yaml")

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    # 环境变量覆盖
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    use_testnet = os.environ.get("USE_TESTNET", str(cfg["exchange"]["sandbox"]))

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "sandbox": use_testnet.lower() in ("true", "1", "yes"),
        "strategy_name": cfg["strategy"]["name"],
        "symbol": cfg["strategy"]["symbol"],
        "timeframe": cfg["strategy"]["timeframe"],
        "strategy_params": cfg["strategy"].get("params", {}),
        "risk": cfg.get("risk", {}),
        "fees": cfg.get("fees", {}),
        "logging": cfg.get("logging", {}),
    }


# ==================== 日志 ====================


def setup_logging(cfg: dict):
    log_level = cfg.get("logging", {}).get("level", "INFO")
    log_file = cfg.get("logging", {}).get("file", "trading.log")

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


# ==================== 主循环 ====================


def run_strategy(cfg: dict):
    """策略主循环"""
    logger = logging.getLogger(__name__)

    # 初始化交易所
    exchange = create_exchange(cfg["api_key"], cfg["api_secret"], sandbox=cfg["sandbox"])

    symbol = cfg["symbol"]
    timeframe = cfg["timeframe"]
    strategy_name = cfg["strategy_name"]
    risk_cfg = cfg.get("risk", {})

    # 加载策略
    if strategy_name not in STRATEGY_REGISTRY:
        logger.error(
            f"Unknown strategy: {strategy_name}. "
            f"Available: {list(STRATEGY_REGISTRY.keys())}"
        )
        sys.exit(1)

    strategy = STRATEGY_REGISTRY[strategy_name]
    signal_func = strategy["func"]
    # 合并默认参数和配置参数
    signal_params = {**strategy["default_params"], **cfg.get("strategy_params", {})}

    # 初始化风控
    balance = exchange.fetch_balance()
    free_usdt = balance["free"].get("USDT", 0)
    risk_controller = RiskController(
        initial_equity=free_usdt,
        max_daily_loss_pct=risk_cfg.get("max_daily_loss_pct", 0.05),
        max_drawdown_pct=risk_cfg.get("max_drawdown_pct", 0.15),
        max_position_pct=risk_cfg.get("max_position_pct", 0.30),
        max_single_loss_pct=risk_cfg.get("risk_per_trade_pct", 0.02),
    )

    current_position = 0.0
    entry_price = 0.0
    stop_loss_mult = risk_cfg.get("stop_loss_atr_mult", 2.0)
    take_profit_mult = risk_cfg.get("take_profit_atr_mult", 4.0)

    logger.info(f"Starting strategy: {strategy_name} on {symbol} {timeframe}")
    logger.info(f"Parameters: {signal_params}")
    logger.info(f"Risk: {risk_controller.get_status()}")

    while True:
        try:
            # 1. 获取数据
            df = fetch_ohlcv(exchange, symbol, timeframe)
            df["atr"] = compute_atr(df)
            df["rsi"] = compute_rsi(df["close"])

            # 2. 生成信号
            signals = signal_func(df, **signal_params)
            signal = int(signals.iloc[-1])
            current_price = float(df["close"].iloc[-1])
            current_atr = float(df["atr"].iloc[-1])

            # 更新风控权益
            mark_value = current_position * current_price if current_position > 0 else 0
            balance = exchange.fetch_balance()
            total_equity = balance["free"].get("USDT", 0) + mark_value
            today_str = str(df.index[-1].date())
            risk_controller.update_equity(total_equity, today_str)

            logger.info(
                f"Price: {current_price:.2f}, ATR: {current_atr:.2f}, "
                f"Signal: {signal}, Position: {current_position}"
            )
            logger.info(f"Risk status: {risk_controller.get_status()}")

            # 3. 检查止损止盈
            if current_position != 0 and entry_price > 0:
                sl, tp = compute_stop_take_profit(
                    entry_price,
                    current_atr,
                    "buy" if current_position > 0 else "sell",
                    stop_loss_mult,
                    take_profit_mult,
                )
                if (current_position > 0 and current_price <= sl) or (
                    current_position < 0 and current_price >= sl
                ):
                    logger.info("Stop loss triggered!")
                    order = execute_order(
                        exchange,
                        symbol,
                        "sell" if current_position > 0 else "buy",
                        abs(current_position),
                    )
                    if order:
                        pnl = (current_price - entry_price) * current_position
                        risk_controller.record_trade(pnl)
                    current_position = 0.0
                    entry_price = 0.0

            # 4. 执行交易（带风控检查）
            if signal == 1 and current_position <= 0:
                if current_position < 0:
                    execute_order(exchange, symbol, "buy", abs(current_position))

                size = calculate_position_size(
                    exchange,
                    symbol,
                    current_atr,
                    risk_cfg.get("max_position_pct", 0.3),
                    risk_cfg.get("risk_per_trade_pct", 0.01),
                    stop_loss_mult,
                )
                if size > 0:
                    order_value = size * current_price
                    allowed, reason = risk_controller.pre_trade_check(
                        order_value, current_price, current_atr, stop_loss_mult
                    )
                    if allowed:
                        order = execute_order(exchange, symbol, "buy", size)
                        if order:
                            current_position = size
                            entry_price = current_price
                    else:
                        logger.warning(f"Trade blocked by risk control: {reason}")

            elif signal == -1 and current_position > 0:
                order = execute_order(exchange, symbol, "sell", current_position)
                if order:
                    pnl = (current_price - entry_price) * current_position
                    risk_controller.record_trade(pnl)
                current_position = 0.0
                entry_price = 0.0

            # 5. 等待下一根K线
            time.sleep(SLEEP_SECONDS.get(timeframe, 3600))

        except KeyboardInterrupt:
            logger.info("Strategy stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    config = load_config()
    setup_logging(config)

    logger = logging.getLogger(__name__)
    if not config["api_key"] or not config["api_secret"]:
        logger.error("Please set BINANCE_API_KEY and BINANCE_API_SECRET")
        sys.exit(1)

    run_strategy(config)

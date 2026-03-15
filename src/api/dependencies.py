"""
API 依赖管理 — Exchange 和 RiskController 单例
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

# 确保 src 目录在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.market_data import create_exchange
from risk.risk_manager import RiskController
from main import load_config

logger = logging.getLogger(__name__)

_exchange = None
_risk_controller = None
_config = None


@asynccontextmanager
async def lifespan(app):
    """FastAPI 生命周期：启动时初始化交易所连接和风控引擎"""
    global _exchange, _risk_controller, _config

    _config = load_config()

    if _config["api_key"] and _config["api_secret"]:
        try:
            _exchange = create_exchange(
                _config["api_key"], _config["api_secret"],
                sandbox=_config["sandbox"],
            )
            balance = _exchange.fetch_balance()
            free_usdt = balance["free"].get("USDT", 0)
            risk_cfg = _config.get("risk", {})
            _risk_controller = RiskController(
                initial_equity=free_usdt,
                max_daily_loss_pct=risk_cfg.get("max_daily_loss_pct", 0.05),
                max_drawdown_pct=risk_cfg.get("max_drawdown_pct", 0.15),
                max_position_pct=risk_cfg.get("max_position_pct", 0.30),
                max_single_loss_pct=risk_cfg.get("risk_per_trade_pct", 0.02),
            )
            logger.info(f"API initialized: equity={free_usdt:.2f} USDT")
        except Exception as e:
            logger.warning(f"Exchange init failed: {e}. Running in demo mode.")
    else:
        logger.warning("No API keys configured. Running in demo mode.")

    yield


def get_exchange():
    return _exchange


def get_risk_controller():
    return _risk_controller


def get_config():
    return _config

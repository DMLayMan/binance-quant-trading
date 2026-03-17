"""Settings 路由 — 配置读取与更新（YAML + .env）"""

import os
import yaml
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv, set_key, dotenv_values

from api.schemas import (
    SettingsResponse, SettingsUpdateRequest,
    EnvConfigResponse, EnvConfigUpdateRequest,
)
from api.dependencies import get_exchange, reinitialize_exchange

router = APIRouter()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "settings.yaml")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")


# ==================== YAML 辅助 ====================


def _read_yaml() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def _write_yaml(data: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


# ==================== Env 辅助 ====================


def _mask_key(value: str) -> str:
    """掩码处理：仅保留末 4 位"""
    if not value or len(value) < 4:
        return ""
    return "****" + value[-4:]


def _is_placeholder(value: str) -> bool:
    """检查是否为占位符值"""
    return value in ("", "your_api_key_here", "your_api_secret_here")


def _get_connection_status() -> tuple[str, str | None]:
    """检查交易所连接状态"""
    exchange = get_exchange()
    if exchange is None:
        return "disconnected", None
    try:
        exchange.fetch_time()
        return "connected", None
    except Exception as e:
        return "error", str(e)


# ==================== YAML Settings 路由 ====================


@router.get("", response_model=SettingsResponse)
def get_settings():
    try:
        cfg = _read_yaml()
    except FileNotFoundError:
        raise HTTPException(404, "Config file not found")

    return SettingsResponse(
        exchange=cfg.get("exchange", {}),
        strategy=cfg.get("strategy", {}),
        risk=cfg.get("risk", {}),
        fees=cfg.get("fees", {}),
        logging=cfg.get("logging", {}),
    )


@router.put("", response_model=SettingsResponse)
def update_settings(req: SettingsUpdateRequest):
    try:
        cfg = _read_yaml()
    except FileNotFoundError:
        raise HTTPException(404, "Config file not found")

    # 深度合并（只更新提供的字段）
    if req.strategy is not None:
        cfg["strategy"] = {**cfg.get("strategy", {}), **req.strategy}
    if req.risk is not None:
        cfg["risk"] = {**cfg.get("risk", {}), **req.risk}
    if req.fees is not None:
        cfg["fees"] = {**cfg.get("fees", {}), **req.fees}
    if req.logging is not None:
        cfg["logging"] = {**cfg.get("logging", {}), **req.logging}

    _write_yaml(cfg)

    return SettingsResponse(
        exchange=cfg.get("exchange", {}),
        strategy=cfg.get("strategy", {}),
        risk=cfg.get("risk", {}),
        fees=cfg.get("fees", {}),
        logging=cfg.get("logging", {}),
    )


# ==================== Env Config 路由 ====================


@router.get("/env", response_model=EnvConfigResponse)
def get_env_config():
    """返回掩码后的 API 凭证状态和连接状态（不暴露明文）"""
    env_values = dotenv_values(ENV_PATH) if os.path.exists(ENV_PATH) else {}

    api_key = env_values.get("BINANCE_API_KEY", "")
    api_secret = env_values.get("BINANCE_API_SECRET", "")
    use_testnet_str = env_values.get("USE_TESTNET", "true")
    use_testnet = use_testnet_str.lower() in ("true", "1", "yes")

    conn_status, conn_error = _get_connection_status()

    return EnvConfigResponse(
        api_key_configured=not _is_placeholder(api_key),
        api_key_masked=_mask_key(api_key) if not _is_placeholder(api_key) else "",
        api_secret_configured=not _is_placeholder(api_secret),
        api_secret_masked=_mask_key(api_secret) if not _is_placeholder(api_secret) else "",
        use_testnet=use_testnet,
        connection_status=conn_status,
        connection_error=conn_error,
    )


@router.put("/env", response_model=EnvConfigResponse)
def update_env_config(req: EnvConfigUpdateRequest):
    """更新 .env 凭证并热重载交易所连接"""
    # 确保 .env 文件存在
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w") as f:
            f.write("# BQT Environment Config\n")

    # 使用 python-dotenv 的 set_key 安全写入
    if req.api_key is not None:
        set_key(ENV_PATH, "BINANCE_API_KEY", req.api_key)
    if req.api_secret is not None:
        set_key(ENV_PATH, "BINANCE_API_SECRET", req.api_secret)
    if req.use_testnet is not None:
        set_key(ENV_PATH, "USE_TESTNET", str(req.use_testnet).lower())

    # 重新加载环境变量
    load_dotenv(ENV_PATH, override=True)

    # 热重载交易所连接
    reinitialize_exchange()

    # 返回更新后的状态
    return get_env_config()


# ==================== 通知配置路由 ====================


class NotifyConfigResponse:
    pass  # placeholder for import check


from pydantic import BaseModel as _BM


class NotifyConfigResp(_BM):
    telegram_configured: bool
    telegram_chat_id_masked: str
    webhook_configured: bool
    webhook_url_masked: str


class NotifyConfigUpdate(_BM):
    telegram_bot_token: str = None
    telegram_chat_id: str = None
    webhook_url: str = None


@router.get("/notify", response_model=NotifyConfigResp)
def get_notify_config():
    """获取通知配置（掩码）"""
    env_values = dotenv_values(ENV_PATH) if os.path.exists(ENV_PATH) else {}

    tg_token = env_values.get("BQT_TELEGRAM_BOT_TOKEN", "")
    tg_chat = env_values.get("BQT_TELEGRAM_CHAT_ID", "")
    webhook = env_values.get("BQT_WEBHOOK_URL", "")

    return NotifyConfigResp(
        telegram_configured=bool(tg_token and tg_chat),
        telegram_chat_id_masked=_mask_key(tg_chat) if tg_chat else "",
        webhook_configured=bool(webhook),
        webhook_url_masked=(webhook[:20] + "...") if len(webhook) > 20 else webhook,
    )


@router.put("/notify", response_model=NotifyConfigResp)
def update_notify_config(req: NotifyConfigUpdate):
    """更新通知配置"""
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w") as f:
            f.write("# BQT Environment Config\n")

    if req.telegram_bot_token is not None:
        set_key(ENV_PATH, "BQT_TELEGRAM_BOT_TOKEN", req.telegram_bot_token)
    if req.telegram_chat_id is not None:
        set_key(ENV_PATH, "BQT_TELEGRAM_CHAT_ID", req.telegram_chat_id)
    if req.webhook_url is not None:
        set_key(ENV_PATH, "BQT_WEBHOOK_URL", req.webhook_url)

    load_dotenv(ENV_PATH, override=True)

    # 重新初始化通知器
    from core.notifier import get_notifier
    notifier = get_notifier()
    notifier.__init__()  # re-init channels from env

    return get_notify_config()

"""
通知框架 — 支持多渠道告警（Telegram / Webhook / 日志）

使用方式:
    from core.notifier import notify, NotifyLevel
    notify(NotifyLevel.WARNING, "Pool daily loss exceeded 3%", pool_id="xxx")
"""

import os
import json
import logging
import urllib.request
from enum import Enum
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class NotifyLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ==================== Channel 接口 ====================


class NotifyChannel:
    """通知渠道基类"""
    def send(self, level: NotifyLevel, message: str, **kwargs) -> bool:
        raise NotImplementedError


class LogChannel(NotifyChannel):
    """日志通知（始终启用）"""
    def send(self, level: NotifyLevel, message: str, **kwargs) -> bool:
        log_msg = f"[NOTIFY:{level.value.upper()}] {message}"
        if level == NotifyLevel.CRITICAL:
            logger.critical(log_msg)
        elif level == NotifyLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        return True


class TelegramChannel(NotifyChannel):
    """Telegram Bot 通知"""
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, level: NotifyLevel, message: str, **kwargs) -> bool:
        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(level.value, "📢")
        text = f"{icon} *BQT Alert*\n{message}"
        try:
            data = json.dumps({
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }).encode()
            req = urllib.request.Request(
                self.api_url, data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False


class WebhookChannel(NotifyChannel):
    """通用 Webhook 通知（POST JSON）"""
    def __init__(self, url: str):
        self.url = url

    def send(self, level: NotifyLevel, message: str, **kwargs) -> bool:
        payload = {
            "level": level.value,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs,
        }
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                self.url, data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return False


# ==================== 全局管理器 ====================


class NotifyManager:
    """通知管理器 — 管理所有通知渠道"""
    def __init__(self):
        self.channels: list[NotifyChannel] = [LogChannel()]
        self._init_from_env()

    def _init_from_env(self):
        """从环境变量自动配置通知渠道"""
        tg_token = os.environ.get("BQT_TELEGRAM_BOT_TOKEN", "")
        tg_chat = os.environ.get("BQT_TELEGRAM_CHAT_ID", "")
        if tg_token and tg_chat:
            self.channels.append(TelegramChannel(tg_token, tg_chat))
            logger.info("Telegram notification channel enabled")

        webhook_url = os.environ.get("BQT_WEBHOOK_URL", "")
        if webhook_url:
            self.channels.append(WebhookChannel(webhook_url))
            logger.info("Webhook notification channel enabled")

    def send(self, level: NotifyLevel, message: str, **kwargs):
        """发送通知到所有渠道"""
        for ch in self.channels:
            try:
                ch.send(level, message, **kwargs)
            except Exception as e:
                logger.error(f"Channel {type(ch).__name__} error: {e}")

    def add_channel(self, channel: NotifyChannel):
        self.channels.append(channel)


# 全局单例
_manager: Optional[NotifyManager] = None


def get_notifier() -> NotifyManager:
    global _manager
    if _manager is None:
        _manager = NotifyManager()
    return _manager


def notify(level: NotifyLevel, message: str, **kwargs):
    """快捷通知函数"""
    get_notifier().send(level, message, **kwargs)

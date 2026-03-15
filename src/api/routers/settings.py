"""Settings 路由 — 配置读取与更新"""

import os
import yaml
from fastapi import APIRouter, HTTPException
from api.schemas import SettingsResponse, SettingsUpdateRequest

router = APIRouter()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "settings.yaml")


def _read_yaml() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def _write_yaml(data: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


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

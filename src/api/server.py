"""
FastAPI 应用入口
"""

import os
import sys
import logging

# 确保 src 目录在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.dependencies import lifespan
from api.routers import overview, market, strategies, backtest, risk, settings, funds, instances, orders_trades

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

app = FastAPI(
    title="Binance Quant Trading Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(overview.router, prefix="/api", tags=["overview"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(risk.router, prefix="/api/risk", tags=["risk"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(funds.router, prefix="/api/funds", tags=["funds"])
app.include_router(instances.router, prefix="/api/instances", tags=["instances"])
app.include_router(orders_trades.router, prefix="/api", tags=["orders_trades"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 生产模式：挂载前端静态文件
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

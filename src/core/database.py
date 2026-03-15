"""
数据库管理 — SQLite + aiosqlite

单文件存储所有持久化数据：资金池、策略实例、订单、成交、权益快照。
"""

import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get(
    "BQT_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "bqt.db"),
)

# ==================== Schema ====================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fund_pools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    allocated_amount REAL NOT NULL,
    current_equity REAL NOT NULL,
    peak_equity REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    max_daily_loss_pct REAL NOT NULL DEFAULT 0.05,
    max_drawdown_pct REAL NOT NULL DEFAULT 0.15,
    take_profit_pct REAL DEFAULT NULL,
    stop_loss_pct REAL DEFAULT NULL,
    daily_start_equity REAL NOT NULL,
    current_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_instances (
    id TEXT PRIMARY KEY,
    fund_pool_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL DEFAULT 'BTC/USDT',
    timeframe TEXT NOT NULL DEFAULT '4h',
    params TEXT NOT NULL DEFAULT '{}',

    stop_loss_atr_mult REAL NOT NULL DEFAULT 2.0,
    take_profit_atr_mult REAL NOT NULL DEFAULT 4.0,
    max_position_pct REAL NOT NULL DEFAULT 0.30,
    risk_per_trade_pct REAL NOT NULL DEFAULT 0.01,

    status TEXT NOT NULL DEFAULT 'pending',
    current_position REAL NOT NULL DEFAULT 0.0,
    entry_price REAL NOT NULL DEFAULT 0.0,
    unrealized_pnl REAL NOT NULL DEFAULT 0.0,
    total_pnl REAL NOT NULL DEFAULT 0.0,
    trade_count INTEGER NOT NULL DEFAULT 0,
    win_count INTEGER NOT NULL DEFAULT 0,
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    trades_today INTEGER NOT NULL DEFAULT 0,
    trades_today_date TEXT NOT NULL DEFAULT '',

    last_signal INTEGER NOT NULL DEFAULT 0,
    last_signal_time TEXT DEFAULT NULL,
    next_check_time TEXT NOT NULL,
    error_message TEXT DEFAULT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (fund_pool_id) REFERENCES fund_pools(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    exchange_order_id TEXT,
    strategy_instance_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL DEFAULT 'market',
    amount REAL NOT NULL,
    price REAL DEFAULT NULL,
    filled_amount REAL NOT NULL DEFAULT 0.0,
    fee REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT DEFAULT NULL,
    created_at TEXT NOT NULL,
    filled_at TEXT DEFAULT NULL,

    FOREIGN KEY (strategy_instance_id) REFERENCES strategy_instances(id)
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    strategy_instance_id TEXT NOT NULL,
    fund_pool_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'long',
    entry_order_id TEXT,
    exit_order_id TEXT,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    amount REAL NOT NULL,
    pnl REAL NOT NULL,
    pnl_pct REAL NOT NULL,
    total_fee REAL NOT NULL DEFAULT 0.0,
    holding_seconds INTEGER NOT NULL DEFAULT 0,
    exit_reason TEXT DEFAULT NULL,
    entry_time TEXT NOT NULL,
    exit_time TEXT NOT NULL,

    FOREIGN KEY (strategy_instance_id) REFERENCES strategy_instances(id),
    FOREIGN KEY (fund_pool_id) REFERENCES fund_pools(id)
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_pool_id TEXT NOT NULL,
    equity REAL NOT NULL,
    timestamp TEXT NOT NULL,

    FOREIGN KEY (fund_pool_id) REFERENCES fund_pools(id)
);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_instance_id TEXT,
    fund_pool_id TEXT,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_instances_status ON strategy_instances(status, next_check_time);
CREATE INDEX IF NOT EXISTS idx_orders_instance ON orders(strategy_instance_id, created_at);
CREATE INDEX IF NOT EXISTS idx_trades_instance ON trades(strategy_instance_id, exit_time);
CREATE INDEX IF NOT EXISTS idx_trades_pool ON trades(fund_pool_id, exit_time);
CREATE INDEX IF NOT EXISTS idx_equity_pool ON equity_snapshots(fund_pool_id, timestamp);
"""


def get_db_path() -> str:
    path = os.path.abspath(DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def init_db() -> sqlite3.Connection:
    """初始化数据库，创建表结构，返回连接"""
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    logger.info(f"Database initialized: {path}")
    return conn


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

# Binance Quantitative Trading System

> 币安量化交易系统 — 完整解决方案

## 项目概述

本项目是一套面向币安(Binance)交易所的量化交易完整解决方案，涵盖：

- **8 种量化策略** — 趋势跟踪、动量、套利、做市
- **实时风控引擎** — 6 层风险检查（日亏损/回撤/仓位/单笔/次数/连亏）
- **回测框架** — 事件驱动、ATR 止损止盈、滑点/手续费模拟
- **Web Dashboard** — React + FastAPI 监控面板（K 线图、策略信号、风控状态）
- **一键部署** — Docker Compose + 阿里云 ECS 部署脚本

## 项目结构

```
binance-quant-trading/
├── config/
│   └── settings.yaml             # 策略/风控/费率/日志配置
├── src/
│   ├── main.py                   # 主入口（策略运行器）
│   ├── strategies/               # 8 种策略
│   │   ├── ma_crossover.py       # 双均线交叉
│   │   ├── macd_strategy.py      # MACD 趋势
│   │   ├── bollinger_breakout.py # 布林带突破
│   │   ├── rsi_momentum.py       # RSI 动量
│   │   ├── turtle_trading.py     # 改良海龟法则
│   │   ├── pairs_trading.py      # 配对交易 / 统计套利
│   │   ├── arbitrage.py          # 套利（基差/三角/费率）
│   │   └── market_maker.py       # A-S 做市
│   ├── data/
│   │   └── market_data.py        # OHLCV/Ticker/OrderBook 数据获取
│   ├── execution/
│   │   └── order_manager.py      # 订单执行/仓位计算/止损止盈
│   ├── backtest/
│   │   └── engine.py             # 事件驱动回测引擎
│   ├── risk/
│   │   └── risk_manager.py       # 风控引擎 + Kelly + 蒙特卡洛
│   ├── utils/
│   │   └── indicators.py         # 技术指标（ATR/RSI/BB/MACD）
│   └── api/                      # FastAPI Dashboard 后端
│       ├── server.py             # 应用入口 + CORS + 路由注册
│       ├── dependencies.py       # Exchange/RiskController 单例管理
│       ├── schemas.py            # Pydantic 请求/响应模型
│       └── routers/
│           ├── overview.py       # GET  /api/overview
│           ├── market.py         # GET  /api/market/{ohlcv,ticker,orderbook}
│           ├── strategies.py     # GET  /api/strategies, /{name}/signals
│           ├── backtest.py       # POST /api/backtest/run
│           ├── risk.py           # GET  /api/risk/{status,config}, POST reset-halt
│           └── settings.py       # GET/PUT /api/settings
├── frontend/                     # React + TypeScript + Tailwind 前端
├── tests/                        # 单元测试（pytest）
├── deploy/aliyun/                # 阿里云一键部署脚本
├── Dockerfile                    # 多阶段构建（Node + Python）
├── docker-compose.yml            # 本地开发用
├── .env.example                  # 环境变量模板
└── docs/                         # 方案设计文档
```

---

## Quick Start

### 前置条件

- Python 3.11+
- Node.js 20+（前端开发时需要）
- Docker & Docker Compose（容器部署时需要）

### 1. 克隆 & 安装

```bash
git clone https://github.com/DMLayMan/binance-quant-trading.git
cd binance-quant-trading
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```ini
# 必填 — 从 https://www.binance.com/cn/my/settings/api-management 获取
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# 测试网模式（首次使用建议 true）
USE_TESTNET=true
```

> **配置优先级：** 环境变量 / `.env` > `config/settings.yaml`
> API 密钥只通过环境变量加载，**永远不会写入 YAML 配置或提交到 Git**。

### 3. 选择策略

编辑 `config/settings.yaml`：

```yaml
strategy:
  name: ma_crossover          # 可选: ma_crossover | macd | bollinger_breakout | rsi | turtle
  symbol: BTC/USDT
  timeframe: 4h               # 1m | 5m | 15m | 1h | 4h | 1d
  params:
    fast_ma: 7
    slow_ma: 25

risk:
  max_position_pct: 0.30      # 单笔最大仓位占总资金比
  risk_per_trade_pct: 0.01    # 单笔风险占总资金比
  stop_loss_atr_mult: 2.0     # 止损 = ATR × 倍数
  take_profit_atr_mult: 4.0   # 止盈 = ATR × 倍数
  max_daily_loss_pct: 0.05    # 日亏损超 5% 暂停交易
  max_drawdown_pct: 0.15      # 最大回撤超 15% 暂停交易
```

### 4. 运行

#### 方式 A：直接运行策略

```bash
cd src
python3 main.py
```

#### 方式 B：启动 Dashboard（API + 前端）

```bash
# 终端 1 — 启动 API 后端
cd src
python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

# 终端 2 — 启动前端开发服务器
cd frontend
npm install --legacy-peer-deps
npm run dev
```

访问：
- 前端面板：http://localhost:5173
- API 文档（Swagger）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

#### 方式 C：Docker Compose 一键启动

```bash
# 复制并编辑环境变量
cp .env.example .env
vim .env

# 启动所有服务
docker compose up -d --build

# 查看日志
docker compose logs -f
```

| 服务 | 端口 | 说明 |
|------|------|------|
| `trading-bot` | — | 策略主循环（无需对外暴露端口） |
| `dashboard` | 8000 | FastAPI + 前端静态文件 |

访问 http://localhost:8000 即可使用 Dashboard。

### 5. 运行测试

```bash
# 在项目根目录
cd src
python3 -m pytest ../tests/ -v

# 单独运行某一类测试
python3 -m pytest ../tests/test_strategies.py -v
python3 -m pytest ../tests/test_risk_manager.py -v
python3 -m pytest ../tests/test_backtest.py -v
python3 -m pytest ../tests/test_indicators.py -v
```

---

## 阿里云一键部署

### 方式 A：已有 ECS 服务器

```bash
bash deploy/aliyun/deploy.sh \
  --host <ECS公网IP> \
  --key ~/.ssh/id_rsa
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | 必填 | ECS 公网 IP |
| `--user` | `root` | SSH 用户名 |
| `--key` | — | SSH 私钥路径 |
| `--port` | `22` | SSH 端口 |

### 方式 B：自动创建 ECS + 部署

```bash
# 前置：安装并配置阿里云 CLI
pip install aliyun-cli
aliyun configure

# 一键创建实例并部署
bash deploy/aliyun/deploy.sh \
  --create-ecs \
  --region cn-hangzhou
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--create-ecs` | — | 自动创建 ECS 实例 |
| `--region` | `cn-hangzhou` | 阿里云地域 |
| `--instance-type` | `ecs.t6-c1m2.large` | 实例规格（2vCPU/4GB） |

### 方式 C：SSH 到服务器手动执行

```bash
git clone https://github.com/DMLayMan/binance-quant-trading.git /opt/bqt
cd /opt/bqt
cp .env.example .env && vim .env
sudo bash deploy/aliyun/setup.sh
```

`setup.sh` 会自动完成：
1. 安装 Docker + Docker Compose（阿里云镜像加速）
2. 配置防火墙（放行 22/80/443）
3. 交互式配置 `.env`
4. 可选：配置域名 + Let's Encrypt SSL
5. 构建并启动所有容器
6. 可选：配置每日自动更新 cron

### 部署后常用命令

```bash
cd /opt/bqt

# 查看服务状态
docker compose -f deploy/aliyun/docker-compose.prod.yml ps

# 查看实时日志
docker compose -f deploy/aliyun/docker-compose.prod.yml logs -f dashboard

# 重启服务
docker compose -f deploy/aliyun/docker-compose.prod.yml restart

# 更新代码并重新部署
git pull && docker compose -f deploy/aliyun/docker-compose.prod.yml up -d --build

# 停止所有服务
docker compose -f deploy/aliyun/docker-compose.prod.yml down
```

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/overview` | 账户总览（余额/持仓/风控状态） |
| GET | `/api/market/ohlcv?symbol=BTC/USDT&timeframe=4h` | K 线 + 技术指标 |
| GET | `/api/market/ticker?symbol=BTC/USDT` | 实时行情 |
| GET | `/api/market/orderbook?symbol=BTC/USDT&depth=20` | 订单簿 |
| GET | `/api/strategies` | 策略列表 |
| GET | `/api/strategies/{name}/signals?symbol=BTC/USDT` | 策略信号 |
| POST | `/api/backtest/run` | 执行回测 |
| GET | `/api/risk/status` | 风控状态 |
| GET | `/api/risk/config` | 风控参数 |
| POST | `/api/risk/reset-halt` | 重置风控暂停 |
| GET | `/api/settings` | 读取配置 |
| PUT | `/api/settings` | 更新配置 |

---

## 策略列表

| 策略 | 类型 | 适用市况 | 夏普比 | 复杂度 |
|------|------|---------|--------|--------|
| 双均线交叉 | 趋势跟踪 | 趋势行情 | 0.8-1.5 | 低 |
| MACD | 趋势跟踪 | 趋势行情 | 0.7-1.3 | 低 |
| 布林带突破 | 趋势跟踪 | Squeeze后 | 0.8-1.6 | 中 |
| RSI 动量 | 动量 | 震荡+趋势 | 0.6-1.2 | 低 |
| 海龟法则 | 趋势跟踪 | 强趋势 | 0.9-1.8 | 中 |
| 配对交易 | 均值回归 | 震荡行情 | 1.0-2.0 | 高 |
| 基差/三角/费率套利 | 套利 | 全市况 | 2.0-5.0 | 中-高 |
| A-S 做市 | 做市 | 高流动性 | 1.5-3.0 | 极高 |

## 技术栈

| 层次 | 技术选型 |
|------|---------|
| 策略引擎 | Python 3.11+ / CCXT / pandas / numpy |
| 回测框架 | 自研事件驱动引擎 / ATR 止损止盈 |
| Web 后端 | FastAPI / Uvicorn / Pydantic |
| Web 前端 | React 19 / TypeScript / Tailwind CSS / Recharts / Lightweight Charts |
| 风控引擎 | Kelly 公式 / 蒙特卡洛模拟 / 6 层实时检查 |
| 容器化 | Docker 多阶段构建 / Docker Compose |
| 部署 | 阿里云 ECS / Nginx / Let's Encrypt SSL |

## 配置参考

### 环境变量 (`.env`)

| 变量 | 必填 | 说明 |
|------|------|------|
| `BINANCE_API_KEY` | 是 | 币安 API Key |
| `BINANCE_API_SECRET` | 是 | 币安 API Secret |
| `USE_TESTNET` | 否 | 测试网模式，默认 `true` |
| `DOMAIN` | 否 | 部署域名（SSL 证书用） |
| `CERTBOT_EMAIL` | 否 | SSL 证书申请邮箱 |

### YAML 配置 (`config/settings.yaml`)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `strategy.name` | string | `ma_crossover` | 策略名称 |
| `strategy.symbol` | string | `BTC/USDT` | 交易对 |
| `strategy.timeframe` | string | `4h` | K 线周期 |
| `strategy.params` | dict | — | 策略参数（覆盖默认值） |
| `risk.max_position_pct` | float | `0.30` | 最大仓位占比 |
| `risk.risk_per_trade_pct` | float | `0.01` | 单笔风险占比 |
| `risk.stop_loss_atr_mult` | float | `2.0` | 止损 ATR 倍数 |
| `risk.take_profit_atr_mult` | float | `4.0` | 止盈 ATR 倍数 |
| `risk.max_daily_loss_pct` | float | `0.05` | 日亏损上限 |
| `risk.max_drawdown_pct` | float | `0.15` | 最大回撤上限 |
| `fees.maker` | float | `0.001` | Maker 手续费率 |
| `fees.taker` | float | `0.001` | Taker 手续费率 |
| `fees.bnb_discount` | bool | `true` | BNB 抵扣手续费 |

## 文档

详细方案文档在 `docs/` 目录下：

1. **[技术调研报告](docs/01-technical-research.md)** — 币安API、框架对比、最新趋势
2. **[系统架构设计](docs/02-system-architecture.md)** — 架构图、模块设计、部署方案
3. **[量化策略体系](docs/03-trading-strategies.md)** — 策略详解、代码模板、回测体系
4. **[风控与资金管理](docs/04-risk-management.md)** — 三层风控、Kelly公式、合规
5. **[研发落地路线图](docs/05-development-roadmap.md)** — 里程碑、任务拆解、成本估算

## 风险提示

> 量化交易存在市场风险，历史回测结果不代表未来收益。
> 请在充分理解风险的前提下，使用小资金进行验证。
> 本方案仅供技术参考，不构成投资建议。

## License

MIT

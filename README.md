# Binance Quantitative Trading System

> 币安量化交易系统 — 完整解决方案

## 项目概述

本项目是一套面向币安(Binance)交易所的量化交易完整解决方案，涵盖从技术调研、系统架构设计、策略体系建设、风控管理到研发落地的全链路方案。

## 项目结构

```
binance-quant-trading/
├── README.md
├── requirements.txt              # Python 依赖
├── .env.example                  # 环境变量模板
├── .gitignore
│
├── config/
│   └── settings.yaml             # 策略与风控配置
│
├── src/                          # 核心代码
│   ├── main.py                   # 主入口（策略运行器）
│   │
│   ├── strategies/               # 策略模块
│   │   ├── ma_crossover.py       # 双均线交叉策略
│   │   ├── macd_strategy.py      # MACD 趋势策略
│   │   ├── bollinger_breakout.py # 布林带突破策略
│   │   ├── rsi_momentum.py       # RSI 动量策略
│   │   ├── turtle_trading.py     # 改良海龟法则
│   │   ├── pairs_trading.py      # 配对交易 / 统计套利
│   │   ├── arbitrage.py          # 套利策略（基差/三角/费率）
│   │   └── market_maker.py       # Avellaneda-Stoikov 做市策略
│   │
│   ├── data/                     # 数据采集
│   │   └── market_data.py        # 行情数据获取（CCXT）
│   │
│   ├── execution/                # 交易执行
│   │   └── order_manager.py      # 订单管理（下单/止损/仓位）
│   │
│   ├── risk/                     # 风控引擎
│   │   └── risk_manager.py       # Kelly公式/指标计算/蒙特卡洛
│   │
│   └── utils/                    # 工具函数
│       └── indicators.py         # 技术指标（ATR/RSI/BB/MACD）
│
├── tests/                        # 测试
│
└── docs/                         # 方案文档
    ├── 01-technical-research.md   # 技术调研报告
    ├── 02-system-architecture.md  # 系统架构设计
    ├── 03-trading-strategies.md   # 量化策略体系
    ├── 04-risk-management.md      # 风控与资金管理
    └── 05-development-roadmap.md  # 研发落地路线图
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env 填入你的 Binance API Key
```

### 3. 运行策略（测试网）

```bash
cd src
python main.py
```

## 策略列表

| 策略 | 类型 | 适用市况 | 夏普比 | 复杂度 |
|------|------|---------|--------|--------|
| 双均线交叉 | 趋势跟踪 | 趋势行情 | 0.8-1.5 | 低 |
| MACD | 趋势跟踪 | 趋势行情 | 0.7-1.3 | 低 |
| 布林带突破 | 趋势跟踪 | Squeeze后 | 0.8-1.6 | 中 |
| RSI 动量 | 动量 | 震荡+趋势 | 0.6-1.2 | 低 |
| 海龟法则 | 趋势跟踪 | 强趋势 | 0.9-1.8 | 中 |
| 配对交易 | 均值回归 | 震荡行情 | 1.0-2.0 | 高 |
| 基差套利 | 套利 | 全市况 | 2.0-4.0 | 中 |
| 三角套利 | 套利 | 全市况 | 3.0+ | 高 |
| 资金费率套利 | 套利 | 正费率期 | 2.5-5.0 | 低 |
| A-S 做市 | 做市 | 高流动性 | 1.5-3.0 | 极高 |

## 技术栈

| 层次 | 技术选型 |
|------|---------|
| 策略研发 | Python 3.11+ / CCXT / pandas / numpy / scikit-learn |
| 高性能执行 | Go / Rust（低延迟下单，规划中） |
| 前端监控 | TypeScript / React / Grafana（规划中） |
| 数据存储 | TimescaleDB + PostgreSQL + Redis（规划中） |
| 部署运维 | Docker + Kubernetes（规划中） |

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

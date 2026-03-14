# 币安量化交易系统 — 系统架构设计

> 版本: v1.0 | 更新日期: 2026-03-13 | 面向: 研发团队

---

## 目录

1. [整体系统架构](#1-整体系统架构)
2. [技术选型](#2-技术选型)
3. [核心模块详细设计](#3-核心模块详细设计)
4. [部署架构](#4-部署架构)
5. [数据流图](#5-数据流图)

---

## 1. 整体系统架构

### 1.1 系统模块关系图

```mermaid
graph TB
    subgraph External["外部系统"]
        BINANCE_WS["Binance WebSocket API"]
        BINANCE_REST["Binance REST API"]
        BINANCE_ORDER["Binance Order Gateway"]
    end

    subgraph DataLayer["数据采集层"]
        MD["市场数据服务<br/>Market Data Service"]
        HD["历史数据管理<br/>Historical Data Manager"]
        DC["数据清洗引擎<br/>Data Cleaning Engine"]
    end

    subgraph StrategyLayer["策略引擎层"]
        SE["策略引擎<br/>Strategy Engine"]
        BT["回测框架<br/>Backtesting Framework"]
        OPT["参数优化器<br/>Parameter Optimizer"]
        SIG["信号生成器<br/>Signal Generator"]
    end

    subgraph ExecutionLayer["交易执行层"]
        OMS["订单管理系统<br/>Order Management System"]
        OR["订单路由<br/>Order Router"]
        EM["执行监控<br/>Execution Monitor"]
        SM["滑点监控<br/>Slippage Monitor"]
    end

    subgraph RiskLayer["风控层"]
        RM["风控引擎<br/>Risk Management Engine"]
        PM["仓位管理<br/>Position Manager"]
        CB["熔断机制<br/>Circuit Breaker"]
        PNL["实时 PnL 计算<br/>Real-time PnL"]
    end

    subgraph MonitorLayer["监控与运维层"]
        MON["系统监控<br/>Prometheus + Grafana"]
        LOG["日志审计<br/>Audit Logger"]
        ALT["告警服务<br/>Alert Service"]
        DASH["交易仪表盘<br/>Trading Dashboard"]
    end

    subgraph Storage["存储层"]
        TSDB["时序数据库<br/>QuestDB"]
        RDBMS["关系型数据库<br/>PostgreSQL"]
        CACHE["缓存层<br/>Redis Cluster"]
        MQ["消息队列<br/>Kafka"]
    end

    BINANCE_WS -->|实时行情推送| MD
    BINANCE_REST -->|历史数据拉取| HD
    MD -->|原始数据| DC
    HD -->|历史数据| DC
    DC -->|清洗后数据| TSDB
    DC -->|数据事件| MQ

    MQ -->|行情数据流| SE
    TSDB -->|历史数据| BT
    SE -->|策略参数| OPT
    OPT -->|优化结果| SE
    SE -->|交易信号| SIG
    BT -->|回测结果| SE

    SIG -->|下单指令| RM
    RM -->|风控审批| OMS
    OMS -->|订单| OR
    OR -->|API 调用| BINANCE_ORDER
    BINANCE_ORDER -->|成交回报| EM
    EM -->|执行结果| SM
    SM -->|滑点数据| PNL

    RM --> PM
    RM --> CB
    PM --> PNL
    PNL -->|PnL 数据| RDBMS

    OMS -->|订单状态| RDBMS
    OMS -->|订单缓存| CACHE
    SE -->|策略状态| CACHE

    MON -->|采集指标| SE
    MON -->|采集指标| OMS
    MON -->|采集指标| RM
    LOG -->|审计日志| RDBMS
    ALT -->|异常事件| MON
    DASH -->|展示数据| CACHE
    DASH -->|展示数据| RDBMS

    style External fill:#ff6b6b,stroke:#333,color:#fff
    style DataLayer fill:#4ecdc4,stroke:#333,color:#fff
    style StrategyLayer fill:#45b7d1,stroke:#333,color:#fff
    style ExecutionLayer fill:#96ceb4,stroke:#333,color:#fff
    style RiskLayer fill:#feca57,stroke:#333,color:#333
    style MonitorLayer fill:#a29bfe,stroke:#333,color:#fff
    style Storage fill:#fd79a8,stroke:#333,color:#fff
```

### 1.2 架构选型：微服务架构

**选型结论：采用微服务架构，但初期以"模块化单体"起步，逐步拆分。**

| 维度 | 单体架构 | 微服务架构 | 我们的选择 |
|------|---------|-----------|-----------|
| 部署复杂度 | 低 | 高 | 初期单体，降低运维成本 |
| 模块间延迟 | 极低（进程内调用） | 较高（网络调用） | 性能关键路径保持进程内通信 |
| 独立扩缩容 | 不支持 | 支持 | 策略引擎和数据服务需要独立扩展 |
| 技术栈异构 | 困难 | 天然支持 | Python + Go/Rust 必须异构 |
| 故障隔离 | 差 | 好 | 风控和交易执行必须隔离 |

**渐进式拆分路径：**

```
Phase 1 (MVP): 模块化单体
  ├── Python 单体: 数据采集 + 策略引擎 + 回测
  └── Go 服务: 订单执行 + 风控

Phase 2 (稳定期): 核心拆分
  ├── Market Data Service (Python)
  ├── Strategy Engine (Python)
  ├── Order Execution Service (Go)
  ├── Risk Management Service (Go)
  └── Monitoring Dashboard (TypeScript)

Phase 3 (规模化): 完全微服务
  └── 按交易对 / 策略类型进一步水平拆分
```

---

## 2. 技术选型

### 2.1 编程语言

| 层次 | 语言 | 理由 |
|------|------|------|
| 策略研发 & 回测 | **Python 3.12+** | 丰富的量化库生态（numpy、pandas、ta-lib）、快速原型迭代、Jupyter 交互式研发 |
| 交易执行 & 风控 | **Go 1.22+** | 高并发、低延迟、内存安全、goroutine 天然适合 WebSocket 长连接管理 |
| 高频关键路径 | **Rust**（可选） | 订单簿维护、撮合模拟等对延迟极度敏感的模块，后期按需引入 |
| 前端监控面板 | **TypeScript + React** | 类型安全、丰富的可视化库（ECharts、TradingView Lightweight Charts） |
| 脚本 & 胶水 | **Python / Shell** | 数据迁移、定时任务、运维脚本 |

### 2.2 消息队列

**选型：Apache Kafka**

| 方案 | 吞吐量 | 延迟 | 持久化 | 回放能力 | 选择理由 |
|------|--------|------|--------|---------|---------|
| **Kafka** | 极高 | 毫秒级 | 强 | 支持 | 行情数据天然是事件流，Kafka 分区模型完美匹配按交易对分流 |
| RabbitMQ | 中 | 微秒级 | 可选 | 不支持 | 延迟更低但不支持历史回放，不利于回测数据重放 |
| Redis Streams | 高 | 微秒级 | 弱 | 有限 | 适合轻量级场景，持久化能力不足以支撑完整行情存储 |

**Kafka Topic 设计：**

```
binance.market.{symbol}.ticker    # 实时 Ticker
binance.market.{symbol}.depth     # 深度数据
binance.market.{symbol}.kline     # K 线数据
binance.market.{symbol}.trade     # 逐笔成交
trading.signal.{strategy_id}      # 交易信号
trading.order.{symbol}            # 订单事件
trading.execution.{symbol}        # 成交回报
risk.alert                        # 风控告警
system.metrics                    # 系统指标
```

### 2.3 数据库

| 类型 | 选型 | 用途 | 理由 |
|------|------|------|------|
| 时序数据库 | **QuestDB** | K线、Tick数据、指标时序 | 列式存储、SQL 兼容、写入性能优异（百万行/秒）、比 InfluxDB 查询更快 |
| 关系型数据库 | **PostgreSQL 16** | 订单、持仓、策略配置、用户管理 | ACID 保证、JSONB 灵活 schema、成熟的生态 |
| 缓存 | **Redis 7 Cluster** | 实时行情快照、订单状态缓存、分布式锁、限流 | 亚毫秒延迟、丰富的数据结构、Pub/Sub 能力 |
| 对象存储 | **MinIO / S3** | 回测报告、日志归档、模型文件 | 兼容 S3 API、可自托管 |

**数据生命周期管理：**

```
实时数据 (< 1h)     → Redis (内存)
近期数据 (1h ~ 30d)  → QuestDB (SSD)
历史数据 (30d ~ 2y)  → QuestDB (HDD 分区)
归档数据 (> 2y)      → S3/MinIO (冷存储)
```

### 2.4 容器化与编排

```mermaid
graph LR
    subgraph K8s["Kubernetes Cluster"]
        subgraph NS_PROD["Namespace: production"]
            MD_POD["Market Data<br/>Pods x2"]
            SE_POD["Strategy Engine<br/>Pods x N"]
            OMS_POD["OMS<br/>Pods x2"]
            RISK_POD["Risk Engine<br/>Pods x2"]
        end

        subgraph NS_INFRA["Namespace: infrastructure"]
            KAFKA_POD["Kafka<br/>Brokers x3"]
            PG_POD["PostgreSQL<br/>Primary + Replica"]
            QUEST_POD["QuestDB<br/>Single Node"]
            REDIS_POD["Redis<br/>Cluster x6"]
        end

        subgraph NS_MONITOR["Namespace: monitoring"]
            PROM["Prometheus"]
            GRAF["Grafana"]
            ALERT["Alertmanager"]
        end
    end

    style K8s fill:#326ce5,stroke:#fff,color:#fff
    style NS_PROD fill:#2ecc71,stroke:#333,color:#fff
    style NS_INFRA fill:#e74c3c,stroke:#333,color:#fff
    style NS_MONITOR fill:#9b59b6,stroke:#333,color:#fff
```

**Docker 镜像策略：**

| 服务 | 基础镜像 | 构建方式 |
|------|---------|---------|
| Python 服务 | `python:3.12-slim` | 多阶段构建，poetry 管理依赖 |
| Go 服务 | `golang:1.22-alpine` → `scratch` | 静态编译，最终镜像 < 20MB |
| 前端 | `node:22-alpine` → `nginx:alpine` | Vite 构建 → Nginx 托管 |

### 2.5 CI/CD 流水线

```mermaid
graph LR
    DEV["开发者<br/>git push"] --> LINT["代码检查<br/>Lint + Format"]
    LINT --> TEST["自动化测试<br/>Unit + Integration"]
    TEST --> BUILD["Docker 构建<br/>多阶段构建"]
    BUILD --> SCAN["安全扫描<br/>Trivy + Snyk"]
    SCAN --> STAGE["部署 Staging<br/>模拟盘验证"]
    STAGE --> APPROVE["人工审批<br/>策略负责人"]
    APPROVE --> PROD["部署 Production<br/>金丝雀发布"]
    PROD --> VERIFY["生产验证<br/>Smoke Test"]

    style DEV fill:#3498db,stroke:#333,color:#fff
    style TEST fill:#2ecc71,stroke:#333,color:#fff
    style APPROVE fill:#e74c3c,stroke:#333,color:#fff
    style PROD fill:#e67e22,stroke:#333,color:#fff
```

**关键原则：**

- 策略代码变更**必须**经过回测验证 + 模拟盘运行 24h 后才能上线实盘
- 基础设施变更（风控参数、交易执行逻辑）采用**蓝绿部署**
- 所有部署可一键回滚，回滚时间 < 30s

---

## 3. 核心模块详细设计

### 3.1 市场数据服务（Market Data Service）

#### 3.1.1 架构概览

```mermaid
graph TB
    subgraph Sources["数据源"]
        WS1["Binance Spot WebSocket"]
        WS2["Binance Futures WebSocket"]
        REST["Binance REST API"]
    end

    subgraph MDS["Market Data Service"]
        CONN["连接管理器<br/>Connection Manager"]
        NORM["数据标准化<br/>Normalizer"]
        AGG["聚合引擎<br/>Aggregator"]
        SNAP["快照管理<br/>Snapshot Manager"]
        DIST["数据分发<br/>Distributor"]
    end

    subgraph Consumers["下游消费者"]
        KAFKA_OUT["Kafka Topics"]
        REDIS_OUT["Redis 快照"]
        QUEST_OUT["QuestDB 持久化"]
    end

    WS1 --> CONN
    WS2 --> CONN
    REST --> CONN
    CONN --> NORM
    NORM --> AGG
    AGG --> SNAP
    AGG --> DIST
    SNAP --> REDIS_OUT
    DIST --> KAFKA_OUT
    DIST --> QUEST_OUT

    style Sources fill:#e74c3c,stroke:#333,color:#fff
    style MDS fill:#3498db,stroke:#333,color:#fff
    style Consumers fill:#2ecc71,stroke:#333,color:#fff
```

#### 3.1.2 实时行情采集

**WebSocket 连接管理：**

```python
# 连接管理器核心设计
class ConnectionManager:
    """
    管理与 Binance 的 WebSocket 连接池。

    设计要点:
    - 每个连接最多订阅 200 个 stream（Binance 限制）
    - 自动重连: 指数退避 (1s → 2s → 4s → ... → 60s max)
    - 心跳检测: 每 30s 发送 pong，超过 90s 无响应则重连
    - 连接轮换: 每 23h 主动重建连接（Binance 24h 强制断开）
    """

    MAX_STREAMS_PER_CONN = 200
    HEARTBEAT_INTERVAL = 30  # seconds
    RECONNECT_MAX_DELAY = 60  # seconds
    CONNECTION_ROTATE_INTERVAL = 23 * 3600  # seconds
```

**订阅的数据流：**

| 数据类型 | Stream 名称 | 频率 | 用途 |
|---------|------------|------|------|
| 逐笔成交 | `{symbol}@trade` | 实时 | 成交价格、成交量追踪 |
| 深度数据 | `{symbol}@depth@100ms` | 100ms | 订单簿维护、流动性分析 |
| K 线 | `{symbol}@kline_{interval}` | 按周期 | 技术指标计算 |
| Ticker | `{symbol}@ticker` | 1s | 价格概览、涨跌幅 |
| 标记价格 | `{symbol}@markPrice` | 3s | 合约标记价格（仅期货） |

#### 3.1.3 历史数据管理

```python
class HistoricalDataManager:
    """
    历史数据拉取与管理。

    策略:
    - 首次部署: 批量拉取近 2 年 K 线数据（REST API，限速 1200 req/min）
    - 增量更新: 每分钟检查数据缺口，自动补全
    - 数据校验: 每日凌晨校验前一日数据完整性（K线连续性、成交量一致性）
    """

    SUPPORTED_INTERVALS = [
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "3d", "1w", "1M"
    ]

    # REST API 限速控制
    RATE_LIMIT = 1200  # requests per minute
    BATCH_SIZE = 1000  # max candles per request
```

#### 3.1.4 数据清洗与对齐

**清洗规则：**

| 规则 | 描述 | 处理方式 |
|------|------|---------|
| 时间戳对齐 | 将所有数据对齐到统一时间基准 | 线性插值或最近邻填充 |
| 异常值检测 | 价格偏离移动均线 > 5 个标准差 | 标记为异常，不参与策略计算 |
| 数据缺口 | 连续缺失超过 5 个周期 | 触发告警 + REST API 补全 |
| 重复数据 | 相同时间戳的重复推送 | 幂等处理，保留最新值 |
| 精度标准化 | 不同交易对的价格/数量精度不同 | 根据 exchangeInfo 统一精度处理 |

#### 3.1.5 数据分发机制

采用**扇出模式（Fan-out）**，一份原始数据分发到多个目的地：

```
原始行情 → Kafka (事件流，供策略引擎消费)
         → Redis (最新快照，供 API 查询)
         → QuestDB (持久化，供回测使用)
```

分发采用异步非阻塞写入，任何一个下游故障不影响其他下游。QuestDB 写入通过批量缓冲（每 100ms 或 1000 条刷盘一次）降低 I/O 压力。

---

### 3.2 策略引擎（Strategy Engine）

#### 3.2.1 策略生命周期

```mermaid
stateDiagram-v2
    [*] --> Draft: 创建策略
    Draft --> Backtesting: 提交回测
    Backtesting --> Reviewed: 回测通过
    Backtesting --> Draft: 回测失败，修改参数
    Reviewed --> PaperTrading: 部署模拟盘
    PaperTrading --> Reviewed: 模拟表现不达标
    PaperTrading --> Approved: 模拟盘验证通过 (≥24h)
    Approved --> Live: 上线实盘
    Live --> Paused: 手动暂停 / 风控触发
    Paused --> Live: 恢复运行
    Live --> Stopped: 策略下线
    Paused --> Stopped: 确认停止
    Stopped --> Draft: 重新修改
    Stopped --> [*]: 归档

    note right of Backtesting
        必须满足:
        - 夏普比率 > 1.5
        - 最大回撤 < 20%
        - 胜率 > 45%
    end note

    note right of PaperTrading
        必须满足:
        - 模拟运行 ≥ 24h
        - 与回测偏差 < 15%
        - 无异常订单
    end note
```

#### 3.2.2 策略抽象接口

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class SignalType(Enum):
    LONG_ENTRY = "long_entry"
    LONG_EXIT = "long_exit"
    SHORT_ENTRY = "short_entry"
    SHORT_EXIT = "short_exit"
    HOLD = "hold"

@dataclass
class Signal:
    signal_type: SignalType
    symbol: str
    price: float
    quantity: float
    confidence: float  # 0.0 ~ 1.0
    metadata: dict     # 策略特定的附加信息

class BaseStrategy(ABC):
    """所有策略的基类。"""

    @abstractmethod
    def on_init(self, context: StrategyContext) -> None:
        """策略初始化，加载参数、预热指标。"""
        ...

    @abstractmethod
    def on_bar(self, bar: Bar) -> list[Signal]:
        """K 线闭合时触发，返回交易信号列表。"""
        ...

    @abstractmethod
    def on_tick(self, tick: Tick) -> list[Signal]:
        """逐笔成交触发（高频策略使用）。"""
        ...

    @abstractmethod
    def on_order_filled(self, order: Order) -> None:
        """订单成交回调，更新策略内部状态。"""
        ...

    @abstractmethod
    def on_stop(self) -> None:
        """策略停止时清理资源。"""
        ...

    def get_parameters(self) -> dict:
        """返回策略可调参数及其范围，用于参数优化。"""
        return {}
```

#### 3.2.3 回测框架设计

```mermaid
graph TB
    subgraph BacktestFramework["回测框架"]
        DATA["历史数据加载<br/>QuestDB → DataFrame"]
        EVENT["事件引擎<br/>Event-Driven Simulation"]
        MATCH["撮合模拟器<br/>Matching Engine"]
        FEE["手续费模型<br/>Fee Model"]
        SLIP["滑点模型<br/>Slippage Model"]
        PERF["绩效分析<br/>Performance Analyzer"]
    end

    DATA --> EVENT
    EVENT -->|Bar/Tick 事件| STRATEGY["用户策略"]
    STRATEGY -->|交易信号| MATCH
    MATCH --> FEE
    FEE --> SLIP
    SLIP -->|模拟成交| EVENT
    EVENT -->|回测结束| PERF

    PERF --> REPORT["回测报告<br/>HTML + JSON"]

    style BacktestFramework fill:#3498db,stroke:#333,color:#fff
```

**撮合模拟器规则：**

| 订单类型 | 撮合逻辑 |
|---------|---------|
| 市价单 | 下一个 Bar 的开盘价 + 滑点 |
| 限价单 | Bar 的 High/Low 触及限价时成交 |
| 止损单 | Bar 的 High/Low 穿过止损价时按止损价成交 |

**滑点模型：**

```python
class SlippageModel:
    """
    基于成交量的滑点估算。

    slippage = base_slippage + volume_impact
    volume_impact = order_size / avg_volume * impact_factor
    """
    BASE_SLIPPAGE_BPS = 1.0   # 基础滑点: 1 bp (0.01%)
    IMPACT_FACTOR = 5.0        # 冲击因子
```

**绩效指标：**

| 指标 | 公式/说明 | 合格阈值 |
|------|---------|---------|
| 年化收益率 | CAGR | > 15% |
| 夏普比率 | (R_p - R_f) / σ_p | > 1.5 |
| 最大回撤 | Max Drawdown | < 20% |
| 索提诺比率 | (R_p - R_f) / σ_downside | > 2.0 |
| 胜率 | Winning Trades / Total Trades | > 45% |
| 盈亏比 | Avg Win / Avg Loss | > 1.5 |
| 卡尔玛比率 | CAGR / Max Drawdown | > 1.0 |

#### 3.2.4 实盘/模拟盘切换

通过**交易执行层的适配器模式**实现零代码切换：

```python
class ExecutionAdapter(ABC):
    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_position(self, symbol: str) -> Position: ...

class LiveExecutionAdapter(ExecutionAdapter):
    """实盘适配器：调用 Binance API。"""
    ...

class PaperExecutionAdapter(ExecutionAdapter):
    """模拟盘适配器：本地撮合，记录到数据库。"""
    ...
```

策略代码完全不感知当前是实盘还是模拟盘，由配置文件控制：

```yaml
# strategy-config.yaml
strategy:
  id: "momentum_btc_001"
  mode: "paper"  # "paper" | "live"
  execution:
    paper:
      initial_balance: 10000  # USDT
      fee_rate: 0.001         # 0.1%
    live:
      api_key_ref: "binance-main"
      max_position_pct: 0.3   # 单策略最大仓位占比
```

#### 3.2.5 策略参数优化

```python
class ParameterOptimizer:
    """
    多目标参数优化器。

    支持的优化方法:
    - Grid Search: 穷举，适合参数空间小 (< 1000 组合)
    - Random Search: 随机采样，适合高维参数空间
    - Bayesian Optimization (Optuna): 智能搜索，适合耗时长的回测
    - Walk-Forward Analysis: 滚动窗口优化，防止过拟合

    防过拟合措施:
    - 样本内/样本外分离 (70%/30%)
    - Walk-Forward 滚动验证
    - 参数稳定性检验（相邻参数组合绩效方差 < 阈值）
    - 最小交易次数要求 (> 100 笔)
    """

    OPTIMIZATION_METHODS = ["grid", "random", "bayesian", "walk_forward"]
    IN_SAMPLE_RATIO = 0.7
    MIN_TRADES = 100
```

---

### 3.3 订单管理系统（OMS）

#### 3.3.1 订单路由

```mermaid
graph TB
    SIG["交易信号<br/>from Strategy Engine"] --> RISK_CHECK["风控前置检查"]
    RISK_CHECK -->|通过| ROUTER["订单路由器"]
    RISK_CHECK -->|拒绝| REJECT["拒绝 + 告警"]

    ROUTER --> SPLIT{"订单拆分判断"}
    SPLIT -->|小单| DIRECT["直接下单"]
    SPLIT -->|大单| TWAP["TWAP 拆单"]
    SPLIT -->|大单| ICEBERG["冰山委托"]

    DIRECT --> BINANCE["Binance API"]
    TWAP --> BINANCE
    ICEBERG --> BINANCE

    BINANCE --> ACK["订单确认<br/>Order ACK"]

    style SIG fill:#3498db,stroke:#333,color:#fff
    style RISK_CHECK fill:#e74c3c,stroke:#333,color:#fff
    style ROUTER fill:#2ecc71,stroke:#333,color:#fff
```

**智能订单拆分规则：**

| 条件 | 策略 | 描述 |
|------|------|------|
| 订单量 < 平均成交量 1% | 直接下单 | 对市场冲击可忽略 |
| 订单量 1% ~ 5% 平均成交量 | TWAP | 按时间均匀拆分，每 30s 一笔 |
| 订单量 > 5% 平均成交量 | 冰山委托 | 每笔展示量为总量的 10%，间隔随机 |

#### 3.3.2 订单状态机

```mermaid
stateDiagram-v2
    [*] --> PendingRisk: 策略下单
    PendingRisk --> PendingNew: 风控通过
    PendingRisk --> Rejected: 风控拒绝
    PendingNew --> New: API 提交成功
    PendingNew --> Failed: API 提交失败
    New --> PartiallyFilled: 部分成交
    New --> Filled: 完全成交
    New --> Cancelled: 用户取消
    New --> Expired: 超时未成交
    PartiallyFilled --> Filled: 剩余部分成交
    PartiallyFilled --> PartialCancelled: 取消剩余
    Failed --> PendingNew: 自动重试 (≤3次)
    Rejected --> [*]
    Filled --> [*]
    Cancelled --> [*]
    Expired --> [*]
    PartialCancelled --> [*]
    Failed --> [*]: 重试耗尽
```

#### 3.3.3 成交撮合确认

```python
class ExecutionConfirmer:
    """
    成交确认机制，确保订单状态与交易所一致。

    三重确认:
    1. WebSocket User Data Stream: 实时推送成交事件（主通道）
    2. REST API 轮询: 每 5s 查询未确认订单（备用通道）
    3. 定时对账: 每 10min 全量对账一次（兜底机制）

    不一致处理:
    - 本地已成交但交易所未确认 → 等待 30s 后标记为 "需人工确认"
    - 本地未成交但交易所已成交 → 立即同步状态，补录成交记录
    - 数量不一致 → 触发告警，暂停相关策略
    """

    POLL_INTERVAL = 5          # seconds
    RECONCILE_INTERVAL = 600   # seconds (10min)
    CONFIRM_TIMEOUT = 30       # seconds
```

#### 3.3.4 滑点监控

```python
@dataclass
class SlippageReport:
    order_id: str
    symbol: str
    expected_price: float      # 信号价格
    actual_price: float        # 实际成交均价
    slippage_bps: float        # 滑点 (basis points)
    market_impact_bps: float   # 市场冲击
    timing_cost_bps: float     # 时机成本

class SlippageMonitor:
    """
    实时滑点监控与分析。

    告警阈值:
    - 单笔滑点 > 10 bps → WARNING
    - 单笔滑点 > 30 bps → CRITICAL，暂停策略
    - 1h 平均滑点 > 5 bps → 建议调整执行策略
    """

    WARNING_THRESHOLD_BPS = 10
    CRITICAL_THRESHOLD_BPS = 30
    HOURLY_AVG_THRESHOLD_BPS = 5
```

---

### 3.4 风控系统（Risk Management）

#### 3.4.1 风控架构

```mermaid
graph TB
    subgraph PreTrade["交易前风控"]
        PT1["仓位限制检查"]
        PT2["订单频率限制"]
        PT3["单笔金额限制"]
        PT4["保证金充足性"]
        PT5["黑名单检查"]
    end

    subgraph InTrade["交易中风控"]
        IT1["实时 PnL 监控"]
        IT2["持仓集中度监控"]
        IT3["杠杆率监控"]
        IT4["回撤实时追踪"]
    end

    subgraph PostTrade["交易后风控"]
        PO1["日终对账"]
        PO2["绩效归因分析"]
        PO3["风险指标汇报"]
    end

    subgraph CircuitBreaker["熔断机制"]
        CB1["策略级熔断"]
        CB2["账户级熔断"]
        CB3["系统级熔断"]
    end

    SIGNAL["交易信号"] --> PreTrade
    PreTrade -->|通过| OMS["订单管理系统"]
    PreTrade -->|拒绝| BLOCK["拦截 + 记录"]

    OMS --> InTrade
    InTrade -->|异常| CircuitBreaker
    CircuitBreaker -->|触发| HALT["暂停交易 + 告警"]

    InTrade -->|日终| PostTrade

    style PreTrade fill:#2ecc71,stroke:#333,color:#fff
    style InTrade fill:#f39c12,stroke:#333,color:#fff
    style PostTrade fill:#3498db,stroke:#333,color:#fff
    style CircuitBreaker fill:#e74c3c,stroke:#333,color:#fff
```

#### 3.4.2 实时 PnL 计算

```python
class RealTimePnLCalculator:
    """
    实时逐笔 PnL 计算引擎（Go 实现，此处用 Python 描述逻辑）。

    计算维度:
    - 已实现盈亏 (Realized PnL): 已平仓部分
    - 未实现盈亏 (Unrealized PnL): 按最新标记价格计算
    - 手续费消耗 (Fee Cost): 累计手续费
    - 资金费率 (Funding Cost): 仅期货，每 8h 结算

    更新频率: 每次成交事件 + 每秒行情更新
    """

    def calculate_unrealized_pnl(
        self, position: Position, mark_price: float
    ) -> float:
        if position.side == "LONG":
            return (mark_price - position.entry_price) * position.quantity
        else:
            return (position.entry_price - mark_price) * position.quantity
```

#### 3.4.3 仓位管理

| 限制维度 | 参数 | 默认值 | 说明 |
|---------|------|--------|------|
| 单策略最大仓位 | `max_position_per_strategy` | 30% | 占总资金比例 |
| 单交易对最大仓位 | `max_position_per_symbol` | 20% | 防止单一资产集中风险 |
| 总仓位上限 | `max_total_position` | 80% | 保留 20% 现金缓冲 |
| 单笔最大下单量 | `max_order_size` | 5% | 占可用余额比例 |
| 日内最大交易次数 | `max_daily_trades` | 500 | 防止策略失控 |
| 最大同时持仓数 | `max_concurrent_positions` | 10 | 分散风险 |

#### 3.4.4 止损/止盈逻辑

```python
class StopLossManager:
    """
    多层级止损/止盈管理。

    止损类型:
    1. 固定止损 (Fixed Stop): 入场价 - N%
    2. 追踪止损 (Trailing Stop): 最高价 - N%，只上不下
    3. ATR 止损: 入场价 - N * ATR(14)
    4. 时间止损: 持仓超过 T 小时未盈利则平仓
    5. 波动率止损: 当波动率突然放大 > 2x 均值时平仓

    止盈类型:
    1. 固定止盈: 入场价 + N%
    2. 分批止盈: 50% 仓位在 +2%, 30% 在 +5%, 20% 在 +10%
    3. 指标止盈: RSI > 80 / MACD 死叉时平仓
    """
```

#### 3.4.5 熔断机制

```python
class CircuitBreaker:
    """
    三级熔断机制。

    Level 1 - 策略级熔断:
      触发: 策略日内亏损 > 3% 或连续亏损 5 笔
      动作: 暂停该策略 30min，通知策略负责人
      恢复: 自动恢复 或 人工确认

    Level 2 - 账户级熔断:
      触发: 账户日内总亏损 > 5% 或单笔亏损 > 2%
      动作: 暂停所有策略，平掉所有非对冲仓位
      恢复: 需人工确认后恢复

    Level 3 - 系统级熔断:
      触发: 市场闪崩(BTC 5min 跌幅 > 10%) / API 异常 / 网络中断
      动作: 全系统停机，市价平掉所有仓位
      恢复: 需管理员手动恢复
    """

    STRATEGY_DAILY_LOSS_LIMIT = 0.03    # 3%
    STRATEGY_CONSECUTIVE_LOSS = 5
    ACCOUNT_DAILY_LOSS_LIMIT = 0.05     # 5%
    ACCOUNT_SINGLE_LOSS_LIMIT = 0.02    # 2%
    MARKET_CRASH_THRESHOLD = 0.10       # 10% in 5min
```

---

### 3.5 监控与告警

#### 3.5.1 监控架构

```mermaid
graph TB
    subgraph DataSources["数据源"]
        APP["应用指标<br/>Prometheus Client"]
        SYS["系统指标<br/>Node Exporter"]
        DB_MON["数据库指标<br/>pg_exporter / Redis"]
        KAFKA_MON["Kafka 指标<br/>JMX Exporter"]
    end

    subgraph MonitorStack["监控栈"]
        PROM["Prometheus<br/>指标存储 & 查询"]
        GRAF["Grafana<br/>可视化仪表盘"]
        ALERT_MGR["Alertmanager<br/>告警路由"]
        LOKI["Loki<br/>日志聚合"]
    end

    subgraph AlertChannels["告警通道"]
        FEISHU["飞书机器人<br/>日常告警"]
        TG["Telegram Bot<br/>交易告警"]
        PHONE["电话告警<br/>P0 级别"]
    end

    APP --> PROM
    SYS --> PROM
    DB_MON --> PROM
    KAFKA_MON --> PROM
    PROM --> GRAF
    PROM --> ALERT_MGR
    ALERT_MGR --> FEISHU
    ALERT_MGR --> TG
    ALERT_MGR --> PHONE

    APP -->|日志| LOKI
    LOKI --> GRAF

    style DataSources fill:#3498db,stroke:#333,color:#fff
    style MonitorStack fill:#9b59b6,stroke:#333,color:#fff
    style AlertChannels fill:#e74c3c,stroke:#333,color:#fff
```

#### 3.5.2 关键监控指标

**业务指标：**

| 指标名称 | 类型 | 标签 | 告警阈值 |
|---------|------|------|---------|
| `trading_pnl_total` | Gauge | strategy, symbol | 日亏损 > 3% |
| `trading_position_value` | Gauge | strategy, symbol | > 仓位上限 |
| `trading_order_latency_ms` | Histogram | type, symbol | P99 > 500ms |
| `trading_signal_count` | Counter | strategy, signal_type | 1min > 100 |
| `trading_fill_rate` | Gauge | strategy | < 80% |
| `trading_slippage_bps` | Histogram | strategy, symbol | P95 > 10bps |

**系统指标：**

| 指标名称 | 类型 | 告警阈值 |
|---------|------|---------|
| `market_data_lag_ms` | Gauge | > 1000ms |
| `kafka_consumer_lag` | Gauge | > 10000 messages |
| `api_error_rate` | Gauge | > 1% (5min) |
| `websocket_reconnect_count` | Counter | > 5 (1h) |
| `system_cpu_usage` | Gauge | > 80% |
| `system_memory_usage` | Gauge | > 85% |

#### 3.5.3 告警分级

| 级别 | 响应时间 | 通知方式 | 示例场景 |
|------|---------|---------|---------|
| **P0 - 致命** | 立即 | 电话 + 飞书 + Telegram | 系统级熔断、API 密钥失效、资金异常 |
| **P1 - 严重** | 5min | 飞书 + Telegram | 策略级熔断、网络中断 > 30s、数据缺口 |
| **P2 - 警告** | 30min | 飞书 | 滑点异常、延迟升高、磁盘 > 80% |
| **P3 - 信息** | 下一工作日 | 飞书（静默通道） | 策略绩效日报、系统健康周报 |

#### 3.5.4 交易日志审计

```python
@dataclass
class AuditLog:
    """
    每笔交易完整审计记录。

    存储: PostgreSQL (交易表) + S3 (JSON 归档)
    保留期: 在线 90 天，归档 5 年
    """
    timestamp: datetime
    event_type: str          # signal | order | fill | cancel | risk_check
    strategy_id: str
    symbol: str
    direction: str
    price: float
    quantity: float
    order_id: str | None
    risk_check_result: dict  # 风控检查详情
    latency_ms: float        # 处理延迟
    metadata: dict           # 完整上下文快照
```

#### 3.5.5 Grafana 仪表盘规划

| 仪表盘 | 内容 | 刷新频率 |
|--------|------|---------|
| Trading Overview | 总 PnL、活跃策略数、持仓概览、资金利用率 | 5s |
| Strategy Performance | 各策略夏普、收益曲线、信号分布 | 30s |
| Execution Quality | 订单延迟、滑点分布、成交率 | 10s |
| Market Data Health | 数据延迟、连接状态、消息吞吐 | 5s |
| System Resources | CPU/内存/磁盘/网络、Kafka Lag | 15s |
| Risk Dashboard | 仓位热力图、回撤实时曲线、熔断状态 | 5s |

---

## 4. 部署架构

### 4.1 低延迟部署

#### 4.1.1 云服务器选型

```mermaid
graph TB
    subgraph UserLocation["运维人员"]
        OPS["国内运维<br/>监控 & 管理"]
    end

    subgraph Cloud["云服务器 (AWS ap-northeast-1)"]
        direction TB
        NOTE["选择东京区域的原因:<br/>- 距离 Binance 服务器最近 (~2ms RTT)<br/>- AWS Direct Connect 可用<br/>- 合规要求相对宽松"]

        subgraph Primary["主集群"]
            APP_PRIMARY["应用服务器<br/>c6i.2xlarge x3<br/>8 vCPU, 16GB RAM"]
            DB_PRIMARY["数据库服务器<br/>r6i.xlarge x2<br/>4 vCPU, 32GB RAM"]
        end

        subgraph Standby["备用集群"]
            APP_STANDBY["应用服务器<br/>c6i.xlarge x2<br/>(冷备)"]
            DB_STANDBY["数据库 Replica<br/>r6i.large x1<br/>(温备)"]
        end
    end

    subgraph BinanceInfra["Binance 基础设施"]
        BINANCE_API["Binance API Gateway<br/>ap-northeast-1"]
    end

    OPS -->|VPN| Cloud
    APP_PRIMARY -->|<2ms| BINANCE_API
    DB_PRIMARY -->|流复制| DB_STANDBY
    APP_PRIMARY -->|Health Check| APP_STANDBY

    style Cloud fill:#ff9900,stroke:#333,color:#fff
    style BinanceInfra fill:#f3ba2f,stroke:#333,color:#333
```

**服务器规格推荐（按阶段）：**

| 阶段 | 应用服务器 | 数据库服务器 | 月成本估算 |
|------|-----------|-----------|-----------|
| MVP (1-3 策略) | c6i.xlarge x1 | r6i.large x1 | ~$300/月 |
| 成长期 (10+ 策略) | c6i.2xlarge x2 | r6i.xlarge x1 | ~$800/月 |
| 规模化 (50+ 策略) | c6i.2xlarge x3 + 备用 | r6i.xlarge x2 | ~$2000/月 |

#### 4.1.2 延迟优化

| 优化项 | 措施 | 预期效果 |
|--------|------|---------|
| 网络 | 选择 AWS Tokyo（ap-northeast-1），与 Binance 服务器同区域 | RTT < 2ms |
| OS | 内核参数调优（tcp_nodelay, tcp_quickack, 减少 buffer bloat） | -0.5ms |
| 应用 | 连接池预热、DNS 缓存、HTTP/2 复用 | -1ms |
| 序列化 | 关键路径使用 MessagePack 替代 JSON | -0.2ms |
| GC | Go 服务调优 GOGC、Python 关键路径使用 Cython | 避免 GC 停顿 |

**目标延迟指标（信号 → 订单提交）：**

| 路径 | 目标 | 说明 |
|------|------|------|
| 信号生成 → 风控检查 | < 1ms | 进程内调用 |
| 风控通过 → API 提交 | < 2ms | 预建立连接 |
| API 提交 → Binance ACK | < 5ms | 取决于网络 |
| 全链路 E2E | < 10ms | P99 |

### 4.2 高可用设计

```mermaid
graph TB
    subgraph HADesign["高可用架构"]
        LB["负载均衡<br/>Nginx / ALB"]

        subgraph Active["主节点集群"]
            A1["App Node 1<br/>(Leader)"]
            A2["App Node 2<br/>(Follower)"]
        end

        subgraph Standby["备用节点"]
            S1["App Node 3<br/>(Cold Standby)"]
        end

        subgraph DBCluster["数据库集群"]
            PG_M["PostgreSQL<br/>Primary"]
            PG_R["PostgreSQL<br/>Replica"]
            REDIS_M["Redis Primary"]
            REDIS_R["Redis Replica"]
        end

        LEADER["Leader Election<br/>(etcd / Redis Lock)"]
    end

    LB --> A1
    LB --> A2
    A1 <-->|Leader 选举| LEADER
    A2 <-->|Leader 选举| LEADER
    LEADER -.->|故障切换| S1

    A1 --> PG_M
    A2 --> PG_R
    PG_M -->|流复制| PG_R
    REDIS_M -->|同步| REDIS_R

    style HADesign fill:#2c3e50,stroke:#333,color:#fff
    style Active fill:#27ae60,stroke:#333,color:#fff
    style Standby fill:#95a5a6,stroke:#333,color:#fff
    style DBCluster fill:#2980b9,stroke:#333,color:#fff
```

**高可用策略：**

| 组件 | 主备模式 | RTO | RPO | 切换方式 |
|------|---------|-----|-----|---------|
| 交易执行服务 | Active-Standby | < 10s | 0 | Leader 选举自动切换 |
| 策略引擎 | Active-Active | < 5s | 0 | 负载均衡自动剔除 |
| 市场数据服务 | Active-Active | < 3s | 0 | 双活，任一可独立运行 |
| PostgreSQL | Primary-Replica | < 30s | < 1s | 自动 Failover (Patroni) |
| Redis | Master-Slave | < 10s | < 1s | Sentinel 自动切换 |
| Kafka | ISR 副本 | < 5s | 0 | 自动 Leader 选举 |

**故障场景与预案：**

| 故障场景 | 检测方式 | 自动处理 | 人工介入 |
|---------|---------|---------|---------|
| 单节点宕机 | Health Check (3s) | 自动剔除 + 流量切换 | 排查原因 |
| 数据库主库不可用 | Patroni 监控 | 自动 Failover | 确认数据一致性 |
| Binance API 不可达 | 连续 3 次 timeout | 暂停下单，持仓不动 | 检查网络/IP 限制 |
| 全区域故障 | 外部探测 | 切换到备用区域 | 启动灾备流程 |
| 资金异常 | PnL 实时校验 | 系统级熔断 | 人工核实账户状态 |

### 4.3 网络优化

```
运维人员 (国内)
    |
    | WireGuard VPN (加密隧道)
    |
    v
AWS Tokyo (ap-northeast-1) ←→ Binance API
    |                           ^
    | 内网通信 (< 0.5ms)        | < 2ms RTT
    |                           |
    v                           |
应用服务器 ──── 数据库集群      |
    |                           |
    └── WebSocket 长连接 ───────┘
        (保持 5 条并发连接)
```

**网络层优化：**

| 策略 | 实施方式 | 效果 |
|------|---------|------|
| 就近部署 | AWS Tokyo，与 Binance 同区域 | RTT < 2ms |
| 连接复用 | WebSocket 长连接池，预建立 5 条 | 避免连接建立延迟 |
| DNS 优化 | 本地 DNS 缓存 + Binance IP 直连 | 消除 DNS 解析时间 |
| TCP 调优 | `TCP_NODELAY`、减小 socket buffer | 减少 Nagle 延迟 |
| 运维通道 | WireGuard VPN 从国内访问 | 安全的远程管理 |
| 备用通道 | 多 ISP 出口（主: AWS、备: 本地 IDC） | 网络故障时快速切换 |

---

## 5. 数据流图

### 5.1 完整数据流向

```mermaid
graph TB
    subgraph ExternalData["外部数据源"]
        BN_WS["Binance WebSocket<br/>实时行情"]
        BN_REST["Binance REST API<br/>历史数据"]
        BN_USER["Binance User Stream<br/>账户 & 订单"]
    end

    subgraph Ingestion["数据采集层"]
        WS_CONN["WebSocket<br/>连接管理器"]
        REST_PULL["REST<br/>数据拉取器"]
        USER_STREAM["User Stream<br/>监听器"]
        NORMALIZER["数据标准化器"]
    end

    subgraph MessageBus["消息总线 (Kafka)"]
        T_MARKET["Topic: market.*<br/>行情数据"]
        T_SIGNAL["Topic: signal.*<br/>交易信号"]
        T_ORDER["Topic: order.*<br/>订单事件"]
        T_EXEC["Topic: execution.*<br/>成交事件"]
        T_RISK["Topic: risk.alert<br/>风控告警"]
    end

    subgraph Processing["处理层"]
        STRATEGY["策略引擎<br/>(Python)"]
        RISK_ENGINE["风控引擎<br/>(Go)"]
        OMS_ENGINE["OMS<br/>(Go)"]
        PNL_CALC["PnL 计算器<br/>(Go)"]
    end

    subgraph Persistence["持久化层"]
        QUESTDB["QuestDB<br/>时序数据"]
        POSTGRES["PostgreSQL<br/>业务数据"]
        REDIS["Redis<br/>实时缓存"]
    end

    subgraph Presentation["展示层"]
        DASHBOARD["Web Dashboard<br/>(TypeScript + React)"]
        GRAFANA["Grafana<br/>监控面板"]
        IM_BOT["IM 告警<br/>飞书 / Telegram"]
    end

    %% 数据采集
    BN_WS -->|实时推送| WS_CONN
    BN_REST -->|批量拉取| REST_PULL
    BN_USER -->|账户更新| USER_STREAM
    WS_CONN --> NORMALIZER
    REST_PULL --> NORMALIZER

    %% 消息分发
    NORMALIZER -->|发布| T_MARKET
    NORMALIZER -->|写入| QUESTDB
    NORMALIZER -->|快照| REDIS

    %% 策略处理
    T_MARKET -->|消费| STRATEGY
    STRATEGY -->|发布信号| T_SIGNAL
    T_SIGNAL -->|消费| RISK_ENGINE
    RISK_ENGINE -->|通过| T_ORDER
    RISK_ENGINE -->|拒绝| T_RISK

    %% 订单执行
    T_ORDER -->|消费| OMS_ENGINE
    OMS_ENGINE -->|API 调用| BN_REST
    USER_STREAM -->|成交回报| T_EXEC
    T_EXEC -->|消费| PNL_CALC
    T_EXEC -->|消费| STRATEGY

    %% 持久化
    T_ORDER -->|消费| POSTGRES
    T_EXEC -->|消费| POSTGRES
    PNL_CALC -->|写入| POSTGRES
    PNL_CALC -->|写入| REDIS

    %% 告警
    T_RISK -->|消费| IM_BOT
    T_RISK -->|消费| GRAFANA

    %% 展示
    REDIS -->|读取| DASHBOARD
    POSTGRES -->|读取| DASHBOARD
    QUESTDB -->|查询| GRAFANA

    style ExternalData fill:#f3ba2f,stroke:#333,color:#333
    style Ingestion fill:#4ecdc4,stroke:#333,color:#fff
    style MessageBus fill:#e74c3c,stroke:#333,color:#fff
    style Processing fill:#3498db,stroke:#333,color:#fff
    style Persistence fill:#9b59b6,stroke:#333,color:#fff
    style Presentation fill:#2ecc71,stroke:#333,color:#fff
```

### 5.2 订单执行数据流（详细）

```mermaid
sequenceDiagram
    participant SE as 策略引擎
    participant RM as 风控引擎
    participant OMS as 订单管理
    participant BN as Binance API
    participant US as User Stream
    participant PNL as PnL 计算
    participant DB as PostgreSQL
    participant CACHE as Redis
    participant MON as 监控告警

    SE->>RM: 交易信号 (symbol, side, qty, price)

    Note over RM: 交易前风控检查
    RM->>RM: 1. 仓位限制
    RM->>RM: 2. 订单频率
    RM->>RM: 3. 资金充足性

    alt 风控通过
        RM->>OMS: 下单指令
        OMS->>DB: 记录订单 (PENDING_NEW)
        OMS->>CACHE: 缓存订单状态
        OMS->>BN: POST /api/v3/order

        BN-->>OMS: Order ACK (orderId)
        OMS->>DB: 更新订单 (NEW)

        US-->>OMS: Execution Report (FILLED)
        OMS->>DB: 更新订单 (FILLED)
        OMS->>PNL: 成交事件
        OMS->>SE: on_order_filled 回调

        PNL->>PNL: 计算已实现/未实现 PnL
        PNL->>DB: 写入 PnL 记录
        PNL->>CACHE: 更新实时 PnL
        PNL->>MON: 推送 PnL 指标

    else 风控拒绝
        RM->>DB: 记录拒绝原因
        RM->>MON: 风控告警
        RM->>SE: 信号被拒绝回调
    end
```

### 5.3 市场数据流（详细）

```mermaid
sequenceDiagram
    participant BN as Binance WebSocket
    participant CM as 连接管理器
    participant NM as 标准化器
    participant KF as Kafka
    participant QDB as QuestDB
    participant RD as Redis
    participant SE as 策略引擎

    BN->>CM: WebSocket 帧 (raw JSON)

    Note over CM: 连接管理
    CM->>CM: 1. 消息去重
    CM->>CM: 2. 序列号校验
    CM->>CM: 3. 心跳检测

    CM->>NM: 原始市场数据

    Note over NM: 数据标准化
    NM->>NM: 1. 时间戳对齐 (UTC)
    NM->>NM: 2. 精度标准化
    NM->>NM: 3. 异常值过滤

    par 并行写入
        NM->>KF: 发布到 market.{symbol}.{type}
        NM->>QDB: 批量写入 (100ms buffer)
        NM->>RD: 更新最新快照
    end

    KF->>SE: 消费行情事件
    SE->>SE: 更新指标 → 生成信号
```

---

## 附录

### A. 关键技术依赖

| 组件 | 版本 | License |
|------|------|---------|
| Python | 3.12+ | PSF |
| Go | 1.22+ | BSD-3 |
| Apache Kafka | 3.7+ | Apache-2.0 |
| QuestDB | 8.0+ | Apache-2.0 |
| PostgreSQL | 16+ | PostgreSQL License |
| Redis | 7.2+ | RSALv2 / SSPLv1 |
| Kubernetes | 1.29+ | Apache-2.0 |
| Prometheus | 2.50+ | Apache-2.0 |
| Grafana | 11+ | AGPL-3.0 |

### B. 名词对照

| 缩写 | 全称 | 中文 |
|------|------|------|
| OMS | Order Management System | 订单管理系统 |
| PnL | Profit and Loss | 盈亏 |
| RTT | Round-Trip Time | 往返延迟 |
| RTO | Recovery Time Objective | 恢复时间目标 |
| RPO | Recovery Point Objective | 恢复点目标 |
| TWAP | Time-Weighted Average Price | 时间加权平均价格 |
| ATR | Average True Range | 平均真实波幅 |
| ISR | In-Sync Replicas | 同步副本集 |
| bps | Basis Points | 基点 (0.01%) |

### C. 参考文档

- [Binance API Documentation](https://binance-docs.github.io/apidocs/)
- [Binance WebSocket Streams](https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams)
- [QuestDB Documentation](https://questdb.io/docs/)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)

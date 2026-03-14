# 风控与资金管理方案

> 本文档定义币安量化交易系统的资金管理体系、风险控制机制、监控告警设计及合规安全要求。
> 所有参数均为建议值，需根据实际资金规模、策略特性和风险偏好进行校准。

---

## 1. 资金管理体系

### 1.1 账户资金分配策略

采用三层资金池架构，实现风险隔离与动态调配：

```
总资金 (Total Capital)
├── 策略运营池 (Strategy Pool)        70%
│   ├── 趋势跟踪策略组              30%
│   ├── 均值回归策略组              20%
│   └── 高频/套利策略组             20%
├── 风险储备金 (Risk Reserve)        20%
│   ├── 追加保证金储备              10%
│   └── 极端行情缓冲               10%
└── 冷储备 (Cold Reserve)           10%
    └── 链下冷钱包，仅人工审批动用
```

**分配原则：**

| 原则 | 说明 |
|------|------|
| 策略间隔离 | 每个策略组使用独立子账户（Binance Sub-account），亏损不互相传染 |
| 单策略资金上限 | 任何单一策略不得超过总资金的 15% |
| 储备金触发线 | 风险储备金低于总资金 10% 时，自动缩减策略仓位至半仓 |
| 季度再平衡 | 每季度根据策略绩效重新分配资金池比例 |

### 1.2 Kelly 公式实战应用

Kelly 公式用于确定最优下注比例，最大化长期资本增长率：

```
f* = (p * b - q) / b

其中：
  f* = 最优仓位比例
  p  = 历史胜率
  q  = 1 - p（败率）
  b  = 盈亏比（平均盈利 / 平均亏损）
```

**实战调整：**

1. **Half-Kelly 原则**：实际使用 f*/2 作为仓位比例，降低波动性
2. **滑动窗口估算**：使用最近 200 笔交易计算 p 和 b，而非全历史
3. **置信区间修正**：当样本量 < 50 笔时，额外打折 30%
4. **上限约束**：无论 Kelly 计算结果如何，单笔仓位不超过总资金 5%

```python
class KellyCalculator:
    """Kelly 仓位计算器"""

    def __init__(self, lookback: int = 200, confidence_min_trades: int = 50):
        self.lookback = lookback
        self.confidence_min_trades = confidence_min_trades

    def calculate(self, trades: list[TradeResult]) -> float:
        recent = trades[-self.lookback:]
        if len(recent) < 20:
            return 0.0  # 样本不足，不开仓

        wins = [t for t in recent if t.pnl > 0]
        losses = [t for t in recent if t.pnl <= 0]

        if not losses:
            return 0.02  # 无亏损记录时保守开仓

        p = len(wins) / len(recent)
        avg_win = sum(t.pnl for t in wins) / len(wins)
        avg_loss = abs(sum(t.pnl for t in losses) / len(losses))
        b = avg_win / avg_loss

        kelly = (p * b - (1 - p)) / b
        kelly = max(kelly, 0.0)

        # Half-Kelly
        kelly *= 0.5

        # 低样本置信修正
        if len(recent) < self.confidence_min_trades:
            kelly *= 0.7

        # 硬上限
        return min(kelly, 0.05)
```

### 1.3 固定比例风险模型

每笔交易风险固定为账户净值的 N%：

```
仓位大小 = (账户净值 * 风险比例) / (入场价 - 止损价)

示例：
  账户净值 = 100,000 USDT
  风险比例 = 1%（每笔最多亏损 1,000 USDT）
  BTC 入场价 = 60,000
  止损价 = 58,500（2.5% 止损）
  仓位 = 1,000 / (60,000 - 58,500) = 0.667 BTC
```

**风险比例分级：**

| 策略类型 | 单笔风险比例 | 说明 |
|---------|------------|------|
| 高频/套利 | 0.1% - 0.3% | 高频次、低单笔风险 |
| 趋势跟踪 | 0.5% - 1.0% | 中等频次、中等风险 |
| 均值回归 | 0.3% - 0.5% | 止损较窄、控制回撤 |
| 事件驱动 | 0.5% - 1.5% | 低频次、可承受较高单笔风险 |

### 1.4 动态仓位调整

根据账户状态和市场环境动态调节仓位倍数：

```python
class DynamicPositionScaler:
    """动态仓位调整器"""

    def compute_scale_factor(self, context: TradingContext) -> float:
        """计算仓位缩放因子，范围 [0.0, 1.5]"""
        factors = []

        # 因子1: 账户回撤程度（回撤越大，仓位越小）
        drawdown = context.current_drawdown  # 当前回撤比例 0~1
        if drawdown > 0.15:
            factors.append(0.0)   # 回撤超 15%，停止开新仓
        elif drawdown > 0.10:
            factors.append(0.3)
        elif drawdown > 0.05:
            factors.append(0.6)
        else:
            factors.append(1.0)

        # 因子2: 近期盈利状态（连续盈利可适度加仓）
        if context.recent_win_streak >= 5:
            factors.append(1.2)
        elif context.recent_loss_streak >= 3:
            factors.append(0.5)
        else:
            factors.append(1.0)

        # 因子3: 市场波动率（VIX 类指标）
        vol_ratio = context.current_vol / context.avg_vol_30d
        if vol_ratio > 2.0:
            factors.append(0.5)   # 波动率异常放大，减仓
        elif vol_ratio > 1.5:
            factors.append(0.7)
        elif vol_ratio < 0.5:
            factors.append(0.8)   # 波动率过低，可能为暴风雨前夜
        else:
            factors.append(1.0)

        # 综合：取所有因子的乘积
        scale = 1.0
        for f in factors:
            scale *= f

        return max(0.0, min(scale, 1.5))
```

**回撤-仓位映射表：**

| 当前回撤 | 仓位缩放 | 操作 |
|---------|---------|------|
| < 5% | 100% | 正常运行 |
| 5% - 10% | 60% | 减仓，停止新策略上线 |
| 10% - 15% | 30% | 仅保留最稳健策略 |
| > 15% | 0% | 全面停止开新仓，人工介入审查 |
| > 20% | 强制平仓 | 全部策略平仓，系统熔断 |

---

## 2. 风险控制体系

### 2.1 单策略风控

#### 2.1.1 止损机制

采用多层止损，取最先触发者：

| 止损类型 | 逻辑 | 适用场景 |
|---------|------|---------|
| 固定百分比止损 | 入场价的 N%（趋势策略 2-5%，均值回归 1-2%） | 所有策略 |
| ATR 追踪止损 | 最高价 - N * ATR(14)，随价格上移 | 趋势跟踪 |
| 时间止损 | 持仓超过 T 小时未达预期，平仓 | 短线策略 |
| 波动率止损 | 当 15min 波动率突然放大 3x，立即止损 | 高频策略 |
| 总亏损止损 | 单策略当日亏损超过日度预算，当日暂停 | 所有策略 |

```python
@dataclass
class StopLossConfig:
    # 固定止损
    fixed_pct: float = 0.02          # 2% 固定止损
    # ATR 追踪止损
    atr_multiplier: float = 2.5
    atr_period: int = 14
    # 时间止损
    max_holding_hours: float = 48.0
    # 波动率止损
    vol_spike_threshold: float = 3.0
    # 日度亏损上限
    daily_loss_limit_pct: float = 0.03  # 单策略日亏损不超过分配资金的 3%
```

#### 2.1.2 止盈机制

| 止盈类型 | 逻辑 |
|---------|------|
| 固定目标止盈 | 达到盈亏比目标（如 2:1）后平仓 |
| 分批止盈 | 目标1 平 50%，目标2 平 30%，剩余 20% 追踪止损 |
| ATR 追踪止盈 | 利润回撤超过 1.5 * ATR 时平仓 |
| 信号反转止盈 | 策略信号转向时平仓 |

#### 2.1.3 持仓时间限制

| 策略类型 | 最大持仓时间 | 超时处理 |
|---------|------------|---------|
| 高频/scalping | 15 分钟 | 市价平仓 |
| 日内交易 | 24 小时 | 市价平仓 |
| 趋势跟踪 | 7 天 | 触发信号审查，可人工延期 |
| 套利 | 1 小时 | 市价平仓两腿 |

### 2.2 组合层面风控

#### 2.2.1 总敞口控制

```python
class PortfolioRiskManager:
    """组合层面风控管理器"""

    # 总敞口限制
    MAX_GROSS_EXPOSURE = 3.0     # 总杠杆不超过 3x
    MAX_NET_EXPOSURE = 1.5       # 净敞口不超过 1.5x
    MAX_SINGLE_ASSET = 0.25      # 单币种不超过总资金 25%
    MAX_CORRELATED_GROUP = 0.40  # 高相关资产组合不超过 40%

    def check_exposure(self, positions: list[Position]) -> RiskCheckResult:
        gross = sum(abs(p.notional) for p in positions) / self.total_capital
        net = sum(p.notional for p in positions) / self.total_capital

        violations = []
        if gross > self.MAX_GROSS_EXPOSURE:
            violations.append(f"总杠杆 {gross:.2f}x 超过上限 {self.MAX_GROSS_EXPOSURE}x")
        if abs(net) > self.MAX_NET_EXPOSURE:
            violations.append(f"净敞口 {net:.2f}x 超过上限 {self.MAX_NET_EXPOSURE}x")

        return RiskCheckResult(passed=len(violations) == 0, violations=violations)
```

#### 2.2.2 相关性监控

- 使用 30 日滚动相关系数矩阵
- 相关系数 > 0.7 的资产对视为同一风险组
- 同一风险组总仓位不超过总资金 40%
- 每日更新相关性矩阵，相关性突变时触发告警

#### 2.2.3 VaR 监控

```
日度 VaR(95%) = 组合价值 * σ_daily * 1.645
日度 VaR(99%) = 组合价值 * σ_daily * 2.326

约束：
  VaR(95%) 不得超过总资金的 2%
  VaR(99%) 不得超过总资金的 3.5%
  CVaR(99%) 不得超过总资金的 5%
```

使用历史模拟法（最近 250 个交易日）和参数法取较大值。

### 2.3 系统层面风控

#### 2.3.1 API 异常处理

| 异常类型 | 检测方式 | 处理策略 |
|---------|---------|---------|
| API 响应延迟 > 2s | 请求耗时监控 | 切换至备用端点，暂停高频策略 |
| HTTP 429 (频率限制) | 响应状态码 | 指数退避重试，降低请求频率 |
| HTTP 5xx (服务端错误) | 响应状态码 | 3 次重试后暂停该 API 依赖的策略 |
| 签名错误 (HTTP 401) | 响应状态码 | 立即告警，可能是 API Key 泄露 |
| WebSocket 断连 | 心跳超时 | 自动重连，超过 3 次切换备用流 |
| 数据异常 (价格跳变) | 价格合理性校验 | 丢弃异常数据，使用上一有效价格 |

```python
class APICircuitBreaker:
    """API 熔断器"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "closed"  # closed / open / half_open
        self.last_failure_time = 0

    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half_open"
            else:
                raise CircuitBreakerOpenError("API 熔断中，等待恢复")

        try:
            result = await func(*args, **kwargs)
            if self.state == "half_open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.critical(f"API 熔断触发: {e}")
            raise
```

#### 2.3.2 网络中断应对

```
网络中断检测 → 5s 内无法恢复
  ├── 立即：暂停所有新订单提交
  ├── 30s：触发一级告警（推送到运维群）
  ├── 60s：尝试切换备用网络/VPN
  ├── 5min：触发二级告警（电话通知负责人）
  └── 15min：如仍未恢复，通过备用通道（手机 App）手动平仓关键仓位
```

#### 2.3.3 交易所维护应对

- 订阅币安官方公告 API 和社交媒体
- 维护前 30 分钟自动减仓至 50%
- 维护期间禁止开新仓
- 维护结束后进行数据完整性校验（对比维护前后持仓、余额）

### 2.4 黑天鹅事件应对预案

#### 2.4.1 预案分级

| 等级 | 触发条件 | 响应措施 |
|------|---------|---------|
| L1 - 关注 | BTC 1h 跌幅 > 5% | 全策略仓位缩减至 50%，增加监控频率 |
| L2 - 警告 | BTC 1h 跌幅 > 10% 或日跌幅 > 15% | 停止开新仓，非核心策略全部平仓 |
| L3 - 危机 | BTC 1h 跌幅 > 15% 或多币种同时闪崩 | 全部策略紧急平仓，系统熔断 |
| L4 - 极端 | 交易所暂停交易/提现受限 | 激活应急通信链，法务介入 |

#### 2.4.2 熔断机制

```python
class SystemCircuitBreaker:
    """系统级熔断器"""

    THRESHOLDS = {
        "portfolio_drawdown_1h": 0.05,    # 组合1小时回撤 > 5%
        "portfolio_drawdown_24h": 0.10,   # 组合24小时回撤 > 10%
        "single_strategy_loss": 0.03,     # 单策略日亏损 > 3%
        "total_daily_loss": 0.05,         # 总日亏损 > 5%
        "consecutive_losses": 10,          # 连续亏损 >= 10 笔
    }

    async def evaluate(self, metrics: RiskMetrics) -> CircuitBreakerAction:
        if metrics.portfolio_dd_1h > self.THRESHOLDS["portfolio_drawdown_1h"]:
            return CircuitBreakerAction.HALT_ALL  # 全面停止

        if metrics.total_daily_pnl_pct < -self.THRESHOLDS["total_daily_loss"]:
            return CircuitBreakerAction.HALT_ALL

        if metrics.portfolio_dd_24h > self.THRESHOLDS["portfolio_drawdown_24h"]:
            return CircuitBreakerAction.REDUCE_TO_HALF

        if metrics.consecutive_losses >= self.THRESHOLDS["consecutive_losses"]:
            return CircuitBreakerAction.PAUSE_STRATEGY

        return CircuitBreakerAction.NORMAL
```

#### 2.4.3 应急流程

```
黑天鹅事件发生
  │
  ├─ 自动化响应（< 1 秒）
  │   ├── 熔断器检查 → 触发平仓
  │   ├── 取消所有挂单
  │   └── 发送紧急告警
  │
  ├─ 人工确认（< 5 分钟）
  │   ├── 值班人员确认事件性质
  │   ├── 决定是否恢复部分策略
  │   └── 评估资金安全状况
  │
  └─ 事后复盘（< 24 小时）
      ├── 损失统计
      ├── 系统表现评估
      ├── 预案优化建议
      └── 输出事件报告
```

---

## 3. 监控告警设计

### 3.1 实时 PnL 监控仪表盘

#### 仪表盘模块设计

| 模块 | 指标 | 刷新频率 |
|------|------|---------|
| 总览面板 | 总资产、日PnL、日收益率、总回撤 | 1s |
| 策略面板 | 各策略PnL、胜率、夏普比率、最大回撤 | 5s |
| 持仓面板 | 当前持仓、未实现PnL、杠杆率、各币种敞口 | 1s |
| 订单面板 | 活跃订单、近期成交、滑点统计 | 实时 |
| 风控面板 | VaR、敞口比例、熔断状态、告警历史 | 5s |
| 系统面板 | API 延迟、WebSocket 状态、CPU/内存、队列深度 | 10s |

#### 关键图表

- 资金曲线（日、周、月级别，含基准线对比）
- 各策略收益归因瀑布图
- 持仓热力图（币种 x 策略矩阵）
- 回撤水下图（Underwater Plot）
- 滑点分布直方图

### 3.2 异常交易检测

```python
class AnomalyDetector:
    """异常交易检测器"""

    RULES = [
        # 规则1: 单笔亏损超过日度预算的 50%
        {"name": "large_single_loss", "condition": lambda t: t.pnl < -t.daily_budget * 0.5},

        # 规则2: 滑点超过预期的 5 倍
        {"name": "excessive_slippage", "condition": lambda t: t.slippage > t.expected_slippage * 5},

        # 规则3: 成交量异常（超过历史均值 10 倍）
        {"name": "volume_spike", "condition": lambda t: t.volume > t.avg_volume_30d * 10},

        # 规则4: 价格偏离（成交价偏离中间价 > 1%）
        {"name": "price_deviation", "condition": lambda t: abs(t.fill_price - t.mid_price) / t.mid_price > 0.01},

        # 规则5: 高频重复下单（同方向同币种 1 分钟内 > 20 笔）
        {"name": "rapid_fire", "condition": lambda t: t.same_direction_count_1min > 20},

        # 规则6: 策略PnL偏离回测预期 > 3 个标准差
        {"name": "strategy_deviation", "condition": lambda t: abs(t.live_sharpe - t.backtest_sharpe) > 3 * t.sharpe_std},
    ]
```

### 3.3 告警分级与通知渠道

| 级别 | 触发场景 | 通知渠道 | 响应时限 |
|------|---------|---------|---------|
| P0 - 致命 | 系统熔断、API Key 疑似泄露、资金异常 | 电话 + 短信 + 飞书/Telegram + 邮件 | 5 分钟 |
| P1 - 严重 | 单策略日亏损超限、网络持续中断、回撤触及减仓线 | 飞书/Telegram + 邮件 | 15 分钟 |
| P2 - 警告 | API 延迟升高、相关性突变、VaR 接近上限 | 飞书/Telegram | 1 小时 |
| P3 - 信息 | 策略到期、配置变更、定期报告 | 飞书/Telegram | 无硬性要求 |

**告警抑制规则：**
- 同一告警 5 分钟内不重复发送（去重窗口）
- P0 告警不受抑制，每次触发必须通知
- 告警升级：P2 告警持续 30 分钟未消除自动升级为 P1

### 3.4 风控报告模板

#### 日报（每日 UTC 00:00 自动生成）

```markdown
# 日度风控报告 - {date}

## 1. 损益概览
| 指标 | 数值 | 对比前日 |
|------|------|---------|
| 总资产 (USDT) | | |
| 日PnL (USDT) | | |
| 日收益率 | | |
| 当前回撤 | | |

## 2. 策略表现
| 策略 | PnL | 胜率 | 交易次数 | 最大单笔亏损 |
|------|-----|------|---------|------------|

## 3. 风控指标
- VaR(95%): ___  (上限: 2%)
- 总杠杆: ___x  (上限: 3x)
- 最大持仓集中度: ___  (上限: 25%)

## 4. 告警记录
| 时间 | 级别 | 内容 | 处理状态 |

## 5. 待处理事项
- [ ] ...
```

#### 周报（每周一生成）

在日报基础上增加：
- 周度收益归因分析
- 策略相关性矩阵变化
- 市场环境评估（波动率趋势、主流币联动性）
- 下周策略调整建议

#### 月报（每月1日生成）

在周报基础上增加：
- 月度夏普比率、Sortino 比率、Calmar 比率
- 最大回撤分析（时间、幅度、恢复天数）
- 资金利用率统计
- 与基准（BTC Buy & Hold）的对比
- 下月资金分配调整建议

---

## 4. 合规与安全

### 4.1 API Key 安全管理

#### 4.1.1 密钥分级

| 用途 | API 权限 | 安全要求 |
|------|---------|---------|
| 实盘交易 | 现货交易 + 合约交易 | IP 白名单 + 无提现权限 + 硬件密钥签名 |
| 行情数据 | 只读 | IP 白名单 |
| 风控监控 | 只读 + 账户信息 | IP 白名单 |
| 提现操作 | 提现 | 仅人工使用，不存入代码/系统 |

#### 4.1.2 密钥存储

```
密钥存储层级：
├── 生产环境
│   ├── 首选：HashiCorp Vault / AWS Secrets Manager
│   ├── 备选：加密配置文件（AES-256-GCM）+ 环境变量注入
│   └── 禁止：明文存储、代码仓库、日志输出
│
├── 开发/测试环境
│   ├── 使用独立的 Testnet API Key
│   └── .env 文件 + .gitignore
│
└── 密钥轮换
    ├── 每 90 天强制轮换
    ├── 疑似泄露时立即轮换
    └── 旧密钥保留 24h 后删除（确保无活跃会话）
```

#### 4.1.3 IP 白名单

- 生产服务器的固定公网 IP 加入白名单
- 不使用动态 IP / 家庭网络
- 备用服务器 IP 预先加入白名单
- 每月审查白名单条目，移除不再使用的 IP

#### 4.1.4 权限最小化

```python
# API Key 权限配置建议
API_KEY_PERMISSIONS = {
    "trading_bot": {
        "spot_trading": True,
        "futures_trading": True,
        "margin_trading": False,    # 除非策略需要
        "withdraw": False,          # 永远禁止
        "internal_transfer": False, # 禁止
        "ip_whitelist": ["x.x.x.x"],
    },
    "data_reader": {
        "spot_trading": False,
        "futures_trading": False,
        "read_only": True,
        "ip_whitelist": ["x.x.x.x"],
    },
}
```

### 4.2 交易审计日志

#### 日志内容

每笔交易记录以下信息，保留至少 3 年：

```python
@dataclass
class TradeAuditLog:
    # 交易标识
    trade_id: str               # 内部交易ID
    exchange_order_id: str      # 交易所订单ID
    timestamp: datetime         # UTC 时间戳

    # 交易详情
    strategy_id: str            # 策略标识
    symbol: str                 # 交易对
    side: str                   # BUY / SELL
    order_type: str             # LIMIT / MARKET
    quantity: Decimal
    price: Decimal              # 下单价
    fill_price: Decimal         # 成交均价
    slippage: Decimal           # 滑点

    # 风控上下文
    pre_trade_exposure: Decimal # 交易前敞口
    post_trade_exposure: Decimal # 交易后敞口
    risk_check_passed: bool     # 是否通过风控检查
    risk_check_details: dict    # 风控检查详情

    # 系统元数据
    api_latency_ms: int         # API 请求延迟
    signal_to_fill_ms: int      # 信号到成交延迟
    server_id: str              # 执行服务器标识
```

#### 日志存储

| 层级 | 存储 | 保留期限 | 用途 |
|------|------|---------|------|
| 热数据 | PostgreSQL / ClickHouse | 90 天 | 实时查询、日常分析 |
| 温数据 | 对象存储 (Parquet) | 1 年 | 月度回顾、策略优化 |
| 冷数据 | 归档存储 | 3+ 年 | 合规审计、争议追溯 |

### 4.3 反洗钱合规考量

虽然量化交易系统是自有资金运营，仍需关注：

| 合规要点 | 措施 |
|---------|------|
| 资金来源合法性 | 记录所有入金来源，保留银行流水 |
| 交易行为合规 | 避免 wash trading（自成交）、market manipulation |
| 跨境合规 | 关注运营所在地的加密货币法规，必要时咨询法律顾问 |
| 税务申报 | 完整记录所有交易的已实现收益，按当地税法申报 |
| KYC/KYT | 如未来涉及第三方资金，需实施 KYC 和交易监控 |

### 4.4 数据隐私保护

| 数据类型 | 保护措施 |
|---------|---------|
| API 密钥 | AES-256-GCM 加密存储，运行时内存中解密 |
| 交易记录 | 数据库加密（TDE），传输加密（TLS 1.3） |
| 策略参数 | 代码仓库访问控制（最小权限），敏感参数通过 Vault 注入 |
| 个人信息 | 日志中脱敏处理，不记录全量 API Key |
| 备份数据 | 加密备份，异地存储，定期验证恢复流程 |

**日志脱敏规则：**

```python
SENSITIVE_PATTERNS = [
    (r"apiKey=[\w]+", "apiKey=***"),
    (r"secret=[\w]+", "secret=***"),
    (r"password=[\w]+", "password=***"),
    (r"\b[A-Za-z0-9]{64}\b", "[REDACTED_KEY]"),  # 疑似64位密钥
]
```

---

## 附录

### A. 风控参数速查表

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 单笔最大风险 | 1% 总资金 | 固定比例风险模型 |
| 单策略日亏损上限 | 3% 分配资金 | 触发单策略暂停 |
| 组合日亏损上限 | 5% 总资金 | 触发系统熔断 |
| 最大总杠杆 | 3x | 多空总和 |
| 最大净敞口 | 1.5x | 多空净值 |
| 单币种仓位上限 | 25% 总资金 | 集中度控制 |
| VaR(95%) 上限 | 2% 总资金 | 日度 VaR |
| 最大回撤熔断线 | 20% | 触发全面平仓 |
| API 请求超时 | 5s | 超时视为失败 |
| WebSocket 心跳超时 | 30s | 超时触发重连 |

### B. 应急联系人模板

| 角色 | 姓名 | 联系方式 | 职责 |
|------|------|---------|------|
| 一线值班 | - | 电话/飞书 | P2+告警首响 |
| 策略负责人 | - | 电话/飞书 | 策略异常决策 |
| 技术负责人 | - | 电话/飞书 | 系统故障处理 |
| 风控负责人 | - | 电话/飞书 | P0 事件总协调 |

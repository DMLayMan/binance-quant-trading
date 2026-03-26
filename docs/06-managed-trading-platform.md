# 全托管量化交易平台 — 架构规划

> 从"策略脚本"到"全托管交易平台"的完整升级方案

## 一、核心场景

```
用户 A：
  "我有 50,000 USDT，想用双均线策略做 BTC/USDT 4h 级别交易，
   止损设 3%，止盈 8%，最大回撤 10% 时自动暂停。
   全部托管给平台，我只看收益。"

用户 B：
  "我有 100,000 USDT，同时跑 MACD 和 RSI 两个策略，
   各分配 50,000，每日最大亏损 2,000 USDT。
   随时可以调整策略参数或暂停某个策略。"
```

**平台能力要求：**
1. 用户设置资金池 → 选策略 → 配参数 → 一键启动托管
2. 平台定时轮询行情 → 策略决策 → 风控检查 → 自动下单
3. 用户随时查看资金/收益/持仓/历史
4. 用户随时调整策略参数/止损止盈/暂停/停止

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                         用户层 (Frontend)                            │
│  React Dashboard: 资金概览 / 策略管理 / 持仓监控 / 历史记录           │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ REST + WebSocket
┌───────────────────────────────┴──────────────────────────────────────┐
│                         API 网关层 (FastAPI)                          │
│  认证中间件(JWT) → 路由 → 请求校验 → 响应序列化                       │
│                                                                      │
│  /auth     → 注册/登录/Token刷新                                     │
│  /fund     → 资金池 CRUD / 充值提现记录                               │
│  /strategy → 策略实例 创建/启动/暂停/停止/参数调整                     │
│  /position → 当前持仓 / 历史交易                                      │
│  /monitor  → 实时收益 / 风控状态 / 系统健康                           │
│  /ws       → WebSocket 实时推送(交易事件/收益变化)                     │
└───────┬────────────────────────┬──────────────────────┬──────────────┘
        │                        │                      │
┌───────┴────────┐   ┌───────────┴──────────┐   ┌──────┴───────────┐
│ 调度引擎       │   │ 执行引擎             │   │ 风控引擎         │
│ (Scheduler)    │   │ (Executor)           │   │ (Risk Engine)    │
│                │   │                      │   │                  │
│ • 按 timeframe │   │ • 接收交易指令       │   │ • 用户级风控     │
│   定时触发策略 │   │ • 调用 Binance API   │   │ • 策略级风控     │
│ • 管理策略实例 │   │ • 订单状态跟踪       │   │ • 全局风控       │
│   生命周期     │   │ • 成交回报处理       │   │ • 止损/止盈触发  │
│ • 并发控制     │   │ • 失败重试/告警      │   │ • 回撤暂停       │
└───────┬────────┘   └───────────┬──────────┘   └──────┬───────────┘
        │                        │                      │
┌───────┴────────────────────────┴──────────────────────┴───────────┐
│                          数据层 (Persistence)                      │
│                                                                    │
│  SQLite/PostgreSQL:                                                │
│    users          → 用户账户/认证信息                                │
│    fund_pools     → 资金池(金额/状态/绑定策略)                       │
│    strategy_instances → 策略实例(参数/状态/所属资金池)                │
│    orders         → 订单记录(Binance订单ID/状态/成交)                │
│    trades         → 成交记录(入场/出场/盈亏/手续费)                   │
│    equity_snapshots → 权益快照(定时记录/绘制收益曲线)                 │
│    risk_events    → 风控事件日志(触发原因/处置结果)                   │
│                                                                    │
│  内存缓存:                                                          │
│    行情缓存(按 symbol+timeframe, TTL 与 K 线周期匹配)                │
│    策略信号缓存(最近 N 根 K 线的信号)                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心数据模型

### 3.1 用户与资金池

```python
class User:
    id: str                     # UUID
    username: str               # 登录名
    password_hash: str          # bcrypt
    binance_api_key: str        # 加密存储 (AES-256)
    binance_api_secret: str     # 加密存储
    use_testnet: bool           # 是否测试网
    created_at: datetime
    is_active: bool

class FundPool:
    id: str                     # UUID
    user_id: str                # 所属用户
    name: str                   # "我的BTC策略池"
    allocated_amount: float     # 分配金额 (USDT)
    current_equity: float       # 当前权益
    peak_equity: float          # 历史最高权益
    status: str                 # active / paused / stopped
    created_at: datetime

    # 用户自定义风控
    max_daily_loss_pct: float   # 日最大亏损 (%)
    max_drawdown_pct: float     # 最大回撤 (%)
    take_profit_pct: float      # 目标止盈 (%)  ← 新增: 达标后自动停止
    stop_loss_pct: float        # 总止损 (%)    ← 新增: 亏损到阈值自动停止
```

### 3.2 策略实例

```python
class StrategyInstance:
    id: str                     # UUID
    fund_pool_id: str           # 所属资金池
    strategy_name: str          # ma_crossover / macd / rsi / ...
    symbol: str                 # BTC/USDT
    timeframe: str              # 4h
    params: dict                # {"fast": 7, "slow": 25}

    # 风控参数
    stop_loss_atr_mult: float   # 止损 ATR 倍数
    take_profit_atr_mult: float # 止盈 ATR 倍数
    max_position_pct: float     # 单笔最大仓位占比
    risk_per_trade_pct: float   # 单笔风险占比

    # 运行状态
    status: str                 # pending / running / paused / stopped / error
    current_position: float     # 当前持仓数量
    entry_price: float          # 入场均价
    unrealized_pnl: float       # 未实现盈亏
    total_pnl: float            # 已实现总盈亏
    trade_count: int            # 总交易次数
    win_count: int              # 盈利次数

    last_signal: int            # 最近信号 (1/-1/0)
    last_signal_time: datetime  # 最近信号时间
    next_check_time: datetime   # 下次检查时间
    error_message: str          # 异常信息
```

### 3.3 订单与成交

```python
class Order:
    id: str                     # 内部 UUID
    exchange_order_id: str      # Binance 订单 ID
    strategy_instance_id: str   # 所属策略实例
    user_id: str                # 所属用户

    symbol: str
    side: str                   # buy / sell
    order_type: str             # market / limit
    amount: float               # 下单数量
    price: float                # 下单价格 (limit) / 成交均价 (market)
    filled_amount: float        # 已成交数量
    fee: float                  # 手续费

    status: str                 # pending / filled / partially_filled / cancelled / failed
    created_at: datetime
    filled_at: datetime
    reason: str                 # "signal_buy" / "stop_loss" / "take_profit" / "manual_close"

class Trade:
    id: str
    strategy_instance_id: str
    user_id: str

    entry_order_id: str         # 入场订单
    exit_order_id: str          # 出场订单
    symbol: str
    side: str                   # long / short
    entry_price: float
    exit_price: float
    amount: float
    pnl: float                  # 净盈亏 (扣除手续费)
    pnl_pct: float              # 盈亏百分比
    total_fee: float
    holding_duration: int       # 持仓时长 (秒)
    exit_reason: str            # signal / stop_loss / take_profit / manual / risk_halt

    entry_time: datetime
    exit_time: datetime
```

---

## 四、核心流程

### 4.1 用户操作动线

```
① 注册/登录
   └→ 填写 Binance API Key/Secret (加密存储)

② 创建资金池
   └→ 设定池名称、分配金额
   └→ 设定总止盈(如+20%)、总止损(如-10%)、最大回撤(如-15%)

③ 绑定策略
   └→ 选择策略(如 ma_crossover)
   └→ 选择交易对(BTC/USDT) 和 周期(4h)
   └→ 调整策略参数(快线7/慢线25)
   └→ 设定单笔止损止盈(ATR 倍数)、仓位比例

④ 启动托管
   └→ 系统校验: API Key 有效性 → 余额充足性 → 参数合理性
   └→ 创建 StrategyInstance, 状态=running
   └→ 调度引擎注册定时任务

⑤ 日常监控 (被动)
   └→ Dashboard 自动刷新: 资金曲线/持仓/收益
   └→ WebSocket 实时推送: 交易提醒/风控告警

⑥ 主动干预 (随时)
   └→ 调整策略参数 → 下次 K 线生效
   └→ 调整止损止盈 → 立即生效
   └→ 暂停策略 → 保持当前持仓, 不开新仓
   └→ 停止策略 → 平掉所有持仓, 资金回池
   └→ 手动平仓 → 指定策略立即市价平仓
```

### 4.2 托管执行流程 (调度引擎核心)

```
                      ┌─────────────────────┐
                      │    Scheduler Loop    │
                      │ (每分钟扫描一次)      │
                      └──────────┬──────────┘
                                 │
                    查询所有 status=running 且
                    next_check_time <= now 的策略实例
                                 │
                    ┌────────────┴────────────┐
                    │     对每个策略实例       │
                    │     (并发执行)           │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              ▼                                      │
    ┌─────────────────┐                             │
    │ 1. 获取行情数据  │                             │
    │   (带缓存)       │                             │
    └────────┬────────┘                             │
             │                                      │
    ┌────────▼────────┐                             │
    │ 2. 计算技术指标  │                             │
    │   ATR/RSI/MACD  │                             │
    └────────┬────────┘                             │
             │                                      │
    ┌────────▼────────┐     ┌──────────────────┐   │
    │ 3. 策略信号生成  │────▶│ 决策模型矩阵      │   │
    │   signal_func() │     │ (见 4.3 节)       │   │
    └────────┬────────┘     └──────────────────┘   │
             │                                      │
    ┌────────▼─────────────────────┐               │
    │ 4. 持仓检查                   │               │
    │   • 有持仓 → 检查止损/止盈    │               │
    │   • 触发 SL/TP → 生成平仓指令 │               │
    └────────┬─────────────────────┘               │
             │                                      │
    ┌────────▼────────┐                             │
    │ 5. 风控三层检查  │                             │
    │   用户级 → 策略级 → 全局级                     │
    │   任一层 REJECT → 跳过本次                     │
    └────────┬────────┘                             │
             │ PASS                                 │
    ┌────────▼────────┐                             │
    │ 6. 生成交易指令  │                             │
    │   计算仓位大小    │                             │
    │   确定订单类型    │                             │
    └────────┬────────┘                             │
             │                                      │
    ┌────────▼────────┐                             │
    │ 7. 执行下单      │                             │
    │   调用 Binance   │                             │
    │   记录 Order     │                             │
    └────────┬────────┘                             │
             │                                      │
    ┌────────▼─────────────────────┐               │
    │ 8. 后处理                     │               │
    │   • 更新持仓/权益             │               │
    │   • 记录 Trade (如平仓)       │               │
    │   • 检查总止盈/总止损         │               │
    │   • 推送 WebSocket 事件       │               │
    │   • 计算 next_check_time     │               │
    └──────────────────────────────┘               │
                                                    │
              ◀─────────────────────────────────────┘
                      下一个策略实例
```

### 4.3 决策模型矩阵

每个策略的信号函数保持不变（纯技术指标），但在生成最终交易指令前，需经过 **决策评估层** ：

```
                    策略原始信号
                    signal = +1 (买入)
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐    ┌──────────┐    ┌──────────┐
    │信号强度  │    │趋势过滤   │    │时间过滤   │
    │评估      │    │          │    │          │
    │ ATR 波动 │    │ 大周期趋 │    │ 避开重大  │
    │ 是否足够 │    │ 势是否一 │    │ 数据发布  │
    │ 支撑止损 │    │ 致       │    │ 时段      │
    └────┬────┘    └────┬─────┘    └────┬─────┘
         │              │               │
         └──────────────┼───────────────┘
                        ▼
               ┌────────────────┐
               │ 综合评分 0-100  │
               │ ≥ 60 → 执行    │
               │ < 60 → 跳过    │
               └────────────────┘
```

**五种注册策略的决策逻辑：**

| 策略 | 信号生成 | 买入条件 | 卖出条件 | 止损 | 止盈 |
|------|---------|---------|---------|------|------|
| **ma_crossover** | 快线上穿慢线=+1, 下穿=-1 | 金叉 + ATR > 阈值 | 死叉 或 止损触发 | ATR × N | ATR × M |
| **macd** | MACD线上穿信号线=+1, 下穿=-1 | MACD金叉 + 柱状图递增 | MACD死叉 或 止损触发 | ATR × N | ATR × M |
| **bollinger_breakout** | 价格突破上轨=+1, 跌破下轨=-1 | Squeeze后突破 + 量能放大 | 回归中轨 或 止损触发 | ATR × N | ATR × M |
| **rsi** | RSI从超卖回升=+1, 从超买回落=-1 | RSI < 30后回升 + 趋势向上 | RSI > 70后回落 或 止损触发 | ATR × N | ATR × M |
| **turtle** | N日新高突破=+1, N日新低跌破=-1 | 通道突破 + 量能确认 | 反向通道突破 或 止损触发 | ATR × N | ATR × M |

**通用出场逻辑（所有策略共享）：**
1. **ATR 硬止损**: 价格跌破 `entry - ATR × stop_loss_mult` → 立即平仓
2. **ATR 硬止盈**: 价格突破 `entry + ATR × take_profit_mult` → 立即平仓
3. **反向信号**: 策略产生相反信号 → 平仓（并可反向开仓）
4. **资金池止盈**: `current_equity / allocated >= 1 + take_profit_pct` → 停止策略
5. **资金池止损**: `current_equity / allocated <= 1 - stop_loss_pct` → 停止策略
6. **回撤暂停**: `drawdown >= max_drawdown_pct` → 暂停策略，保持持仓

### 4.4 定时调度机制

```python
# 调度策略: 按 timeframe 对齐到 K 线收盘时间

SCHEDULE_MAP = {
    "1m":  "每分钟第 5 秒",       # K线刚闭合
    "5m":  "每 5 分钟 + 5 秒",
    "15m": "每 15 分钟 + 5 秒",
    "1h":  "每小时第 0 分 5 秒",
    "4h":  "每 4 小时第 0 分 5 秒", # 00:00, 04:00, 08:00, 12:00, 16:00, 20:00
    "1d":  "每天 00:00:05 UTC",
}

# 调度引擎核心循环 (每 10 秒扫描一次)
async def scheduler_loop():
    while True:
        now = datetime.utcnow()

        # 查询需要执行的策略实例
        instances = db.query(StrategyInstance).filter(
            StrategyInstance.status == "running",
            StrategyInstance.next_check_time <= now,
        ).all()

        # 并发执行 (限制并发数, 避免 API 限速)
        semaphore = asyncio.Semaphore(5)  # 最多 5 个并发
        tasks = [execute_strategy(inst, semaphore) for inst in instances]
        await asyncio.gather(*tasks, return_exceptions=True)

        await asyncio.sleep(10)
```

---

## 五、风控体系

### 三层风控架构

```
┌────────────────────────────────────────────┐
│ 第 1 层: 策略级风控 (per StrategyInstance)  │
│                                            │
│  • 单笔仓位 ≤ max_position_pct            │
│  • 单笔风险 ≤ risk_per_trade_pct          │
│  • ATR 止损 / 止盈                         │
│  • 连续亏损 ≥ 5 次 → 暂停该策略            │
│  • 当日交易 ≥ 50 次 → 暂停该策略           │
├────────────────────────────────────────────┤
│ 第 2 层: 资金池级风控 (per FundPool)        │
│                                            │
│  • 日亏损 ≥ max_daily_loss_pct → 暂停池    │
│  • 回撤 ≥ max_drawdown_pct → 暂停池        │
│  • 权益 ≥ take_profit 目标 → 通知用户      │
│  • 权益 ≤ stop_loss 阈值 → 全部平仓+停止   │
│  • 池内所有策略共享风控额度                  │
├────────────────────────────────────────────┤
│ 第 3 层: 全局风控 (系统级)                  │
│                                            │
│  • 单用户最大同时持仓数 ≤ N                 │
│  • API 限速保护 (Binance 1200 req/min)     │
│  • 异常检测: 单分钟亏损 > 阈值 → 全局暂停  │
│  • 交易所连接断开 → 暂停所有策略            │
│  • 余额不足 → 阻止开仓                     │
└────────────────────────────────────────────┘
```

---

## 六、API 设计 (新增端点)

### 6.1 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 (username, password, api_key, api_secret) |
| POST | `/api/auth/login` | 登录 → JWT Token |
| POST | `/api/auth/refresh` | 刷新 Token |
| GET  | `/api/auth/me` | 当前用户信息 |

### 6.2 资金池

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/funds` | 创建资金池 |
| GET  | `/api/funds` | 列出所有资金池 |
| GET  | `/api/funds/{id}` | 资金池详情 (含收益曲线) |
| PUT  | `/api/funds/{id}` | 修改风控参数 |
| POST | `/api/funds/{id}/pause` | 暂停资金池 (保持持仓) |
| POST | `/api/funds/{id}/stop` | 停止资金池 (平仓) |

### 6.3 策略实例

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/instances` | 创建策略实例 (绑定资金池) |
| GET  | `/api/instances` | 列出所有策略实例 |
| GET  | `/api/instances/{id}` | 实例详情 (含信号/持仓/盈亏) |
| PUT  | `/api/instances/{id}/params` | 调整策略参数 (下个K线生效) |
| PUT  | `/api/instances/{id}/risk` | 调整止损止盈 (立即生效) |
| POST | `/api/instances/{id}/start` | 启动 |
| POST | `/api/instances/{id}/pause` | 暂停 (不平仓) |
| POST | `/api/instances/{id}/stop` | 停止 (平仓) |
| POST | `/api/instances/{id}/close-position` | 手动平仓 |

### 6.4 交易记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/orders?instance_id=&status=` | 订单列表 |
| GET  | `/api/trades?instance_id=&from=&to=` | 成交记录 |
| GET  | `/api/trades/summary` | 交易统计 (胜率/盈亏比/夏普) |

### 6.5 实时推送

| 类型 | 路径 | 推送事件 |
|------|------|---------|
| WebSocket | `/ws` | trade_opened, trade_closed, risk_alert, equity_update, signal_generated |

---

## 七、分期实施计划

### Phase 1: 单用户全托管 MVP (优先级最高)

> 目标: 一个用户能完整跑通 "配资金 → 选策略 → 自动交易 → 查收益" 全流程

**范围:**
- [ ] SQLite 数据库 (fund_pools, strategy_instances, orders, trades, equity_snapshots)
- [ ] 调度引擎: 按 timeframe 定时触发策略, 并发执行
- [ ] 执行引擎: 信号 → 风控 → 下单 → 订单跟踪 → 成交记录
- [ ] 资金池 CRUD API + 策略实例生命周期管理 API
- [ ] 三层风控 (策略级/资金池级/全局级)
- [ ] 总止盈/总止损: 资金池收益达标自动停止
- [ ] 前端: 资金池管理页 + 策略配置页 + 持仓/订单页
- [ ] 基础权益快照 (每次交易后记录)

**技术决策:**
- 数据库: SQLite (单用户足够, 后续可迁移 PostgreSQL)
- 调度: asyncio 内置调度 (无需 Celery)
- 认证: 暂不需要 (单用户)

### Phase 2: 多用户 + 实时推送

**范围:**
- [ ] 用户认证 (JWT + bcrypt)
- [ ] API Key 加密存储 (AES-256)
- [ ] 多用户数据隔离
- [ ] WebSocket 实时推送 (交易事件/权益变化)
- [ ] 迁移到 PostgreSQL
- [ ] 收益曲线图表 (分钟级/小时级/日级)

### Phase 3: 高级功能

**范围:**
- [ ] 策略组合 (一个资金池跑多策略, 资金分配比例)
- [ ] 条件单 (限价止盈/移动止损)
- [ ] 交易复盘 (每笔交易的入场理由回溯)
- [ ] 邮件/微信/Telegram 告警通知
- [ ] 策略回测 → 一键部署
- [ ] 策略绩效排行榜

---

## 八、关键技术决策

### 8.1 为什么不用 Celery / Redis Queue?

对于 Phase 1, asyncio + SQLite 已满足需求:
- 单进程内的协程调度足够处理 50+ 策略实例
- K 线级别调度 (最快 1 分钟) 不需要毫秒级任务队列
- 减少运维复杂度 (无需额外部署 Redis/RabbitMQ)

当并发量超过 200 策略实例时, 可引入 Celery。

### 8.2 行情缓存策略

```python
# 同一 symbol + timeframe 在同一根 K 线周期内只请求一次
cache_key = f"{symbol}:{timeframe}"
cache_ttl = TIMEFRAME_SECONDS[timeframe]  # 4h → 14400s

# 多个策略实例使用相同 symbol+timeframe 时共享缓存
# 避免触发 Binance API 限速 (1200 req/min)
```

### 8.3 订单状态机

```
pending → submitted → filled    → (正常完成)
                   → partially_filled → filled / cancelled
                   → failed     → (记录错误, 告警)
                   → cancelled  → (用户取消或风控取消)
```

### 8.4 资金隔离方案

Phase 1 采用 **逻辑隔离**: 所有交易使用同一个 Binance 账户, 但通过数据库记账实现资金池隔离。

```
用户实际余额:  100,000 USDT
├── 资金池 A:  50,000 USDT (逻辑分配)
├── 资金池 B:  30,000 USDT (逻辑分配)
└── 未分配:    20,000 USDT
```

风控在下单前校验: `order_value <= fund_pool.available_amount`

---

## 九、现有代码复用评估

| 现有模块 | 复用方式 | 改造程度 |
|---------|---------|---------|
| `strategies/*.py` | 信号函数直接复用, 无需修改 | 零改动 |
| `utils/indicators.py` | 技术指标直接复用 | 零改动 |
| `data/market_data.py` | 加一层缓存包装 | 小改动 |
| `execution/order_manager.py` | 拆分为 下单+跟踪, 加状态机 | 中改动 |
| `risk/risk_manager.py` | RiskController 改为 per-instance, 加资金池级检查 | 中改动 |
| `backtest/engine.py` | 直接复用 | 零改动 |
| `api/schemas.py` | 扩展新模型 | 小改动 |
| `api/server.py` | 加新路由 + 中间件 | 小改动 |
| 前端组件 | 扩展新页面, 复用 MetricCard/Sidebar 等 | 中改动 |

**代码复用率约 70%**, 核心策略和指标完全复用。

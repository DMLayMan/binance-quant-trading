# BQT 投资策略完整解决方案 — 深度设计文档

> 基于当前架构的全方位升级路线，聚焦核心竞争力与差异化壁垒

---

## 一、现有架构评估

### 已建成的基础

| 模块 | 当前状态 | 成熟度 |
|------|----------|--------|
| 策略框架 | 5 个趋势策略 + 3 个储备策略 | ★★★☆☆ |
| 执行引擎 | 单信号 → 市价单 → 全仓进出 | ★★☆☆☆ |
| 风控系统 | 三层静态阈值（策略/池/止盈） | ★★★☆☆ |
| 回测引擎 | 事件驱动、手续费/滑点模拟 | ★★★☆☆ |
| 资金管理 | 资金池隔离 + ATR/Kelly 仓位 | ★★★☆☆ |

### 核心短板

1. **策略单一化**：仅有趋势跟踪类，缺乏均值回归、统计套利、量价因子的组合
2. **信号粒度粗**：只有 +1/-1/0 三种信号，没有信号强度和置信度
3. **执行原始**：仅 Market Order，没有执行算法和订单管理
4. **风控是「刹车」而非「方向盘」**：只会停、不会调，无法动态调整敞口
5. **策略之间无协作**：多个实例各自为战，资金分配是人工静态设定

---

## 二、完整解决方案架构

```
                           ┌────────────────────────┐
                           │   Strategy Orchestrator │
                           │   (策略编排器)           │
                           └────────┬───────────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
    ┌──────────▼──────────┐ ┌──────▼──────────┐ ┌──────▼──────────┐
    │  Alpha Engine       │ │ Risk Engine     │ │ Execution Engine│
    │  (信号工厂)          │ │ (智能风控)       │ │ (智能执行)       │
    │                     │ │                 │ │                 │
    │ • 多因子合成         │ │ • 动态 VaR      │ │ • TWAP/VWAP     │
    │ • 多时间框架         │ │ • 相关性监控     │ │ • 冰山订单       │
    │ • 信号置信度         │ │ • 尾部风险       │ │ • 滑点优化       │
    │ • 市况识别           │ │ • 预测性保护     │ │ • 智能路由       │
    └──────────┬──────────┘ └──────┬──────────┘ └──────┬──────────┘
               │                    │                    │
    ┌──────────▼────────────────────▼────────────────────▼──────────┐
    │                    Portfolio Manager (组合管理器)                │
    │  • 动态资金分配  • 策略轮动  • 对冲管理  • 复利优化             │
    └──────────────────────────────┬────────────────────────────────┘
                                   │
    ┌──────────────────────────────▼────────────────────────────────┐
    │                  Intelligence Layer (数据智能层)                │
    │  • 市况分类  • 波动率预测  • 流动性分析  • 异常检测            │
    └──────────────────────────────────────────────────────────────┘
```

---

## 三、核心模块详细设计

### 模块 1：Alpha Engine — 信号工厂

#### 亮点：多因子信号融合 + 置信度评分

**当前问题**：每个策略独立输出 +1/0/-1，多个策略同时运行时各自为战，无法形成协同判断。

**解决方案**：引入「信号强度」和「多因子融合」机制。

```python
@dataclass
class AlphaSignal:
    """带置信度的信号（替代简单的 +1/0/-1）"""
    direction: int          # +1 多, -1 空, 0 无信号
    strength: float         # 0.0 ~ 1.0 信号强度
    confidence: float       # 0.0 ~ 1.0 置信度
    factors: dict           # 贡献因子分解
    regime: str             # trending / ranging / volatile
    timestamp: str

class AlphaEngine:
    """多因子信号合成引擎"""

    def generate(self, symbol, timeframe, df) -> AlphaSignal:
        # 1. 收集各因子得分
        scores = {
            "trend":    self._trend_score(df),      # MA/MACD/ADX
            "momentum": self._momentum_score(df),    # RSI/Stoch/CCI
            "volatility": self._volatility_score(df),# BB/ATR ratio
            "volume":   self._volume_score(df),      # OBV/VWAP/CVD
            "structure": self._structure_score(df),   # S/R/Fibonacci
        }

        # 2. 市况识别 → 动态调整因子权重
        regime = self._classify_regime(df)
        weights = REGIME_WEIGHTS[regime]
        # trending 行情加重 trend 权重
        # ranging 行情加重 mean_reversion 权重

        # 3. 加权融合 → 方向 + 强度
        composite = sum(scores[k] * weights[k] for k in scores)
        direction = 1 if composite > 0.3 else (-1 if composite < -0.3 else 0)
        strength = min(abs(composite), 1.0)

        # 4. 多时间框架一致性 → 置信度
        htf_alignment = self._check_higher_timeframe(symbol, timeframe)
        confidence = strength * htf_alignment

        return AlphaSignal(
            direction=direction,
            strength=strength,
            confidence=confidence,
            factors=scores,
            regime=regime,
            timestamp=now_iso(),
        )
```

#### 独特竞争力

| 特性 | 传统量化平台 | BQT 方案 |
|------|-------------|---------|
| 信号输出 | 离散 +1/-1 | 连续强度 + 置信度 |
| 因子协作 | 独立策略并行 | 动态加权融合 |
| 市况适应 | 固定参数 | Regime-Aware 权重调整 |
| 时间框架 | 单时间框架 | 多 TF 一致性验证 |

**核心创新**：信号强度直接映射到仓位大小。高置信度 → 满仓位；低置信度 → 轻仓位。不再是「全进全出」的二元决策，而是像专业交易员一样「看多少下多少」。

---

### 模块 2：市况分类引擎 (Regime Detector)

#### 亮点：让策略知道「现在该用什么打法」

```python
class RegimeDetector:
    """
    市况四象限分类:
      - Trending Up    (趋势上涨)  → 重仓趋势策略
      - Trending Down  (趋势下跌)  → 做空或观望
      - Mean-Reverting (区间震荡)  → 均值回归策略
      - Volatile/Chaos (高波乱市)  → 减仓或对冲
    """

    def classify(self, df: pd.DataFrame) -> RegimeState:
        # 维度1: 趋势强度 (ADX)
        adx = compute_adx(df, period=14)
        trend_strength = adx.iloc[-1]

        # 维度2: 波动率状态 (ATR percentile)
        atr = compute_atr(df)
        atr_pctile = (atr.iloc[-1] - atr.rolling(100).min().iloc[-1]) / \
                     (atr.rolling(100).max().iloc[-1] - atr.rolling(100).min().iloc[-1])

        # 维度3: 方向 (50EMA 斜率)
        ema50 = df['close'].ewm(span=50).mean()
        slope = (ema50.iloc[-1] - ema50.iloc[-5]) / ema50.iloc[-5]

        # 维度4: 市场效率 (Efficiency Ratio)
        er = abs(df['close'].iloc[-1] - df['close'].iloc[-20]) / \
             df['close'].diff().abs().rolling(20).sum().iloc[-1]

        # 综合判定
        if trend_strength > 25 and er > 0.4:
            regime = "trending_up" if slope > 0 else "trending_down"
        elif atr_pctile > 0.8:
            regime = "volatile"
        else:
            regime = "mean_reverting"

        return RegimeState(
            regime=regime,
            trend_strength=trend_strength,
            volatility_percentile=atr_pctile,
            direction_slope=slope,
            efficiency_ratio=er,
            recommended_strategies=REGIME_STRATEGY_MAP[regime],
        )
```

**实际场景**：
- 2024年 BTC 从 4 万涨到 7 万 → Regime 持续检测为 `trending_up` → 自动加重海龟/MA 策略权重
- 2024年 ETH 长期 3000-4000 震荡 → 检测为 `mean_reverting` → 自动切换到 RSI/Bollinger 策略
- 黑天鹅闪崩 → 检测为 `volatile` → 自动降仓位、加宽止损

---

### 模块 3：智能风控引擎 (Adaptive Risk Engine)

#### 亮点：从「刹车」进化为「自适应方向盘」

**当前系统的问题**：风控阈值是写死的（5% 日亏损、15% 最大回撤）。无论市场环境如何变化，同样的阈值。这导致：
- 低波动期：阈值太宽松，保护不足
- 高波动期：阈值太紧，频繁熔断错过反弹

**解决方案**：动态风控 + 预测性保护

```python
class AdaptiveRiskEngine:
    """自适应风控引擎"""

    def compute_dynamic_limits(self, pool: FundPool,
                                instances: list[StrategyInstance],
                                market_data: dict) -> RiskLimits:
        # 1. 基于波动率的动态阈值
        realized_vol = self._compute_realized_vol(market_data, window=30)
        vol_regime = "low" if realized_vol < 0.3 else (
                     "high" if realized_vol > 0.7 else "normal")

        # 波动率越高 → 止损越宽、仓位越小
        vol_multiplier = {
            "low":    {"stop_mult": 0.8, "position_mult": 1.2},
            "normal": {"stop_mult": 1.0, "position_mult": 1.0},
            "high":   {"stop_mult": 1.5, "position_mult": 0.6},
        }[vol_regime]

        # 2. 基于策略表现的动态仓位
        # 近期表现好的策略获得更多资金
        perf_scores = {}
        for inst in instances:
            if inst.trade_count >= 10:
                win_rate = inst.win_count / inst.trade_count
                avg_pnl = inst.total_pnl / inst.trade_count
                # Bayesian-smoothed score
                perf_scores[inst.id] = (win_rate * 0.4 +
                    min(avg_pnl / pool.allocated_amount * 100, 1.0) * 0.6)

        # 3. 跨策略相关性风险
        # 如果多个策略持有同方向仓位 → 实际风险远大于单策略度量
        correlation_penalty = self._compute_correlation_risk(instances)

        # 4. 尾部风险调整 (CVaR)
        cvar_95 = self._compute_cvar(pool, confidence=0.95)

        return RiskLimits(
            max_daily_loss_pct=pool.max_daily_loss_pct * vol_multiplier["stop_mult"],
            max_drawdown_pct=pool.max_drawdown_pct * vol_multiplier["stop_mult"],
            max_position_pct=pool.max_position_pct * vol_multiplier["position_mult"],
            correlation_adjusted_exposure=1.0 - correlation_penalty,
            cvar_95=cvar_95,
            strategy_allocations=perf_scores,
        )

    def _compute_correlation_risk(self, instances) -> float:
        """
        计算跨策略相关性风险惩罚

        如果 3 个策略都在做多 BTC → 相关性惩罚 = 高
        如果 1 个做多 BTC + 1 个做多 ETH + 1 个做空 SOL → 惩罚 = 低
        """
        positions = [(i.symbol, i.current_position) for i in instances
                     if i.current_position != 0]
        if len(positions) < 2:
            return 0.0

        # 计算符号方向集中度
        long_exposure = sum(p for _, p in positions if p > 0)
        short_exposure = sum(abs(p) for _, p in positions if p < 0)
        net_exposure = abs(long_exposure - short_exposure)
        gross_exposure = long_exposure + short_exposure

        if gross_exposure == 0:
            return 0.0

        # 净敞口/总敞口 越接近 1 → 越集中 → 惩罚越大
        concentration = net_exposure / gross_exposure
        return concentration * 0.3  # 最多降低 30% 仓位
```

#### 预测性保护 — 在亏损发生前行动

```python
class DrawdownPredictor:
    """基于实时指标预测即将发生的回撤"""

    def predict(self, pool: FundPool, market_state: dict) -> DrawdownForecast:
        risk_signals = []

        # 信号 1: 波动率突增（ATR 突破 2 倍标准差）
        if market_state['atr_zscore'] > 2.0:
            risk_signals.append(("vol_spike", 0.7))

        # 信号 2: 流动性枯竭（买卖价差扩大）
        if market_state['spread_percentile'] > 0.9:
            risk_signals.append(("liquidity_dry", 0.8))

        # 信号 3: 持仓盈利回吐速度
        if pool.peak_equity > 0:
            retracement_speed = self._compute_retracement_speed(pool)
            if retracement_speed > 0.5:  # 快速回吐
                risk_signals.append(("profit_giveback", 0.6))

        # 信号 4: 连续亏损模式检测
        loss_pattern = self._detect_loss_pattern(pool)
        if loss_pattern == "accelerating":
            risk_signals.append(("loss_acceleration", 0.9))

        # 综合评分 → 建议行动
        if not risk_signals:
            return DrawdownForecast(risk_level="low", action="none")

        max_score = max(s for _, s in risk_signals)
        if max_score > 0.8:
            return DrawdownForecast(
                risk_level="critical",
                action="reduce_50pct",  # 建议减仓 50%
                signals=risk_signals,
            )
        elif max_score > 0.6:
            return DrawdownForecast(
                risk_level="elevated",
                action="tighten_stops",  # 收紧止损
                signals=risk_signals,
            )

        return DrawdownForecast(risk_level="moderate", action="monitor")
```

#### 独特竞争力

| 维度 | 普通量化平台 | BQT 方案 |
|------|-------------|---------|
| 风控模式 | 静态阈值触发 | 动态自适应 + 预测性 |
| 响应方式 | 全停 or 全跑 | 梯度调整（减仓/收紧/暂停） |
| 跨策略感知 | 无 | 相关性惩罚 + 集中度控制 |
| 波动率适应 | 无 | 高波放宽止损、缩小仓位 |
| 预测能力 | 无 | 4 维信号预测即将到来的回撤 |

---

### 模块 4：智能执行引擎 (Smart Execution)

#### 亮点：从「一锤子市价单」进化到「专业执行算法」

```python
class SmartExecutor:
    """智能订单执行引擎"""

    def execute(self, intent: TradeIntent, market: MarketSnapshot) -> ExecutionPlan:
        """
        根据订单大小和市场状况，自动选择最优执行策略

        小单（< 市场 1 分钟成交量的 1%）→ 直接市价
        中单（1% ~ 10%）→ TWAP 拆单
        大单（> 10%）→ 冰山 + TWAP
        """
        order_impact = intent.size * intent.price / market.volume_1m

        if order_impact < 0.01:
            return self._market_order(intent)
        elif order_impact < 0.10:
            return self._twap_execution(intent, slices=5, interval_sec=30)
        else:
            return self._iceberg_execution(intent, visible_pct=0.15,
                                            slices=10, interval_sec=60)

    def _twap_execution(self, intent, slices, interval_sec):
        """
        TWAP: 将大单拆分为 N 个小单，每隔固定时间执行一笔

        优势: 减少市场冲击，获得更好的平均价格
        """
        slice_size = intent.size / slices
        plan = ExecutionPlan(algorithm="TWAP", total_slices=slices)

        for i in range(slices):
            plan.add_slice(
                size=slice_size,
                delay_seconds=i * interval_sec,
                order_type="limit",  # 限价单，比市价便宜 1 tick
                limit_offset=-0.0001,
                fallback="market",   # 超时未成交 → 转市价
                fallback_timeout=interval_sec * 0.8,
            )

        return plan

    def _iceberg_execution(self, intent, visible_pct, slices, interval_sec):
        """
        冰山订单: 每次只露出总量的一小部分

        防止暴露真实意图，避免被做市商/MEV 机器人狙击
        """
        visible_size = intent.size * visible_pct
        plan = ExecutionPlan(algorithm="ICEBERG", total_slices=slices)

        remaining = intent.size
        for i in range(slices):
            sz = min(visible_size, remaining)
            if sz <= 0:
                break
            plan.add_slice(
                size=sz,
                delay_seconds=i * interval_sec,
                order_type="limit",
                limit_offset=-0.0002,
                fallback="market",
                fallback_timeout=interval_sec * 0.7,
            )
            remaining -= sz

        return plan
```

#### 执行质量分析 (Implementation Shortfall)

```python
class ExecutionAnalyzer:
    """衡量执行质量：实际成交价 vs 理论价格的偏差"""

    def analyze(self, intent: TradeIntent, fills: list[Fill]) -> ExecutionReport:
        decision_price = intent.decision_price  # 信号触发时的价格
        avg_fill_price = sum(f.price * f.size for f in fills) / sum(f.size for f in fills)

        # Implementation Shortfall = 实际成本 - 理论成本
        if intent.side == "buy":
            shortfall_bps = (avg_fill_price - decision_price) / decision_price * 10000
        else:
            shortfall_bps = (decision_price - avg_fill_price) / decision_price * 10000

        return ExecutionReport(
            decision_price=decision_price,
            avg_fill_price=avg_fill_price,
            shortfall_bps=shortfall_bps,       # 滑点（基点）
            total_fees=sum(f.fee for f in fills),
            fill_rate=sum(f.size for f in fills) / intent.size,
            time_to_fill_sec=(fills[-1].timestamp - fills[0].timestamp).seconds,
            slices_used=len(fills),
        )
```

**实际价值**：假设一个 10 万美元的订单，市价单滑点 0.1%，智能执行后滑点降低到 0.02%。单次节省 80 美元，一年 200 笔交易节省 16,000 美元。

---

### 模块 5：策略编排器 (Strategy Orchestrator)

#### 亮点：从「策略并行运行」到「策略协同决策」

这是整套方案最核心的差异化竞争力。

```python
class StrategyOrchestrator:
    """
    策略编排器 — 统一管理多策略的信号、资金分配和冲突协调

    核心理念：多个策略不是各自为战的「独立兵种」，
    而是一支有统一指挥的「协同军团」。
    """

    def orchestrate(self, pool: FundPool,
                     instances: list[StrategyInstance],
                     market_state: MarketSnapshot) -> list[TradeDecision]:
        decisions = []

        # Step 1: 收集所有策略的 Alpha 信号
        signals = {}
        for inst in instances:
            if inst.status == "running":
                signals[inst.id] = self.alpha_engine.generate(
                    inst.symbol, inst.timeframe, market_state.get_ohlcv(inst.symbol)
                )

        # Step 2: 市况判定
        regime = self.regime_detector.classify(market_state.primary_df)

        # Step 3: 冲突检测与仲裁
        # 例: 策略 A 说买 BTC，策略 B 说卖 BTC → 取置信度高的
        resolved = self._resolve_conflicts(signals)

        # Step 4: 动态风控约束
        risk_limits = self.risk_engine.compute_dynamic_limits(
            pool, instances, market_state
        )

        # Step 5: 资金分配 (Risk Parity)
        allocations = self._risk_parity_allocation(
            pool, resolved, risk_limits, regime
        )

        # Step 6: 生成执行计划
        for inst_id, alloc in allocations.items():
            signal = resolved[inst_id]
            if signal.direction != 0 and signal.confidence > 0.3:
                decisions.append(TradeDecision(
                    instance_id=inst_id,
                    direction=signal.direction,
                    target_position_pct=alloc.position_pct * signal.strength,
                    confidence=signal.confidence,
                    regime=regime.regime,
                    execution_algo="auto",  # 智能执行引擎自动选择
                ))

        return decisions

    def _risk_parity_allocation(self, pool, signals, limits, regime):
        """
        风险平价分配：确保每个策略贡献相同的风险量

        不是按资金等分，而是按波动率反向加权：
        - 低波动策略 → 分配更多资金（因为风险贡献小）
        - 高波动策略 → 分配较少资金（因为风险贡献大）

        最终目标：组合层面的风险均匀分散
        """
        vols = {}
        for inst_id, signal in signals.items():
            inst = self._get_instance(inst_id)
            vols[inst_id] = self._estimate_strategy_vol(inst)

        total_inv_vol = sum(1/v for v in vols.values() if v > 0)
        allocations = {}
        for inst_id, vol in vols.items():
            if vol > 0:
                # 基础分配 = 波动率倒数权重
                base_pct = (1/vol) / total_inv_vol

                # 绩效调整: 近期表现好的策略额外加成
                perf_mult = limits.strategy_allocations.get(inst_id, 0.5) + 0.5

                # 相关性调整
                corr_mult = limits.correlation_adjusted_exposure

                final_pct = base_pct * perf_mult * corr_mult
                allocations[inst_id] = Allocation(
                    position_pct=min(final_pct, limits.max_position_pct)
                )

        return allocations

    def _resolve_conflicts(self, signals):
        """
        信号冲突仲裁

        同一交易对的多个信号:
        1. 方向一致 → 取最高置信度
        2. 方向矛盾 → 置信度差 > 0.3 则取高者；否则取消信号（观望）
        """
        by_symbol = {}
        for inst_id, sig in signals.items():
            symbol = self._get_instance(inst_id).symbol
            by_symbol.setdefault(symbol, []).append((inst_id, sig))

        resolved = {}
        for symbol, entries in by_symbol.items():
            if len(entries) == 1:
                resolved[entries[0][0]] = entries[0][1]
                continue

            # 按置信度排序
            sorted_entries = sorted(entries, key=lambda x: x[1].confidence, reverse=True)
            best_id, best_sig = sorted_entries[0]

            for inst_id, sig in sorted_entries[1:]:
                if sig.direction == best_sig.direction:
                    # 同方向：保留各自信号
                    resolved[inst_id] = sig
                elif abs(best_sig.confidence - sig.confidence) > 0.3:
                    # 反方向但置信度差距大：弱方取消
                    resolved[inst_id] = AlphaSignal(direction=0, strength=0,
                                                     confidence=0, factors={},
                                                     regime=sig.regime,
                                                     timestamp=sig.timestamp)
                else:
                    # 反方向且置信度接近：都取消（市场方向不明）
                    resolved[inst_id] = AlphaSignal(direction=0, strength=0,
                                                     confidence=0, factors={},
                                                     regime=sig.regime,
                                                     timestamp=sig.timestamp)
                    resolved[best_id] = resolved[inst_id]

            if best_id not in resolved:
                resolved[best_id] = best_sig

        return resolved
```

---

### 模块 6：动态资金管理 (Dynamic Capital Allocation)

#### 亮点：资金自动流向最优策略

```python
class DynamicAllocator:
    """
    策略轮动 + 动态资金分配

    核心算法: Modified Momentum + Mean Reversion hybrid
    - 短期 (7天): 关注策略的 Sharpe Ratio 趋势
    - 中期 (30天): 关注累计收益与回撤比
    - 均值回归约束: 防止「追涨杀跌」——不会因为一个策略短期暴赚就 all-in
    """

    def rebalance(self, pool: FundPool,
                   instances: list[StrategyInstance]) -> dict[str, float]:
        scores = {}
        for inst in instances:
            if inst.trade_count < 5:
                scores[inst.id] = 0.5  # 新策略给予中性分
                continue

            # 短期动量 (近 7 天 Sharpe)
            short_sharpe = self._rolling_sharpe(inst, days=7)

            # 中期稳定性 (近 30 天 Calmar)
            mid_calmar = self._rolling_calmar(inst, days=30)

            # 均值回归约束 (避免过拟合近期表现)
            long_avg = self._long_term_avg_score(inst, days=90)
            reversion_penalty = max(0, (short_sharpe - long_avg) * 0.3)

            scores[inst.id] = (
                short_sharpe * 0.4 +
                mid_calmar * 0.4 -
                reversion_penalty * 0.2
            )

        # 归一化 → 资金分配比例
        total = sum(max(s, 0.1) for s in scores.values())  # 最低 10% 保底
        allocations = {
            inst_id: max(score, 0.1) / total
            for inst_id, score in scores.items()
        }

        return allocations
```

**实际场景**：
- Q1 趋势行情：海龟策略 Sharpe 2.5 → 自动获得 40% 资金分配
- Q2 转入震荡：海龟 Sharpe 降至 0.3，RSI 策略 Sharpe 升至 1.8 → 资金自动从海龟流向 RSI
- 全程无需人工干预

---

## 四、方案亮点与独特竞争力总结

### 亮点 1：「信号工厂」— 从粗暴信号到精细决策

| | 传统方案 | BQT |
|---|---------|-----|
| 信号 | +1 / -1 | 方向 + 强度(0~1) + 置信度(0~1) |
| 仓位 | 固定比例 | 信号强度 × 风险预算 → 动态仓位 |
| 开仓条件 | 任何信号都开 | 置信度 > 阈值才开，弱信号观望 |
| 多策略 | 各自独立 | 冲突仲裁 + 加权融合 |

> **护城河**：大多数开源/零售量化平台停留在简单信号阶段。多因子融合 + 置信度评分是机构级能力的下沉。

### 亮点 2：「自适应风控」— 活的风控系统

传统风控 = 写死的阈值 + 触发后全停。BQT 的风控是活的：

- **动态阈值**：波动率高时自动放宽止损（避免被「洗」出局）、缩小仓位（控制绝对损失）
- **预测性保护**：在回撤真正发生之前，通过 4 维信号（波动率突增、流动性枯竭、盈利回吐加速、连亏模式）提前预警和减仓
- **梯度响应**：不是非黑即白的「全停/全跑」，而是「监控→收紧止损→减仓50%→暂停」的梯度响应

> **护城河**：自适应风控需要大量的市场微观结构知识和回测验证。这是最难被复制的部分。

### 亮点 3：「策略编排」— 统一指挥的协同军团

这是整套方案最大的差异化：

- **信号冲突仲裁**：两个策略方向矛盾时，不是两个都执行，而是比较置信度后做出统一决策
- **风险平价分配**：资金不是等分给每个策略，而是按波动率反向加权，确保每个策略贡献相同的风险
- **策略轮动**：自动将资金从表现差的策略调配到表现好的策略
- **市况感知**：趋势行情自动加重趋势策略权重，震荡行情自动切换到均值回归

> **护城河**：多策略编排是对冲基金级别的系统架构。零售量化平台几乎不做这个层面的优化。

### 亮点 4：「智能执行」— 省下的每一个基点都是利润

- **自动选择执行算法**：小单直接市价、中单 TWAP 拆分、大单冰山隐藏
- **执行质量追踪**：每笔交易记录 Implementation Shortfall，持续优化
- **反 MEV/抢跑保护**：冰山订单隐藏真实意图

> **护城河**：执行优化在加密市场尤其重要（24/7 运行、MEV 风险、流动性碎片化）。

### 亮点 5：「市况分类」— 让策略知道现在用什么打法

大多数量化系统在所有市场环境下使用相同参数。BQT 的 Regime Detector 实现：

- 4 种市况自动识别（趋势上涨/趋势下跌/区间震荡/高波乱市）
- 每种市况自动调整因子权重和策略选择
- 避免在震荡市用趋势策略（最常见的亏损原因）

---

## 五、技术实现路线图

### Phase 3A — Alpha Engine + Regime Detector
- 多因子信号合成框架
- 信号强度 / 置信度评分
- 市况四象限分类器
- 多时间框架一致性验证

### Phase 3B — Adaptive Risk Engine
- 动态波动率调整阈值
- 跨策略相关性监控
- 回撤预测器（4 维信号）
- 梯度响应机制

### Phase 3C — Smart Execution
- TWAP / VWAP 拆单执行
- 冰山订单
- 限价单管理（自动挂单/撤单）
- 执行质量分析报告

### Phase 3D — Strategy Orchestrator
- 信号冲突仲裁
- 风险平价资金分配
- 策略轮动引擎
- 统一仪表盘（策略协同视图）

---

## 六、为什么这套方案难以被复制

1. **系统性**：不是单点优化，而是从信号生成→风控→执行→资金分配的完整闭环。每个模块单独拿出来都有价值，但组合在一起产生 1+1>2 的协同效应。

2. **知识密度**：融合了机构量化（多因子、风险平价）、市场微观结构（执行算法、流动性分析）、和加密市场特有逻辑（24/7、高波动、MEV 防护）三个领域的知识。

3. **数据飞轮**：策略表现数据 → 训练 Regime Detector → 优化资金分配 → 更好的组合表现 → 更多数据。使用越久，系统越智能。

4. **工程复杂度**：实时多策略编排、动态风控、执行算法的并发协调，需要稳健的工程基础设施。在现有架构（异步调度器 + 三层风控 + 策略注册表）上扩展是自然演进，但从零搭建的门槛很高。

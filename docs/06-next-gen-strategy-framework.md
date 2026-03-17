# BQT 下一代策略框架设计方案

> 版本: v2.0 | 设计日期: 2026-03-17 | 面向: 策略研发团队 & 系统架构师
>
> 基于 BQT v1.0 现有架构，设计全面升级的策略框架。

---

## 目录

1. [现状分析与升级动机](#1-现状分析与升级动机)
2. [总体架构：五层引擎模型](#2-总体架构五层引擎模型)
3. [策略组合引擎](#3-策略组合引擎)
4. [多周期共振系统](#4-多周期共振系统)
5. [自适应参数系统](#5-自适应参数系统)
6. [高级仓位管理系统](#6-高级仓位管理系统)
7. [市场状态检测引擎](#7-市场状态检测引擎)
8. [五大引擎协同工作流](#8-五大引擎协同工作流)
9. [竞品对比与独特竞争力](#9-竞品对比与独特竞争力)
10. [实施路径与里程碑](#10-实施路径与里程碑)

---

## 1. 现状分析与升级动机

### 1.1 现有系统能力边界

BQT v1.0 已经实现了一个可工作的量化交易系统骨架，核心能力包括：

| 能力维度 | 现有实现 | 局限性 |
|---------|---------|--------|
| 策略模式 | 5 个独立策略，每个策略一个 `signal_func` 返回 BUY/SELL/HOLD | 策略之间完全孤立，无法联合决策 |
| 时间周期 | 单一 timeframe（配置文件固定为 4h） | 无法利用多周期共振信号 |
| 参数管理 | 硬编码默认参数 + 配置文件覆盖 | 参数静态，无法根据市场动态调整 |
| 仓位管理 | ATR 固定比例 + Kelly 公式 | 无金字塔加仓、网格、自适应止损等高级能力 |
| 市场识别 | 无 | 不区分趋势/震荡/高波动，所有市况用同一策略 |
| 风控模式 | 单层 RiskController（日亏损 + 回撤 + 频率限制） | 无策略组合层面的风控协调 |

**核心问题**：v1.0 的每个策略独立运行，像五个互不认识的交易员各干各的。v2.0 要让它们变成一个有协作、有分工、有纪律的交易团队。

### 1.2 升级核心目标

```
v1.0: 独立策略 → 单一信号 → 固定仓位 → 执行
v2.0: 市场识别 → 策略选择 → 多策略投票 → 多周期确认 → 动态仓位 → 智能执行
```

**量化目标**：

| 指标 | v1.0 估计 | v2.0 目标 | 提升方式 |
|------|----------|----------|---------|
| 组合夏普比率 | 0.8-1.2 | 1.8-2.5 | 策略组合 + 市场自适应 |
| 最大回撤 | 15-25% | 8-12% | 动态仓位 + 状态切换 |
| 年化收益 | 20-40% | 40-80% | 多周期共振 + 自适应参数 |
| 信号准确率 | 35-45% | 50-60% | 投票机制 + 置信度加权 |
| 参数失效检测 | 无 | <4h 发现 | Walk-Forward 实时监控 |

---

## 2. 总体架构：五层引擎模型

### 2.1 架构全景

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BQT v2.0 下一代策略框架                          │
│                                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │ Layer 5     │  │  市场状态     │  │             │  │              │ │
│  │ 市场状态    │──│  检测引擎     │──│  趋势/震荡/  │──│  输出：当前   │ │
│  │ 检测引擎    │  │  MarketRegime│  │  高波动分类  │  │  市场状态    │ │
│  └──────┬──────┘  └──────────────┘  └─────────────┘  └──────┬───────┘ │
│         │                                                     │         │
│         v                                                     v         │
│  ┌─────────────┐  ┌──────────────────────────────────────────────────┐ │
│  │ Layer 4     │  │                                                  │ │
│  │ 自适应参数  │  │  根据市场状态 → 选择策略子集 → 调整参数范围       │ │
│  │ 系统        │  │  Walk-Forward 实时校准 → 贝叶斯参数更新           │ │
│  └──────┬──────┘  └──────────────────────────────────────────────────┘ │
│         │                                                               │
│         v                                                               │
│  ┌─────────────┐  ┌──────────────────────────────────────────────────┐ │
│  │ Layer 3     │  │                                                  │ │
│  │ 多周期共振  │  │  高周期确认方向 → 中周期确认时机 → 低周期精确入场 │ │
│  │ 系统        │  │  输出：共振分数 0-100                            │ │
│  └──────┬──────┘  └──────────────────────────────────────────────────┘ │
│         │                                                               │
│         v                                                               │
│  ┌─────────────┐  ┌──────────────────────────────────────────────────┐ │
│  │ Layer 2     │  │                                                  │ │
│  │ 策略组合    │  │  多策略投票 → 置信度加权 → 信号合成 → 最终决策   │ │
│  │ 引擎        │  │  输出：合成信号 + 置信度                         │ │
│  └──────┬──────┘  └──────────────────────────────────────────────────┘ │
│         │                                                               │
│         v                                                               │
│  ┌─────────────┐  ┌──────────────────────────────────────────────────┐ │
│  │ Layer 1     │  │                                                  │ │
│  │ 高级仓位    │  │  置信度 → 仓位比例 → 金字塔/网格执行 → 智能止损  │ │
│  │ 管理系统    │  │  输出：精确的仓位指令                             │ │
│  └─────────────┘  └──────────────────────────────────────────────────┘ │
│                                                                         │
│                              │                                          │
│                              v                                          │
│                   ┌────────────────────┐                                │
│                   │  OMS + RiskEngine  │                                │
│                   │  (现有 v1.0 模块)  │                                │
│                   └────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流方向

```
市场数据 (Kafka)
    │
    ├──→ 市场状态检测引擎 (Layer 5)
    │        │
    │        └──→ 当前状态: TRENDING_UP / TRENDING_DOWN / RANGING / VOLATILE
    │
    ├──→ 自适应参数系统 (Layer 4)
    │        │
    │        └──→ 为每个策略输出当前最优参数集
    │
    ├──→ 多周期共振系统 (Layer 3)
    │        │
    │        └──→ 共振分数 + 方向确认
    │
    ├──→ 策略组合引擎 (Layer 2)
    │        │
    │        └──→ 合成信号 + 置信度
    │
    └──→ 高级仓位管理系统 (Layer 1)
             │
             └──→ 精确仓位指令 → OMS 执行
```

**独特竞争力**：现有竞品（3Commas, Pionex, OKX Signal Bot）的策略是"平面"的——一个策略配一个参数集运行。BQT v2.0 是"立体"的——五层引擎垂直协作，每一层为下一层提供增强信息。这种架构使得即使单个策略不变，整体系统的决策质量也能因为上下文信息的丰富而大幅提升。

---

## 3. 策略组合引擎

### 3.1 设计哲学

单策略的致命弱点：**在其不适用的市况下会产生持续亏损**。MA 交叉在震荡市中反复止损，RSI 在强趋势中过早反转。组合引擎的核心不是简单叠加，而是让策略之间形成互补和验证。

### 3.2 三种组合模式

#### 模式一：投票制（Ensemble Voting）

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

class SignalType(Enum):
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2

@dataclass
class StrategyVote:
    """单个策略的投票结果"""
    strategy_name: str
    signal: SignalType
    confidence: float          # 0.0-1.0，该策略对自己信号的确信度
    weight: float              # 该策略在当前市场状态下的权重
    reasoning: dict            # 决策依据（用于审计和调试）

@dataclass
class EnsembleConfig:
    """组合投票配置"""
    min_agreement_ratio: float = 0.6      # 最低同意比例（加权后）
    min_total_confidence: float = 0.5     # 最低总置信度
    veto_threshold: float = 0.8           # 任一策略置信度超此值可一票否决
    max_strategies_per_vote: int = 5      # 每次投票最多参与的策略数

class EnsembleVotingEngine:
    """
    加权投票组合引擎

    独特设计：
    1. 动态权重——权重不是固定的，而是根据策略近期表现实时调整
    2. 置信度衰减——策略信号越久未被市场验证，置信度越低
    3. 一票否决——高置信度的反向信号可以否决多数票
    4. 市场状态权重——同一策略在不同市况下权重不同
    """

    def __init__(self, config: EnsembleConfig):
        self.config = config
        # 策略近期表现追踪（滑动窗口）
        self._performance_window: dict[str, list[float]] = {}
        # 策略-市场状态权重矩阵
        self._regime_weights: dict[str, dict[str, float]] = {
            # strategy_name -> {regime -> weight}
            "ma_crossover":       {"trending_up": 1.2, "trending_down": 1.2,
                                   "ranging": 0.3, "volatile": 0.5},
            "macd":               {"trending_up": 1.0, "trending_down": 1.0,
                                   "ranging": 0.4, "volatile": 0.6},
            "bollinger_breakout": {"trending_up": 0.8, "trending_down": 0.8,
                                   "ranging": 0.6, "volatile": 1.3},
            "rsi_momentum":       {"trending_up": 0.5, "trending_down": 0.5,
                                   "ranging": 1.2, "volatile": 0.8},
            "turtle":             {"trending_up": 1.4, "trending_down": 1.4,
                                   "ranging": 0.2, "volatile": 0.7},
        }

    def vote(
        self,
        votes: list[StrategyVote],
        current_regime: str,
    ) -> tuple[SignalType, float, dict]:
        """
        执行加权投票

        Returns:
            (最终信号, 合成置信度, 决策详情)
        """
        # 1. 应用市场状态权重
        adjusted_votes = []
        for v in votes:
            regime_weight = self._regime_weights.get(
                v.strategy_name, {}
            ).get(current_regime, 1.0)

            # 性能动态调整：近期表现好的策略获得更高权重
            perf_multiplier = self._get_performance_multiplier(v.strategy_name)

            effective_weight = v.weight * regime_weight * perf_multiplier
            adjusted_votes.append((v, effective_weight))

        # 2. 检查一票否决
        for v, w in adjusted_votes:
            if v.confidence >= self.config.veto_threshold:
                # 如果一个高置信度信号与多数方向相反，触发否决
                majority_direction = self._get_majority_direction(adjusted_votes)
                if v.signal.value * majority_direction < 0:
                    return SignalType.HOLD, 0.0, {
                        "reason": "veto",
                        "veto_by": v.strategy_name,
                        "veto_confidence": v.confidence,
                    }

        # 3. 加权投票计算
        total_weight = sum(w for _, w in adjusted_votes)
        if total_weight == 0:
            return SignalType.HOLD, 0.0, {"reason": "no_weight"}

        weighted_signal = sum(
            v.signal.value * v.confidence * w
            for v, w in adjusted_votes
        ) / total_weight

        # 4. 计算同意比例
        if weighted_signal > 0:
            agreement = sum(
                w for v, w in adjusted_votes if v.signal.value > 0
            ) / total_weight
        elif weighted_signal < 0:
            agreement = sum(
                w for v, w in adjusted_votes if v.signal.value < 0
            ) / total_weight
        else:
            agreement = 0.0

        # 5. 判定最终信号
        if agreement < self.config.min_agreement_ratio:
            return SignalType.HOLD, 0.0, {
                "reason": "insufficient_agreement",
                "agreement": agreement,
            }

        # 6. 计算合成置信度
        composite_confidence = min(
            abs(weighted_signal),
            agreement,
        )

        if composite_confidence < self.config.min_total_confidence:
            return SignalType.HOLD, composite_confidence, {
                "reason": "low_confidence",
            }

        # 7. 映射到信号类型
        if weighted_signal > 1.0:
            final_signal = SignalType.STRONG_BUY
        elif weighted_signal > 0.3:
            final_signal = SignalType.BUY
        elif weighted_signal < -1.0:
            final_signal = SignalType.STRONG_SELL
        elif weighted_signal < -0.3:
            final_signal = SignalType.SELL
        else:
            final_signal = SignalType.HOLD

        return final_signal, composite_confidence, {
            "reason": "consensus",
            "weighted_signal": weighted_signal,
            "agreement": agreement,
            "votes_detail": [
                {
                    "strategy": v.strategy_name,
                    "signal": v.signal.name,
                    "confidence": v.confidence,
                    "effective_weight": w,
                }
                for v, w in adjusted_votes
            ],
        }

    def update_performance(self, strategy_name: str, pnl: float):
        """更新策略近期表现，用于动态权重调整"""
        if strategy_name not in self._performance_window:
            self._performance_window[strategy_name] = []
        window = self._performance_window[strategy_name]
        window.append(pnl)
        if len(window) > 50:  # 保留最近 50 笔
            window.pop(0)

    def _get_performance_multiplier(self, strategy_name: str) -> float:
        """根据近期表现计算权重倍数"""
        window = self._performance_window.get(strategy_name, [])
        if len(window) < 10:
            return 1.0  # 样本不足，不调整

        win_rate = sum(1 for p in window if p > 0) / len(window)
        # 胜率 50% 时 multiplier=1.0，60% 时 1.3，40% 时 0.7
        return 0.1 + win_rate * 2.0

    def _get_majority_direction(
        self, adjusted_votes: list[tuple[StrategyVote, float]]
    ) -> int:
        """获取多数方向"""
        weighted_sum = sum(
            v.signal.value * w for v, w in adjusted_votes
        )
        if weighted_sum > 0:
            return 1
        elif weighted_sum < 0:
            return -1
        return 0
```

**独特竞争力**：3Commas 的 DCA Bot 只能运行单一策略。Pionex 的网格机器人不涉及策略组合。BQT v2.0 的投票引擎实现了：
- **市场状态感知权重**：趋势策略在趋势市获得高权重，在震荡市被自动降权
- **一票否决机制**：防止多个弱信号压倒一个强反向信号
- **性能自适应**：近期表现差的策略自动被降权，无需人工干预

#### 模式二：级联制（Cascading Filter）

```python
@dataclass
class CascadeStage:
    """级联阶段定义"""
    name: str
    strategy_func: Callable
    pass_condition: str      # "agree" = 信号方向一致, "not_oppose" = 不反对即可
    min_confidence: float    # 该阶段最低置信度要求

class CascadeEngine:
    """
    级联过滤组合引擎

    设计理念：信号必须通过层层过滤才能最终执行。
    类似于军队的指挥链——连长建议，营长审核，团长批准。

    级联示例：
    Stage 1: 趋势过滤器（MA交叉判断大方向）
      ↓ 通过
    Stage 2: 动量确认器（MACD/RSI 确认动量）
      ↓ 通过
    Stage 3: 入场精确器（布林带突破找精确入场点）
      ↓ 通过
    Stage 4: 风险校验器（ATR + 波动率检查仓位可行性）
      ↓ 通过
    最终信号执行
    """

    def __init__(self, stages: list[CascadeStage]):
        self.stages = stages

    def evaluate(
        self, market_data: dict, context: dict
    ) -> tuple[SignalType, float, list[dict]]:
        """
        逐级评估

        Returns:
            (最终信号, 最终置信度, 各阶段评估详情)
        """
        current_signal = None
        current_confidence = 1.0
        stage_reports = []

        for stage in self.stages:
            result = stage.strategy_func(market_data, context)
            stage_signal = result["signal"]
            stage_confidence = result["confidence"]

            report = {
                "stage": stage.name,
                "signal": stage_signal.name,
                "confidence": stage_confidence,
                "passed": False,
            }

            # 第一阶段确定方向
            if current_signal is None:
                if stage_confidence >= stage.min_confidence:
                    current_signal = stage_signal
                    current_confidence = stage_confidence
                    report["passed"] = True
                else:
                    stage_reports.append(report)
                    return SignalType.HOLD, 0.0, stage_reports
            else:
                # 后续阶段验证/过滤
                if stage.pass_condition == "agree":
                    # 方向必须一致
                    if stage_signal.value * current_signal.value > 0:
                        current_confidence *= stage_confidence
                        report["passed"] = True
                    else:
                        stage_reports.append(report)
                        return SignalType.HOLD, 0.0, stage_reports

                elif stage.pass_condition == "not_oppose":
                    # 不主动反对即可（HOLD也算通过）
                    if stage_signal.value * current_signal.value >= 0:
                        current_confidence *= max(stage_confidence, 0.5)
                        report["passed"] = True
                    else:
                        # 反对但置信度低可以忽略
                        if stage_confidence < stage.min_confidence:
                            current_confidence *= 0.7  # 惩罚但不否决
                            report["passed"] = True
                            report["note"] = "weak_opposition_ignored"
                        else:
                            stage_reports.append(report)
                            return SignalType.HOLD, 0.0, stage_reports

            stage_reports.append(report)

        return current_signal or SignalType.HOLD, current_confidence, stage_reports
```

#### 模式三：动态轮换制（Strategy Rotation）

```python
class StrategyRotationEngine:
    """
    策略动态轮换引擎

    核心逻辑：
    - 维护每个策略的"健康分数"（综合近期收益、夏普、回撤）
    - 每个评估周期（默认24h），重新排名所有策略
    - 只激活排名前 N 的策略
    - 新激活策略有"热身期"（减半仓位运行48h）

    独特设计：
    - 不是简单的"好用就用、不好就停"
    - 引入"冷却期"：被停用的策略必须等待至少1个评估周期才能重新激活
    - 引入"多样性约束"：激活策略必须覆盖至少2种策略类型（趋势+非趋势）
    """

    STRATEGY_TYPES = {
        "ma_crossover": "trend",
        "macd": "trend",
        "bollinger_breakout": "breakout",
        "rsi_momentum": "mean_reversion",
        "turtle": "trend",
    }

    def __init__(
        self,
        evaluation_interval_hours: int = 24,
        max_active_strategies: int = 3,
        warmup_hours: int = 48,
        cooldown_periods: int = 1,
        min_type_diversity: int = 2,
    ):
        self.evaluation_interval_hours = evaluation_interval_hours
        self.max_active_strategies = max_active_strategies
        self.warmup_hours = warmup_hours
        self.cooldown_periods = cooldown_periods
        self.min_type_diversity = min_type_diversity

        self._strategy_health: dict[str, float] = {}
        self._active_strategies: set[str] = set()
        self._cooldown_until: dict[str, int] = {}  # strategy -> epoch
        self._warmup_until: dict[str, int] = {}    # strategy -> epoch

    def evaluate_and_rotate(
        self,
        strategy_metrics: dict[str, dict],  # name -> {sharpe, return, drawdown, ...}
        current_epoch: int,
    ) -> dict[str, float]:
        """
        评估并轮换策略

        Returns:
            {strategy_name: position_scale_factor}
            factor=1.0 正常, 0.5 热身中, 0.0 停用
        """
        # 1. 计算健康分数
        for name, metrics in strategy_metrics.items():
            self._strategy_health[name] = self._compute_health_score(metrics)

        # 2. 排名（排除冷却中的策略）
        eligible = {
            name: score
            for name, score in self._strategy_health.items()
            if self._cooldown_until.get(name, 0) <= current_epoch
        }
        ranked = sorted(eligible.items(), key=lambda x: x[1], reverse=True)

        # 3. 选择激活策略（满足多样性约束）
        new_active = set()
        type_coverage = set()

        for name, score in ranked:
            if len(new_active) >= self.max_active_strategies:
                break
            strategy_type = self.STRATEGY_TYPES.get(name, "unknown")

            # 多样性检查：前 min_type_diversity 个位置必须是不同类型
            if len(new_active) < self.min_type_diversity:
                if strategy_type in type_coverage and len(type_coverage) < self.min_type_diversity:
                    continue  # 跳过重复类型，直到满足多样性要求

            new_active.add(name)
            type_coverage.add(strategy_type)

        # 如果多样性未满足，放宽约束
        if len(type_coverage) < self.min_type_diversity:
            for name, score in ranked:
                strategy_type = self.STRATEGY_TYPES.get(name, "unknown")
                if strategy_type not in type_coverage:
                    new_active.add(name)
                    type_coverage.add(strategy_type)
                    if len(type_coverage) >= self.min_type_diversity:
                        break

        # 4. 处理新激活和停用
        newly_activated = new_active - self._active_strategies
        newly_deactivated = self._active_strategies - new_active

        for name in newly_activated:
            self._warmup_until[name] = current_epoch + self.warmup_hours

        for name in newly_deactivated:
            self._cooldown_until[name] = current_epoch + (
                self.cooldown_periods * self.evaluation_interval_hours
            )

        self._active_strategies = new_active

        # 5. 生成仓位缩放因子
        result = {}
        for name in strategy_metrics:
            if name not in new_active:
                result[name] = 0.0
            elif self._warmup_until.get(name, 0) > current_epoch:
                result[name] = 0.5  # 热身中，半仓
            else:
                result[name] = 1.0

        return result

    def _compute_health_score(self, metrics: dict) -> float:
        """
        策略健康分数计算

        权重分配：
        - 近期夏普比率: 40%
        - 近期收益率: 25%
        - 最大回撤: 20%（越小越好）
        - 信号质量: 15%（胜率 * 盈亏比）
        """
        sharpe_score = max(0, min(metrics.get("sharpe_ratio", 0) / 3.0, 1.0))
        return_score = max(0, min(
            (metrics.get("annualized_return_pct", 0) + 20) / 120, 1.0
        ))
        dd_score = max(0, 1.0 - abs(metrics.get("max_drawdown_pct", 0)) / 30)
        quality_score = (
            metrics.get("win_rate_pct", 0) / 100 *
            min(metrics.get("profit_loss_ratio", 0) / 3.0, 1.0)
        )

        return (
            sharpe_score * 0.40 +
            return_score * 0.25 +
            dd_score * 0.20 +
            quality_score * 0.15
        )
```

### 3.3 置信度评分体系

每个策略不再仅输出 BUY/SELL/HOLD，而是输出带置信度的信号：

```python
@dataclass
class EnrichedSignal:
    """增强型信号（v2.0 核心数据结构）"""
    signal_type: SignalType
    confidence: float                # 0.0-1.0
    timeframe: str                   # 产生此信号的时间周期
    strategy_name: str
    entry_zone: tuple[float, float]  # 建议入场价格区间
    stop_loss: float                 # 建议止损价
    take_profit: list[float]         # 多级止盈价
    max_hold_bars: int               # 建议最大持有K线数
    regime_alignment: float          # 与当前市场状态的一致性 0-1

    # 置信度来源分解
    technical_confidence: float      # 技术指标置信度
    volume_confidence: float         # 成交量确认度
    trend_alignment: float           # 趋势一致性
    regime_confidence: float         # 市场状态确认度
```

**置信度计算公式**（以 MA 交叉策略为例）：

```python
def compute_ma_crossover_confidence(
    df: pd.DataFrame,
    fast_ema: pd.Series,
    slow_ema: pd.Series,
    current_regime: str,
) -> float:
    """
    MA交叉策略置信度计算

    4个维度综合：
    1. 交叉强度（均线间距的变化速率）
    2. 成交量确认（交叉时成交量是否放大）
    3. 趋势一致性（ADX是否确认趋势存在）
    4. 市场状态匹配度
    """
    current = df.iloc[-1]
    price = current["close"]

    # 维度1: 交叉强度 (均线间距占价格的百分比)
    spread_pct = abs(fast_ema.iloc[-1] - slow_ema.iloc[-1]) / price
    spread_velocity = spread_pct - abs(
        fast_ema.iloc[-2] - slow_ema.iloc[-2]
    ) / df["close"].iloc[-2]
    crossover_strength = min(spread_velocity * 1000, 1.0)  # 归一化

    # 维度2: 成交量确认
    volume_ma = df["volume"].rolling(20).mean().iloc[-1]
    volume_ratio = current["volume"] / volume_ma if volume_ma > 0 else 0
    volume_conf = min(volume_ratio / 2.0, 1.0)  # 2倍均量时满分

    # 维度3: 趋势强度 (使用ADX代理：用DI+/DI-差值)
    high_low_range = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
    price_range = abs(df["close"].iloc[-1] - df["close"].iloc[-14])
    trend_ratio = price_range / (high_low_range * 14) if high_low_range > 0 else 0
    trend_conf = min(trend_ratio * 2, 1.0)

    # 维度4: 市场状态匹配
    regime_match = {
        "trending_up": 0.9 if fast_ema.iloc[-1] > slow_ema.iloc[-1] else 0.3,
        "trending_down": 0.9 if fast_ema.iloc[-1] < slow_ema.iloc[-1] else 0.3,
        "ranging": 0.2,
        "volatile": 0.4,
    }.get(current_regime, 0.5)

    # 加权合成
    confidence = (
        crossover_strength * 0.30 +
        volume_conf * 0.25 +
        trend_conf * 0.25 +
        regime_match * 0.20
    )

    return round(max(0.0, min(confidence, 1.0)), 4)
```

---

## 4. 多周期共振系统

### 4.1 设计原理

**核心洞察**：同一个交易信号如果在多个时间周期上同时出现，其可靠性显著高于单周期信号。这在加密市场中尤为重要——由于散户噪声多，低周期假信号频繁，但高周期信号的稳定性更强。

```
周线趋势看方向  →  "BTC 处于周线级别上涨趋势"
日线确认结构    →  "日线在回踩EMA25后企稳"
4H 找入场时机   →  "4H MACD 金叉 + 量能放大"
1H 精确入场     →  "1H 突破前高，确认入场"

四个周期同方向 = 高共振分数 = 高置信度 = 大仓位
```

### 4.2 共振评分引擎

```python
from dataclasses import dataclass

@dataclass
class TimeframeSignal:
    """单一时间周期的信号"""
    timeframe: str           # "1w", "1d", "4h", "1h", "15m"
    direction: int           # 1=看多, -1=看空, 0=中性
    strength: float          # 0.0-1.0 信号强度
    trend_alignment: float   # 与更高周期趋势的一致性

@dataclass
class ConfluenceResult:
    """共振评估结果"""
    confluence_score: float  # 0-100 共振分数
    direction: int           # 最终方向
    aligned_timeframes: int  # 同向的时间周期数
    timeframe_details: list[TimeframeSignal]
    recommended_action: str  # "aggressive_entry" / "normal_entry" / "wait" / "no_trade"

class MultiTimeframeConfluenceEngine:
    """
    多周期共振引擎

    独特设计点：
    1. 层级权重递减——高周期权重高，低周期权重低（符合"大周期定方向"的交易逻辑）
    2. 对齐分数而非简单计数——不是"几个周期同向"而是"加权后的方向一致性"
    3. 自适应周期选择——根据策略类型和市场波动率自动选择合适的分析周期组合
    4. 冲突惩罚——高低周期方向相反时施加额外惩罚，而非简单抵消
    """

    # 时间周期权重（高周期 > 低周期）
    TIMEFRAME_WEIGHTS = {
        "1w":  0.30,   # 周线决定大方向
        "1d":  0.25,   # 日线确认结构
        "4h":  0.20,   # 4H 找节奏
        "1h":  0.15,   # 1H 找入场
        "15m": 0.10,   # 15M 精确点位
    }

    # 策略类型推荐的周期组合
    STRATEGY_TIMEFRAMES = {
        "trend_following": ["1w", "1d", "4h", "1h"],
        "mean_reversion":  ["1d", "4h", "1h", "15m"],
        "breakout":        ["1d", "4h", "1h"],
        "scalping":        ["4h", "1h", "15m"],
    }

    def evaluate_confluence(
        self,
        timeframe_signals: list[TimeframeSignal],
        strategy_type: str = "trend_following",
        volatility_regime: str = "normal",
    ) -> ConfluenceResult:
        """
        评估多周期共振

        核心算法：
        1. 按策略类型筛选相关周期
        2. 计算加权方向分数
        3. 检测高低周期冲突
        4. 生成共振分数和推荐动作
        """
        # 1. 筛选相关周期
        relevant_tfs = self.STRATEGY_TIMEFRAMES.get(
            strategy_type, ["1d", "4h", "1h"]
        )
        relevant_signals = [
            s for s in timeframe_signals if s.timeframe in relevant_tfs
        ]

        if not relevant_signals:
            return ConfluenceResult(
                confluence_score=0, direction=0,
                aligned_timeframes=0, timeframe_details=[],
                recommended_action="no_trade",
            )

        # 2. 加权方向分数
        total_weight = 0
        weighted_direction = 0
        aligned_count = 0

        for sig in relevant_signals:
            weight = self.TIMEFRAME_WEIGHTS.get(sig.timeframe, 0.1)
            weighted_direction += sig.direction * sig.strength * weight
            total_weight += weight

        if total_weight > 0:
            normalized_direction = weighted_direction / total_weight
        else:
            normalized_direction = 0

        # 确定主方向
        if normalized_direction > 0.1:
            primary_direction = 1
        elif normalized_direction < -0.1:
            primary_direction = -1
        else:
            primary_direction = 0

        # 3. 计算同向周期数和冲突惩罚
        conflict_penalty = 0
        for sig in relevant_signals:
            if sig.direction == primary_direction and primary_direction != 0:
                aligned_count += 1
            elif sig.direction * primary_direction < 0:
                # 高周期与主方向冲突——严重惩罚
                tf_weight = self.TIMEFRAME_WEIGHTS.get(sig.timeframe, 0.1)
                conflict_penalty += tf_weight * sig.strength * 30  # 惩罚系数

        # 4. 生成共振分数 (0-100)
        base_score = abs(normalized_direction) * 100
        alignment_bonus = (aligned_count / len(relevant_signals)) * 20
        raw_score = base_score + alignment_bonus - conflict_penalty

        # 波动率调整：高波动时降低共振分数（信号不可靠）
        volatility_factor = {
            "low": 1.1,
            "normal": 1.0,
            "high": 0.8,
            "extreme": 0.6,
        }.get(volatility_regime, 1.0)

        confluence_score = max(0, min(100, raw_score * volatility_factor))

        # 5. 推荐动作
        if confluence_score >= 75 and aligned_count >= 3:
            action = "aggressive_entry"
        elif confluence_score >= 55 and aligned_count >= 2:
            action = "normal_entry"
        elif confluence_score >= 35:
            action = "wait"  # 观望，等待更多确认
        else:
            action = "no_trade"

        return ConfluenceResult(
            confluence_score=round(confluence_score, 1),
            direction=primary_direction,
            aligned_timeframes=aligned_count,
            timeframe_details=relevant_signals,
            recommended_action=action,
        )
```

### 4.3 自适应周期选择

```python
class AdaptiveTimeframeSelector:
    """
    根据市场状态自动选择分析周期组合

    关键创新：
    - 高波动期自动切换到更高周期（过滤噪声）
    - 低波动期可以使用更低周期（捕捉微小机会）
    - 避免在周期转换时产生虚假信号
    """

    def select_timeframes(
        self,
        current_volatility: float,      # 当前波动率（ATR/Price 百分比）
        avg_volatility_30d: float,       # 30日平均波动率
        strategy_type: str,
    ) -> list[str]:
        """选择当前最优时间周期组合"""
        vol_ratio = current_volatility / avg_volatility_30d if avg_volatility_30d > 0 else 1

        if vol_ratio > 2.0:
            # 极端波动——只看高周期
            return ["1w", "1d", "4h"]
        elif vol_ratio > 1.5:
            # 高波动——偏向高周期
            return ["1d", "4h", "1h"]
        elif vol_ratio < 0.5:
            # 极低波动——可以看更低周期
            if strategy_type in ("mean_reversion", "scalping"):
                return ["4h", "1h", "15m", "5m"]
            else:
                return ["1d", "4h", "1h", "15m"]
        else:
            # 正常波动——使用策略默认周期
            return MultiTimeframeConfluenceEngine.STRATEGY_TIMEFRAMES.get(
                strategy_type, ["1d", "4h", "1h"]
            )
```

---

## 5. 自适应参数系统

### 5.1 设计哲学

v1.0 的问题：MA 交叉的 fast=7, slow=25 是在回测时优化出的"历史最优参数"。但市场是非稳态的——2025年牛市的最优参数和2026年震荡市的最优参数截然不同。

v2.0 的解决方案：**参数不是固定值，而是一个随市场状态动态更新的分布**。

### 5.2 Walk-Forward 实时优化引擎

```python
import numpy as np
from dataclasses import dataclass

@dataclass
class ParameterRange:
    """参数搜索范围"""
    name: str
    min_val: float
    max_val: float
    step: float
    current_best: float
    distribution: str = "uniform"  # "uniform" / "gaussian"

@dataclass
class WalkForwardWindow:
    """Walk-Forward 窗口定义"""
    train_bars: int      # 训练窗口K线数
    test_bars: int       # 测试窗口K线数
    step_bars: int       # 每次滑动的K线数
    min_trades: int      # 训练集最低交易次数要求

class WalkForwardOptimizer:
    """
    Walk-Forward 实时参数优化引擎

    vs 竞品差异：
    - 3Commas: 参数完全手动设置，无自动优化
    - Freqtrade Hyperopt: 只在离线回测时优化，不能实时调整
    - BQT v2.0: 滚动窗口实时优化 + 贝叶斯更新 + 参数稳定性检测

    核心算法：
    1. 维护一个滑动窗口的训练集
    2. 在训练集上用贝叶斯优化搜索最优参数
    3. 在测试集上验证参数有效性
    4. 如果测试集表现达标，更新实盘参数
    5. 如果连续N个窗口测试不达标，触发"参数失效告警"
    """

    def __init__(
        self,
        window: WalkForwardWindow,
        param_ranges: list[ParameterRange],
        optimization_metric: str = "sharpe_ratio",
        min_improvement_pct: float = 10,       # 新参数必须比旧参数好10%以上才更新
        max_consecutive_failures: int = 3,      # 连续3次测试失败则告警
        parameter_stability_threshold: float = 0.3,  # 参数变化超过30%视为不稳定
    ):
        self.window = window
        self.param_ranges = param_ranges
        self.optimization_metric = optimization_metric
        self.min_improvement_pct = min_improvement_pct
        self.max_consecutive_failures = max_consecutive_failures
        self.parameter_stability_threshold = parameter_stability_threshold

        self._consecutive_failures = 0
        self._parameter_history: list[dict] = []
        self._current_params: dict = {
            p.name: p.current_best for p in param_ranges
        }

    def optimize_step(
        self,
        full_data,                 # 完整历史数据
        backtest_func,             # 回测函数
        current_bar_index: int,    # 当前位置
    ) -> dict:
        """
        执行一步 Walk-Forward 优化

        Returns:
            {
                "action": "update" / "hold" / "alert",
                "new_params": dict,
                "train_metric": float,
                "test_metric": float,
                "stability_warning": bool,
            }
        """
        # 1. 切分训练集和测试集
        train_end = current_bar_index - self.window.test_bars
        train_start = max(0, train_end - self.window.train_bars)
        test_start = train_end
        test_end = current_bar_index

        train_data = full_data.iloc[train_start:train_end]
        test_data = full_data.iloc[test_start:test_end]

        # 2. 在训练集上贝叶斯优化
        best_params, best_train_metric = self._bayesian_optimize(
            train_data, backtest_func
        )

        # 3. 在测试集上验证
        test_metric = self._evaluate_params(
            test_data, backtest_func, best_params
        )

        # 4. 评估当前参数在测试集上的表现（基准）
        current_metric = self._evaluate_params(
            test_data, backtest_func, self._current_params
        )

        # 5. 决策
        improvement = (
            (test_metric - current_metric) / abs(current_metric)
            if current_metric != 0 else 0
        )

        # 检查参数稳定性
        stability_warning = self._check_parameter_stability(best_params)

        if test_metric > 0 and improvement > self.min_improvement_pct / 100:
            # 新参数显著更好——更新
            self._current_params = best_params
            self._parameter_history.append(best_params)
            self._consecutive_failures = 0
            return {
                "action": "update",
                "new_params": best_params,
                "train_metric": best_train_metric,
                "test_metric": test_metric,
                "improvement_pct": improvement * 100,
                "stability_warning": stability_warning,
            }
        elif test_metric > 0:
            # 新参数不够好——保持现有参数
            self._consecutive_failures = 0
            return {
                "action": "hold",
                "new_params": self._current_params,
                "train_metric": best_train_metric,
                "test_metric": test_metric,
                "stability_warning": stability_warning,
            }
        else:
            # 测试失败（负收益）
            self._consecutive_failures += 1
            action = "alert" if (
                self._consecutive_failures >= self.max_consecutive_failures
            ) else "hold"

            return {
                "action": action,
                "new_params": self._current_params,
                "train_metric": best_train_metric,
                "test_metric": test_metric,
                "consecutive_failures": self._consecutive_failures,
                "stability_warning": True,
            }

    def _bayesian_optimize(self, train_data, backtest_func):
        """
        贝叶斯优化搜索最优参数

        使用高斯过程作为代理模型，Expected Improvement 作为采集函数。
        比网格搜索效率高 10-50 倍。
        """
        # 简化版贝叶斯优化（生产环境使用 optuna）
        best_params = None
        best_metric = float("-inf")

        # 先用随机搜索热启动
        for _ in range(20):
            params = {}
            for pr in self.param_ranges:
                if pr.distribution == "gaussian":
                    val = np.random.normal(pr.current_best, (pr.max_val - pr.min_val) / 6)
                    val = max(pr.min_val, min(pr.max_val, val))
                else:
                    val = np.random.uniform(pr.min_val, pr.max_val)
                # 对齐到步长
                val = round(val / pr.step) * pr.step
                params[pr.name] = val

            metric = self._evaluate_params(train_data, backtest_func, params)
            if metric > best_metric:
                best_metric = metric
                best_params = params.copy()

        return best_params or self._current_params, best_metric

    def _evaluate_params(self, data, backtest_func, params) -> float:
        """用指定参数运行回测，返回优化指标"""
        result = backtest_func(data, **params)
        return result.get(self.optimization_metric, 0)

    def _check_parameter_stability(self, new_params: dict) -> bool:
        """检查参数是否发生剧烈变化"""
        if not self._parameter_history:
            return False

        last_params = self._parameter_history[-1]
        for name, new_val in new_params.items():
            old_val = last_params.get(name, new_val)
            if old_val != 0:
                change_pct = abs(new_val - old_val) / abs(old_val)
                if change_pct > self.parameter_stability_threshold:
                    return True  # 参数变化过大
        return False
```

### 5.3 市场状态驱动的参数预设

```python
class RegimeAwareParameterManager:
    """
    市场状态感知的参数管理器

    核心创新：不是在所有参数空间中盲目搜索，
    而是根据当前市场状态缩小搜索范围。

    例如：
    - 趋势市 → MA 策略的均线周期应该偏长（抓大趋势）
    - 震荡市 → RSI 策略的超买超卖阈值应该偏窄（快进快出）
    - 高波动市 → 所有止损应该放宽（避免被扫出）
    """

    # 市场状态 → 参数范围映射
    REGIME_PARAM_PRESETS = {
        "trending_up": {
            "ma_crossover": {
                "fast": ParameterRange("fast", 5, 15, 1, 7),
                "slow": ParameterRange("slow", 20, 50, 1, 25),
            },
            "rsi_momentum": {
                "period": ParameterRange("period", 10, 20, 1, 14),
                "overbought": ParameterRange("overbought", 75, 85, 1, 80),
                "oversold": ParameterRange("oversold", 35, 50, 1, 40),
            },
            "_risk": {
                "stop_loss_atr_mult": ParameterRange("sl_mult", 2.0, 4.0, 0.5, 3.0),
                "take_profit_atr_mult": ParameterRange("tp_mult", 4.0, 8.0, 0.5, 6.0),
            },
        },
        "ranging": {
            "ma_crossover": {
                "fast": ParameterRange("fast", 3, 8, 1, 5),
                "slow": ParameterRange("slow", 15, 25, 1, 20),
            },
            "rsi_momentum": {
                "period": ParameterRange("period", 7, 14, 1, 10),
                "overbought": ParameterRange("overbought", 65, 75, 1, 70),
                "oversold": ParameterRange("oversold", 25, 35, 1, 30),
            },
            "_risk": {
                "stop_loss_atr_mult": ParameterRange("sl_mult", 1.0, 2.5, 0.5, 1.5),
                "take_profit_atr_mult": ParameterRange("tp_mult", 2.0, 4.0, 0.5, 3.0),
            },
        },
        "volatile": {
            "ma_crossover": {
                "fast": ParameterRange("fast", 10, 20, 1, 12),
                "slow": ParameterRange("slow", 30, 60, 1, 40),
            },
            "rsi_momentum": {
                "period": ParameterRange("period", 14, 28, 1, 21),
                "overbought": ParameterRange("overbought", 80, 90, 1, 85),
                "oversold": ParameterRange("oversold", 10, 25, 1, 15),
            },
            "_risk": {
                "stop_loss_atr_mult": ParameterRange("sl_mult", 3.0, 5.0, 0.5, 4.0),
                "take_profit_atr_mult": ParameterRange("tp_mult", 5.0, 10.0, 0.5, 7.0),
            },
        },
    }

    def get_param_ranges(
        self,
        strategy_name: str,
        current_regime: str,
    ) -> dict[str, ParameterRange]:
        """获取当前市场状态下的参数搜索范围"""
        regime_presets = self.REGIME_PARAM_PRESETS.get(current_regime, {})
        strategy_presets = regime_presets.get(strategy_name, {})
        risk_presets = regime_presets.get("_risk", {})

        # 合并策略参数和风控参数
        combined = {}
        combined.update(strategy_presets)
        combined.update(risk_presets)
        return combined
```

---

## 6. 高级仓位管理系统

### 6.1 设计哲学

v1.0 的仓位管理是"一刀切"：计算出仓位大小，一次性建仓。v2.0 引入四种高级仓位管理模式，根据信号强度和市场状态自动选择。

### 6.2 金字塔加仓系统

```python
@dataclass
class PyramidLevel:
    """金字塔加仓层级"""
    level: int                     # 层级编号（0=初始仓位）
    entry_price: float
    size: float
    timestamp: float
    trigger_condition: str         # 触发此层级的条件描述

class PyramidPositionManager:
    """
    金字塔（顺势加仓）管理器

    核心规则：
    1. 初始仓位 = 信号仓位的 40%
    2. 价格向有利方向移动 1x ATR 后，加仓 30%
    3. 再移动 1x ATR 后，加仓 20%
    4. 再移动 1x ATR 后，加仓最后 10%
    5. 每次加仓后，整体止损上移到保本位
    6. 总仓位不超过风控上限

    vs 3Commas DCA:
    - 3Commas 的 DCA 是逆势加仓（亏损时加仓摊平成本）
    - BQT 的金字塔是顺势加仓（盈利时加仓扩大利润）
    - 顺势加仓在趋势市场中收益更高、风险更低
    """

    PYRAMID_ALLOCATION = [0.40, 0.30, 0.20, 0.10]  # 每层仓位比例
    ADD_TRIGGER_ATR_MULT = 1.0  # 每层加仓触发距离 = 1x ATR

    def __init__(self, max_levels: int = 4):
        self.max_levels = max_levels
        self.levels: list[PyramidLevel] = []
        self.total_target_size: float = 0
        self.direction: int = 0  # 1=多, -1=空
        self.base_atr: float = 0

    def initialize(
        self,
        direction: int,
        total_target_size: float,
        entry_price: float,
        atr: float,
    ):
        """初始化金字塔，建立第一层仓位"""
        self.direction = direction
        self.total_target_size = total_target_size
        self.base_atr = atr

        first_size = total_target_size * self.PYRAMID_ALLOCATION[0]
        self.levels = [
            PyramidLevel(
                level=0,
                entry_price=entry_price,
                size=first_size,
                timestamp=0,
                trigger_condition="initial_entry",
            )
        ]
        return first_size, entry_price

    def check_add_level(
        self,
        current_price: float,
        current_atr: float,
    ) -> tuple[bool, float, float]:
        """
        检查是否应该加仓

        Returns:
            (should_add, add_size, add_price)
        """
        if len(self.levels) >= self.max_levels:
            return False, 0, 0

        if not self.levels:
            return False, 0, 0

        last_entry = self.levels[-1].entry_price
        next_level = len(self.levels)

        # 计算加仓触发价格
        trigger_distance = self.ADD_TRIGGER_ATR_MULT * self.base_atr
        if self.direction == 1:
            trigger_price = last_entry + trigger_distance
            should_add = current_price >= trigger_price
        else:
            trigger_price = last_entry - trigger_distance
            should_add = current_price <= trigger_price

        if should_add and next_level < len(self.PYRAMID_ALLOCATION):
            add_size = self.total_target_size * self.PYRAMID_ALLOCATION[next_level]
            return True, add_size, current_price

        return False, 0, 0

    def get_breakeven_stop(self) -> float:
        """计算保本止损价（所有层级加权平均入场价）"""
        if not self.levels:
            return 0

        total_cost = sum(l.entry_price * l.size for l in self.levels)
        total_size = sum(l.size for l in self.levels)

        if total_size == 0:
            return 0

        avg_entry = total_cost / total_size
        return avg_entry  # 保本价，实际止损可以设在此基础上加一定缓冲

    def get_trailing_stop(self, highest_since_entry: float) -> float:
        """
        渐进式追踪止损

        规则：
        - 仅1层仓位时：追踪距离 = 2.5x ATR
        - 2层时：追踪距离 = 2.0x ATR
        - 3层时：追踪距离 = 1.5x ATR
        - 4层满仓时：追踪距离 = 1.0x ATR（更紧）

        逻辑：仓位越大，止损越紧，因为潜在亏损金额更大
        """
        trail_multipliers = [2.5, 2.0, 1.5, 1.0]
        trail_mult = trail_multipliers[min(len(self.levels) - 1, 3)]
        trail_distance = trail_mult * self.base_atr

        if self.direction == 1:
            return highest_since_entry - trail_distance
        else:
            return highest_since_entry + trail_distance  # 空头用最低价

    @property
    def current_size(self) -> float:
        return sum(l.size for l in self.levels)

    @property
    def average_entry(self) -> float:
        if not self.levels:
            return 0
        total_cost = sum(l.entry_price * l.size for l in self.levels)
        total_size = sum(l.size for l in self.levels)
        return total_cost / total_size if total_size > 0 else 0
```

### 6.3 智能止损系统

```python
class IntelligentStopManager:
    """
    智能止损管理器

    五种止损类型的动态切换：
    1. 初始止损（ATR 固定）→ 建仓后立刻生效
    2. 保本止损 → 盈利超过 1x ATR 后切换
    3. 追踪止损 → 盈利超过 2x ATR 后切换
    4. 时间止损 → 持仓超过N根K线未达到目标盈利
    5. 波动率止损 → 波动率突然放大时收紧止损

    vs Pionex 的止损：
    - Pionex 只有固定百分比止损和追踪止损
    - BQT v2.0 有五种止损自动切换的状态机
    """

    def __init__(
        self,
        entry_price: float,
        direction: int,
        atr: float,
        initial_sl_mult: float = 2.0,
        breakeven_trigger_mult: float = 1.0,
        trailing_trigger_mult: float = 2.0,
        max_hold_bars: int = 100,
        vol_spike_threshold: float = 2.5,
    ):
        self.entry_price = entry_price
        self.direction = direction
        self.atr = atr
        self.initial_sl_mult = initial_sl_mult
        self.breakeven_trigger_mult = breakeven_trigger_mult
        self.trailing_trigger_mult = trailing_trigger_mult
        self.max_hold_bars = max_hold_bars
        self.vol_spike_threshold = vol_spike_threshold

        # 状态
        self.state = "initial"  # initial / breakeven / trailing
        self.bars_held = 0
        self.highest_favorable = entry_price  # 持仓以来最高有利价格

        # 计算初始止损
        if direction == 1:
            self.current_stop = entry_price - initial_sl_mult * atr
        else:
            self.current_stop = entry_price + initial_sl_mult * atr

    def update(
        self,
        current_price: float,
        current_atr: float,
        current_vol: float,
        avg_vol_30d: float,
    ) -> tuple[float, str, bool]:
        """
        更新止损价

        Returns:
            (止损价, 当前状态, 是否应该平仓)
        """
        self.bars_held += 1

        # 更新最高有利价格
        if self.direction == 1:
            self.highest_favorable = max(self.highest_favorable, current_price)
            unrealized_atr = (current_price - self.entry_price) / self.atr
        else:
            self.highest_favorable = min(self.highest_favorable, current_price)
            unrealized_atr = (self.entry_price - current_price) / self.atr

        # 波动率止损检查（优先级最高）
        vol_ratio = current_vol / avg_vol_30d if avg_vol_30d > 0 else 1
        if vol_ratio > self.vol_spike_threshold:
            # 波动率暴涨，收紧止损到 0.5x ATR
            if self.direction == 1:
                vol_stop = current_price - 0.5 * current_atr
                self.current_stop = max(self.current_stop, vol_stop)
            else:
                vol_stop = current_price + 0.5 * current_atr
                self.current_stop = min(self.current_stop, vol_stop)
            return self.current_stop, "volatility_tightened", False

        # 时间止损检查
        if self.bars_held >= self.max_hold_bars and unrealized_atr < 1.0:
            return self.current_stop, "time_stop", True

        # 状态机转换
        if self.state == "initial":
            if unrealized_atr >= self.breakeven_trigger_mult:
                # 切换到保本止损
                self.state = "breakeven"
                if self.direction == 1:
                    self.current_stop = self.entry_price + 0.1 * self.atr  # 微利
                else:
                    self.current_stop = self.entry_price - 0.1 * self.atr
                return self.current_stop, "breakeven", False

        elif self.state == "breakeven":
            if unrealized_atr >= self.trailing_trigger_mult:
                self.state = "trailing"

        if self.state == "trailing":
            # 追踪止损：止损只能向有利方向移动
            trail_distance = 1.5 * current_atr
            if self.direction == 1:
                new_stop = self.highest_favorable - trail_distance
                self.current_stop = max(self.current_stop, new_stop)
            else:
                new_stop = self.highest_favorable + trail_distance
                self.current_stop = min(self.current_stop, new_stop)

        # 检查是否触发
        if self.direction == 1 and current_price <= self.current_stop:
            return self.current_stop, self.state, True
        elif self.direction == -1 and current_price >= self.current_stop:
            return self.current_stop, self.state, True

        return self.current_stop, self.state, False
```

### 6.4 置信度驱动的仓位计算

```python
class ConfidenceBasedPositionSizer:
    """
    基于置信度的仓位计算器

    核心创新：仓位大小 = f(置信度, 共振分数, 市场状态, Kelly值)

    而不是传统的 仓位 = 固定比例 * 资金

    这意味着：
    - 高置信度 + 高共振 + 趋势市 = 满仓（资金利用率高）
    - 低置信度 + 低共振 + 震荡市 = 小仓（降低风险）
    - 同一个策略在不同时刻的仓位差异可以达到 5 倍
    """

    def calculate_position(
        self,
        total_equity: float,
        signal_confidence: float,       # 0-1，策略组合引擎输出
        confluence_score: float,         # 0-100，多周期共振分数
        regime: str,                     # 当前市场状态
        kelly_fraction: float,           # 当前 Kelly 值
        current_drawdown_pct: float,     # 当前回撤百分比
        price: float,
        atr: float,
    ) -> dict:
        """
        计算仓位

        Returns:
            {
                "position_size": float,          # 仓位数量
                "position_value_pct": float,     # 占资金百分比
                "risk_amount": float,            # 风险金额
                "entry_mode": str,               # "pyramid" / "full" / "grid"
                "reasoning": dict,               # 计算推理过程
            }
        """
        # 1. 基础仓位 = Kelly 值（已经是半 Kelly）
        base_pct = kelly_fraction

        # 2. 置信度调节 (0.2x ~ 1.5x)
        confidence_multiplier = 0.2 + signal_confidence * 1.3

        # 3. 共振分数调节 (0.5x ~ 1.3x)
        confluence_multiplier = 0.5 + (confluence_score / 100) * 0.8

        # 4. 市场状态调节
        regime_multiplier = {
            "trending_up": 1.2,
            "trending_down": 1.2,
            "ranging": 0.7,
            "volatile": 0.5,
        }.get(regime, 1.0)

        # 5. 回撤保护 (回撤越大，仓位越小)
        drawdown_multiplier = max(0.0, 1.0 - current_drawdown_pct * 5)
        # 回撤 5% → multiplier=0.75
        # 回撤 10% → multiplier=0.50
        # 回撤 15% → multiplier=0.25
        # 回撤 20% → multiplier=0.00（停止开仓）

        # 6. 综合计算
        final_pct = (
            base_pct
            * confidence_multiplier
            * confluence_multiplier
            * regime_multiplier
            * drawdown_multiplier
        )

        # 7. 硬上下限
        final_pct = max(0.005, min(final_pct, 0.15))  # 0.5% ~ 15%

        position_value = total_equity * final_pct
        position_size = position_value / price if price > 0 else 0

        # 8. 选择入场模式
        if signal_confidence > 0.7 and confluence_score > 70:
            entry_mode = "pyramid"  # 高置信度用金字塔加仓
        elif regime == "ranging" and signal_confidence > 0.5:
            entry_mode = "grid"     # 震荡市用网格
        else:
            entry_mode = "full"     # 一次性建仓

        return {
            "position_size": round(position_size, 8),
            "position_value_pct": round(final_pct * 100, 2),
            "risk_amount": round(position_value * atr * 2 / price, 2),
            "entry_mode": entry_mode,
            "reasoning": {
                "base_kelly_pct": round(base_pct * 100, 2),
                "confidence_mult": round(confidence_multiplier, 3),
                "confluence_mult": round(confluence_multiplier, 3),
                "regime_mult": round(regime_multiplier, 3),
                "drawdown_mult": round(drawdown_multiplier, 3),
                "final_pct": round(final_pct * 100, 2),
            },
        }
```

---

## 7. 市场状态检测引擎

### 7.1 设计哲学

"如果你不知道现在是什么市场，你就不应该交易。"——市场状态检测是整个 v2.0 框架的总指挥，它决定了哪些策略激活、参数如何设置、仓位多大。

### 7.2 四状态分类模型

```python
from enum import Enum

class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"

class MarketRegimeDetector:
    """
    市场状态检测器

    使用多维度指标综合判断，而非单一指标：

    维度1: 趋势强度 (ADX + 均线排列)
    维度2: 波动率水平 (ATR百分比 + 布林带宽)
    维度3: 价格结构 (高低点序列 + 分形)
    维度4: 成交量特征 (量能趋势 + 量价背离)

    每个维度输出一个0-1的分数，最终通过决策树合成市场状态。

    vs 3Commas/Pionex/OKX Signal Bot：
    这三个产品完全没有市场状态检测功能。
    用户必须自己判断市场状态并手动切换策略。
    BQT v2.0 自动完成这一切。
    """

    def __init__(
        self,
        adx_trend_threshold: float = 25,
        adx_strong_threshold: float = 40,
        vol_high_ratio: float = 1.5,
        vol_extreme_ratio: float = 2.5,
        lookback_period: int = 100,
    ):
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_strong_threshold = adx_strong_threshold
        self.vol_high_ratio = vol_high_ratio
        self.vol_extreme_ratio = vol_extreme_ratio
        self.lookback_period = lookback_period

        # 状态平滑：防止在状态边界频繁切换
        self._regime_history: list[MarketRegime] = []
        self._min_regime_duration = 6  # 最少维持6根K线才允许切换

    def detect(self, df) -> tuple[MarketRegime, dict]:
        """
        检测当前市场状态

        Returns:
            (市场状态, 详细分数)
        """
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # ========== 维度1: 趋势强度 ==========

        # ADX 计算（简化版）
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where(
            (plus_dm > minus_dm) & (plus_dm > 0), 0
        )
        minus_dm = minus_dm.where(
            (minus_dm > plus_dm) & (minus_dm > 0), 0
        )

        tr = self._true_range(df)
        atr14 = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr14)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr14)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(14).mean()

        current_adx = float(adx.iloc[-1]) if not adx.isna().iloc[-1] else 0
        current_plus_di = float(plus_di.iloc[-1]) if not plus_di.isna().iloc[-1] else 0
        current_minus_di = float(minus_di.iloc[-1]) if not minus_di.isna().iloc[-1] else 0

        # 均线排列
        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()
        ema200 = close.ewm(span=200).mean()

        bullish_alignment = (
            close.iloc[-1] > ema20.iloc[-1] > ema50.iloc[-1]  # > ema200 可选
        )
        bearish_alignment = (
            close.iloc[-1] < ema20.iloc[-1] < ema50.iloc[-1]
        )

        trend_score = min(current_adx / 50, 1.0)  # 0-1

        # ========== 维度2: 波动率水平 ==========

        atr_pct = (atr14 / close * 100).iloc[-1]
        atr_pct_avg = (atr14 / close * 100).rolling(
            self.lookback_period
        ).mean().iloc[-1]

        vol_ratio = atr_pct / atr_pct_avg if atr_pct_avg > 0 else 1

        # 布林带带宽
        bb_width = (close.rolling(20).std() * 2 / close.rolling(20).mean()).iloc[-1]
        bb_width_avg = (
            close.rolling(20).std() * 2 / close.rolling(20).mean()
        ).rolling(self.lookback_period).mean().iloc[-1]
        bb_ratio = bb_width / bb_width_avg if bb_width_avg > 0 else 1

        volatility_score = min((vol_ratio + bb_ratio) / 2 / 2, 1.0)

        # ========== 维度3: 价格结构 ==========

        # 高低点序列分析
        recent_highs = high.rolling(10).max()
        recent_lows = low.rolling(10).min()

        higher_highs = sum(
            1 for i in range(-5, 0)
            if recent_highs.iloc[i] > recent_highs.iloc[i-5]
        )
        higher_lows = sum(
            1 for i in range(-5, 0)
            if recent_lows.iloc[i] > recent_lows.iloc[i-5]
        )

        uptrend_structure = (higher_highs + higher_lows) / 10  # 0-1
        downtrend_structure = (
            sum(1 for i in range(-5, 0)
                if recent_highs.iloc[i] < recent_highs.iloc[i-5]) +
            sum(1 for i in range(-5, 0)
                if recent_lows.iloc[i] < recent_lows.iloc[i-5])
        ) / 10

        # ========== 维度4: 成交量特征 ==========

        vol_ma = volume.rolling(20).mean()
        vol_trend = (
            volume.rolling(10).mean().iloc[-1] /
            volume.rolling(20).mean().iloc[-1]
        ) if vol_ma.iloc[-1] > 0 else 1

        # ========== 综合判断 ==========

        raw_regime = self._classify(
            adx=current_adx,
            plus_di=current_plus_di,
            minus_di=current_minus_di,
            trend_score=trend_score,
            volatility_score=volatility_score,
            vol_ratio=vol_ratio,
            bullish_alignment=bullish_alignment,
            bearish_alignment=bearish_alignment,
            uptrend_structure=uptrend_structure,
            downtrend_structure=downtrend_structure,
        )

        # 状态平滑
        smoothed_regime = self._smooth_regime(raw_regime)

        details = {
            "adx": round(current_adx, 2),
            "plus_di": round(current_plus_di, 2),
            "minus_di": round(current_minus_di, 2),
            "trend_score": round(trend_score, 3),
            "volatility_score": round(volatility_score, 3),
            "vol_ratio": round(vol_ratio, 3),
            "bb_ratio": round(bb_ratio, 3),
            "bullish_alignment": bullish_alignment,
            "bearish_alignment": bearish_alignment,
            "uptrend_structure": round(uptrend_structure, 3),
            "downtrend_structure": round(downtrend_structure, 3),
            "volume_trend": round(vol_trend, 3),
            "raw_regime": raw_regime.value,
            "smoothed_regime": smoothed_regime.value,
        }

        return smoothed_regime, details

    def _classify(self, **indicators) -> MarketRegime:
        """基于多维指标的决策树分类"""

        # 极端波动优先判断
        if indicators["vol_ratio"] > self.vol_extreme_ratio:
            return MarketRegime.VOLATILE

        # 强趋势判断
        if indicators["adx"] > self.adx_trend_threshold:
            if indicators["plus_di"] > indicators["minus_di"]:
                if indicators["bullish_alignment"] or indicators["uptrend_structure"] > 0.6:
                    return MarketRegime.TRENDING_UP
            else:
                if indicators["bearish_alignment"] or indicators["downtrend_structure"] > 0.6:
                    return MarketRegime.TRENDING_DOWN

        # 高波动但无明确趋势
        if indicators["vol_ratio"] > self.vol_high_ratio:
            return MarketRegime.VOLATILE

        # 无趋势、低波动 = 震荡
        if indicators["adx"] < self.adx_trend_threshold:
            return MarketRegime.RANGING

        # 弱趋势判断（ADX在阈值附近）
        if indicators["uptrend_structure"] > 0.5:
            return MarketRegime.TRENDING_UP
        elif indicators["downtrend_structure"] > 0.5:
            return MarketRegime.TRENDING_DOWN

        return MarketRegime.RANGING

    def _smooth_regime(self, raw_regime: MarketRegime) -> MarketRegime:
        """状态平滑：防止频繁切换"""
        self._regime_history.append(raw_regime)

        if len(self._regime_history) < self._min_regime_duration:
            return raw_regime

        # 检查最近N根K线是否大多数指向同一状态
        recent = self._regime_history[-self._min_regime_duration:]
        regime_counts: dict[MarketRegime, int] = {}
        for r in recent:
            regime_counts[r] = regime_counts.get(r, 0) + 1

        # 超过2/3多数才切换
        threshold = self._min_regime_duration * 2 / 3
        for regime, count in regime_counts.items():
            if count >= threshold:
                return regime

        # 无明确多数，保持上一个状态
        return self._regime_history[-2] if len(self._regime_history) >= 2 else raw_regime

    def _true_range(self, df) -> "pd.Series":
        import pandas as pd
        return pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
```

---

## 8. 五大引擎协同工作流

### 8.1 完整决策链路

```
每根K线闭合时触发：

Step 1: 市场状态检测
    输入: 最新OHLCV数据
    输出: MarketRegime + 详细分数
    耗时: < 5ms

Step 2: 参数自适应调整
    输入: MarketRegime + 参数历史
    动作: 如果状态切换，更新参数搜索范围
         如果到达Walk-Forward窗口边界，触发参数优化
    输出: 各策略当前参数集
    耗时: < 100ms（Walk-Forward优化时 < 2s）

Step 3: 策略轮换检查（每24h执行一次）
    输入: 各策略近期绩效指标
    动作: 排名 → 激活/停用策略
    输出: 策略激活列表 + 仓位缩放因子

Step 4: 多周期数据获取
    输入: 策略类型 + 波动率状态
    动作: 自适应选择时间周期 → 并行获取多周期数据
    输出: 各周期OHLCV数据

Step 5: 各策略生成信号
    输入: 多周期数据 + 当前参数 + 市场状态
    动作: 每个激活策略独立生成EnrichedSignal
    输出: list[EnrichedSignal]
    耗时: < 10ms/策略

Step 6: 多周期共振评估
    输入: 各周期的信号
    输出: 共振分数 + 方向确认
    耗时: < 5ms

Step 7: 策略组合投票
    输入: 各策略的EnrichedSignal + 市场状态权重
    动作: 加权投票 + 一票否决检查 + 置信度合成
    输出: 最终信号 + 合成置信度
    耗时: < 2ms

Step 8: 仓位计算
    输入: 置信度 + 共振分数 + Kelly值 + 回撤状态
    输出: 精确仓位 + 入场模式（金字塔/网格/全量）
    耗时: < 2ms

Step 9: 止损止盈设定
    输入: 入场价 + ATR + 入场模式
    输出: 初始止损价 + 多级止盈价
    耗时: < 1ms

Step 10: 提交至OMS + RiskEngine
    输入: 仓位指令 + 止损止盈
    动作: v1.0 现有的风控检查 + 订单执行
    输出: 成交回报

总端到端延迟: < 200ms（正常） / < 3s（含参数优化）
```

### 8.2 引擎间数据依赖图

```
MarketRegimeDetector
    │
    ├──→ StrategyRotationEngine        (决定哪些策略活跃)
    ├──→ RegimeAwareParameterManager   (缩小参数搜索范围)
    ├──→ EnsembleVotingEngine          (市场状态权重)
    └──→ ConfidenceBasedPositionSizer  (市场状态仓位调节)

WalkForwardOptimizer
    │
    └──→ 各策略当前最优参数

MultiTimeframeConfluenceEngine
    │
    └──→ 共振分数 + 方向确认

EnsembleVotingEngine
    │
    └──→ 合成信号 + 置信度

ConfidenceBasedPositionSizer + PyramidPositionManager + IntelligentStopManager
    │
    └──→ 完整的仓位执行计划
```

### 8.3 Redis 状态同步

五大引擎的中间状态通过 Redis 共享，实现松耦合：

```python
# Redis Key 设计
REDIS_KEYS = {
    # 市场状态
    "regime:current":               "trending_up",        # 当前状态
    "regime:details":               "{...json...}",       # 详细指标
    "regime:history:1h":            "[...]",              # 1小时状态历史
    "regime:transition_count_24h":  "3",                  # 24h内状态切换次数

    # 策略状态
    "strategy:active_set":          '["ma_crossover","turtle","rsi_momentum"]',
    "strategy:{name}:params":       '{"fast":7,"slow":25}',
    "strategy:{name}:health":       "0.78",
    "strategy:{name}:last_signal":  '{"type":"BUY","confidence":0.72}',

    # 共振状态
    "confluence:score":             "72.5",
    "confluence:direction":         "1",
    "confluence:aligned_tfs":       "3",

    # 仓位状态
    "position:{symbol}:mode":       "pyramid",
    "position:{symbol}:levels":     "[...]",
    "position:{symbol}:stop":       "58200.00",
    "position:{symbol}:stop_state": "trailing",

    # Walk-Forward 状态
    "wf:{strategy}:last_optimize":  "1710648000",
    "wf:{strategy}:failures":       "0",
    "wf:{strategy}:param_version":  "17",
}
```

---

## 9. 竞品对比与独特竞争力

### 9.1 功能矩阵对比

| 功能 | 3Commas | Pionex | OKX Signal Bot | Freqtrade | **BQT v2.0** |
|------|---------|--------|---------------|-----------|-------------|
| 策略组合投票 | 无 | 无 | 无 | 无 | **加权投票+一票否决+动态权重** |
| 多周期共振 | 无 | 无 | 无 | 部分（需手写） | **自适应周期选择+共振评分** |
| 市场状态检测 | 无 | 无 | 无 | 无 | **4维度多指标分类+平滑** |
| 自适应参数 | 无 | 无 | 无 | Hyperopt（离线） | **Walk-Forward实时+状态驱动** |
| 金字塔加仓 | DCA（逆势） | DCA（逆势） | 无 | 无 | **顺势金字塔+渐进止损** |
| 智能止损 | 固定+追踪 | 固定+追踪 | 固定 | ATR止损 | **5种止损状态机自动切换** |
| 置信度仓位 | 无 | 无 | 无 | 无 | **4维度置信度驱动仓位** |
| 策略轮换 | 无 | 无 | 无 | 无 | **健康分+多样性约束轮换** |
| 波动率自适应 | 无 | 无 | 无 | 无 | **全链路波动率感知** |

### 9.2 BQT v2.0 的六大独特竞争力

**竞争力一：立体决策架构**

竞品是"平面"的——一个策略、一组参数、一种止损。BQT v2.0 是"立体"的——五层引擎垂直协作，市场状态在顶层流入，精确仓位指令在底层流出。中间每一层都为下一层提供增强信息。这种架构使得单个策略的信号质量通过上下文信息被系统性放大。

**竞争力二：智能降级能力**

当市场变得不确定时，BQT v2.0 不是简单停止交易，而是：
- 共振分数降低 → 自动缩小仓位（不是停止交易）
- 投票无共识 → 切换到低风险策略（不是停止所有策略）
- 波动率飙升 → 收紧止损 + 降低新仓位（不是平掉所有仓位）

这种"优雅降级"比竞品的"全开或全关"更符合实际交易需求。

**竞争力三：顺势金字塔 vs 逆势 DCA**

3Commas 和 Pionex 的核心模式是 DCA（Dollar Cost Averaging）——亏损时加仓摊低成本。这在趋势行情中会导致灾难性亏损（越跌越买）。BQT v2.0 的金字塔是顺势加仓——只在盈利时加仓，亏损时止损。统计上，在加密市场的强趋势行情中，顺势金字塔的期望收益是逆势 DCA 的 2-3 倍。

**竞争力四：参数自愈能力**

所有竞品的参数都是"设好就不管"。市场变化后参数失效，用户只能手动回测再调整。BQT v2.0 的 Walk-Forward 引擎实时监控参数有效性：
- 参数失效 → 4小时内检测到 → 自动缩小仓位 + 触发重新优化
- 市场状态切换 → 即时切换到对应状态的参数预设范围
- 新优化参数 → 必须在测试集上比旧参数好10%以上才会更新（防过拟合）

**竞争力五：全链路波动率感知**

波动率不只影响止损距离，它影响整个决策链路：
- 市场状态检测：波动率是分类的核心维度之一
- 周期选择：高波动自动切换到高周期
- 共振评分：高波动时共振分数打折（信号不可靠）
- 参数范围：高波动时止损放宽、均线放长
- 仓位计算：高波动时自动减仓
- 止损管理：波动率暴涨时自动收紧止损

从数据入口到订单出口，波动率信息贯穿始终。竞品最多在止损一个环节考虑波动率。

**竞争力六：可审计的决策推理链**

每笔交易都有完整的决策推理记录：

```json
{
    "trade_id": "T20260317_001",
    "decision_chain": {
        "market_regime": {"state": "trending_up", "adx": 32.5, "confidence": 0.78},
        "active_strategies": ["ma_crossover", "turtle", "rsi_momentum"],
        "strategy_votes": [
            {"strategy": "ma_crossover", "signal": "BUY", "confidence": 0.72, "weight": 1.44},
            {"strategy": "turtle", "signal": "BUY", "confidence": 0.65, "weight": 1.68},
            {"strategy": "rsi_momentum", "signal": "HOLD", "confidence": 0.30, "weight": 0.60}
        ],
        "ensemble_result": {"signal": "BUY", "composite_confidence": 0.68},
        "confluence": {"score": 72.5, "aligned_timeframes": 3, "direction": 1},
        "position_sizing": {
            "base_kelly": "3.2%", "confidence_mult": 1.08,
            "confluence_mult": 1.08, "regime_mult": 1.2,
            "final_position": "4.5%", "entry_mode": "pyramid"
        },
        "stop_loss": {"initial": 58200, "type": "ATR", "atr_mult": 3.0},
        "execution_latency_ms": 87
    }
}
```

这在策略出问题时提供完整的诊断链，而竞品只能看到"信号触发 → 下单"的黑盒。

---

## 10. 实施路径与里程碑

### 10.1 分阶段实施计划

```
Phase A (Week 1-3): 市场状态检测引擎
    ├── MarketRegimeDetector 实现
    ├── 回测验证（2年历史数据，验证状态分类准确率）
    ├── Redis 状态发布
    └── Grafana 市场状态仪表盘

Phase B (Week 3-6): 策略信号增强
    ├── EnrichedSignal 数据结构
    ├── 每个现有策略增加置信度计算
    ├── 策略注册表升级（支持置信度输出）
    └── 回测引擎适配新信号格式

Phase C (Week 5-8): 策略组合引擎
    ├── EnsembleVotingEngine
    ├── CascadeEngine
    ├── StrategyRotationEngine
    ├── 回测验证（组合 vs 单策略的夏普比率对比）
    └── API 暴露组合状态

Phase D (Week 7-10): 多周期共振系统
    ├── MultiTimeframeConfluenceEngine
    ├── AdaptiveTimeframeSelector
    ├── 多周期数据并行获取管道
    └── 回测验证（共振分数与实际收益的相关性）

Phase E (Week 9-12): 自适应参数系统
    ├── WalkForwardOptimizer
    ├── RegimeAwareParameterManager
    ├── 参数失效告警系统
    └── 回测验证（Walk-Forward效率 > 50%）

Phase F (Week 11-14): 高级仓位管理
    ├── PyramidPositionManager
    ├── IntelligentStopManager
    ├── ConfidenceBasedPositionSizer
    └── 回测验证（金字塔 vs 全量建仓的收益对比）

Phase G (Week 13-16): 集成测试 + 模拟盘
    ├── 五大引擎端到端集成
    ├── Testnet 模拟盘运行 2 周
    ├── 性能优化（确保延迟 < 200ms）
    └── 压力测试（50个并发策略实例）

Phase H (Week 15-18): 小资金实盘 + 调优
    ├── 5% 资金实盘运行
    ├── 每日对比 v1.0 vs v2.0 表现
    ├── 参数微调
    └── 稳定运行 4 周后全量切换
```

### 10.2 关键验收指标

| 里程碑 | 验收指标 |
|--------|---------|
| Phase A 完成 | 市场状态分类准确率 > 70%（人工标注对比） |
| Phase C 完成 | 组合策略回测夏普比率比最佳单策略高 30%+ |
| Phase D 完成 | 共振分数 > 70 的信号胜率 > 55% |
| Phase E 完成 | Walk-Forward 效率 > 50%，参数失效检测 < 4h |
| Phase F 完成 | 金字塔模式在趋势市收益比全量建仓高 20%+ |
| Phase G 完成 | 端到端延迟 P99 < 200ms |
| Phase H 完成 | 实盘组合夏普比率 > 1.5，最大回撤 < 12% |

---

## 附录A：核心数据结构汇总

```python
# v2.0 核心数据结构
from dataclasses import dataclass
from enum import Enum

class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"

class SignalType(Enum):
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2

@dataclass
class EnrichedSignal:
    signal_type: SignalType
    confidence: float
    timeframe: str
    strategy_name: str
    entry_zone: tuple[float, float]
    stop_loss: float
    take_profit: list[float]
    max_hold_bars: int
    regime_alignment: float
    technical_confidence: float
    volume_confidence: float
    trend_alignment: float
    regime_confidence: float

@dataclass
class ConfluenceResult:
    confluence_score: float
    direction: int
    aligned_timeframes: int
    timeframe_details: list
    recommended_action: str

@dataclass
class PositionPlan:
    position_size: float
    position_value_pct: float
    risk_amount: float
    entry_mode: str              # "pyramid" / "full" / "grid"
    stop_loss: float
    take_profit_levels: list[float]
    reasoning: dict
```

## 附录B：配置文件扩展

```yaml
# strategy-v2-config.yaml
strategy_framework:
  version: "2.0"

  # 市场状态检测
  regime_detector:
    adx_trend_threshold: 25
    adx_strong_threshold: 40
    vol_high_ratio: 1.5
    vol_extreme_ratio: 2.5
    smoothing_bars: 6

  # 策略组合
  ensemble:
    mode: "voting"             # "voting" / "cascade" / "rotation"
    min_agreement_ratio: 0.6
    min_total_confidence: 0.5
    veto_threshold: 0.8

  # 策略轮换
  rotation:
    evaluation_interval_hours: 24
    max_active_strategies: 3
    warmup_hours: 48
    cooldown_periods: 1
    min_type_diversity: 2

  # 多周期共振
  confluence:
    timeframe_weights:
      "1w": 0.30
      "1d": 0.25
      "4h": 0.20
      "1h": 0.15
      "15m": 0.10
    aggressive_entry_threshold: 75
    normal_entry_threshold: 55
    wait_threshold: 35

  # Walk-Forward 参数优化
  walk_forward:
    train_bars: 500
    test_bars: 100
    step_bars: 50
    min_trades: 30
    optimization_metric: "sharpe_ratio"
    min_improvement_pct: 10
    max_consecutive_failures: 3

  # 仓位管理
  position:
    pyramid:
      allocation: [0.40, 0.30, 0.20, 0.10]
      add_trigger_atr_mult: 1.0
    stop_loss:
      initial_atr_mult: 2.0
      breakeven_trigger_atr: 1.0
      trailing_trigger_atr: 2.0
      max_hold_bars: 100
      vol_spike_threshold: 2.5
    sizing:
      min_position_pct: 0.005
      max_position_pct: 0.15
      drawdown_sensitivity: 5.0  # 回撤1%对应仓位减少5%
```

## 附录C：与 v1.0 的向后兼容

v2.0 框架完全兼容 v1.0 的策略代码。现有的 `signal_func` 函数无需修改，系统会自动包装为 `EnrichedSignal`（置信度默认为 0.5）。

```python
class V1StrategyAdapter:
    """
    v1.0 策略适配器
    将旧版 signal_func(df, **kwargs) -> pd.Series
    包装为 v2.0 的 EnrichedSignal 输出
    """

    def __init__(self, strategy_name: str, signal_func, default_params: dict):
        self.strategy_name = strategy_name
        self.signal_func = signal_func
        self.default_params = default_params

    def generate_signal(self, df, regime: str, **kwargs) -> EnrichedSignal:
        params = {**self.default_params, **kwargs}
        signals = self.signal_func(df, **params)
        last_signal = int(signals.iloc[-1])

        # 简单的置信度估算（基于信号频率）
        recent_signals = signals.iloc[-20:]
        signal_consistency = abs(recent_signals.mean())  # 方向一致性

        return EnrichedSignal(
            signal_type=SignalType(max(-2, min(2, last_signal))),
            confidence=0.5 + signal_consistency * 0.3,  # 0.5-0.8 范围
            timeframe=kwargs.get("timeframe", "4h"),
            strategy_name=self.strategy_name,
            entry_zone=(df["close"].iloc[-1] * 0.998, df["close"].iloc[-1] * 1.002),
            stop_loss=0,  # 由仓位管理系统计算
            take_profit=[],
            max_hold_bars=100,
            regime_alignment=0.5,  # 默认值
            technical_confidence=0.5,
            volume_confidence=0.5,
            trend_alignment=0.5,
            regime_confidence=0.5,
        )
```

这确保了升级到 v2.0 时，团队可以逐步迁移策略，而不是一次性全部重写。

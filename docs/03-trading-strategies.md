# 量化策略体系

> 版本: v1.0 | 更新日期: 2026-03-13 | 面向: 策略研发工程师

---

## 目录

1. [策略分类体系](#1-策略分类体系)
2. [回测体系](#2-回测体系)
3. [策略评估与选择矩阵](#3-策略评估与选择矩阵)
4. [策略代码模板](#4-策略代码模板)

---

## 1. 策略分类体系

### 1.1 趋势跟踪策略

趋势策略的核心假设：**价格存在动量效应，趋势一旦形成会持续一段时间**。加密市场因散户占比高、情绪驱动强，趋势信号往往比传统市场更显著，但假突破也更频繁。

#### 1.1.1 双均线交叉策略（Moving Average Crossover）

**原理**：短期均线上穿长期均线（Golden Cross）产生买入信号，下穿（Death Cross）产生卖出信号。均线本质是价格的滞后平滑，短期均线对价格变化更敏感，当短均线从下方穿越长均线时，意味着近期价格走势强于长期趋势。

**参数配置**：

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 快速均线 | EMA-7 / EMA-12 | 对价格变化敏感 |
| 慢速均线 | EMA-25 / EMA-26 | 过滤短期噪声 |
| K线周期 | 1H / 4H | 加密市场 24/7，日线以下更灵活 |
| 信号确认 | 连续 2 根 K 线 | 减少假信号 |

**Python 实现**：

```python
import pandas as pd

def ma_crossover_signal(df: pd.DataFrame, fast: int = 7, slow: int = 25) -> pd.Series:
    """
    双均线交叉信号生成
    返回: 1=买入, -1=卖出, 0=持有
    """
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()

    signal = pd.Series(0, index=df.index)
    # Golden Cross: 快线从下方穿越慢线
    signal[(ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))] = 1
    # Death Cross: 快线从上方穿越慢线
    signal[(ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))] = -1

    return signal
```

**适用场景**：单边趋势行情（BTC 大牛/大熊市），不适合震荡市。
**预期表现**：夏普比率 0.8-1.5，最大回撤 15-25%，胜率约 35-45%（靠盈亏比取胜）。

---

#### 1.1.2 MACD 趋势策略

**原理**：MACD = EMA(12) - EMA(26)，信号线 = EMA(MACD, 9)。MACD 上穿信号线为买入信号，柱状图（MACD - Signal）由负转正加强确认。

**参数配置**：

| 参数 | 标准值 | 加密市场优化值 |
|------|--------|---------------|
| 快速EMA | 12 | 8-12 |
| 慢速EMA | 26 | 21-26 |
| 信号线 | 9 | 7-9 |
| K线周期 | 4H / 1D | 加密市场波动大，4H 更灵活 |

**Python 实现**：

```python
def macd_signal(df: pd.DataFrame, fast=12, slow=26, signal_period=9) -> pd.Series:
    """MACD 交叉信号"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line

    signal = pd.Series(0, index=df.index)
    # MACD 上穿信号线 + 柱状图由负转正
    buy = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    sell = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
    signal[buy] = 1
    signal[sell] = -1

    return signal
```

**增强方法**：
- 结合零轴过滤：仅在 MACD 零轴上方做多，零轴下方做空
- 背离检测：价格创新高但 MACD 未创新高 = 顶背离（看跌信号）

---

#### 1.1.3 布林带突破策略（Bollinger Bands Breakout）

**原理**：布林带 = MA(20) ± 2σ。价格突破上轨为强势信号（可能开启趋势），突破下轨为弱势信号。在加密市场中，布林带收窄（squeeze）后的突破往往预示大行情。

**计算公式**：
```
中轨 = SMA(close, 20)
上轨 = 中轨 + 2 × std(close, 20)
下轨 = 中轨 - 2 × std(close, 20)
带宽 = (上轨 - 下轨) / 中轨
```

**Python 实现**：

```python
def bollinger_breakout_signal(df: pd.DataFrame, period=20, std_dev=2.0) -> pd.Series:
    """布林带突破信号"""
    sma = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    bandwidth = (upper - lower) / sma

    signal = pd.Series(0, index=df.index)
    # Squeeze 后突破上轨（带宽低于阈值 → 突破）
    squeeze = bandwidth < bandwidth.rolling(120).quantile(0.2)  # 带宽处于低位
    signal[(df['close'] > upper) & squeeze.shift(1)] = 1   # 向上突破
    signal[(df['close'] < lower) & squeeze.shift(1)] = -1  # 向下突破

    return signal
```

**假突破过滤**：
- 要求突破时成交量 > 20 周期均量的 1.5 倍
- 收盘价（而非影线）突破带边才确认
- 连续 2 根 K 线收在带外才触发

---

#### 1.1.4 RSI 动量策略

**原理**：RSI = 100 - 100/(1 + RS)，RS = 平均涨幅/平均跌幅。RSI > 70 超买，RSI < 30 超卖。但在强趋势中，RSI 可以长期维持在超买/超卖区。

**加密市场优化**：
- 趋势行情中，RSI 50 作为多空分界线比 70/30 更有效
- RSI 背离是重要的趋势反转信号

```python
def rsi_signal(df: pd.DataFrame, period=14, overbought=70, oversold=30) -> pd.Series:
    """RSI 超买超卖信号"""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    signal = pd.Series(0, index=df.index)
    # 从超卖区回升
    signal[(rsi > oversold) & (rsi.shift(1) <= oversold)] = 1
    # 从超买区回落
    signal[(rsi < overbought) & (rsi.shift(1) >= overbought)] = -1

    return signal
```

---

#### 1.1.5 改良海龟交易法则

**原理**：经典海龟法则使用 20 日最高/最低价突破入场，55 日突破加仓，用 ATR 管理仓位和止损。

**加密市场改良**：
- 由于加密市场 24/7 交易，使用 **4H K线** 代替日线（20×6=120 根 4H 约等于 20 天）
- ATR 倍数调大：加密市场波动率是传统市场 3-5 倍
- 加入成交量确认过滤

```python
def turtle_signal(df: pd.DataFrame, entry_period=120, exit_period=60) -> pd.Series:
    """改良海龟突破信号（4H K线）"""
    high_entry = df['high'].rolling(entry_period).max()
    low_entry = df['low'].rolling(entry_period).min()
    high_exit = df['high'].rolling(exit_period).max()
    low_exit = df['low'].rolling(exit_period).min()

    # ATR 计算（用于仓位管理）
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(entry_period).mean()

    signal = pd.Series(0, index=df.index)
    signal[df['close'] > high_entry.shift(1)] = 1   # 突破做多
    signal[df['close'] < low_entry.shift(1)] = -1   # 突破做空

    return signal

def turtle_position_size(capital: float, atr: float, risk_pct: float = 0.01) -> float:
    """海龟仓位计算：每笔交易风险不超过总资金的 1%"""
    dollar_risk = capital * risk_pct
    # 止损 = 2 × ATR
    stop_distance = 2 * atr
    position_size = dollar_risk / stop_distance
    return position_size
```

---

### 1.2 均值回归策略

均值回归的核心假设：**价格会围绕均值波动，偏离过大时会回归**。适用于震荡行情，但在趋势行情中可能连续亏损。

#### 1.2.1 统计套利 — 配对交易（Pairs Trading）

**原理**：找到两个高度相关的资产（如 BTC/ETH），当价差偏离历史均值时，做多低估品种、做空高估品种。

**实施步骤**：

1. **协整检验**：使用 Engle-Granger 两步法或 Johansen 检验
2. **价差计算**：`spread = price_A - β × price_B`（β 由 OLS 回归得出）
3. **信号生成**：z-score = (spread - mean) / std

```python
import numpy as np
from statsmodels.tsa.stattools import coint

def find_cointegrated_pairs(prices: pd.DataFrame, significance=0.05):
    """在多个币对中寻找协整配对"""
    n = prices.shape[1]
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            score, pvalue, _ = coint(prices.iloc[:, i], prices.iloc[:, j])
            if pvalue < significance:
                pairs.append((prices.columns[i], prices.columns[j], pvalue))
    return sorted(pairs, key=lambda x: x[2])

def pairs_trading_signal(spread: pd.Series, window=60, entry_z=2.0, exit_z=0.5) -> pd.Series:
    """配对交易信号"""
    mean = spread.rolling(window).mean()
    std = spread.rolling(window).std()
    z_score = (spread - mean) / std

    signal = pd.Series(0, index=spread.index)
    signal[z_score > entry_z] = -1    # 价差过高，做空价差
    signal[z_score < -entry_z] = 1    # 价差过低，做多价差
    signal[z_score.abs() < exit_z] = 0  # 回归均值，平仓

    return signal
```

**加密市场常见配对**：
- BTC / ETH（相关性 0.85+）
- SOL / AVAX（同为 L1 公链）
- BNB / exchange tokens

**风险点**：协整关系可能突然失效（结构性变化），需定期重新检验。

---

#### 1.2.2 Z-Score 偏离回归

**原理**：计算价格相对于滚动均值的标准差偏离度。

```
Z-Score = (Price - SMA(n)) / StdDev(n)
```

- Z > 2.0：做空（价格偏高，预期回归）
- Z < -2.0：做多（价格偏低，预期回归）
- |Z| < 0.5：平仓

```python
def zscore_mean_reversion(df: pd.DataFrame, window=60, entry=2.0, exit_threshold=0.5):
    """Z-Score 均值回归"""
    mean = df['close'].rolling(window).mean()
    std = df['close'].rolling(window).std()
    z = (df['close'] - mean) / std

    signal = pd.Series(0, index=df.index)
    signal[z > entry] = -1       # 做空
    signal[z < -entry] = 1       # 做多
    signal[z.abs() < exit_threshold] = 0  # 平仓

    return signal
```

---

### 1.3 套利策略

套利策略追求**低风险、确定性收益**，利润来源是市场的定价偏差。

#### 1.3.1 现货-合约基差套利（Cash & Carry Arbitrage）

**原理**：当永续合约价格 > 现货价格（正基差），可以同时买入现货 + 做空合约，赚取基差收敛的利润 + 资金费率。

**利润计算**：
```
基差 = 合约价格 - 现货价格
基差率 = 基差 / 现货价格 × 100%
年化收益 ≈ 基差率 × (365 / 持有天数) + 资金费率年化
```

**实施要点**：
- 基差率 > 0.3%（单次）才值得操作（覆盖手续费 + 滑点）
- 现货买入和合约做空需**同时执行**（时间差 < 1 秒）
- 持仓期间收取资金费率（每 8 小时，币安正费率约 0.01%）

```python
def basis_arbitrage_check(spot_price: float, futures_price: float,
                           maker_fee: float = 0.001) -> dict:
    """基差套利可行性检查"""
    basis = futures_price - spot_price
    basis_rate = basis / spot_price
    total_fee = maker_fee * 4  # 开仓2笔 + 平仓2笔

    net_profit_rate = basis_rate - total_fee
    annualized = net_profit_rate * 365  # 假设1天收敛

    return {
        'basis': basis,
        'basis_rate_pct': basis_rate * 100,
        'net_profit_rate_pct': net_profit_rate * 100,
        'annualized_pct': annualized * 100,
        'executable': net_profit_rate > 0.001  # 净利润 > 0.1% 才执行
    }
```

---

#### 1.3.2 跨交易所搬砖套利

**原理**：同一币种在不同交易所存在价差时，低买高卖。

**流程**：
1. 监控 Binance / OKX / Bybit 同币种价格
2. 当价差 > 手续费 + 提币费 + 滑点 时触发
3. 在低价所买入，同时在高价所卖出
4. 定期调平各所余额

**风险**：
- 提币延迟（10-30 分钟）期间价差可能消失
- 需在各交易所预存资金
- 网络拥堵时提币费飙升

---

#### 1.3.3 三角套利

**原理**：利用三个币对之间的汇率不一致获利。

```
路径: USDT → BTC → ETH → USDT
1. 用 USDT 买入 BTC（BTC/USDT）
2. 用 BTC 买入 ETH（ETH/BTC）
3. 卖出 ETH 得到 USDT（ETH/USDT）
如果最终 USDT > 初始 USDT，存在套利空间
```

```python
def triangular_arbitrage_check(
    btc_usdt: float,      # BTC/USDT 买价
    eth_btc: float,        # ETH/BTC 买价
    eth_usdt_sell: float,  # ETH/USDT 卖价
    fee_rate: float = 0.001
) -> dict:
    """三角套利检测"""
    usdt_start = 10000
    # Step 1: USDT → BTC
    btc_amount = (usdt_start / btc_usdt) * (1 - fee_rate)
    # Step 2: BTC → ETH
    eth_amount = (btc_amount / eth_btc) * (1 - fee_rate)
    # Step 3: ETH → USDT
    usdt_end = eth_amount * eth_usdt_sell * (1 - fee_rate)

    profit = usdt_end - usdt_start
    profit_rate = profit / usdt_start

    return {
        'profit_usdt': round(profit, 4),
        'profit_rate_pct': round(profit_rate * 100, 4),
        'executable': profit_rate > 0.0005  # > 0.05% 才执行
    }
```

---

#### 1.3.4 资金费率套利（Funding Rate Arbitrage）

**原理**：币安永续合约每 8 小时结算资金费率。当费率为正时，做多现货 + 做空合约，稳定收取资金费率。

**年化计算**：
```
年化收益 = 单次费率 × 3 × 365
例: 0.01% × 3 × 365 = 10.95% 年化
```

**注意**：
- 费率会变化，需动态监控
- 极端行情时费率可能为负
- 需扣除现货和合约的手续费

---

### 1.4 做市策略

#### 1.4.1 Avellaneda-Stoikov 模型

**原理**：做市商同时挂买单和卖单，赚取买卖价差。A-S 模型通过库存风险参数 γ 动态调整报价：

```
最优报价:
  bid = mid_price - spread/2 - γ × σ² × (T-t) × q
  ask = mid_price + spread/2 - γ × σ² × (T-t) × q

其中:
  γ = 风险厌恶系数（越大越保守）
  σ = 波动率
  T-t = 剩余时间
  q = 当前库存偏移（正=多头库存，需降低 ask 减仓）
  spread = 最小价差 = 2/γ × ln(1 + γ/κ)
  κ = 订单到达强度
```

**实施要点**：
- 适合流动性好的主流币对（BTC/USDT, ETH/USDT）
- 需要 Maker 手续费优惠（VIP 等级或做市商计划）
- 库存管理是核心：库存偏移过大时需主动对冲

```python
import math

class AvellanedaStoikov:
    def __init__(self, gamma=0.1, sigma=0.02, kappa=1.5, T=1.0):
        self.gamma = gamma   # 风险厌恶
        self.sigma = sigma   # 波动率
        self.kappa = kappa   # 订单到达强度
        self.T = T           # 时间周期

    def optimal_quotes(self, mid_price: float, inventory: float,
                        time_remaining: float) -> tuple:
        """计算最优买卖报价"""
        reservation_price = mid_price - self.gamma * self.sigma**2 * \
                           time_remaining * inventory
        optimal_spread = (2 / self.gamma) * math.log(1 + self.gamma / self.kappa)
        optimal_spread += self.gamma * self.sigma**2 * time_remaining

        bid = reservation_price - optimal_spread / 2
        ask = reservation_price + optimal_spread / 2

        return round(bid, 2), round(ask, 2)
```

**币安做市商计划**：
- 需申请加入 Binance Market Maker Program
- VIP 7+ 可获得 Maker 负手续费（-0.005%）
- 要求：月交易量 > $100M 或流动性指标达标

---

### 1.5 AI/ML 量化策略

#### 1.5.1 LSTM 价格预测

**架构设计**：

```
输入特征 (window=60):
  - OHLCV 数据
  - 技术指标: RSI, MACD, BB, ATR, OBV
  - 市场微观结构: 买卖价差, 深度不平衡
  - 时间特征: 小时, 星期几

LSTM 模型:
  Input(60, n_features) → LSTM(128) → Dropout(0.3)
  → LSTM(64) → Dropout(0.3) → Dense(32) → Dense(1)

输出: 下一根K线的涨跌概率
```

**特征工程**：

```python
def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """构建 ML 特征"""
    features = pd.DataFrame(index=df.index)

    # 价格变化特征
    features['returns'] = df['close'].pct_change()
    features['log_returns'] = np.log(df['close'] / df['close'].shift(1))

    # 技术指标
    features['rsi_14'] = compute_rsi(df['close'], 14)
    features['macd'] = df['close'].ewm(12).mean() - df['close'].ewm(26).mean()
    features['bb_position'] = (df['close'] - df['close'].rolling(20).mean()) / \
                               (df['close'].rolling(20).std() * 2)
    features['atr_14'] = compute_atr(df, 14)

    # 成交量特征
    features['volume_ma_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    features['obv'] = (np.sign(df['close'].diff()) * df['volume']).cumsum()

    # 时间特征
    features['hour'] = df.index.hour
    features['day_of_week'] = df.index.dayofweek

    return features.dropna()
```

**过拟合防范**：
- 严格分割：训练集 60% / 验证集 20% / 测试集 20%（按时间顺序）
- 禁止 lookahead bias
- Walk-Forward 验证
- 正则化 + Dropout
- 集成多个模型取平均

---

#### 1.5.2 强化学习交易（DQN）

**状态/动作/奖励定义**：

```
状态 S:
  - 最近 N 根K线的 OHLCV
  - 当前持仓（多头/空头/空仓）
  - 未实现盈亏
  - 账户余额

动作 A:
  - 买入（固定仓位 or Kelly 仓位）
  - 卖出
  - 持有

奖励 R:
  - 基础奖励: 每步的 PnL 变化
  - 风险惩罚: -λ × max_drawdown
  - 交易成本: -fee × |trade_size|
  - 夏普奖励: 正夏普比给予额外奖励
```

**DQN 实现思路**：

```python
# 简化的 DQN 交易环境
class TradingEnv:
    ACTIONS = ['hold', 'buy', 'sell']

    def __init__(self, df, initial_balance=10000):
        self.df = df
        self.initial_balance = initial_balance
        self.reset()

    def reset(self):
        self.balance = self.initial_balance
        self.position = 0  # 1=多, -1=空, 0=空仓
        self.step_idx = 0
        return self._get_state()

    def step(self, action):
        price = self.df['close'].iloc[self.step_idx]
        reward = 0

        if action == 1 and self.position <= 0:  # 买入
            self.position = 1
            self.entry_price = price
            reward -= price * 0.001  # 手续费
        elif action == 2 and self.position >= 0:  # 卖出
            if self.position == 1:
                reward += (price - self.entry_price) / self.entry_price
            self.position = -1 if self.position == 0 else 0

        self.step_idx += 1
        done = self.step_idx >= len(self.df) - 1
        return self._get_state(), reward, done
```

---

#### 1.5.3 情绪分析因子

**数据源**：
- Twitter/X API：关键词搜索 + KOL 监控
- CryptoPanic API：新闻聚合与情绪评分
- Fear & Greed Index：加密市场恐惧贪婪指数
- Reddit（r/cryptocurrency, r/bitcoin）

**情绪打分方法**：

```python
from transformers import pipeline

sentiment_analyzer = pipeline("sentiment-analysis",
                               model="finiteautomata/bertweet-base-sentiment-analysis")

def compute_sentiment_score(texts: list[str]) -> float:
    """批量计算情绪分数 [-1, 1]"""
    results = sentiment_analyzer(texts)
    score_map = {'POS': 1, 'NEG': -1, 'NEU': 0}
    scores = [score_map.get(r['label'], 0) * r['score'] for r in results]
    return sum(scores) / len(scores) if scores else 0

# 因子融合: 情绪因子作为辅助信号
def sentiment_enhanced_signal(technical_signal, sentiment_score, threshold=0.3):
    """情绪增强信号"""
    if technical_signal == 1 and sentiment_score > threshold:
        return 1   # 技术+情绪双确认买入
    elif technical_signal == -1 and sentiment_score < -threshold:
        return -1  # 双确认卖出
    elif technical_signal != 0 and abs(sentiment_score) < threshold:
        return technical_signal * 0.5  # 半仓信号（情绪不配合）
    return 0
```

---

## 2. 回测体系

### 2.1 回测框架设计原则

| 原则 | 说明 |
|------|------|
| 事件驱动 | 模拟真实交易流程：数据到达 → 信号生成 → 下单 → 成交确认 |
| 零未来信息 | 严禁 lookahead bias，所有指标仅使用当前及之前数据 |
| 真实成本 | 包含手续费、滑点、资金费率、提币费 |
| 可复现 | 固定随机种子，记录完整参数和数据版本 |

### 2.2 滑点模拟

```python
def simulate_slippage(price: float, volume: float, order_size: float,
                       is_buy: bool) -> float:
    """
    滑点模拟（固定 + 比例）
    - 固定滑点: 0.01%
    - 比例滑点: 与订单量/市场量的比值成正比
    """
    fixed_slippage = 0.0001  # 0.01%
    volume_impact = (order_size / volume) * 0.1  # 大单冲击
    total_slippage = fixed_slippage + volume_impact

    if is_buy:
        return price * (1 + total_slippage)
    else:
        return price * (1 - total_slippage)
```

### 2.3 手续费计算

| 费率类型 | Maker | Taker | BNB折扣后 |
|---------|-------|-------|----------|
| 普通用户 | 0.10% | 0.10% | 0.075% |
| VIP 1 | 0.09% | 0.10% | 0.0675% |
| VIP 3 | 0.06% | 0.08% | 0.045% |
| 做市商 | -0.005% | 0.02% | - |

### 2.4 关键评估指标

```python
def compute_metrics(equity_curve: pd.Series, risk_free_rate=0.02) -> dict:
    """计算策略评估指标"""
    returns = equity_curve.pct_change().dropna()

    # 年化收益
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0] - 1
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    annualized_return = (1 + total_return) ** (365 / days) - 1

    # 夏普比率 = (Rp - Rf) / σp
    excess_returns = returns.mean() * 365 - risk_free_rate
    sharpe = excess_returns / (returns.std() * np.sqrt(365))

    # 最大回撤
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak
    max_drawdown = drawdown.min()

    # 索提诺比率（只考虑下行波动）
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() * np.sqrt(365)
    sortino = excess_returns / downside_std if downside_std > 0 else 0

    # 卡尔马比率 = 年化收益 / |最大回撤|
    calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

    # 胜率和盈亏比
    trades = returns[returns != 0]
    win_rate = (trades > 0).mean()
    avg_win = trades[trades > 0].mean() if (trades > 0).any() else 0
    avg_loss = abs(trades[trades < 0].mean()) if (trades < 0).any() else 1
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')

    return {
        'annualized_return_pct': round(annualized_return * 100, 2),
        'sharpe_ratio': round(sharpe, 2),
        'max_drawdown_pct': round(max_drawdown * 100, 2),
        'sortino_ratio': round(sortino, 2),
        'calmar_ratio': round(calmar, 2),
        'win_rate_pct': round(win_rate * 100, 2),
        'profit_loss_ratio': round(profit_loss_ratio, 2),
    }
```

### 2.5 Walk-Forward 分析

**流程**：
1. 将数据切割为多个 train/test 窗口（如 180天训练 / 30天测试）
2. 在每个训练窗口上优化参数
3. 用优化后的参数在测试窗口上运行
4. 拼接所有测试窗口的结果，计算整体表现
5. 如果 Walk-Forward 效率（WF效率 = 样本外收益/样本内收益）> 50%，策略具备鲁棒性

### 2.6 Monte Carlo 模拟

对历史交易序列进行随机重排（保持收益分布不变），运行 1000+ 次模拟，生成收益率的置信区间：

```python
def monte_carlo_simulation(trade_returns: np.ndarray, n_simulations=1000) -> dict:
    """蒙特卡洛模拟"""
    results = []
    for _ in range(n_simulations):
        shuffled = np.random.choice(trade_returns, size=len(trade_returns), replace=True)
        equity = np.cumprod(1 + shuffled)
        total_return = equity[-1] - 1
        max_dd = np.min(equity / np.maximum.accumulate(equity) - 1)
        results.append({'return': total_return, 'max_dd': max_dd})

    returns = [r['return'] for r in results]
    drawdowns = [r['max_dd'] for r in results]

    return {
        'return_5th_pct': np.percentile(returns, 5),
        'return_median': np.median(returns),
        'return_95th_pct': np.percentile(returns, 95),
        'max_dd_5th_pct': np.percentile(drawdowns, 5),  # 最差情况
        'max_dd_median': np.median(drawdowns),
    }
```

---

## 3. 策略评估与选择矩阵

### 3.1 策略对比

| 策略 | 适用市况 | 预期年化 | 最大回撤 | 夏普比 | 复杂度 | 最低资金 |
|------|---------|---------|---------|-------|--------|---------|
| 双均线交叉 | 趋势行情 | 20-60% | 15-25% | 0.8-1.5 | 低 | $1,000 |
| MACD | 趋势行情 | 15-50% | 15-30% | 0.7-1.3 | 低 | $1,000 |
| 布林带突破 | Squeeze后 | 25-80% | 20-35% | 0.8-1.6 | 中 | $2,000 |
| RSI 动量 | 震荡+趋势 | 10-40% | 10-20% | 0.6-1.2 | 低 | $1,000 |
| 海龟法则 | 强趋势 | 30-100% | 25-40% | 0.9-1.8 | 中 | $5,000 |
| 配对交易 | 震荡行情 | 10-25% | 5-15% | 1.0-2.0 | 高 | $10,000 |
| Z-Score回归 | 震荡行情 | 8-20% | 5-12% | 1.0-1.8 | 中 | $3,000 |
| 基差套利 | 全市况 | 8-15% | 2-5% | 2.0-4.0 | 中 | $20,000 |
| 资金费率套利 | 正费率期 | 5-15% | 1-3% | 2.5-5.0 | 低 | $10,000 |
| 三角套利 | 全市况 | 3-10% | <1% | 3.0+ | 高 | $50,000 |
| 做市策略 | 高流动性 | 15-40% | 5-15% | 1.5-3.0 | 极高 | $100,000 |
| LSTM 预测 | 全市况 | -20~60% | 20-50% | 0.3-1.5 | 极高 | $5,000 |
| 强化学习 | 全市况 | -30~80% | 25-60% | 0.2-1.5 | 极高 | $5,000 |

### 3.2 市场环境适配

| 市况 | 推荐策略组合 | 资金分配 |
|------|------------|---------|
| 牛市（单边上涨） | 海龟法则 + 均线策略 + 资金费率套利 | 50% + 30% + 20% |
| 熊市（单边下跌） | 反向均线策略 + 基差套利 | 40% + 60% |
| 震荡市 | 配对交易 + Z-Score + 三角套利 | 40% + 30% + 30% |
| 高波动 | 布林带突破 + 做市策略 | 60% + 40% |

### 3.3 Kelly 仓位管理

```python
def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float,
                    kelly_factor: float = 0.5) -> float:
    """
    Kelly 公式计算最优仓位
    kelly_factor: 通常取半 Kelly（0.5）降低波动
    """
    b = avg_win / avg_loss  # 盈亏比
    p = win_rate
    q = 1 - p

    f = (p * b - q) / b
    f = max(0, f)  # 负值意味着不应该交易

    return f * kelly_factor  # 半 Kelly
```

**实战建议**：
- 永远使用**半 Kelly**（Full Kelly 波动太大）
- 单策略仓位上限：总资金的 15%
- 总组合仓位上限：总资金的 80%（保留 20% 现金）

---

## 4. 策略代码模板

以下是一个完整的、可运行的双均线策略代码模板，基于 CCXT 连接币安：

```python
"""
币安量化交易策略模板
基于 CCXT + 双均线交叉策略
"""

import ccxt
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
from typing import Optional

# ==================== 配置 ====================

CONFIG = {
    'exchange': 'binance',
    'symbol': 'BTC/USDT',
    'timeframe': '4h',
    'fast_ma': 7,
    'slow_ma': 25,
    'max_position_pct': 0.3,       # 最大仓位占比 30%
    'risk_per_trade_pct': 0.01,    # 单笔风险 1%
    'stop_loss_atr_mult': 2.0,     # 止损 = 2 × ATR
    'take_profit_atr_mult': 4.0,   # 止盈 = 4 × ATR
    'use_testnet': True,           # 是否使用测试网
}

# ==================== 日志 ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== 交易所连接 ====================

def create_exchange(api_key: str, api_secret: str) -> ccxt.binance:
    """初始化交易所连接"""
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'sandbox': CONFIG['use_testnet'],
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
            'adjustForTimeDifference': True,
        }
    })
    exchange.load_markets()
    logger.info(f"Connected to {'Testnet' if CONFIG['use_testnet'] else 'Production'}")
    return exchange

# ==================== 数据获取 ====================

def fetch_ohlcv(exchange: ccxt.binance, symbol: str, timeframe: str,
                limit: int = 200) -> pd.DataFrame:
    """获取历史K线数据"""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

# ==================== 指标计算 ====================

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标"""
    df = df.copy()

    # 均线
    df['ema_fast'] = df['close'].ewm(span=CONFIG['fast_ma'], adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=CONFIG['slow_ma'], adjust=False).mean()

    # ATR（用于止损止盈）
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    # RSI（辅助过滤）
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df

# ==================== 信号生成 ====================

def generate_signal(df: pd.DataFrame) -> int:
    """
    生成交易信号
    返回: 1=买入, -1=卖出, 0=持有
    """
    if len(df) < CONFIG['slow_ma'] + 2:
        return 0

    current = df.iloc[-1]
    previous = df.iloc[-2]

    # Golden Cross
    if (current['ema_fast'] > current['ema_slow'] and
        previous['ema_fast'] <= previous['ema_slow']):
        if current['rsi'] < 75:  # RSI 过滤：不在极度超买区买入
            return 1

    # Death Cross
    if (current['ema_fast'] < current['ema_slow'] and
        previous['ema_fast'] >= previous['ema_slow']):
        if current['rsi'] > 25:  # RSI 过滤：不在极度超卖区卖出
            return -1

    return 0

# ==================== 仓位计算 ====================

def calculate_position_size(exchange: ccxt.binance, symbol: str,
                             atr: float) -> float:
    """基于风险的仓位计算"""
    balance = exchange.fetch_balance()
    free_usdt = balance['free'].get('USDT', 0)

    # 最大允许仓位
    max_position_value = free_usdt * CONFIG['max_position_pct']

    # 基于风险的仓位
    risk_amount = free_usdt * CONFIG['risk_per_trade_pct']
    stop_distance = atr * CONFIG['stop_loss_atr_mult']
    risk_based_size = risk_amount / stop_distance

    # 取较小值
    ticker = exchange.fetch_ticker(symbol)
    price = ticker['last']
    risk_based_value = risk_based_size * price

    position_value = min(max_position_value, risk_based_value)
    position_size = position_value / price

    # 取整到交易所最小精度
    market = exchange.market(symbol)
    precision = market['precision']['amount']
    position_size = float(exchange.amount_to_precision(symbol, position_size))

    logger.info(f"Position size: {position_size} ({position_value:.2f} USDT)")
    return position_size

# ==================== 下单执行 ====================

def execute_order(exchange: ccxt.binance, symbol: str, side: str,
                   amount: float, price: Optional[float] = None) -> dict:
    """
    执行下单，支持限价单和市价单
    失败自动重试 3 次
    """
    for attempt in range(3):
        try:
            if price:
                order = exchange.create_limit_order(symbol, side, amount, price)
            else:
                order = exchange.create_market_order(symbol, side, amount)

            logger.info(f"Order executed: {side} {amount} {symbol} @ "
                        f"{'market' if not price else price}")
            return order

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds: {e}")
            return None
        except ccxt.NetworkError as e:
            logger.warning(f"Network error (attempt {attempt+1}/3): {e}")
            time.sleep(2 ** attempt)
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error: {e}")
            return None

    logger.error("Order failed after 3 attempts")
    return None

# ==================== 止损止盈 ====================

def manage_stop_loss_take_profit(exchange: ccxt.binance, symbol: str,
                                  entry_price: float, atr: float,
                                  side: str):
    """设置止损止盈单"""
    if side == 'buy':
        stop_price = entry_price - CONFIG['stop_loss_atr_mult'] * atr
        tp_price = entry_price + CONFIG['take_profit_atr_mult'] * atr
    else:
        stop_price = entry_price + CONFIG['stop_loss_atr_mult'] * atr
        tp_price = entry_price - CONFIG['take_profit_atr_mult'] * atr

    logger.info(f"Stop Loss: {stop_price:.2f}, Take Profit: {tp_price:.2f}")
    return stop_price, tp_price

# ==================== 主循环 ====================

def run_strategy(api_key: str, api_secret: str):
    """策略主循环"""
    exchange = create_exchange(api_key, api_secret)
    symbol = CONFIG['symbol']
    timeframe = CONFIG['timeframe']
    current_position = 0  # 1=多头, -1=空头, 0=空仓
    entry_price = 0

    logger.info(f"Starting strategy: {symbol} {timeframe}")
    logger.info(f"Parameters: MA({CONFIG['fast_ma']}/{CONFIG['slow_ma']})")

    while True:
        try:
            # 1. 获取数据
            df = fetch_ohlcv(exchange, symbol, timeframe)
            df = compute_indicators(df)

            # 2. 生成信号
            signal = generate_signal(df)
            current_price = df['close'].iloc[-1]
            current_atr = df['atr'].iloc[-1]

            logger.info(f"Price: {current_price:.2f}, ATR: {current_atr:.2f}, "
                        f"Signal: {signal}, Position: {current_position}")

            # 3. 检查止损止盈（已有仓位时）
            if current_position != 0 and entry_price > 0:
                sl, tp = manage_stop_loss_take_profit(
                    exchange, symbol, entry_price, current_atr,
                    'buy' if current_position == 1 else 'sell'
                )
                if (current_position == 1 and current_price <= sl) or \
                   (current_position == -1 and current_price >= sl):
                    logger.info("Stop loss triggered!")
                    execute_order(exchange, symbol,
                                'sell' if current_position == 1 else 'buy',
                                abs(current_position))
                    current_position = 0
                    entry_price = 0

            # 4. 执行交易
            if signal == 1 and current_position <= 0:
                if current_position == -1:
                    # 先平空仓
                    execute_order(exchange, symbol, 'buy', abs(current_position))

                size = calculate_position_size(exchange, symbol, current_atr)
                if size > 0:
                    order = execute_order(exchange, symbol, 'buy', size)
                    if order:
                        current_position = size
                        entry_price = current_price

            elif signal == -1 and current_position >= 0:
                if current_position > 0:
                    execute_order(exchange, symbol, 'sell', current_position)
                    current_position = 0
                    entry_price = 0

            # 5. 等待下一根K线
            sleep_seconds = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600,
                             '4h': 14400, '1d': 86400}
            time.sleep(sleep_seconds.get(timeframe, 3600))

        except KeyboardInterrupt:
            logger.info("Strategy stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(60)

# ==================== 入口 ====================

if __name__ == '__main__':
    import os
    API_KEY = os.environ.get('BINANCE_API_KEY', '')
    API_SECRET = os.environ.get('BINANCE_API_SECRET', '')

    if not API_KEY or not API_SECRET:
        logger.error("Please set BINANCE_API_KEY and BINANCE_API_SECRET")
        exit(1)

    run_strategy(API_KEY, API_SECRET)
```

---

## 附录：策略开发检查清单

- [ ] 策略逻辑是否存在未来信息泄露（lookahead bias）
- [ ] 是否正确处理了手续费和滑点
- [ ] 回测数据是否覆盖了不同市场环境（牛/熊/震荡）
- [ ] 参数是否经过 Walk-Forward 验证
- [ ] 仓位管理是否合理（单笔风险 < 2%）
- [ ] 是否有止损机制
- [ ] 极端行情下的行为是否可控
- [ ] 代码是否有完整的错误处理和日志
- [ ] 是否在测试网验证过
- [ ] 是否考虑了 API 限流和网络异常

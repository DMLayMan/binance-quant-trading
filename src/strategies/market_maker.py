"""
做市策略 — Avellaneda-Stoikov 模型

原理：做市商同时挂买单和卖单，赚取买卖价差。
通过库存风险参数 γ 动态调整报价。

适用场景：高流动性主流币对
预期表现：夏普比率 1.5-3.0，最大回撤 5-15%
最低资金：$100,000
"""

import math


class AvellanedaStoikov:
    """Avellaneda-Stoikov 最优做市模型"""

    def __init__(
        self,
        gamma: float = 0.1,
        sigma: float = 0.02,
        kappa: float = 1.5,
        T: float = 1.0,
    ):
        """
        Args:
            gamma: 风险厌恶系数（越大越保守）
            sigma: 波动率
            kappa: 订单到达强度
            T: 时间周期
        """
        self.gamma = gamma
        self.sigma = sigma
        self.kappa = kappa
        self.T = T

    def optimal_quotes(
        self, mid_price: float, inventory: float, time_remaining: float
    ) -> tuple[float, float]:
        """
        计算最优买卖报价

        Args:
            mid_price: 中间价
            inventory: 当前库存偏移（正=多头库存）
            time_remaining: 剩余时间（0-1）

        Returns:
            (bid_price, ask_price)
        """
        reservation_price = mid_price - self.gamma * self.sigma**2 * \
            time_remaining * inventory

        optimal_spread = (2 / self.gamma) * math.log(
            1 + self.gamma / self.kappa
        )
        optimal_spread += self.gamma * self.sigma**2 * time_remaining

        bid = reservation_price - optimal_spread / 2
        ask = reservation_price + optimal_spread / 2

        return round(bid, 2), round(ask, 2)

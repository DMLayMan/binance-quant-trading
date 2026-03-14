"""
套利策略集合

包含：
- 现货-合约基差套利 (Cash & Carry)
- 三角套利 (Triangular Arbitrage)
- 资金费率套利 (Funding Rate Arbitrage)
"""


def basis_arbitrage_check(
    spot_price: float,
    futures_price: float,
    maker_fee: float = 0.001,
) -> dict:
    """
    基差套利可行性检查

    Args:
        spot_price: 现货价格
        futures_price: 合约价格
        maker_fee: 单边手续费率

    Returns:
        套利分析结果
    """
    basis = futures_price - spot_price
    basis_rate = basis / spot_price
    total_fee = maker_fee * 4  # 开仓2笔 + 平仓2笔

    net_profit_rate = basis_rate - total_fee
    annualized = net_profit_rate * 365  # 假设1天收敛

    return {
        "basis": basis,
        "basis_rate_pct": basis_rate * 100,
        "net_profit_rate_pct": net_profit_rate * 100,
        "annualized_pct": annualized * 100,
        "executable": net_profit_rate > 0.001,  # 净利润 > 0.1% 才执行
    }


def triangular_arbitrage_check(
    btc_usdt: float,
    eth_btc: float,
    eth_usdt_sell: float,
    fee_rate: float = 0.001,
) -> dict:
    """
    三角套利检测

    路径: USDT → BTC → ETH → USDT

    Args:
        btc_usdt: BTC/USDT 买价
        eth_btc: ETH/BTC 买价
        eth_usdt_sell: ETH/USDT 卖价
        fee_rate: 单边手续费率

    Returns:
        套利分析结果
    """
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
        "profit_usdt": round(profit, 4),
        "profit_rate_pct": round(profit_rate * 100, 4),
        "executable": profit_rate > 0.0005,  # > 0.05% 才执行
    }


def funding_rate_annual_return(
    funding_rate: float, periods_per_day: int = 3
) -> float:
    """
    资金费率年化收益计算

    Args:
        funding_rate: 单次资金费率（如 0.0001 = 0.01%）
        periods_per_day: 每天结算次数（币安默认 3 次/天，每 8 小时）

    Returns:
        年化收益率
    """
    return funding_rate * periods_per_day * 365

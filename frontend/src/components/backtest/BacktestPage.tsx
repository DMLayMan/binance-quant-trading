import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useStrategies, useRunBacktest } from "../../api/hooks.ts";
import type { BacktestRequest, BacktestResponse } from "../../types/index.ts";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

function fmt(n: number, d = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];

export default function BacktestPage() {
  const { data: strategies } = useStrategies();
  const mutation = useRunBacktest();

  const [form, setForm] = useState<BacktestRequest>({
    strategy_name: "ma_crossover",
    symbol: "BTC/USDT",
    timeframe: "4h",
    initial_capital: 100000,
    maker_fee: 0.001,
    taker_fee: 0.001,
    slippage_pct: 0.0001,
    stop_loss_atr_mult: 2.0,
    take_profit_atr_mult: 4.0,
    strategy_params: {},
  });

  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [tradeSort, setTradeSort] = useState<"time" | "pnl">("time");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate(form, {
      onSuccess: (data) => setResult(data),
    });
  }

  function update(field: string, value: unknown) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const sortedTrades = result
    ? [...result.trade_log].sort((a, b) =>
        tradeSort === "pnl" ? b.pnl - a.pnl : a.timestamp - b.timestamp,
      )
    : [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Backtest</h1>

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-xl bg-gray-800 p-5"
        >
          <div>
            <label className="mb-1 block text-xs text-gray-400">Strategy</label>
            <select
              value={form.strategy_name}
              onChange={(e) => update("strategy_name", e.target.value)}
              className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600"
            >
              {strategies?.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-gray-400">Symbol</label>
              <input
                value={form.symbol}
                onChange={(e) => update("symbol", e.target.value)}
                className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Timeframe
              </label>
              <select
                value={form.timeframe}
                onChange={(e) => update("timeframe", e.target.value)}
                className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600"
              >
                {TIMEFRAMES.map((tf) => (
                  <option key={tf} value={tf}>
                    {tf}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-gray-400">
              Initial Capital (USDT)
            </label>
            <input
              type="number"
              value={form.initial_capital}
              onChange={(e) => update("initial_capital", Number(e.target.value))}
              className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Maker Fee
              </label>
              <input
                type="number"
                step="0.0001"
                value={form.maker_fee}
                onChange={(e) => update("maker_fee", Number(e.target.value))}
                className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Taker Fee
              </label>
              <input
                type="number"
                step="0.0001"
                value={form.taker_fee}
                onChange={(e) => update("taker_fee", Number(e.target.value))}
                className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Stop Loss (ATR x)
              </label>
              <input
                type="number"
                step="0.1"
                value={form.stop_loss_atr_mult}
                onChange={(e) =>
                  update("stop_loss_atr_mult", Number(e.target.value))
                }
                className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Take Profit (ATR x)
              </label>
              <input
                type="number"
                step="0.1"
                value={form.take_profit_atr_mult}
                onChange={(e) =>
                  update("take_profit_atr_mult", Number(e.target.value))
                }
                className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={mutation.isPending}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Running..." : "Run Backtest"}
          </button>

          {mutation.isError && (
            <p className="text-sm text-red-400">
              {mutation.error?.message || "Backtest failed"}
            </p>
          )}
        </form>

        {/* Results */}
        <div className="space-y-4">
          {mutation.isPending && <LoadingSpinner />}

          {result && (
            <>
              {/* Metrics */}
              <div className="rounded-xl bg-gray-800 p-5">
                <h2 className="mb-4 text-lg font-semibold text-white">
                  Performance Summary
                </h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    {
                      label: "Total Return",
                      value: `${fmt(result.summary.total_return_pct)}%`,
                      positive: result.summary.total_return_pct >= 0,
                    },
                    {
                      label: "Annualized Return",
                      value: `${fmt(result.summary.annualized_return_pct)}%`,
                      positive: result.summary.annualized_return_pct >= 0,
                    },
                    {
                      label: "Sharpe Ratio",
                      value: fmt(result.summary.sharpe_ratio),
                      positive: result.summary.sharpe_ratio >= 1,
                    },
                    {
                      label: "Sortino Ratio",
                      value: fmt(result.summary.sortino_ratio),
                      positive: result.summary.sortino_ratio >= 1,
                    },
                    {
                      label: "Max Drawdown",
                      value: `${fmt(result.summary.max_drawdown_pct)}%`,
                      positive: false,
                    },
                    {
                      label: "Win Rate",
                      value: `${fmt(result.summary.win_rate_pct)}%`,
                      positive: result.summary.win_rate_pct >= 50,
                    },
                    {
                      label: "Profit Factor",
                      value: fmt(result.summary.profit_factor),
                      positive: result.summary.profit_factor >= 1,
                    },
                    {
                      label: "Total Fees",
                      value: `$${fmt(result.summary.total_fees)}`,
                      positive: false,
                    },
                  ].map((m) => (
                    <div key={m.label} className="rounded-lg bg-gray-700/50 p-3">
                      <div className="text-xs text-gray-400">{m.label}</div>
                      <div
                        className={`mt-1 text-lg font-bold ${
                          m.positive ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {m.value}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex gap-4 text-sm text-gray-400">
                  <span>
                    Initial: ${fmt(result.summary.initial_capital)}
                  </span>
                  <span>
                    Final: ${fmt(result.summary.final_equity)}
                  </span>
                  <span>Trades: {result.summary.total_trades}</span>
                </div>
              </div>

              {/* Equity Curve */}
              {result.equity_curve.length > 0 && (
                <div className="rounded-xl bg-gray-800 p-5">
                  <h2 className="mb-4 text-lg font-semibold text-white">
                    Equity Curve
                  </h2>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart
                      data={result.equity_curve.map((p) => ({
                        time: new Date(p.timestamp).toLocaleDateString(),
                        equity: p.equity,
                      }))}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis
                        dataKey="time"
                        stroke="#6b7280"
                        fontSize={11}
                        tickLine={false}
                      />
                      <YAxis
                        stroke="#6b7280"
                        fontSize={11}
                        tickLine={false}
                        tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#1f2937",
                          border: "1px solid #374151",
                          borderRadius: "8px",
                          color: "#e5e7eb",
                        }}
                        formatter={(v) => [`$${fmt(Number(v))}`, "Equity"]}
                      />
                      <Area
                        type="monotone"
                        dataKey="equity"
                        stroke="#3b82f6"
                        fill="url(#eqGradient)"
                        strokeWidth={2}
                      />
                      <defs>
                        <linearGradient
                          id="eqGradient"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#3b82f6"
                            stopOpacity={0.3}
                          />
                          <stop
                            offset="100%"
                            stopColor="#3b82f6"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Trade Log */}
              {result.trade_log.length > 0 && (
                <div className="rounded-xl bg-gray-800 p-5">
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-white">
                      Trade Log ({result.trade_log.length})
                    </h2>
                    <div className="flex gap-1 text-xs">
                      <button
                        onClick={() => setTradeSort("time")}
                        className={`rounded px-2 py-1 ${tradeSort === "time" ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-400"}`}
                      >
                        By Time
                      </button>
                      <button
                        onClick={() => setTradeSort("pnl")}
                        className={`rounded px-2 py-1 ${tradeSort === "pnl" ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-400"}`}
                      >
                        By P&L
                      </button>
                    </div>
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-gray-800">
                        <tr className="border-b border-gray-700 text-left text-gray-400">
                          <th className="pb-2 pr-3">Time</th>
                          <th className="pb-2 pr-3">Side</th>
                          <th className="pb-2 pr-3 text-right">Price</th>
                          <th className="pb-2 pr-3 text-right">Amount</th>
                          <th className="pb-2 pr-3 text-right">Fee</th>
                          <th className="pb-2 text-right">P&L</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedTrades.map((t, i) => (
                          <tr
                            key={i}
                            className="border-b border-gray-700/50"
                          >
                            <td className="py-1.5 pr-3 text-gray-400">
                              {new Date(t.timestamp).toLocaleString()}
                            </td>
                            <td className="py-1.5 pr-3">
                              <span
                                className={
                                  t.side === "buy"
                                    ? "text-green-400"
                                    : "text-red-400"
                                }
                              >
                                {t.side.toUpperCase()}
                              </span>
                            </td>
                            <td className="py-1.5 pr-3 text-right text-gray-300">
                              ${fmt(t.price)}
                            </td>
                            <td className="py-1.5 pr-3 text-right text-gray-300">
                              {t.amount.toFixed(6)}
                            </td>
                            <td className="py-1.5 pr-3 text-right text-gray-400">
                              ${fmt(t.fee)}
                            </td>
                            <td
                              className={`py-1.5 text-right font-medium ${t.pnl >= 0 ? "text-green-400" : "text-red-400"}`}
                            >
                              {t.pnl !== 0
                                ? `${t.pnl >= 0 ? "+" : ""}$${fmt(t.pnl)}`
                                : "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}

          {!result && !mutation.isPending && (
            <div className="flex h-64 items-center justify-center rounded-xl bg-gray-800 text-gray-500">
              Configure parameters and run a backtest to see results
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

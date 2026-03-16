import { useState } from "react";
import {
  useOrders,
  useTrades,
  useTradeStats,
  useRiskEvents,
} from "../../api/hooks.ts";
import MetricCard from "../shared/MetricCard.tsx";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

type Tab = "trades" | "orders" | "risk-events";

export default function TradesPage() {
  const [tab, setTab] = useState<Tab>("trades");
  const { data: stats, isLoading: statsLoading } = useTradeStats();
  const { data: trades, isLoading: tradesLoading } = useTrades();
  const { data: orders, isLoading: ordersLoading } = useOrders();
  const { data: events, isLoading: eventsLoading } = useRiskEvents();

  const isLoading = statsLoading && tradesLoading;
  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Orders & Trades</h1>

      {/* Stats Cards */}
      {stats && stats.total_trades > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Total P&L"
            value={`$${fmt(stats.total_pnl)}`}
            change={stats.total_pnl}
          />
          <MetricCard
            title="Win Rate"
            value={`${fmt(stats.win_rate)}%`}
            subtitle={`${stats.winning_trades}W / ${stats.losing_trades}L of ${stats.total_trades}`}
          />
          <MetricCard
            title="Avg Win / Loss"
            value={`$${fmt(stats.avg_win)} / $${fmt(stats.avg_loss)}`}
            subtitle={`Best: $${fmt(stats.max_win)} | Worst: $${fmt(stats.max_loss)}`}
          />
          <MetricCard
            title="Total Fees"
            value={`$${fmt(stats.total_fees)}`}
            subtitle={`Avg hold: ${formatDuration(stats.avg_holding_seconds)}`}
          />
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg bg-gray-800 p-1 w-fit">
        {(["trades", "orders", "risk-events"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t
                ? "bg-gray-700 text-white"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {t === "risk-events" ? "Risk Events" : t.charAt(0).toUpperCase() + t.slice(1)}
            {t === "trades" && trades ? ` (${trades.length})` : ""}
            {t === "orders" && orders ? ` (${orders.length})` : ""}
            {t === "risk-events" && events ? ` (${events.length})` : ""}
          </button>
        ))}
      </div>

      {/* Trades tab */}
      {tab === "trades" && (
        <div className="rounded-xl bg-gray-800 p-5">
          {tradesLoading ? (
            <LoadingSpinner />
          ) : trades && trades.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700 text-left text-gray-400">
                    <th className="pb-3 pr-3">Symbol</th>
                    <th className="pb-3 pr-3">Side</th>
                    <th className="pb-3 pr-3 text-right">Entry</th>
                    <th className="pb-3 pr-3 text-right">Exit</th>
                    <th className="pb-3 pr-3 text-right">Amount</th>
                    <th className="pb-3 pr-3 text-right">P&L</th>
                    <th className="pb-3 pr-3 text-right">P&L %</th>
                    <th className="pb-3 pr-3">Reason</th>
                    <th className="pb-3 pr-3">Duration</th>
                    <th className="pb-3">Exit Time</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((t) => (
                    <tr key={t.id} className="border-b border-gray-700/50">
                      <td className="py-2.5 pr-3 font-medium text-white">{t.symbol}</td>
                      <td className="py-2.5 pr-3">
                        <span className={t.side === "buy" ? "text-green-400" : "text-red-400"}>
                          {t.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 text-right text-gray-300">${fmt(t.entry_price)}</td>
                      <td className="py-2.5 pr-3 text-right text-gray-300">${fmt(t.exit_price)}</td>
                      <td className="py-2.5 pr-3 text-right text-gray-300">{t.amount.toFixed(6)}</td>
                      <td className={`py-2.5 pr-3 text-right font-medium ${t.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                        ${fmt(t.pnl)}
                      </td>
                      <td className={`py-2.5 pr-3 text-right ${t.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {fmt(t.pnl_pct)}%
                      </td>
                      <td className="py-2.5 pr-3 text-gray-400 text-xs">{t.exit_reason ?? "-"}</td>
                      <td className="py-2.5 pr-3 text-gray-400 text-xs">{formatDuration(t.holding_seconds)}</td>
                      <td className="py-2.5 text-gray-500 text-xs">{new Date(t.exit_time).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-center text-gray-500 py-8">No trades recorded yet.</p>
          )}
        </div>
      )}

      {/* Orders tab */}
      {tab === "orders" && (
        <div className="rounded-xl bg-gray-800 p-5">
          {ordersLoading ? (
            <LoadingSpinner />
          ) : orders && orders.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700 text-left text-gray-400">
                    <th className="pb-3 pr-3">Symbol</th>
                    <th className="pb-3 pr-3">Side</th>
                    <th className="pb-3 pr-3">Type</th>
                    <th className="pb-3 pr-3 text-right">Amount</th>
                    <th className="pb-3 pr-3 text-right">Price</th>
                    <th className="pb-3 pr-3 text-right">Filled</th>
                    <th className="pb-3 pr-3 text-right">Fee</th>
                    <th className="pb-3 pr-3">Status</th>
                    <th className="pb-3 pr-3">Reason</th>
                    <th className="pb-3">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.id} className="border-b border-gray-700/50">
                      <td className="py-2.5 pr-3 font-medium text-white">{o.symbol}</td>
                      <td className="py-2.5 pr-3">
                        <span className={o.side === "buy" ? "text-green-400" : "text-red-400"}>
                          {o.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 text-gray-300">{o.order_type}</td>
                      <td className="py-2.5 pr-3 text-right text-gray-300">{o.amount.toFixed(6)}</td>
                      <td className="py-2.5 pr-3 text-right text-gray-300">
                        {o.price != null ? `$${fmt(o.price)}` : "-"}
                      </td>
                      <td className="py-2.5 pr-3 text-right text-gray-300">{o.filled_amount.toFixed(6)}</td>
                      <td className="py-2.5 pr-3 text-right text-gray-300">${fmt(o.fee)}</td>
                      <td className="py-2.5 pr-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          o.status === "filled" ? "bg-green-500/20 text-green-400" :
                          o.status === "cancelled" ? "bg-gray-500/20 text-gray-400" :
                          "bg-yellow-500/20 text-yellow-400"
                        }`}>
                          {o.status}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 text-gray-400 text-xs max-w-[120px] truncate">{o.reason ?? "-"}</td>
                      <td className="py-2.5 text-gray-500 text-xs">{new Date(o.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-center text-gray-500 py-8">No orders recorded yet.</p>
          )}
        </div>
      )}

      {/* Risk Events tab */}
      {tab === "risk-events" && (
        <div className="rounded-xl bg-gray-800 p-5">
          {eventsLoading ? (
            <LoadingSpinner />
          ) : events && events.length > 0 ? (
            <div className="space-y-2">
              {events.map((ev) => (
                <div key={ev.id} className="flex items-start gap-3 rounded-lg bg-gray-900 p-3">
                  <span className={`mt-0.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                    ev.event_type.includes("stop") || ev.event_type.includes("halt")
                      ? "bg-red-500/20 text-red-400"
                      : ev.event_type.includes("warn")
                        ? "bg-yellow-500/20 text-yellow-400"
                        : "bg-blue-500/20 text-blue-400"
                  }`}>
                    {ev.event_type}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-200">{ev.message}</p>
                    <p className="text-xs text-gray-500 mt-1">{new Date(ev.timestamp).toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-500 py-8">No risk events recorded.</p>
          )}
        </div>
      )}
    </div>
  );
}

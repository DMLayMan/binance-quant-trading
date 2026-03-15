import { useOverview } from "../../api/hooks.ts";
import MetricCard from "../shared/MetricCard.tsx";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export default function OverviewPage() {
  const { data, isLoading, error } = useOverview();

  if (isLoading) return <LoadingSpinner />;
  if (error)
    return (
      <p className="text-red-400">
        Failed to load overview: {(error as Error).message}
      </p>
    );
  if (!data) return null;

  const risk = data.risk_status;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Overview</h1>
        {risk && (
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              risk.is_halted
                ? "bg-red-500/20 text-red-400"
                : "bg-green-500/20 text-green-400"
            }`}
          >
            {risk.is_halted ? "HALTED" : "ACTIVE"}
          </span>
        )}
      </div>

      {/* Metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Equity"
          value={`$${fmt(data.equity)}`}
          subtitle="Total account value"
        />
        <MetricCard
          title="Free USDT"
          value={`$${fmt(data.free_usdt)}`}
          subtitle="Available balance"
        />
        <MetricCard
          title="Daily P&L"
          value={`$${fmt(data.daily_pnl)}`}
          change={data.daily_pnl_pct}
        />
        <MetricCard
          title="Daily P&L %"
          value={`${fmt(data.daily_pnl_pct)}%`}
          change={data.daily_pnl_pct}
        />
      </div>

      {/* Halt reason */}
      {risk?.is_halted && risk.halt_reason && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-4 text-sm text-red-300">
          <span className="font-semibold">Halt reason:</span>{" "}
          {risk.halt_reason}
        </div>
      )}

      {/* Positions table */}
      {data.positions.length > 0 && (
        <div className="rounded-xl bg-gray-800 p-5">
          <h2 className="mb-4 text-lg font-semibold text-white">
            Open Positions
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-left text-gray-400">
                  <th className="pb-3 pr-4">Symbol</th>
                  <th className="pb-3 pr-4">Side</th>
                  <th className="pb-3 pr-4 text-right">Amount</th>
                  <th className="pb-3 pr-4 text-right">Entry Price</th>
                  <th className="pb-3 pr-4 text-right">Mark Price</th>
                  <th className="pb-3 text-right">Unrealized P&L</th>
                </tr>
              </thead>
              <tbody>
                {data.positions.map((p) => (
                  <tr
                    key={p.symbol + p.side}
                    className="border-b border-gray-700/50"
                  >
                    <td className="py-3 pr-4 font-medium text-white">
                      {p.symbol}
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={
                          p.side === "long"
                            ? "text-green-400"
                            : "text-red-400"
                        }
                      >
                        {p.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-right text-gray-300">
                      {p.amount.toFixed(6)}
                    </td>
                    <td className="py-3 pr-4 text-right text-gray-300">
                      ${fmt(p.entry_price)}
                    </td>
                    <td className="py-3 pr-4 text-right text-gray-300">
                      ${fmt(p.mark_price)}
                    </td>
                    <td
                      className={`py-3 text-right font-medium ${
                        p.unrealized_pnl >= 0
                          ? "text-green-400"
                          : "text-red-400"
                      }`}
                    >
                      ${fmt(p.unrealized_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.positions.length === 0 && (
        <div className="rounded-xl bg-gray-800 p-8 text-center text-gray-500">
          No open positions
        </div>
      )}
    </div>
  );
}

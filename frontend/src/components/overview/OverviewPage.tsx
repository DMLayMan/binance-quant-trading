import { Link } from "react-router-dom";
import { useDashboard, useEnvConfig } from "../../api/hooks.ts";
import MetricCard from "../shared/MetricCard.tsx";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

const statusColors: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  stopped: "bg-red-500/20 text-red-400",
  running: "bg-green-500/20 text-green-400",
  pending: "bg-gray-500/20 text-gray-400",
  error: "bg-red-500/20 text-red-400",
};

function StatusDot({ status }: { status: string }) {
  const dotColor =
    status === "connected" ? "bg-green-400" :
    status === "error" ? "bg-red-400" :
    "bg-gray-500";
  return <span className={`inline-block w-2 h-2 rounded-full ${dotColor}`} />;
}

export default function OverviewPage() {
  const { data, isLoading, error } = useDashboard();
  const { data: envConfig } = useEnvConfig();

  if (isLoading) return <LoadingSpinner />;
  if (error)
    return (
      <p className="text-red-400">
        Failed to load dashboard: {(error as Error).message}
      </p>
    );
  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        {envConfig && (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <StatusDot status={envConfig.connection_status} />
            <span>
              {envConfig.connection_status === "connected"
                ? "Exchange Connected"
                : envConfig.connection_status === "error"
                  ? "Connection Error"
                  : "Not Connected"}
            </span>
            {envConfig.use_testnet && (
              <span className="rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">
                Testnet
              </span>
            )}
          </div>
        )}
      </div>

      {/* Key Metrics */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Equity"
          value={`$${fmt(data.total_equity)}`}
          subtitle={`Allocated: $${fmt(data.total_allocated)}`}
        />
        <MetricCard
          title="Total P&L"
          value={`$${fmt(data.total_pnl)}`}
          change={data.total_pnl_pct}
        />
        <MetricCard
          title="Active Pools / Instances"
          value={`${data.active_pools} / ${data.running_instances}`}
          subtitle={`${data.total_trades} trades total`}
        />
        <MetricCard
          title="Risk Events (24h)"
          value={String(data.recent_risk_events)}
          subtitle={data.recent_risk_events > 0 ? "Check risk events" : "All clear"}
        />
      </div>

      {/* Fund Pools Summary */}
      <div className="rounded-xl bg-gray-800 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Fund Pools</h2>
          <Link to="/funds" className="text-sm text-blue-400 hover:text-blue-300">
            View all
          </Link>
        </div>
        {data.pools.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.pools.map((pool) => (
              <div key={pool.id} className="rounded-lg bg-gray-900 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-white text-sm">{pool.name}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                      statusColors[pool.status] ?? "bg-gray-500/20 text-gray-400"
                    }`}
                  >
                    {pool.status.toUpperCase()}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500">Equity</span>
                    <p className="text-white font-medium">${fmt(pool.current_equity)}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">P&L</span>
                    <p className={pool.pnl >= 0 ? "text-green-400 font-medium" : "text-red-400 font-medium"}>
                      ${fmt(pool.pnl)}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500">Instances</span>
                    <p className="text-white font-medium">{pool.instance_count}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm text-center py-4">
            No fund pools yet.{" "}
            <Link to="/funds" className="text-blue-400 hover:text-blue-300">Create one</Link>
          </p>
        )}
      </div>

      {/* Two-column: Active Instances + Recent Trades */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Active Instances */}
        <div className="rounded-xl bg-gray-800 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Active Instances</h2>
            <Link to="/instances" className="text-sm text-blue-400 hover:text-blue-300">
              View all
            </Link>
          </div>
          {data.active_instances.length > 0 ? (
            <div className="space-y-2">
              {data.active_instances.map((inst) => (
                <div key={inst.id} className="flex items-center justify-between rounded-lg bg-gray-900 px-4 py-3">
                  <div>
                    <span className="text-sm font-medium text-white">{inst.strategy_name}</span>
                    <span className="ml-2 text-xs text-gray-500">
                      {inst.symbol} · {inst.timeframe}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-medium ${inst.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      ${fmt(inst.total_pnl)}
                    </span>
                    <span className="text-xs text-gray-500">{inst.trade_count} trades</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusColors[inst.status] ?? "bg-gray-500/20 text-gray-400"}`}>
                      {inst.status.toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm text-center py-4">
              No active instances.{" "}
              <Link to="/instances" className="text-blue-400 hover:text-blue-300">Create one</Link>
            </p>
          )}
        </div>

        {/* Recent Trades */}
        <div className="rounded-xl bg-gray-800 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Recent Trades</h2>
            <Link to="/trades" className="text-sm text-blue-400 hover:text-blue-300">
              View all
            </Link>
          </div>
          {data.recent_trades.length > 0 ? (
            <div className="space-y-2">
              {data.recent_trades.map((trade) => (
                <div key={trade.id} className="flex items-center justify-between rounded-lg bg-gray-900 px-4 py-3">
                  <div>
                    <span className="text-sm font-medium text-white">{trade.symbol}</span>
                    <span className={`ml-2 text-xs ${trade.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                      {trade.side.toUpperCase()}
                    </span>
                    {trade.exit_reason && (
                      <span className="ml-2 text-xs text-gray-500">{trade.exit_reason}</span>
                    )}
                  </div>
                  <div className="text-right">
                    <span className={`text-sm font-medium ${trade.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      ${fmt(trade.pnl)} ({fmt(trade.pnl_pct)}%)
                    </span>
                    <p className="text-xs text-gray-500">{new Date(trade.exit_time).toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm text-center py-4">No trades recorded yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}

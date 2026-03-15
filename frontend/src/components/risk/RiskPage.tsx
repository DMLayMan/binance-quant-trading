import { useRiskStatus, useRiskConfig, useResetHalt } from "../../api/hooks.ts";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

function fmt(n: number, d = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function ProgressBar({
  label,
  current,
  limit,
  unit = "%",
  invert = false,
}: {
  label: string;
  current: number;
  limit: number;
  unit?: string;
  invert?: boolean;
}) {
  const ratio = limit !== 0 ? Math.abs(current) / Math.abs(limit) : 0;
  const pct = Math.min(ratio * 100, 100);
  const color =
    pct < 50 ? "bg-green-500" : pct < 80 ? "bg-yellow-500" : "bg-red-500";

  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300">
          {invert ? `-${fmt(Math.abs(current))}` : fmt(current)}
          {unit} / {invert ? `-${fmt(Math.abs(limit))}` : fmt(limit)}
          {unit}
        </span>
      </div>
      <div className="h-2.5 w-full rounded-full bg-gray-700">
        <div
          className={`h-2.5 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function RiskPage() {
  const { data: status, isLoading: statusLoading } = useRiskStatus();
  const { data: config } = useRiskConfig();
  const resetMutation = useResetHalt();

  if (statusLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Risk Management</h1>
        {status && (
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              status.is_halted
                ? "bg-red-500/20 text-red-400"
                : "bg-green-500/20 text-green-400"
            }`}
          >
            {status.is_halted ? "HALTED" : "ACTIVE"}
          </span>
        )}
      </div>

      {/* Halt panel */}
      {status?.is_halted && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
          <div className="mb-3 text-sm text-red-300">
            <span className="font-semibold">Halt reason:</span>{" "}
            {status.halt_reason}
          </div>
          <button
            onClick={() => {
              if (confirm("Are you sure you want to reset the halt?")) {
                resetMutation.mutate();
              }
            }}
            disabled={resetMutation.isPending}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50"
          >
            {resetMutation.isPending ? "Resetting..." : "Reset Halt"}
          </button>
        </div>
      )}

      {/* Risk gauges */}
      {status && config && (
        <div className="rounded-xl bg-gray-800 p-5">
          <h2 className="mb-5 text-lg font-semibold text-white">
            Risk Gauges
          </h2>
          <div className="space-y-5">
            <ProgressBar
              label="Drawdown"
              current={status.drawdown_pct}
              limit={config.max_drawdown_pct * 100}
              unit="%"
              invert
            />
            <ProgressBar
              label="Daily Loss"
              current={status.daily_pnl_pct < 0 ? status.daily_pnl_pct : 0}
              limit={config.max_daily_loss_pct * 100}
              unit="%"
              invert
            />
            <ProgressBar
              label="Trades Today"
              current={status.trades_today}
              limit={config.max_trades_per_day}
              unit=""
            />
            <ProgressBar
              label="Consecutive Losses"
              current={status.consecutive_losses}
              limit={config.max_consecutive_losses}
              unit=""
            />
          </div>
        </div>
      )}

      {/* Risk metrics */}
      <div className="grid gap-4 sm:grid-cols-2">
        {status && (
          <div className="rounded-xl bg-gray-800 p-5">
            <h2 className="mb-4 text-lg font-semibold text-white">
              Current Status
            </h2>
            <table className="w-full text-sm">
              <tbody>
                {[
                  ["Equity", `$${fmt(status.current_equity)}`],
                  ["Peak Equity", `$${fmt(status.peak_equity)}`],
                  ["Drawdown", `${fmt(status.drawdown_pct)}%`],
                  ["Daily P&L", `$${fmt(status.daily_pnl)}`],
                  ["Daily P&L %", `${fmt(status.daily_pnl_pct)}%`],
                  ["Trades Today", String(status.trades_today)],
                  [
                    "Consecutive Losses",
                    String(status.consecutive_losses),
                  ],
                ].map(([k, v]) => (
                  <tr key={k} className="border-b border-gray-700/50">
                    <td className="py-2 text-gray-400">{k}</td>
                    <td className="py-2 text-right text-gray-200">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {config && (
          <div className="rounded-xl bg-gray-800 p-5">
            <h2 className="mb-4 text-lg font-semibold text-white">
              Risk Limits
            </h2>
            <table className="w-full text-sm">
              <tbody>
                {[
                  [
                    "Max Daily Loss",
                    `${(config.max_daily_loss_pct * 100).toFixed(1)}%`,
                  ],
                  [
                    "Max Drawdown",
                    `${(config.max_drawdown_pct * 100).toFixed(1)}%`,
                  ],
                  [
                    "Max Position Size",
                    `${(config.max_position_pct * 100).toFixed(1)}%`,
                  ],
                  [
                    "Max Single Loss",
                    `${(config.max_single_loss_pct * 100).toFixed(1)}%`,
                  ],
                  ["Max Trades/Day", String(config.max_trades_per_day)],
                  [
                    "Max Consecutive Losses",
                    String(config.max_consecutive_losses),
                  ],
                ].map(([k, v]) => (
                  <tr key={k} className="border-b border-gray-700/50">
                    <td className="py-2 text-gray-400">{k}</td>
                    <td className="py-2 text-right text-gray-200">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

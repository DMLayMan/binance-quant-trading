import { useState } from "react";
import {
  useInstances,
  useCreateInstance,
  useInstanceAction,
  useFundPools,
  useStrategies,
} from "../../api/hooks.ts";
import type { InstanceResponse } from "../../types/index.ts";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

const statusColors: Record<string, string> = {
  pending: "bg-gray-500/20 text-gray-400",
  running: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  stopped: "bg-red-500/20 text-red-400",
  error: "bg-red-500/20 text-red-400",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusColors[status] ?? "bg-gray-500/20 text-gray-400"}`}>
      {status.toUpperCase()}
    </span>
  );
}

function CreateInstanceForm({ onClose }: { onClose: () => void }) {
  const { data: pools } = useFundPools("active");
  const { data: strategies } = useStrategies();
  const create = useCreateInstance();

  const [form, setForm] = useState({
    fund_pool_id: "",
    strategy_name: "",
    symbol: "BTC/USDT",
    timeframe: "4h",
    stop_loss_atr_mult: "2.0",
    take_profit_atr_mult: "4.0",
    max_position_pct: "0.30",
    risk_per_trade_pct: "0.01",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        fund_pool_id: form.fund_pool_id,
        strategy_name: form.strategy_name,
        symbol: form.symbol,
        timeframe: form.timeframe,
        stop_loss_atr_mult: Number(form.stop_loss_atr_mult),
        take_profit_atr_mult: Number(form.take_profit_atr_mult),
        max_position_pct: Number(form.max_position_pct),
        risk_per_trade_pct: Number(form.risk_per_trade_pct),
      },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <div className="rounded-xl bg-gray-800 p-5 mb-4">
      <h3 className="text-lg font-semibold text-white mb-4">Create Strategy Instance</h3>
      <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Fund Pool</label>
          <select
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.fund_pool_id}
            onChange={(e) => setForm({ ...form, fund_pool_id: e.target.value })}
            required
          >
            <option value="">Select pool...</option>
            {pools?.map((p) => (
              <option key={p.id} value={p.id}>{p.name} (${fmt(p.current_equity)})</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Strategy</label>
          <select
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.strategy_name}
            onChange={(e) => setForm({ ...form, strategy_name: e.target.value })}
            required
          >
            <option value="">Select strategy...</option>
            {strategies?.map((s) => (
              <option key={s.name} value={s.name}>{s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Symbol</label>
          <input
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.symbol}
            onChange={(e) => setForm({ ...form, symbol: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Timeframe</label>
          <select
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.timeframe}
            onChange={(e) => setForm({ ...form, timeframe: e.target.value })}
          >
            {["1m", "5m", "15m", "1h", "4h", "1d"].map((tf) => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">SL ATR Mult</label>
          <input
            type="number" step="0.1" min="0"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.stop_loss_atr_mult}
            onChange={(e) => setForm({ ...form, stop_loss_atr_mult: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">TP ATR Mult</label>
          <input
            type="number" step="0.1" min="0"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.take_profit_atr_mult}
            onChange={(e) => setForm({ ...form, take_profit_atr_mult: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Max Position %</label>
          <input
            type="number" step="0.01" min="0" max="1"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.max_position_pct}
            onChange={(e) => setForm({ ...form, max_position_pct: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Risk/Trade %</label>
          <input
            type="number" step="0.001" min="0" max="0.1"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.risk_per_trade_pct}
            onChange={(e) => setForm({ ...form, risk_per_trade_pct: e.target.value })}
          />
        </div>
        <div className="sm:col-span-2 lg:col-span-4 flex gap-3">
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {create.isPending ? "Creating..." : "Create"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-600"
          >
            Cancel
          </button>
        </div>
        {create.isError && (
          <p className="sm:col-span-2 lg:col-span-4 text-sm text-red-400">{create.error.message}</p>
        )}
      </form>
    </div>
  );
}

function InstanceRow({ inst }: { inst: InstanceResponse }) {
  const action = useInstanceAction();

  const handleAction = (act: "start" | "pause" | "stop") => {
    if (act === "stop" && !confirm("Stop this instance permanently?")) return;
    action.mutate({ id: inst.id, action: act });
  };

  return (
    <tr className="border-b border-gray-700/50 hover:bg-gray-800/50">
      <td className="py-3 pr-3">
        <div className="font-medium text-white text-sm">{inst.strategy_name}</div>
        <div className="text-xs text-gray-500">{inst.id.slice(0, 8)}...</div>
      </td>
      <td className="py-3 pr-3 text-sm text-gray-300">{inst.symbol}</td>
      <td className="py-3 pr-3 text-sm text-gray-300">{inst.timeframe}</td>
      <td className="py-3 pr-3"><StatusBadge status={inst.status} /></td>
      <td className="py-3 pr-3 text-sm text-right">
        {inst.current_position > 0 ? (
          <span className="text-white">{inst.current_position.toFixed(6)}</span>
        ) : (
          <span className="text-gray-500">-</span>
        )}
      </td>
      <td className={`py-3 pr-3 text-sm text-right font-medium ${inst.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
        ${fmt(inst.total_pnl)}
      </td>
      <td className="py-3 pr-3 text-sm text-right text-gray-300">
        {inst.trade_count} <span className="text-gray-500">({fmt(inst.win_rate)}%)</span>
      </td>
      <td className="py-3 pr-3 text-sm text-gray-300">{inst.consecutive_losses}</td>
      <td className="py-3 text-right">
        <div className="flex gap-1 justify-end">
          {(inst.status === "pending" || inst.status === "paused") && (
            <button
              onClick={() => handleAction("start")}
              disabled={action.isPending}
              className="rounded px-2 py-1 text-xs bg-green-600/20 text-green-400 hover:bg-green-600/30"
            >
              Start
            </button>
          )}
          {inst.status === "running" && (
            <button
              onClick={() => handleAction("pause")}
              disabled={action.isPending}
              className="rounded px-2 py-1 text-xs bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30"
            >
              Pause
            </button>
          )}
          {inst.status !== "stopped" && (
            <button
              onClick={() => handleAction("stop")}
              disabled={action.isPending}
              className="rounded px-2 py-1 text-xs bg-red-600/20 text-red-400 hover:bg-red-600/30"
            >
              Stop
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function InstancesPage() {
  const { data: instances, isLoading, error } = useInstances();
  const [showCreate, setShowCreate] = useState(false);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <p className="text-red-400">Failed to load instances: {(error as Error).message}</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Strategy Instances</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showCreate ? "Cancel" : "+ New Instance"}
        </button>
      </div>

      {showCreate && <CreateInstanceForm onClose={() => setShowCreate(false)} />}

      {instances && instances.length > 0 ? (
        <div className="rounded-xl bg-gray-800 p-5">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-left text-gray-400">
                  <th className="pb-3 pr-3">Strategy</th>
                  <th className="pb-3 pr-3">Symbol</th>
                  <th className="pb-3 pr-3">TF</th>
                  <th className="pb-3 pr-3">Status</th>
                  <th className="pb-3 pr-3 text-right">Position</th>
                  <th className="pb-3 pr-3 text-right">Total P&L</th>
                  <th className="pb-3 pr-3 text-right">Trades (Win%)</th>
                  <th className="pb-3 pr-3">Consec Loss</th>
                  <th className="pb-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {instances.map((inst) => (
                  <InstanceRow key={inst.id} inst={inst} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="rounded-xl bg-gray-800 p-8 text-center text-gray-500">
          No strategy instances. Create a fund pool first, then add instances.
        </div>
      )}
    </div>
  );
}

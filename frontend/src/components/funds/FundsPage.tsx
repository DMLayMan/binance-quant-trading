import { useState } from "react";
import {
  useFundPools,
  useCreateFundPool,
  useFundPoolAction,
} from "../../api/hooks.ts";
import type { FundPoolResponse } from "../../types/index.ts";
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
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusColors[status] ?? "bg-gray-500/20 text-gray-400"}`}>
      {status.toUpperCase()}
    </span>
  );
}

function CreatePoolForm({ onClose }: { onClose: () => void }) {
  const create = useCreateFundPool();
  const [form, setForm] = useState({
    name: "",
    allocated_amount: "",
    max_daily_loss_pct: "0.05",
    max_drawdown_pct: "0.15",
    take_profit_pct: "",
    stop_loss_pct: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        name: form.name,
        allocated_amount: Number(form.allocated_amount),
        max_daily_loss_pct: Number(form.max_daily_loss_pct),
        max_drawdown_pct: Number(form.max_drawdown_pct),
        take_profit_pct: form.take_profit_pct ? Number(form.take_profit_pct) : null,
        stop_loss_pct: form.stop_loss_pct ? Number(form.stop_loss_pct) : null,
      },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <div className="rounded-xl bg-gray-800 p-5 mb-4">
      <h3 className="text-lg font-semibold text-white mb-4">Create Fund Pool</h3>
      <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Name</label>
          <input
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Allocated Amount (USDT)</label>
          <input
            type="number"
            step="0.01"
            min="1"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.allocated_amount}
            onChange={(e) => setForm({ ...form, allocated_amount: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Max Daily Loss %</label>
          <input
            type="number"
            step="0.01"
            min="0"
            max="1"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.max_daily_loss_pct}
            onChange={(e) => setForm({ ...form, max_daily_loss_pct: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Max Drawdown %</label>
          <input
            type="number"
            step="0.01"
            min="0"
            max="1"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.max_drawdown_pct}
            onChange={(e) => setForm({ ...form, max_drawdown_pct: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Take Profit % (optional)</label>
          <input
            type="number"
            step="0.01"
            min="0"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.take_profit_pct}
            onChange={(e) => setForm({ ...form, take_profit_pct: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Stop Loss % (optional)</label>
          <input
            type="number"
            step="0.01"
            min="0"
            className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-white border border-gray-600 focus:border-blue-500 focus:outline-none"
            value={form.stop_loss_pct}
            onChange={(e) => setForm({ ...form, stop_loss_pct: e.target.value })}
          />
        </div>
        <div className="sm:col-span-2 lg:col-span-3 flex gap-3">
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
          <p className="sm:col-span-2 lg:col-span-3 text-sm text-red-400">{create.error.message}</p>
        )}
      </form>
    </div>
  );
}

function PoolCard({ pool }: { pool: FundPoolResponse }) {
  const action = useFundPoolAction();

  const handleAction = (act: "pause" | "resume" | "stop") => {
    if (act === "stop" && !confirm("Are you sure you want to permanently stop this pool?")) return;
    action.mutate({ id: pool.id, action: act });
  };

  return (
    <div className="rounded-xl bg-gray-800 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-white">{pool.name}</h3>
        <StatusBadge status={pool.status} />
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <span className="text-gray-500">Allocated</span>
          <p className="text-white font-medium">${fmt(pool.allocated_amount)}</p>
        </div>
        <div>
          <span className="text-gray-500">Equity</span>
          <p className="text-white font-medium">${fmt(pool.current_equity)}</p>
        </div>
        <div>
          <span className="text-gray-500">P&L</span>
          <p className={`font-medium ${pool.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
            ${fmt(pool.pnl)} ({fmt(pool.pnl_pct)}%)
          </p>
        </div>
        <div>
          <span className="text-gray-500">Drawdown</span>
          <p className={`font-medium ${pool.drawdown_pct > 10 ? "text-red-400" : "text-gray-300"}`}>
            {fmt(pool.drawdown_pct)}%
          </p>
        </div>
        <div>
          <span className="text-gray-500">Instances</span>
          <p className="text-white font-medium">{pool.instance_count}</p>
        </div>
        <div>
          <span className="text-gray-500">Peak Equity</span>
          <p className="text-gray-300">${fmt(pool.peak_equity)}</p>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-700 flex gap-2 text-xs">
        <span className="text-gray-500">Daily Loss: {(pool.max_daily_loss_pct * 100).toFixed(0)}%</span>
        <span className="text-gray-500">Max DD: {(pool.max_drawdown_pct * 100).toFixed(0)}%</span>
        {pool.take_profit_pct != null && <span className="text-gray-500">TP: {(pool.take_profit_pct * 100).toFixed(0)}%</span>}
        {pool.stop_loss_pct != null && <span className="text-gray-500">SL: {(pool.stop_loss_pct * 100).toFixed(0)}%</span>}
      </div>

      {pool.status !== "stopped" && (
        <div className="mt-3 pt-3 border-t border-gray-700 flex gap-2">
          {pool.status === "active" && (
            <button
              onClick={() => handleAction("pause")}
              disabled={action.isPending}
              className="rounded-lg bg-yellow-600/20 px-3 py-1.5 text-xs font-medium text-yellow-400 hover:bg-yellow-600/30"
            >
              Pause
            </button>
          )}
          {pool.status === "paused" && (
            <button
              onClick={() => handleAction("resume")}
              disabled={action.isPending}
              className="rounded-lg bg-green-600/20 px-3 py-1.5 text-xs font-medium text-green-400 hover:bg-green-600/30"
            >
              Resume
            </button>
          )}
          <button
            onClick={() => handleAction("stop")}
            disabled={action.isPending}
            className="rounded-lg bg-red-600/20 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-600/30"
          >
            Stop
          </button>
        </div>
      )}
    </div>
  );
}

export default function FundsPage() {
  const { data: pools, isLoading, error } = useFundPools();
  const [showCreate, setShowCreate] = useState(false);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <p className="text-red-400">Failed to load fund pools: {(error as Error).message}</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Fund Pools</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showCreate ? "Cancel" : "+ New Pool"}
        </button>
      </div>

      {showCreate && <CreatePoolForm onClose={() => setShowCreate(false)} />}

      {pools && pools.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {pools.map((pool) => (
            <PoolCard key={pool.id} pool={pool} />
          ))}
        </div>
      ) : (
        <div className="rounded-xl bg-gray-800 p-8 text-center text-gray-500">
          No fund pools. Create one to get started.
        </div>
      )}
    </div>
  );
}

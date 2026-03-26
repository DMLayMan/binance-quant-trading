import { useState } from "react";
import { useStrategies, useStrategySignals } from "../../api/hooks.ts";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

export default function StrategiesPage() {
  const { data: strategies, isLoading, error } = useStrategies();
  const [selected, setSelected] = useState<string>("");
  const [signalSymbol] = useState("BTC/USDT");
  const [signalTf] = useState("1h");

  const {
    data: signals,
    isLoading: sigLoading,
  } = useStrategySignals(selected, signalSymbol, signalTf);

  if (isLoading) return <LoadingSpinner />;
  if (error)
    return (
      <p className="text-red-400">
        Failed to load strategies: {(error as Error).message}
      </p>
    );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Strategies</h1>

      {/* Strategy cards grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {strategies?.map((s) => (
          <button
            key={s.name}
            onClick={() => setSelected(s.name === selected ? "" : s.name)}
            className={`rounded-xl p-5 text-left transition-colors border ${
              selected === s.name
                ? "bg-gray-800 border-blue-500"
                : "bg-gray-800 border-gray-700 hover:border-gray-600"
            }`}
          >
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white">{s.name}</h3>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  s.is_active
                    ? "bg-green-500/20 text-green-400"
                    : "bg-gray-700 text-gray-400"
                }`}
              >
                {s.is_active ? "Active" : "Inactive"}
              </span>
            </div>
            <p className="mt-2 text-sm text-gray-400">{s.description}</p>
            <div className="mt-3 flex flex-wrap gap-1">
              {Object.entries(s.default_params).map(([k, v]) => (
                <span
                  key={k}
                  className="rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-300"
                >
                  {k}: {String(v)}
                </span>
              ))}
            </div>
          </button>
        ))}
      </div>

      {/* Signals panel */}
      {selected && (
        <div className="rounded-xl bg-gray-800 p-5">
          <h2 className="mb-4 text-lg font-semibold text-white">
            Signals &mdash; {selected}{" "}
            <span className="text-sm font-normal text-gray-400">
              ({signalSymbol} / {signalTf})
            </span>
          </h2>

          {sigLoading && <LoadingSpinner />}

          {signals && signals.signals.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700 text-left text-gray-400">
                    <th className="pb-3 pr-4">Time</th>
                    <th className="pb-3 pr-4">Signal</th>
                    <th className="pb-3 text-right">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.signals.map((sp, i) => (
                    <tr key={i} className="border-b border-gray-700/50">
                      <td className="py-2 pr-4 text-gray-300">
                        {new Date(sp.timestamp).toLocaleString()}
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-semibold ${
                            sp.signal === "buy"
                              ? "bg-green-500/20 text-green-400"
                              : sp.signal === "sell"
                                ? "bg-red-500/20 text-red-400"
                                : "bg-gray-700 text-gray-300"
                          }`}
                        >
                          {sp.signal.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2 text-right text-gray-300">
                        ${sp.price.toLocaleString("en-US", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {signals && signals.signals.length === 0 && (
            <p className="text-gray-500">No signals found for this period.</p>
          )}
        </div>
      )}
    </div>
  );
}

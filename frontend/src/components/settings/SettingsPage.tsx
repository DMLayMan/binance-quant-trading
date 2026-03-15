import { useEffect, useState } from "react";
import { useSettings, useUpdateSettings } from "../../api/hooks.ts";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

export default function SettingsPage() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();
  const [saved, setSaved] = useState(false);

  const [strategy, setStrategy] = useState<Record<string, unknown>>({});
  const [risk, setRisk] = useState<Record<string, unknown>>({});
  const [fees, setFees] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (settings) {
      setStrategy(settings.strategy);
      setRisk(settings.risk);
      setFees(settings.fees);
    }
  }, [settings]);

  function handleSave() {
    setSaved(false);
    updateMutation.mutate(
      {
        exchange: settings?.exchange || {},
        strategy,
        risk,
        fees,
        logging: settings?.logging || {},
      },
      {
        onSuccess: () => {
          setSaved(true);
          setTimeout(() => setSaved(false), 3000);
        },
      },
    );
  }

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <div className="flex items-center gap-3">
          {saved && (
            <span className="text-sm text-green-400">Saved!</span>
          )}
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {updateMutation.isPending ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {updateMutation.isError && (
        <p className="text-sm text-red-400">
          {updateMutation.error?.message || "Failed to save"}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Strategy */}
        <Section title="Strategy">
          <Field
            label="Name"
            value={String(strategy.name || "")}
            onChange={(v) => setStrategy((s) => ({ ...s, name: v }))}
          />
          <Field
            label="Symbol"
            value={String(strategy.symbol || "")}
            onChange={(v) => setStrategy((s) => ({ ...s, symbol: v }))}
          />
          <Field
            label="Timeframe"
            value={String(strategy.timeframe || "")}
            onChange={(v) => setStrategy((s) => ({ ...s, timeframe: v }))}
          />
          {typeof strategy.params === "object" &&
            strategy.params !== null &&
            Object.entries(strategy.params as Record<string, unknown>).map(
              ([k, v]) => (
                <Field
                  key={k}
                  label={`param: ${k}`}
                  value={String(v)}
                  type="number"
                  onChange={(val) =>
                    setStrategy((s) => ({
                      ...s,
                      params: {
                        ...((s.params as Record<string, unknown>) || {}),
                        [k]: Number(val),
                      },
                    }))
                  }
                />
              ),
            )}
        </Section>

        {/* Risk */}
        <Section title="Risk">
          {[
            ["max_position_pct", "Max Position %"],
            ["risk_per_trade_pct", "Risk Per Trade %"],
            ["stop_loss_atr_mult", "Stop Loss (ATR x)"],
            ["take_profit_atr_mult", "Take Profit (ATR x)"],
            ["max_daily_loss_pct", "Max Daily Loss %"],
            ["max_drawdown_pct", "Max Drawdown %"],
          ].map(([key, label]) => (
            <Field
              key={key}
              label={label}
              value={String(risk[key] ?? "")}
              type="number"
              step="0.01"
              onChange={(v) =>
                setRisk((r) => ({ ...r, [key]: Number(v) }))
              }
            />
          ))}
        </Section>

        {/* Fees */}
        <Section title="Fees">
          <Field
            label="Maker Fee"
            value={String(fees.maker ?? "")}
            type="number"
            step="0.0001"
            onChange={(v) => setFees((f) => ({ ...f, maker: Number(v) }))}
          />
          <Field
            label="Taker Fee"
            value={String(fees.taker ?? "")}
            type="number"
            step="0.0001"
            onChange={(v) => setFees((f) => ({ ...f, taker: Number(v) }))}
          />
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={Boolean(fees.bnb_discount)}
              onChange={(e) =>
                setFees((f) => ({ ...f, bnb_discount: e.target.checked }))
              }
              className="h-4 w-4 rounded bg-gray-700 border-gray-600"
            />
            <label className="text-sm text-gray-300">BNB Fee Discount</label>
          </div>
        </Section>

        {/* Exchange (read-only) */}
        <Section title="Exchange (read-only)">
          {settings?.exchange &&
            Object.entries(settings.exchange as Record<string, unknown>).map(([k, v]) => (
              <div
                key={k}
                className="flex justify-between border-b border-gray-700/50 py-2 text-sm"
              >
                <span className="text-gray-400">{k}</span>
                <span className="text-gray-300">{String(v)}</span>
              </div>
            ))}
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-gray-800 p-5">
      <h2 className="mb-4 text-lg font-semibold text-white">{title}</h2>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  step,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  step?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-gray-400">{label}</label>
      <input
        type={type}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600 focus:outline-none focus:border-blue-500"
      />
    </div>
  );
}

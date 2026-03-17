import { useEffect, useState } from "react";
import {
  useSettings,
  useUpdateSettings,
  useEnvConfig,
  useUpdateEnvConfig,
  useNotifyConfig,
  useUpdateNotifyConfig,
} from "../../api/hooks.ts";
import type { EnvConfigUpdateRequest, NotifyConfigUpdate } from "../../types/index.ts";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

export default function SettingsPage() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();
  const [saved, setSaved] = useState(false);

  const [strategy, setStrategy] = useState<Record<string, unknown>>({});
  const [risk, setRisk] = useState<Record<string, unknown>>({});
  const [fees, setFees] = useState<Record<string, unknown>>({});

  // ── Env Config 状态 ──
  const { data: envConfig, isLoading: envLoading } = useEnvConfig();
  const updateEnvMutation = useUpdateEnvConfig();
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [useTestnet, setUseTestnet] = useState(true);
  const [envSaved, setEnvSaved] = useState(false);

  // ── Notify Config 状态 ──
  const { data: notifyConfig } = useNotifyConfig();
  const updateNotifyMutation = useUpdateNotifyConfig();
  const [tgBotToken, setTgBotToken] = useState("");
  const [tgChatId, setTgChatId] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [notifySaved, setNotifySaved] = useState(false);

  useEffect(() => {
    if (settings) {
      setStrategy(settings.strategy);
      setRisk(settings.risk);
      setFees(settings.fees);
    }
  }, [settings]);

  useEffect(() => {
    if (envConfig) {
      setUseTestnet(envConfig.use_testnet);
    }
  }, [envConfig]);

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

  function handleEnvSave() {
    setEnvSaved(false);
    const payload: EnvConfigUpdateRequest = {};

    if (apiKey.trim()) payload.api_key = apiKey.trim();
    if (apiSecret.trim()) payload.api_secret = apiSecret.trim();
    payload.use_testnet = useTestnet;

    updateEnvMutation.mutate(payload, {
      onSuccess: () => {
        setEnvSaved(true);
        setApiKey("");
        setApiSecret("");
        setTimeout(() => setEnvSaved(false), 3000);
      },
    });
  }

  function handleNotifySave() {
    setNotifySaved(false);
    const payload: NotifyConfigUpdate = {};
    if (tgBotToken.trim()) payload.telegram_bot_token = tgBotToken.trim();
    if (tgChatId.trim()) payload.telegram_chat_id = tgChatId.trim();
    if (webhookUrl.trim()) payload.webhook_url = webhookUrl.trim();

    updateNotifyMutation.mutate(payload, {
      onSuccess: () => {
        setNotifySaved(true);
        setTgBotToken("");
        setTgChatId("");
        setWebhookUrl("");
        setTimeout(() => setNotifySaved(false), 3000);
      },
    });
  }

  if (isLoading || envLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Exchange & API ── */}
        <Section title="Exchange & API">
          {/* 连接状态 */}
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                envConfig?.connection_status === "connected"
                  ? "bg-green-500"
                  : envConfig?.connection_status === "error"
                    ? "bg-red-500"
                    : "bg-gray-500"
              }`}
            />
            <span className="text-sm text-gray-300">
              {envConfig?.connection_status === "connected"
                ? "Connected"
                : envConfig?.connection_status === "error"
                  ? `Error: ${envConfig.connection_error}`
                  : "Not connected"}
            </span>
          </div>

          {/* API Key */}
          <div>
            <label className="mb-1 block text-xs text-gray-400">
              API Key
              {envConfig?.api_key_configured && (
                <span className="ml-2 text-green-400">
                  (Current: {envConfig.api_key_masked})
                </span>
              )}
            </label>
            <input
              type="password"
              autoComplete="new-password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={
                envConfig?.api_key_configured
                  ? "Enter new key to update"
                  : "Enter API key"
              }
              className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* API Secret */}
          <div>
            <label className="mb-1 block text-xs text-gray-400">
              API Secret
              {envConfig?.api_secret_configured && (
                <span className="ml-2 text-green-400">
                  (Current: {envConfig.api_secret_masked})
                </span>
              )}
            </label>
            <input
              type="password"
              autoComplete="new-password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              placeholder={
                envConfig?.api_secret_configured
                  ? "Enter new secret to update"
                  : "Enter API secret"
              }
              className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Testnet 开关 */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={useTestnet}
              onChange={(e) => setUseTestnet(e.target.checked)}
              className="h-4 w-4 rounded bg-gray-700 border-gray-600"
            />
            <label className="text-sm text-gray-300">
              Use Testnet (Sandbox)
            </label>
          </div>

          {/* 保存按钮 */}
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleEnvSave}
              disabled={updateEnvMutation.isPending}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
            >
              {updateEnvMutation.isPending ? "Saving..." : "Save API Config"}
            </button>
            {envSaved && (
              <span className="text-sm text-green-400">Saved!</span>
            )}
            {updateEnvMutation.isError && (
              <span className="text-sm text-red-400">
                {updateEnvMutation.error?.message || "Failed to save"}
              </span>
            )}
          </div>
        </Section>

        {/* ── Strategy ── */}
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

        {/* ── Risk ── */}
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

        {/* ── Notifications ── */}
        <Section title="Notifications">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${notifyConfig?.telegram_configured ? "bg-green-500" : "bg-gray-500"}`} />
            <span className="text-sm text-gray-300">
              Telegram: {notifyConfig?.telegram_configured
                ? `Configured (${notifyConfig.telegram_chat_id_masked})`
                : "Not configured"}
            </span>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Telegram Bot Token</label>
            <input
              type="password"
              autoComplete="new-password"
              value={tgBotToken}
              onChange={(e) => setTgBotToken(e.target.value)}
              placeholder="Enter bot token"
              className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Telegram Chat ID</label>
            <input
              type="password"
              autoComplete="new-password"
              value={tgChatId}
              onChange={(e) => setTgChatId(e.target.value)}
              placeholder="Enter chat ID"
              className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex items-center gap-2 pt-1">
            <span className={`h-2.5 w-2.5 rounded-full ${notifyConfig?.webhook_configured ? "bg-green-500" : "bg-gray-500"}`} />
            <span className="text-sm text-gray-300">
              Webhook: {notifyConfig?.webhook_configured
                ? `Configured (${notifyConfig.webhook_url_masked})`
                : "Not configured"}
            </span>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Webhook URL</label>
            <input
              type="text"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://..."
              className="w-full rounded-lg bg-gray-700 px-3 py-2 text-sm text-gray-200 border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleNotifySave}
              disabled={updateNotifyMutation.isPending}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
            >
              {updateNotifyMutation.isPending ? "Saving..." : "Save Notifications"}
            </button>
            {notifySaved && <span className="text-sm text-green-400">Saved!</span>}
          </div>
        </Section>

        {/* ── Fees ── */}
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
      </div>

      {/* ── Strategy / Risk / Fees 全局保存 ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {updateMutation.isPending ? "Saving..." : "Save Settings"}
        </button>
        {saved && <span className="text-sm text-green-400">Saved!</span>}
        {updateMutation.isError && (
          <p className="text-sm text-red-400">
            {updateMutation.error?.message || "Failed to save"}
          </p>
        )}
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

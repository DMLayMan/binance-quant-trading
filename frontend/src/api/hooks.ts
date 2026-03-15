import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "./client.ts";
import type {
  OverviewResponse,
  OHLCVResponse,
  TickerResponse,
  OrderBookResponse,
  StrategyInfo,
  StrategySignalsResponse,
  BacktestRequest,
  BacktestResponse,
  RiskStatusResponse,
  RiskConfigResponse,
  SettingsResponse,
  EnvConfigResponse,
  EnvConfigUpdateRequest,
} from "../types/index.ts";

/* ── Overview ── */

export function useOverview() {
  return useQuery<OverviewResponse>({
    queryKey: ["overview"],
    queryFn: async () => (await client.get<OverviewResponse>("/overview")).data,
    refetchInterval: 10_000,
  });
}

/* ── Market ── */

export function useOHLCV(symbol: string, timeframe: string, limit = 200) {
  return useQuery<OHLCVResponse>({
    queryKey: ["ohlcv", symbol, timeframe, limit],
    queryFn: async () =>
      (
        await client.get<OHLCVResponse>("/market/ohlcv", {
          params: { symbol, timeframe, limit },
        })
      ).data,
    enabled: !!symbol,
  });
}

export function useTicker(symbol: string) {
  return useQuery<TickerResponse>({
    queryKey: ["ticker", symbol],
    queryFn: async () =>
      (
        await client.get<TickerResponse>("/market/ticker", {
          params: { symbol },
        })
      ).data,
    refetchInterval: 5_000,
    enabled: !!symbol,
  });
}

export function useOrderBook(symbol: string, depth = 10) {
  return useQuery<OrderBookResponse>({
    queryKey: ["orderbook", symbol, depth],
    queryFn: async () =>
      (
        await client.get<OrderBookResponse>("/market/orderbook", {
          params: { symbol, depth },
        })
      ).data,
    refetchInterval: 3_000,
    enabled: !!symbol,
  });
}

/* ── Strategies ── */

export function useStrategies() {
  return useQuery<StrategyInfo[]>({
    queryKey: ["strategies"],
    queryFn: async () =>
      (await client.get<StrategyInfo[]>("/strategies")).data,
    staleTime: 60_000,
  });
}

export function useStrategySignals(
  name: string,
  symbol: string,
  timeframe: string,
) {
  return useQuery<StrategySignalsResponse>({
    queryKey: ["strategy-signals", name, symbol, timeframe],
    queryFn: async () =>
      (
        await client.get<StrategySignalsResponse>(
          `/strategies/${name}/signals`,
          { params: { symbol, timeframe } },
        )
      ).data,
    enabled: !!name,
  });
}

/* ── Backtest ── */

export function useRunBacktest() {
  return useMutation<BacktestResponse, Error, BacktestRequest>({
    mutationFn: async (req) =>
      (await client.post<BacktestResponse>("/backtest/run", req)).data,
  });
}

/* ── Risk ── */

export function useRiskStatus() {
  return useQuery<RiskStatusResponse>({
    queryKey: ["risk-status"],
    queryFn: async () =>
      (await client.get<RiskStatusResponse>("/risk/status")).data,
    refetchInterval: 5_000,
  });
}

export function useRiskConfig() {
  return useQuery<RiskConfigResponse>({
    queryKey: ["risk-config"],
    queryFn: async () =>
      (await client.get<RiskConfigResponse>("/risk/config")).data,
  });
}

export function useResetHalt() {
  const qc = useQueryClient();
  return useMutation<void, Error>({
    mutationFn: async () => {
      await client.post("/risk/reset-halt");
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["risk-status"] });
      void qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });
}

/* ── Settings ── */

export function useSettings() {
  return useQuery<SettingsResponse>({
    queryKey: ["settings"],
    queryFn: async () =>
      (await client.get<SettingsResponse>("/settings")).data,
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation<SettingsResponse, Error, SettingsResponse>({
    mutationFn: async (body) =>
      (await client.put<SettingsResponse>("/settings", body)).data,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}

/* ── Environment Config ── */

export function useEnvConfig() {
  return useQuery<EnvConfigResponse>({
    queryKey: ["env-config"],
    queryFn: async () =>
      (await client.get<EnvConfigResponse>("/settings/env")).data,
  });
}

export function useUpdateEnvConfig() {
  const qc = useQueryClient();
  return useMutation<EnvConfigResponse, Error, EnvConfigUpdateRequest>({
    mutationFn: async (body) =>
      (await client.put<EnvConfigResponse>("/settings/env", body)).data,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["env-config"] });
      void qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });
}

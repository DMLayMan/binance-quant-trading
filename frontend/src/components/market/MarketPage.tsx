import { useState, useRef, useEffect, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
} from "lightweight-charts";
import type {
  IChartApi,
  ISeriesApi,
  CandlestickData,
  HistogramData,
  LineData,
  Time,
} from "lightweight-charts";
import { useOHLCV, useTicker } from "../../api/hooks.ts";
import LoadingSpinner from "../shared/LoadingSpinner.tsx";

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"];
const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];

function fmt(n: number, d = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

export default function MarketPage() {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const { data: ohlcv, isLoading } = useOHLCV(symbol, timeframe);
  const { data: ticker } = useTicker(symbol);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbMiddleRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null);

  /* Create chart once */
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "#1f2937" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "#374151" },
        horzLines: { color: "#374151" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 500,
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true, secondsVisible: false },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    const bbUpper = chart.addSeries(LineSeries, {
      color: "rgba(99,102,241,0.5)",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const bbMiddle = chart.addSeries(LineSeries, {
      color: "rgba(99,102,241,0.3)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const bbLower = chart.addSeries(LineSeries, {
      color: "rgba(99,102,241,0.5)",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    bbUpperRef.current = bbUpper;
    bbMiddleRef.current = bbMiddle;
    bbLowerRef.current = bbLower;

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  /* Resize observer */
  const handleResize = useCallback(() => {
    if (chartRef.current && chartContainerRef.current) {
      chartRef.current.applyOptions({
        width: chartContainerRef.current.clientWidth,
      });
    }
  }, []);

  useEffect(() => {
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [handleResize]);

  /* Update chart data */
  useEffect(() => {
    if (!ohlcv || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    const candles: CandlestickData<Time>[] = ohlcv.candles.map((c) => ({
      time: (c.timestamp / 1000) as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    const volumes: HistogramData<Time>[] = ohlcv.candles.map((c) => ({
      time: (c.timestamp / 1000) as Time,
      value: c.volume,
      color: c.close >= c.open ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)",
    }));

    candleSeriesRef.current.setData(candles);
    volumeSeriesRef.current.setData(volumes);

    /* Bollinger Bands */
    const ind = ohlcv.indicators;
    if (ind && bbUpperRef.current && bbMiddleRef.current && bbLowerRef.current) {
      const makeLine = (arr: (number | null)[]): LineData<Time>[] =>
        ohlcv.candles
          .map((c, i) => ({
            time: (c.timestamp / 1000) as Time,
            value: arr[i],
          }))
          .filter((d): d is LineData<Time> => d.value != null);

      bbUpperRef.current.setData(makeLine(ind.bb_upper));
      bbMiddleRef.current.setData(makeLine(ind.bb_middle));
      bbLowerRef.current.setData(makeLine(ind.bb_lower));
    } else {
      bbUpperRef.current?.setData([]);
      bbMiddleRef.current?.setData([]);
      bbLowerRef.current?.setData([]);
    }

    chartRef.current?.timeScale().fitContent();
  }, [ohlcv]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white">Market</h1>

      {/* Controls bar */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          className="rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-200 border border-gray-700 focus:outline-none focus:border-blue-500"
        >
          {SYMBOLS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <div className="flex gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                timeframe === tf
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Ticker bar */}
      {ticker && (
        <div className="flex flex-wrap gap-6 rounded-lg bg-gray-800 px-5 py-3 text-sm">
          <div>
            <span className="text-gray-500">Last</span>{" "}
            <span className="font-semibold text-white">${fmt(ticker.last)}</span>
          </div>
          <div>
            <span className="text-gray-500">Bid</span>{" "}
            <span className="text-green-400">${fmt(ticker.bid)}</span>
          </div>
          <div>
            <span className="text-gray-500">Ask</span>{" "}
            <span className="text-red-400">${fmt(ticker.ask)}</span>
          </div>
          <div>
            <span className="text-gray-500">Spread</span>{" "}
            <span className="text-gray-300">
              ${(ticker.ask - ticker.bid).toFixed(2)}
            </span>
          </div>
          <div>
            <span className="text-gray-500">24h Vol</span>{" "}
            <span className="text-gray-300">
              {ticker.volume_24h.toLocaleString("en-US")}
            </span>
          </div>
          <div>
            <span className="text-gray-500">24h</span>{" "}
            <span
              className={
                ticker.change_24h_pct >= 0 ? "text-green-400" : "text-red-400"
              }
            >
              {ticker.change_24h_pct >= 0 ? "+" : ""}
              {ticker.change_24h_pct.toFixed(2)}%
            </span>
          </div>
        </div>
      )}

      {/* Chart */}
      {isLoading && <LoadingSpinner />}
      <div
        ref={chartContainerRef}
        className="rounded-lg bg-gray-800 overflow-hidden"
      />
    </div>
  );
}

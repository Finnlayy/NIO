import React, { useState, useMemo } from 'react';
import {
  OHLCVCandle,
  BacktestTrade,
  EquityCurvePoint,
  DataProviderId,
} from '../types/terminal';
import { AlertCircle, Eye, EyeOff } from 'lucide-react';

export type ChartViewMode = 'PRICE' | 'EQUITY' | 'DRAWDOWN';

export interface ChartOpenPaperPosition {
  pair: string;
  side: 'LONG' | 'SHORT';
  entryPrice: number;
  stopLossPrice: number;
  takeProfitPrice: number;
  unrealizedPnl: number;
  qty: number;
  isBreakEven?: boolean;
}

interface TerminalWorkspaceChartProps {
  symbol: string;
  timeframe: string;
  provider: DataProviderId;
  candles: OHLCVCandle[];
  trades: BacktestTrade[];
  equityCurve: EquityCurvePoint[];
  initialCapital: number;
  selectedTradeId: string | null;
  onSelectTrade: (tradeId: string | null) => void;
  fastEmaPeriod: number;
  slowEmaPeriod: number;
  openPaperPositions?: ChartOpenPaperPosition[];
}

function calcEMA(values: number[], period: number): number[] {
  if (values.length === 0) return [];
  const k = 2 / (period + 1);
  const ema: number[] = [values[0]];
  for (let i = 1; i < values.length; i++) {
    ema.push(values[i] * k + ema[i - 1] * (1 - k));
  }
  return ema;
}

export const TerminalWorkspaceChart: React.FC<TerminalWorkspaceChartProps> = React.memo(({
  symbol,
  timeframe,
  provider,
  candles,
  trades,
  equityCurve,
  initialCapital,
  selectedTradeId,
  onSelectTrade,
  fastEmaPeriod,
  slowEmaPeriod,
  openPaperPositions = [],
}) => {
  const [viewMode, setViewMode] = useState<ChartViewMode>('PRICE');
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showEma, setShowEma] = useState<boolean>(true);
  const [showVwap, setShowVwap] = useState<boolean>(true);
  const [showTradeMarkers, setShowTradeMarkers] = useState<boolean>(true);
  const [showPaperPositionLines, setShowPaperPositionLines] = useState<boolean>(true);
  const [showShadowEquity, setShowShadowEquity] = useState<boolean>(true);

  const visibleCandles = useMemo(() => {
    if (!candles || candles.length === 0) return [];
    return candles.slice(-140);
  }, [candles]);

  const offsetIndex = Math.max(0, candles.length - visibleCandles.length);

  const { fastEma, slowEma } = useMemo(() => {
    const closes = candles.map((c) => c.close);
    const f = calcEMA(closes, Math.max(2, fastEmaPeriod));
    const s = calcEMA(closes, Math.max(3, slowEmaPeriod));
    return {
      fastEma: f.slice(offsetIndex),
      slowEma: s.slice(offsetIndex),
    };
  }, [candles, fastEmaPeriod, slowEmaPeriod, offsetIndex]);

  const visibleTrades = useMemo(() => {
    if (!visibleCandles.length) return [];
    const minTime = visibleCandles[0].time;
    const maxTime = visibleCandles[visibleCandles.length - 1].time;
    return trades.filter((t) => t.exitTime >= minTime && t.entryTime <= maxTime);
  }, [trades, visibleCandles]);

  const selectedTrade = useMemo(
    () => trades.find((t) => t.id === selectedTradeId) || null,
    [trades, selectedTradeId]
  );

  const formatPrice = (val: number) => {
    if (val < 0.01) return val.toFixed(6);
    if (val < 1) return val.toFixed(4);
    if (val < 100) return val.toFixed(3);
    return val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  // Price Mode Bounds
  const priceBounds = useMemo(() => {
    if (!visibleCandles.length) return { min: 0, max: 100 };
    let min = Infinity;
    let max = -Infinity;
    for (const c of visibleCandles) {
      if (c.low < min) min = c.low;
      if (c.high > max) max = c.high;
    }
    if (selectedTrade) {
      min = Math.min(min, selectedTrade.stopLossPrice, selectedTrade.takeProfitPrice);
      max = Math.max(max, selectedTrade.stopLossPrice, selectedTrade.takeProfitPrice);
    }
    if (showPaperPositionLines && openPaperPositions.length > 0) {
      for (const pos of openPaperPositions) {
        if (pos.entryPrice > 0) {
          min = Math.min(min, pos.entryPrice, pos.stopLossPrice, pos.takeProfitPrice);
          max = Math.max(max, pos.entryPrice, pos.stopLossPrice, pos.takeProfitPrice);
        }
      }
    }
    const range = Math.max(max - min, min * 0.005, 0.000001);
    return { min: min - range * 0.06, max: max + range * 0.06 };
  }, [visibleCandles, selectedTrade, showPaperPositionLines, openPaperPositions]);

  // Equity Mode Bounds
  const equityBounds = useMemo(() => {
    if (!equityCurve.length) return { min: initialCapital * 0.9, max: initialCapital * 1.1 };
    let min = initialCapital;
    let max = initialCapital;
    for (const pt of equityCurve) {
      min = Math.min(min, pt.equity);
      max = Math.max(max, pt.equity);
      if (showShadowEquity) {
        min = Math.min(min, pt.shadowEquity);
        max = Math.max(max, pt.shadowEquity);
      }
    }
    const range = Math.max(max - min, initialCapital * 0.02);
    return { min: min - range * 0.08, max: max + range * 0.08 };
  }, [equityCurve, initialCapital, showShadowEquity]);

  // Drawdown Mode Bounds
  const ddBounds = useMemo(() => {
    if (!equityCurve.length) return { maxDd: 5 };
    let maxDd = 1;
    for (const pt of equityCurve) {
      if (pt.drawdownPct > maxDd) maxDd = pt.drawdownPct;
    }
    return { maxDd: maxDd * 1.15 };
  }, [equityCurve]);

  if (!visibleCandles.length) {
    return (
      <div className="flex-1 bg-[#07090E] border-b border-[#1B2230] flex flex-col items-center justify-center p-6 text-center">
        <AlertCircle className="w-6 h-6 text-[#8B95A5] mb-2" />
        <div className="text-xs font-semibold text-[#E6EDF3]">
          Keine OHLCV-Kerzendaten für {symbol} ({timeframe}) geladen
        </div>
        <div className="text-[11px] text-[#8B95A5] mt-1">
          Wähle links ein Symbol aus dem Multi-Source-Screener oder starte den Backtest.
        </div>
      </div>
    );
  }

  // SVG coordinate dimensions
  const W = 960;
  const H = 290;
  const PAD_LEFT = 12;
  const PAD_RIGHT = 68;
  const PAD_TOP = 16;
  const PAD_BOTTOM = 24;
  const plotW = W - PAD_LEFT - PAD_RIGHT;
  const plotH = H - PAD_TOP - PAD_BOTTOM;

  const activeCandle =
    hoverIndex !== null && visibleCandles[hoverIndex]
      ? visibleCandles[hoverIndex]
      : visibleCandles[visibleCandles.length - 1];

  const xForIdx = (idx: number, total: number) =>
    PAD_LEFT + (total <= 1 ? plotW / 2 : (idx / (total - 1)) * plotW);

  const findCandleIdxByTime = (timeMs: number) => {
    let bestIdx = 0;
    let bestDist = Infinity;
    for (let i = 0; i < visibleCandles.length; i++) {
      const dist = Math.abs(visibleCandles[i].time - timeMs);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = i;
      }
    }
    return bestIdx;
  };

  const yForPrice = (p: number) => {
    const ratio = (p - priceBounds.min) / Math.max(priceBounds.max - priceBounds.min, 1e-9);
    return PAD_TOP + plotH - ratio * plotH;
  };

  const yForEquity = (eq: number) => {
    const ratio = (eq - equityBounds.min) / Math.max(equityBounds.max - equityBounds.min, 1e-9);
    return PAD_TOP + plotH - ratio * plotH;
  };

  const yForDd = (ddPct: number) => {
    const ratio = ddPct / Math.max(ddBounds.maxDd, 0.1);
    return PAD_TOP + ratio * plotH;
  };

  const buildPolyline = (values: number[], yFn: (v: number) => number) => {
    return values
      .map((v, i) => `${xForIdx(i, values.length).toFixed(1)},${yFn(v).toFixed(1)}`)
      .join(' ');
  };

  const priceGridTicks = [0, 0.25, 0.5, 0.75, 1].map(
    (t) => priceBounds.min + t * (priceBounds.max - priceBounds.min)
  );

  const equityGridTicks = [0, 0.25, 0.5, 0.75, 1].map(
    (t) => equityBounds.min + t * (equityBounds.max - equityBounds.min)
  );

  return (
    <div className="flex flex-col bg-[#07090E] border-b border-[#1B2230] select-none">
      {/* Chart Toolbar */}
      <div className="flex items-center justify-between px-2.5 py-1 bg-[#0C1017] border-b border-[#1B2230] gap-2 flex-wrap">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setViewMode('PRICE')}
            className={`px-2 py-0.5 text-[10px] font-semibold tracking-wider uppercase border transition-colors ${
              viewMode === 'PRICE'
                ? 'bg-[#00E5FF]/15 text-[#00E5FF] border-[#00E5FF]/50'
                : 'bg-[#07090E] text-[#8B95A5] border-[#1B2230] hover:text-[#E6EDF3]'
            }`}
          >
            PREIS & SIGNALE ({visibleTrades.length})
          </button>
          <button
            type="button"
            onClick={() => setViewMode('EQUITY')}
            className={`px-2 py-0.5 text-[10px] font-semibold tracking-wider uppercase border transition-colors ${
              viewMode === 'EQUITY'
                ? 'bg-[#089981]/15 text-[#089981] border-[#089981]/50'
                : 'bg-[#07090E] text-[#8B95A5] border-[#1B2230] hover:text-[#E6EDF3]'
            }`}
          >
            EQUITY-KURVE (${initialCapital.toFixed(0)} BASIS)
          </button>
          <button
            type="button"
            onClick={() => setViewMode('DRAWDOWN')}
            className={`px-2 py-0.5 text-[10px] font-semibold tracking-wider uppercase border transition-colors ${
              viewMode === 'DRAWDOWN'
                ? 'bg-[#F23645]/15 text-[#F23645] border-[#F23645]/50'
                : 'bg-[#07090E] text-[#8B95A5] border-[#1B2230] hover:text-[#E6EDF3]'
            }`}
          >
            DRAWDOWN %
          </button>
        </div>

        {/* OHLCV Live Crosshair Readout */}
        {activeCandle && (
          <div className="flex items-center gap-2.5 text-[10px] font-mono tabular-nums">
            <span className="text-[#8B95A5]">
              {new Date(activeCandle.time).toLocaleTimeString('de-DE', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
            <span>
              <span className="text-[#566173]">O </span>
              <span className="text-[#E6EDF3]">{formatPrice(activeCandle.open)}</span>
            </span>
            <span>
              <span className="text-[#566173]">H </span>
              <span className="text-[#089981]">{formatPrice(activeCandle.high)}</span>
            </span>
            <span>
              <span className="text-[#566173]">L </span>
              <span className="text-[#F23645]">{formatPrice(activeCandle.low)}</span>
            </span>
            <span>
              <span className="text-[#566173]">C </span>
              <span
                className={
                  activeCandle.close >= activeCandle.open ? 'text-[#089981]' : 'text-[#F23645]'
                }
              >
                {formatPrice(activeCandle.close)}
              </span>
            </span>
            {activeCandle.vwap && (
              <span>
                <span className="text-[#A855F7]">VWAP </span>
                <span className="text-[#E6EDF3]">{formatPrice(activeCandle.vwap)}</span>
              </span>
            )}
          </div>
        )}

        {/* Overlay Toggles */}
        <div className="flex items-center gap-1">
          {viewMode === 'PRICE' && (
            <>
              <button
                type="button"
                onClick={() => setShowEma((v) => !v)}
                className={`px-1.5 py-0.5 text-[9px] font-mono border ${
                  showEma
                    ? 'border-[#00E5FF]/40 text-[#00E5FF] bg-[#00E5FF]/10'
                    : 'border-[#1B2230] text-[#566173]'
                }`}
              >
                EMA {fastEmaPeriod}/{slowEmaPeriod}
              </button>
              <button
                type="button"
                onClick={() => setShowVwap((v) => !v)}
                className={`px-1.5 py-0.5 text-[9px] font-mono border ${
                  showVwap
                    ? 'border-[#A855F7]/40 text-[#A855F7] bg-[#A855F7]/10'
                    : 'border-[#1B2230] text-[#566173]'
                }`}
              >
                VWAP
              </button>
              <button
                type="button"
                onClick={() => setShowTradeMarkers((v) => !v)}
                className={`px-1.5 py-0.5 text-[9px] font-mono border flex items-center gap-1 whitespace-nowrap shrink-0 ${
                  showTradeMarkers
                    ? 'border-[#089981]/40 text-[#089981] bg-[#089981]/10'
                    : 'border-[#1B2230] text-[#566173]'
                }`}
              >
                {showTradeMarkers ? <Eye className="w-2.5 h-2.5" /> : <EyeOff className="w-2.5 h-2.5" />}
                TRADES
              </button>
              <button
                type="button"
                onClick={() => setShowPaperPositionLines((v) => !v)}
                title="Horizontale Entry-, Stop-Loss- und Take-Profit-Linien für offene Paper-Positionen ein-/ausblenden"
                className={`px-1.5 py-0.5 text-[9px] font-mono border flex items-center gap-1 whitespace-nowrap shrink-0 ${
                  showPaperPositionLines
                    ? 'border-[#00E5FF]/50 text-[#00E5FF] bg-[#00E5FF]/15'
                    : 'border-[#1B2230] text-[#566173]'
                }`}
              >
                PAPER-POS ({openPaperPositions.length})
              </button>
            </>
          )}
          {viewMode === 'EQUITY' && (
            <button
              type="button"
              onClick={() => setShowShadowEquity((v) => !v)}
              className={`px-1.5 py-0.5 text-[9px] font-mono border ${
                showShadowEquity
                  ? 'border-[#A855F7]/50 text-[#A855F7] bg-[#A855F7]/15'
                  : 'border-[#1B2230] text-[#566173]'
              }`}
            >
              SHADOW ENGINE (GEGENSTRATEGIE)
            </button>
          )}
          {selectedTrade && (
            <button
              type="button"
              onClick={() => onSelectTrade(null)}
              className="px-1.5 py-0.5 text-[9px] font-mono border border-[#F59E0B]/50 text-[#F59E0B] bg-[#F59E0B]/10"
            >
              FOKUS LÖSEN (#{selectedTrade.tradeNumber})
            </button>
          )}
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative w-full h-[275px] bg-[#07090E]">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-full overflow-visible"
          onMouseLeave={() => setHoverIndex(null)}
        >
          {/* PRICE & SIGNALS VIEW */}
          {viewMode === 'PRICE' && (
            <>
              {/* Horizontal Grid Lines */}
              {priceGridTicks.map((tick, idx) => {
                const y = yForPrice(tick);
                return (
                  <g key={idx}>
                    <line
                      x1={PAD_LEFT}
                      y1={y}
                      x2={W - PAD_RIGHT}
                      y2={y}
                      stroke="#141A24"
                      strokeDasharray="2 2"
                    />
                    <text
                      x={W - PAD_RIGHT + 5}
                      y={y + 3}
                      fill="#8B95A5"
                      fontSize="9"
                      fontFamily="JetBrains Mono, monospace"
                    >
                      {formatPrice(tick)}
                    </text>
                  </g>
                );
              })}

              {/* Selected Trade Stop-Loss & Take-Profit Horizontal Lines */}
              {selectedTrade && (
                <g>
                  <line
                    x1={PAD_LEFT}
                    y1={yForPrice(selectedTrade.stopLossPrice)}
                    x2={W - PAD_RIGHT}
                    y2={yForPrice(selectedTrade.stopLossPrice)}
                    stroke="#F23645"
                    strokeWidth="1"
                    strokeDasharray="4 2"
                  />
                  <text
                    x={PAD_LEFT + 6}
                    y={yForPrice(selectedTrade.stopLossPrice) - 3}
                    fill="#F23645"
                    fontSize="9"
                    fontFamily="JetBrains Mono, monospace"
                  >
                    BT SL {formatPrice(selectedTrade.stopLossPrice)}
                  </text>
                  <line
                    x1={PAD_LEFT}
                    y1={yForPrice(selectedTrade.takeProfitPrice)}
                    x2={W - PAD_RIGHT}
                    y2={yForPrice(selectedTrade.takeProfitPrice)}
                    stroke="#089981"
                    strokeWidth="1"
                    strokeDasharray="4 2"
                  />
                  <text
                    x={PAD_LEFT + 6}
                    y={yForPrice(selectedTrade.takeProfitPrice) - 3}
                    fill="#089981"
                    fontSize="9"
                    fontFamily="JetBrains Mono, monospace"
                  >
                    BT TP {formatPrice(selectedTrade.takeProfitPrice)}
                  </text>
                </g>
              )}

              {/* Open Paper Position Entry, Auto-SL & Auto-TP Horizontal Lines */}
              {showPaperPositionLines &&
                openPaperPositions.map((pos, pIdx) => {
                  const yEntry = yForPrice(pos.entryPrice);
                  const ySl = yForPrice(pos.stopLossPrice);
                  const yTp = yForPrice(pos.takeProfitPrice);
                  const pnlSign = pos.unrealizedPnl >= 0 ? '+' : '';
                  return (
                    <g key={`paper-pos-${pos.pair}-${pIdx}`}>
                      {/* Paper Entry Line */}
                      <line
                        x1={PAD_LEFT}
                        y1={yEntry}
                        x2={W - PAD_RIGHT}
                        y2={yEntry}
                        stroke="#00E5FF"
                        strokeWidth="1.3"
                        strokeDasharray="6 2"
                      />
                      <text
                        x={PAD_LEFT + 6}
                        y={yEntry - 4}
                        fill="#00E5FF"
                        fontSize="9"
                        fontWeight="bold"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        PAPER {pos.side} ENTRY {formatPrice(pos.entryPrice)} ({pnlSign}$
                        {pos.unrealizedPnl.toFixed(2)})
                      </text>

                      {/* Paper Stop-Loss Line */}
                      <line
                        x1={PAD_LEFT}
                        y1={ySl}
                        x2={W - PAD_RIGHT}
                        y2={ySl}
                        stroke={pos.isBreakEven ? '#00E5FF' : '#F59E0B'}
                        strokeWidth="1.2"
                        strokeDasharray="3 3"
                      />
                      <text
                        x={W - PAD_RIGHT - 155}
                        y={ySl - 4}
                        fill={pos.isBreakEven ? '#00E5FF' : '#F59E0B'}
                        fontSize="9"
                        fontWeight="bold"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        {pos.isBreakEven ? 'AUTO-SL (BE)' : 'AUTO-SL'} {formatPrice(pos.stopLossPrice)}
                      </text>

                      {/* Paper Take-Profit Line */}
                      <line
                        x1={PAD_LEFT}
                        y1={yTp}
                        x2={W - PAD_RIGHT}
                        y2={yTp}
                        stroke="#089981"
                        strokeWidth="1.2"
                        strokeDasharray="3 3"
                      />
                      <text
                        x={W - PAD_RIGHT - 155}
                        y={yTp - 4}
                        fill="#089981"
                        fontSize="9"
                        fontWeight="bold"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        AUTO-TP {formatPrice(pos.takeProfitPrice)}
                      </text>
                    </g>
                  );
                })}

              {/* VWAP Line */}
              {showVwap && (
                <polyline
                  fill="none"
                  stroke="#A855F7"
                  strokeWidth="1.2"
                  strokeDasharray="3 2"
                  opacity="0.75"
                  points={buildPolyline(
                    visibleCandles.map((c) => c.vwap || c.close),
                    yForPrice
                  )}
                />
              )}

              {/* Fast & Slow EMA Lines */}
              {showEma && fastEma.length === visibleCandles.length && (
                <>
                  <polyline
                    fill="none"
                    stroke="#00E5FF"
                    strokeWidth="1.3"
                    opacity="0.85"
                    points={buildPolyline(fastEma, yForPrice)}
                  />
                  <polyline
                    fill="none"
                    stroke="#F59E0B"
                    strokeWidth="1.2"
                    opacity="0.75"
                    points={buildPolyline(slowEma, yForPrice)}
                  />
                </>
              )}

              {/* Candlesticks */}
              {visibleCandles.map((c, idx) => {
                const x = xForIdx(idx, visibleCandles.length);
                const isBull = c.close >= c.open;
                const color = isBull ? '#089981' : '#F23645';
                const yHigh = yForPrice(c.high);
                const yLow = yForPrice(c.low);
                const yOpen = yForPrice(c.open);
                const yClose = yForPrice(c.close);
                const bodyTop = Math.min(yOpen, yClose);
                const bodyH = Math.max(1.5, Math.abs(yClose - yOpen));
                const candleW = Math.max(2, Math.min(7, plotW / visibleCandles.length - 1.5));

                return (
                  <g
                    key={c.time}
                    onMouseEnter={() => setHoverIndex(idx)}
                    className="cursor-crosshair"
                  >
                    <line x1={x} y1={yHigh} x2={x} y2={yLow} stroke={color} strokeWidth="1" />
                    <rect
                      x={x - candleW / 2}
                      y={bodyTop}
                      width={candleW}
                      height={bodyH}
                      fill={color}
                    />
                  </g>
                );
              })}

              {/* Trade Entry & Exit Connecting Lines + Glowing Markers */}
              {showTradeMarkers &&
                visibleTrades.map((t) => {
                  const localEntryIdx = findCandleIdxByTime(t.entryTime);
                  const localExitIdx = findCandleIdxByTime(t.exitTime);
                  const x1 = xForIdx(localEntryIdx, visibleCandles.length);
                  const y1 = yForPrice(t.entryPrice);
                  const x2 = xForIdx(localExitIdx, visibleCandles.length);
                  const y2 = yForPrice(t.exitPrice);
                  const isWin = t.netPnlUsd >= 0;
                  const isSelected = t.id === selectedTradeId;

                  return (
                    <g
                      key={t.id}
                      onClick={() => onSelectTrade(isSelected ? null : t.id)}
                      className="cursor-pointer"
                    >
                      <line
                        x1={x1}
                        y1={y1}
                        x2={x2}
                        y2={y2}
                        stroke={isWin ? '#089981' : '#F23645'}
                        strokeWidth={isSelected ? '2' : '1.1'}
                        strokeDasharray="2 2"
                        opacity={isSelected ? '1' : '0.75'}
                      />
                      {/* Entry Dot (Cyan) */}
                      <circle
                        cx={x1}
                        cy={y1}
                        r={isSelected ? 4.5 : 3}
                        fill="#00E5FF"
                        stroke="#07090E"
                        strokeWidth="1"
                      />
                      {/* Exit Dot (Emerald for Win, Crimson for Loss) */}
                      <circle
                        cx={x2}
                        cy={y2}
                        r={isSelected ? 5 : 3.2}
                        fill={isWin ? '#089981' : '#F23645'}
                        stroke="#E6EDF3"
                        strokeWidth="0.8"
                      />
                    </g>
                  );
                })}
            </>
          )}

          {/* EQUITY CURVE VIEW ($1,000 BASIS + SHADOW ENGINE COUNTER-CURVE) */}
          {viewMode === 'EQUITY' && equityCurve.length > 0 && (
            <>
              {equityGridTicks.map((tick, idx) => {
                const y = yForEquity(tick);
                return (
                  <g key={idx}>
                    <line
                      x1={PAD_LEFT}
                      y1={y}
                      x2={W - PAD_RIGHT}
                      y2={y}
                      stroke="#141A24"
                      strokeDasharray="2 2"
                    />
                    <text
                      x={W - PAD_RIGHT + 5}
                      y={y + 3}
                      fill="#8B95A5"
                      fontSize="9"
                      fontFamily="JetBrains Mono, monospace"
                    >
                      ${tick.toFixed(0)}
                    </text>
                  </g>
                );
              })}

              {/* $1,000 Baseline */}
              <line
                x1={PAD_LEFT}
                y1={yForEquity(initialCapital)}
                x2={W - PAD_RIGHT}
                y2={yForEquity(initialCapital)}
                stroke="#566173"
                strokeWidth="1"
                strokeDasharray="3 3"
              />

              {/* Shadow Inverse Equity Curve */}
              {showShadowEquity && (
                <polyline
                  fill="none"
                  stroke="#A855F7"
                  strokeWidth="1.4"
                  strokeDasharray="3 2"
                  points={buildPolyline(
                    equityCurve.map((pt) => pt.shadowEquity),
                    yForEquity
                  )}
                />
              )}

              {/* Primary Equity Curve */}
              <polyline
                fill="none"
                stroke="#089981"
                strokeWidth="2"
                points={buildPolyline(
                  equityCurve.map((pt) => pt.equity),
                  yForEquity
                )}
              />
            </>
          )}

          {/* DRAWDOWN % VIEW */}
          {viewMode === 'DRAWDOWN' && equityCurve.length > 0 && (
            <>
              {[0, 0.25, 0.5, 0.75, 1].map((t, idx) => {
                const val = t * ddBounds.maxDd;
                const y = yForDd(val);
                return (
                  <g key={idx}>
                    <line
                      x1={PAD_LEFT}
                      y1={y}
                      x2={W - PAD_RIGHT}
                      y2={y}
                      stroke="#141A24"
                      strokeDasharray="2 2"
                    />
                    <text
                      x={W - PAD_RIGHT + 5}
                      y={y + 3}
                      fill="#F23645"
                      fontSize="9"
                      fontFamily="JetBrains Mono, monospace"
                    >
                      -{val.toFixed(1)}%
                    </text>
                  </g>
                );
              })}
              <polyline
                fill="none"
                stroke="#F23645"
                strokeWidth="1.8"
                points={buildPolyline(
                  equityCurve.map((pt) => pt.drawdownPct),
                  yForDd
                )}
              />
            </>
          )}
        </svg>

        {/* Bottom Legend Strip */}
        <div className="absolute bottom-1 left-2.5 right-2.5 flex items-center justify-between text-[9px] font-mono tabular-nums text-[#8B95A5] pointer-events-none">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#00E5FF] inline-block" />
              ENTER
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#089981] inline-block" />
              EXIT WIN / TP
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#F23645] inline-block" />
              EXIT LOSS / SL
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-0.5 bg-[#A855F7] inline-block" />
              {viewMode === 'EQUITY' ? 'SHADOW ENGINE (INVERS)' : 'VWAP'}
            </span>
          </div>
          <div>
            QUELLE: <span className="text-[#00E5FF] font-semibold">{provider}</span> ·{' '}
            {visibleCandles.length} BARS ({timeframe})
          </div>
        </div>
      </div>
    </div>
  );
});

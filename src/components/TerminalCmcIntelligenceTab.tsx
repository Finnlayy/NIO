import React, { useState, useMemo } from 'react';
import {
  CmcIntelligencePayload,
  CmcDexNetwork,
} from '../types/terminal';
import {
  Globe,
  TrendingUp,
  Layers,
  Building2,
  Radio,
  RefreshCw,
  ArrowUpRight,
  ShieldCheck,
  Flame,
  Play,
  Search,
} from 'lucide-react';

interface TerminalCmcIntelligenceTabProps {
  data: CmcIntelligencePayload | null;
  isLoading: boolean;
  activeSymbol: string;
  onSelectSymbolAndLoad: (symbol: string, runBacktestImmediately?: boolean) => void;
  onRefresh: () => void;
}

type CmcSubView = 'RANKED_SCREENER' | 'DEX_ONCHAIN' | 'EXCHANGE_LIQUIDITY' | 'SIGNALS_HEADLINES';

function formatCompactUsd(val: number): string {
  if (val >= 1_000_000_000_000) return `$${(val / 1_000_000_000_000).toFixed(2)}T`;
  if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(2)}B`;
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(2)}`;
}

function formatPriceSmart(price: number): string {
  if (price >= 1000) return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (price >= 1) return `$${price.toFixed(3)}`;
  if (price >= 0.01) return `$${price.toFixed(4)}`;
  return `$${price.toFixed(7)}`;
}

export const TerminalCmcIntelligenceTab: React.FC<TerminalCmcIntelligenceTabProps> = React.memo(({
  data,
  isLoading,
  activeSymbol,
  onSelectSymbolAndLoad,
  onRefresh,
}) => {
  const [subView, setSubView] = useState<CmcSubView>('RANKED_SCREENER');
  const [rankFilter, setRankFilter] = useState<'ALL' | 'GAINERS' | 'LOSERS' | 'HIGH_VOL' | 'AI' | 'MEME' | 'LAYER1'>('ALL');
  const [dexNetworkFilter, setDexNetworkFilter] = useState<'ALL' | CmcDexNetwork>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredRankedAssets = useMemo(() => {
    if (!data) return [];
    let list = [...data.rankedAssets];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (a) =>
          a.symbol.toLowerCase().includes(q) ||
          a.name.toLowerCase().includes(q) ||
          a.category.toLowerCase().includes(q)
      );
    }
    if (rankFilter === 'GAINERS') {
      list = list.filter((a) => a.change24hPct > 0).sort((a, b) => b.change24hPct - a.change24hPct);
    } else if (rankFilter === 'LOSERS') {
      list = list.filter((a) => a.change24hPct < 0).sort((a, b) => a.change24hPct - b.change24hPct);
    } else if (rankFilter === 'HIGH_VOL') {
      list = [...list].sort((a, b) => b.volume24hUsd - a.volume24hUsd);
    } else if (rankFilter === 'AI') {
      list = list.filter((a) => a.category === 'AI');
    } else if (rankFilter === 'MEME') {
      list = list.filter((a) => a.category === 'MEME');
    } else if (rankFilter === 'LAYER1') {
      list = list.filter((a) => a.category === 'LAYER1');
    }
    return list;
  }, [data, rankFilter, searchQuery]);

  const filteredDexPairs = useMemo(() => {
    if (!data) return [];
    return data.dexPairs.filter((pair) => {
      if (dexNetworkFilter !== 'ALL' && pair.network !== dexNetworkFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          pair.pairSymbol.toLowerCase().includes(q) ||
          pair.dexName.toLowerCase().includes(q) ||
          pair.network.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [data, dexNetworkFilter, searchQuery]);

  if (!data) {
    return (
      <div className="p-4 text-xs font-mono text-[#8B95A5] flex items-center justify-between">
        <span>Lade CoinMarketCap Global Intelligence, DEXscan & Exchange Liquidity...</span>
        <button
          type="button"
          onClick={onRefresh}
          className="px-2 py-1 border border-[#3861FB]/50 bg-[#3861FB]/15 text-[#E6EDF3]"
        >
          Erneut laden
        </button>
      </div>
    );
  }

  const { globalMetrics } = data;
  const fgColor =
    globalMetrics.fearAndGreedIndex >= 60
      ? 'text-[#089981] border-[#089981]/40 bg-[#089981]/10'
      : globalMetrics.fearAndGreedIndex <= 40
      ? 'text-[#F23645] border-[#F23645]/40 bg-[#F23645]/10'
      : 'text-[#F59E0B] border-[#F59E0B]/40 bg-[#F59E0B]/10';

  return (
    <div className="flex flex-col h-full bg-[#07090E] text-[#E6EDF3] font-mono select-none">
      {/* Top CMC Global Macro & Telemetry Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-2.5 py-1.5 bg-[#0C1017] border-b border-[#1B2230] text-[10px] tabular-nums">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.5 bg-[#3861FB]/20 border border-[#3861FB]/50 text-[#60A5FA] font-bold">
              CMC STAGE #{data.cascadePosition}
            </span>
            <span className="text-[#8B95A5]">
              {data.sourceMode === 'CMC_PRO_API' ? 'PRO REST v1/v4' : 'KEYLESS PUBLIC + DEXSCAN'}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <span className="text-[#8B95A5]">MCAP:</span>
            <span className="font-bold text-[#E6EDF3]">{formatCompactUsd(globalMetrics.totalMarketCapUsd)}</span>
            <span
              className={
                globalMetrics.totalMarketCapChange24hPct >= 0 ? 'text-[#089981]' : 'text-[#F23645]'
              }
            >
              ({globalMetrics.totalMarketCapChange24hPct >= 0 ? '+' : ''}
              {globalMetrics.totalMarketCapChange24hPct.toFixed(2)}%)
            </span>
          </div>

          <div className="flex items-center gap-1">
            <span className="text-[#8B95A5]">24H VOL:</span>
            <span className="font-bold text-[#E6EDF3]">{formatCompactUsd(globalMetrics.totalVolume24hUsd)}</span>
          </div>

          <div className="flex items-center gap-1">
            <span className="text-[#8B95A5]">DEX 24H:</span>
            <span className="font-bold text-[#00E5FF]">{formatCompactUsd(globalMetrics.dexVolume24hUsd)}</span>
          </div>

          <div className="flex items-center gap-1">
            <span className="text-[#8B95A5]">DOM:</span>
            <span className="text-[#F59E0B] font-semibold">BTC {globalMetrics.btcDominancePct}%</span>
            <span className="text-[#8B95A5]">/</span>
            <span className="text-[#60A5FA] font-semibold">ETH {globalMetrics.ethDominancePct}%</span>
          </div>

          <div className={`flex items-center gap-1 px-1.5 py-0.5 border ${fgColor}`}>
            <Flame className="w-3 h-3" />
            <span className="font-bold">
              F&G: {globalMetrics.fearAndGreedIndex}/100 ({globalMetrics.fearAndGreedLabel})
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <div className="relative">
            <Search className="w-3 h-3 text-[#8B95A5] absolute left-1.5 top-1.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter Symbol / DEX / Chain..."
              className="bg-[#07090E] border border-[#1B2230] pl-5 pr-2 py-0.5 text-[10px] text-[#E6EDF3] focus:border-[#3861FB] focus:outline-none w-40"
            />
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center gap-1 px-2 py-0.5 border border-[#1B2230] bg-[#111722] hover:border-[#3861FB] text-[10px] text-[#E6EDF3]"
            title="CoinMarketCap & DEX Daten sofort aktualisieren"
          >
            <RefreshCw className={`w-3 h-3 text-[#60A5FA] ${isLoading ? 'animate-spin' : ''}`} />
            <span>SYNC</span>
          </button>
        </div>
      </div>

      {/* Sub-navigation bar */}
      <div className="flex items-center justify-between px-2.5 py-1 bg-[#090D14] border-b border-[#1B2230] text-[10px]">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setSubView('RANKED_SCREENER')}
            className={`flex items-center gap-1 px-2 py-0.5 border ${
              subView === 'RANKED_SCREENER'
                ? 'border-[#3861FB] bg-[#3861FB]/20 text-[#E6EDF3] font-bold'
                : 'border-transparent text-[#8B95A5] hover:text-[#E6EDF3]'
            }`}
          >
            <TrendingUp className="w-3 h-3 text-[#60A5FA]" />
            <span>1. RANKED CRYPTO SCREENER ({data.rankedAssets.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setSubView('DEX_ONCHAIN')}
            className={`flex items-center gap-1 px-2 py-0.5 border ${
              subView === 'DEX_ONCHAIN'
                ? 'border-[#00E5FF] bg-[#00E5FF]/15 text-[#00E5FF] font-bold'
                : 'border-transparent text-[#8B95A5] hover:text-[#E6EDF3]'
            }`}
          >
            <Layers className="w-3 h-3 text-[#00E5FF]" />
            <span>2. DEX ON-CHAIN PAIRS & LIQUIDITY ({data.dexPairs.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setSubView('EXCHANGE_LIQUIDITY')}
            className={`flex items-center gap-1 px-2 py-0.5 border ${
              subView === 'EXCHANGE_LIQUIDITY'
                ? 'border-[#089981] bg-[#089981]/15 text-[#089981] font-bold'
                : 'border-transparent text-[#8B95A5] hover:text-[#E6EDF3]'
            }`}
          >
            <Building2 className="w-3 h-3 text-[#089981]" />
            <span>3. EXCHANGE ACTIVITY & PoR ({data.exchanges.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setSubView('SIGNALS_HEADLINES')}
            className={`flex items-center gap-1 px-2 py-0.5 border ${
              subView === 'SIGNALS_HEADLINES'
                ? 'border-[#A855F7] bg-[#A855F7]/15 text-[#C084FC] font-bold'
                : 'border-transparent text-[#8B95A5] hover:text-[#E6EDF3]'
            }`}
          >
            <Radio className="w-3 h-3 text-[#C084FC]" />
            <span>4. HEADLINES, TRENDS & COMMUNITY ({data.signals.length})</span>
          </button>
        </div>

        {/* Context filter pills */}
        {subView === 'RANKED_SCREENER' && (
          <div className="flex items-center gap-1">
            {(['ALL', 'GAINERS', 'LOSERS', 'HIGH_VOL', 'LAYER1', 'AI', 'MEME'] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setRankFilter(f)}
                className={`px-1.5 py-0.5 text-[9px] border ${
                  rankFilter === f
                    ? 'border-[#60A5FA] bg-[#3861FB]/20 text-[#E6EDF3]'
                    : 'border-[#1B2230] text-[#8B95A5] hover:text-[#E6EDF3]'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        )}

        {subView === 'DEX_ONCHAIN' && (
          <div className="flex items-center gap-1">
            {(['ALL', 'SOLANA', 'ETHEREUM', 'BASE', 'BSC'] as const).map((net) => (
              <button
                key={net}
                type="button"
                onClick={() => setDexNetworkFilter(net)}
                className={`px-1.5 py-0.5 text-[9px] border ${
                  dexNetworkFilter === net
                    ? 'border-[#00E5FF] bg-[#00E5FF]/15 text-[#00E5FF]'
                    : 'border-[#1B2230] text-[#8B95A5] hover:text-[#E6EDF3]'
                }`}
              >
                {net}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-auto">
        {subView === 'RANKED_SCREENER' && (
          <table className="w-full text-left border-collapse text-[10px] tabular-nums">
            <thead className="sticky top-0 bg-[#0C1017] text-[#8B95A5] border-b border-[#1B2230] z-10">
              <tr>
                <th className="py-1 px-2">CMC #</th>
                <th className="py-1 px-2">ASSET / PAIR</th>
                <th className="py-1 px-2">SECTOR</th>
                <th className="py-1 px-2 text-right">PRICE (USD)</th>
                <th className="py-1 px-2 text-right">1H %</th>
                <th className="py-1 px-2 text-right">24H %</th>
                <th className="py-1 px-2 text-right">7D %</th>
                <th className="py-1 px-2 text-right">MARKET CAP</th>
                <th className="py-1 px-2 text-right">24H VOLUME</th>
                <th className="py-1 px-2 text-right">VOL/MCAP</th>
                <th className="py-1 px-2">SIGNAL</th>
                <th className="py-1 px-2 text-right">TERMINAL ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#141A24]">
              {filteredRankedAssets.map((asset) => {
                const isSelected = asset.symbol === activeSymbol;
                return (
                  <tr
                    key={asset.symbol}
                    onClick={() => onSelectSymbolAndLoad(asset.symbol, false)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? 'bg-[#3861FB]/15' : 'hover:bg-[#111722]'
                    }`}
                  >
                    <td className="py-1 px-2 font-bold text-[#60A5FA]">#{asset.cmcRank}</td>
                    <td className="py-1 px-2">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-[#E6EDF3]">{asset.symbol}</span>
                        <span className="text-[#8B95A5] text-[9px]">{asset.name}</span>
                      </div>
                    </td>
                    <td className="py-1 px-2">
                      <span className="px-1 py-0.2 border border-[#263042] bg-[#0C1017] text-[9px] text-[#8B95A5]">
                        {asset.category}
                      </span>
                    </td>
                    <td className="py-1 px-2 text-right font-bold text-[#E6EDF3]">
                      {formatPriceSmart(asset.price)}
                    </td>
                    <td
                      className={`py-1 px-2 text-right ${
                        asset.change1hPct >= 0 ? 'text-[#089981]' : 'text-[#F23645]'
                      }`}
                    >
                      {asset.change1hPct >= 0 ? '+' : ''}
                      {asset.change1hPct.toFixed(2)}%
                    </td>
                    <td
                      className={`py-1 px-2 text-right font-semibold ${
                        asset.change24hPct >= 0 ? 'text-[#089981]' : 'text-[#F23645]'
                      }`}
                    >
                      {asset.change24hPct >= 0 ? '+' : ''}
                      {asset.change24hPct.toFixed(2)}%
                    </td>
                    <td
                      className={`py-1 px-2 text-right ${
                        asset.change7dPct >= 0 ? 'text-[#089981]' : 'text-[#F23645]'
                      }`}
                    >
                      {asset.change7dPct >= 0 ? '+' : ''}
                      {asset.change7dPct.toFixed(2)}%
                    </td>
                    <td className="py-1 px-2 text-right text-[#E6EDF3]">
                      {formatCompactUsd(asset.marketCapUsd)}
                    </td>
                    <td className="py-1 px-2 text-right text-[#00E5FF]">
                      {formatCompactUsd(asset.volume24hUsd)}
                    </td>
                    <td className="py-1 px-2 text-right text-[#8B95A5]">
                      {asset.volumeMcRatioPct.toFixed(2)}%
                    </td>
                    <td className="py-1 px-2">
                      <span
                        className={`px-1 py-0.2 text-[9px] border ${
                          asset.tag === 'TOP_GAINER'
                            ? 'border-[#089981]/50 bg-[#089981]/15 text-[#089981]'
                            : asset.tag === 'TOP_LOSER'
                            ? 'border-[#F23645]/50 bg-[#F23645]/15 text-[#F23645]'
                            : asset.tag === 'HIGH_VOL'
                            ? 'border-[#00E5FF]/50 bg-[#00E5FF]/15 text-[#00E5FF]'
                            : 'border-[#263042] text-[#8B95A5]'
                        }`}
                      >
                        {asset.tag}
                      </span>
                    </td>
                    <td className="py-1 px-2 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectSymbolAndLoad(asset.symbol, true);
                        }}
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 border border-[#089981]/60 bg-[#089981]/15 hover:bg-[#089981]/30 text-[#089981] text-[9px] font-bold"
                      >
                        <Play className="w-2.5 h-2.5" />
                        <span>CHART & BACKTEST</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {subView === 'DEX_ONCHAIN' && (
          <table className="w-full text-left border-collapse text-[10px] tabular-nums">
            <thead className="sticky top-0 bg-[#0C1017] text-[#8B95A5] border-b border-[#1B2230] z-10">
              <tr>
                <th className="py-1 px-2">NETWORK</th>
                <th className="py-1 px-2">DEX PROTOCOL</th>
                <th className="py-1 px-2">ON-CHAIN PAIR</th>
                <th className="py-1 px-2 text-right">PRICE (USD)</th>
                <th className="py-1 px-2 text-right">1H %</th>
                <th className="py-1 px-2 text-right">24H %</th>
                <th className="py-1 px-2 text-right">POOL LIQUIDITY</th>
                <th className="py-1 px-2 text-right">24H DEX VOL</th>
                <th className="py-1 px-2 text-right">24H BUYS / SELLS</th>
                <th className="py-1 px-2 text-right">FDV</th>
                <th className="py-1 px-2 text-right">AUDIT</th>
                <th className="py-1 px-2 text-right">WORKSPACE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#141A24]">
              {filteredDexPairs.map((pair) => {
                const isSelected = pair.pairSymbol === activeSymbol;
                const totalTx = pair.txns24hBuys + pair.txns24hSells;
                const buyRatioPct = Math.round((pair.txns24hBuys / Math.max(1, totalTx)) * 100);
                return (
                  <tr
                    key={pair.id}
                    onClick={() => onSelectSymbolAndLoad(pair.pairSymbol, false)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? 'bg-[#00E5FF]/15' : 'hover:bg-[#111722]'
                    }`}
                  >
                    <td className="py-1 px-2">
                      <span className="px-1.5 py-0.5 border border-[#00E5FF]/40 bg-[#00E5FF]/10 text-[#00E5FF] text-[9px] font-bold">
                        {pair.network}
                      </span>
                    </td>
                    <td className="py-1 px-2 text-[#E6EDF3]">
                      {pair.dexName}{' '}
                      <span className="text-[#8B95A5] text-[9px]">({pair.feeTierBps} bps)</span>
                    </td>
                    <td className="py-1 px-2">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-[#E6EDF3]">{pair.pairSymbol}</span>
                        <span className="text-[#8B95A5] text-[9px]">{pair.poolAddress}</span>
                      </div>
                    </td>
                    <td className="py-1 px-2 text-right font-bold text-[#E6EDF3]">
                      {formatPriceSmart(pair.priceUsd)}
                    </td>
                    <td
                      className={`py-1 px-2 text-right ${
                        pair.change1hPct >= 0 ? 'text-[#089981]' : 'text-[#F23645]'
                      }`}
                    >
                      {pair.change1hPct >= 0 ? '+' : ''}
                      {pair.change1hPct.toFixed(2)}%
                    </td>
                    <td
                      className={`py-1 px-2 text-right font-semibold ${
                        pair.change24hPct >= 0 ? 'text-[#089981]' : 'text-[#F23645]'
                      }`}
                    >
                      {pair.change24hPct >= 0 ? '+' : ''}
                      {pair.change24hPct.toFixed(2)}%
                    </td>
                    <td className="py-1 px-2 text-right font-semibold text-[#00E5FF]">
                      {formatCompactUsd(pair.liquidityUsd)}
                    </td>
                    <td className="py-1 px-2 text-right text-[#E6EDF3]">
                      {formatCompactUsd(pair.volume24hUsd)}
                    </td>
                    <td className="py-1 px-2 text-right">
                      <span className="text-[#089981]">{pair.txns24hBuys.toLocaleString()} B</span>
                      <span className="text-[#8B95A5]"> / </span>
                      <span className="text-[#F23645]">{pair.txns24hSells.toLocaleString()} S</span>
                      <span className="text-[#8B95A5] ml-1">({buyRatioPct}%)</span>
                    </td>
                    <td className="py-1 px-2 text-right text-[#8B95A5]">
                      {formatCompactUsd(pair.fdvUsd)}
                    </td>
                    <td className="py-1 px-2 text-right">
                      <span className="text-[#089981] font-semibold">{pair.securityScore}/100</span>
                    </td>
                    <td className="py-1 px-2 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectSymbolAndLoad(pair.pairSymbol, true);
                        }}
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 border border-[#00E5FF]/60 bg-[#00E5FF]/15 hover:bg-[#00E5FF]/30 text-[#00E5FF] text-[9px] font-bold"
                      >
                        <Play className="w-2.5 h-2.5" />
                        <span>LOAD DEX PAIR</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {subView === 'EXCHANGE_LIQUIDITY' && (
          <table className="w-full text-left border-collapse text-[10px] tabular-nums">
            <thead className="sticky top-0 bg-[#0C1017] text-[#8B95A5] border-b border-[#1B2230] z-10">
              <tr>
                <th className="py-1 px-2">#</th>
                <th className="py-1 px-2">EXCHANGE / VENUE</th>
                <th className="py-1 px-2">TYPE</th>
                <th className="py-1 px-2 text-right">24H VOLUME (USD)</th>
                <th className="py-1 px-2 text-right">24H VOL CHG</th>
                <th className="py-1 px-2 text-right">CMC LIQUIDITY SCORE</th>
                <th className="py-1 px-2 text-right">MARKET PAIRS</th>
                <th className="py-1 px-2 text-right">PROOF OF RESERVES (PoR)</th>
                <th className="py-1 px-2 text-right">FEES (M/T)</th>
                <th className="py-1 px-2 text-right">TOP ANCHOR PAIR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#141A24]">
              {data.exchanges.map((ex) => (
                <tr key={ex.exchangeId} className="hover:bg-[#111722]">
                  <td className="py-1.5 px-2 font-bold text-[#60A5FA]">#{ex.rank}</td>
                  <td className="py-1.5 px-2 font-bold text-[#E6EDF3]">{ex.name}</td>
                  <td className="py-1.5 px-2">
                    <span
                      className={`px-1.5 py-0.5 text-[9px] border ${
                        ex.type === 'CEX'
                          ? 'border-[#3861FB]/50 bg-[#3861FB]/15 text-[#60A5FA]'
                          : 'border-[#00E5FF]/50 bg-[#00E5FF]/15 text-[#00E5FF]'
                      }`}
                    >
                      {ex.type}
                    </span>
                  </td>
                  <td className="py-1.5 px-2 text-right font-bold text-[#E6EDF3]">
                    {formatCompactUsd(ex.volume24hUsd)}
                  </td>
                  <td
                    className={`py-1.5 px-2 text-right ${
                      ex.change24hPct >= 0 ? 'text-[#089981]' : 'text-[#F23645]'
                    }`}
                  >
                    +{ex.change24hPct.toFixed(1)}%
                  </td>
                  <td className="py-1.5 px-2 text-right">
                    <div className="inline-flex items-center gap-1.5">
                      <div className="w-16 h-1.5 bg-[#1B2230] overflow-hidden">
                        <div
                          className="h-full bg-[#089981]"
                          style={{ width: `${Math.min(100, ex.liquidityScore / 10)}%` }}
                        />
                      </div>
                      <span className="font-bold text-[#089981]">{ex.liquidityScore}/1000</span>
                    </div>
                  </td>
                  <td className="py-1.5 px-2 text-right text-[#E6EDF3]">
                    {ex.marketPairsCount.toLocaleString()}
                  </td>
                  <td className="py-1.5 px-2 text-right">
                    <span className="inline-flex items-center gap-1 text-[#089981]">
                      <ShieldCheck className="w-3 h-3" />
                      <span>{formatCompactUsd(ex.proofOfReservesUsd)}</span>
                    </span>
                  </td>
                  <td className="py-1.5 px-2 text-right text-[#8B95A5]">
                    {ex.makerFeeBps}/{ex.takerFeeBps} bps
                  </td>
                  <td className="py-1.5 px-2 text-right">
                    <button
                      type="button"
                      onClick={() => onSelectSymbolAndLoad(ex.topPair, true)}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 border border-[#263042] hover:border-[#00E5FF] text-[#00E5FF] text-[9px]"
                    >
                      <span>{ex.topPair}</span>
                      <ArrowUpRight className="w-2.5 h-2.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {subView === 'SIGNALS_HEADLINES' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 p-2">
            {data.signals.map((sig) => (
              <div
                key={sig.id}
                onClick={() => onSelectSymbolAndLoad(sig.symbol, false)}
                className="p-2.5 bg-[#0C1017] border border-[#1B2230] hover:border-[#3861FB] cursor-pointer flex flex-col justify-between gap-1.5"
              >
                <div className="flex items-center justify-between gap-2 text-[9px]">
                  <div className="flex items-center gap-1.5">
                    <span className="px-1.5 py-0.5 border border-[#3861FB]/50 bg-[#3861FB]/15 text-[#60A5FA] font-bold">
                      {sig.category}
                    </span>
                    <span className="font-bold text-[#00E5FF]">{sig.symbol}</span>
                    <span className="text-[#8B95A5]">{sig.timeFormatted}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="px-1.5 py-0.5 bg-[#089981]/15 border border-[#089981]/40 text-[#089981] font-bold">
                      {sig.bullishVotesPct}% BULLISH
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectSymbolAndLoad(sig.symbol, true);
                      }}
                      className="px-1.5 py-0.5 border border-[#089981]/50 bg-[#089981]/15 text-[#089981] hover:bg-[#089981]/30 font-bold"
                    >
                      TEST {sig.symbol}
                    </button>
                  </div>
                </div>
                <div className="text-[11px] font-bold text-[#E6EDF3] leading-snug">
                  {sig.headline}
                </div>
                <div className="text-[10px] text-[#8B95A5] leading-relaxed">{sig.summary}</div>
                <div className="flex items-center justify-between text-[9px] text-[#8B95A5] pt-1 border-t border-[#141A24]">
                  <span className="flex items-center gap-1">
                    <Globe className="w-2.5 h-2.5 text-[#60A5FA]" />
                    {sig.source}
                  </span>
                  <span className="text-[#00E5FF]">Klicken zum Laden in Chart & Strategie →</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
});

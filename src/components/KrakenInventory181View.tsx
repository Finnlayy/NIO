import React, { useState, useMemo } from 'react';
import {
  Layers,
  Terminal,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  ShieldCheck,
  Cpu,
  BookOpen,
  Zap,
  Play,
  Copy,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import {
  KRAKEN_TOP_LEVEL_COMMANDS,
  KRAKEN_181_LEAF_COMMANDS,
  KRAKEN_MCP_27_LOADED,
  KRAKEN_VERSION_DRIFT_MATRIX,
  KrakenLeafCommand,
  KrakenTopLevelCommand,
} from '../data/krakenInventory181';

interface KrakenInventory181ViewProps {
  onSelectCommandForTerminal?: (command: string, args: string) => void;
  onRefreshSummary?: () => void;
}

export const KrakenInventory181View: React.FC<KrakenInventory181ViewProps> = ({
  onSelectCommandForTerminal,
  onRefreshSummary,
}) => {
  const [selectedFamily, setSelectedFamily] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeSubTab, setActiveSubTab] = useState<'leaves' | 'layers' | 'drift' | 'paper-sot'>('leaves');
  const [expandedLeafId, setExpandedLeafId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Copy helper
  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  // Distinct families for filter
  const families = useMemo(() => {
    const set = new Set(KRAKEN_181_LEAF_COMMANDS.map((c) => c.family));
    return ['ALL', ...Array.from(set)];
  }, []);

  // Filtered Leaf Commands
  const filteredLeaves = useMemo(() => {
    return KRAKEN_181_LEAF_COMMANDS.filter((cmd) => {
      const matchesFamily = selectedFamily === 'ALL' || cmd.family === selectedFamily;
      const matchesStatus = selectedStatus === 'ALL' || cmd.sigmaStatus === selectedStatus;
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        cmd.id.toLowerCase().includes(q) ||
        cmd.topLevel.toLowerCase().includes(q) ||
        cmd.argvTemplate.toLowerCase().includes(q) ||
        cmd.description.toLowerCase().includes(q) ||
        cmd.sigmaRole.toLowerCase().includes(q);

      return matchesFamily && matchesStatus && matchesSearch;
    });
  }, [selectedFamily, selectedStatus, searchQuery]);

  // Status counts
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {
      ALL: KRAKEN_181_LEAF_COMMANDS.length,
      SOT_LEDGER: 0,
      CLI_CALL: 0,
      MAPPED_0_4_1: 0,
      FEED_CLI: 0,
      ORCHESTRATOR: 0,
      GAP: 0,
    };
    KRAKEN_181_LEAF_COMMANDS.forEach((c) => {
      if (counts[c.sigmaStatus] !== undefined) counts[c.sigmaStatus]++;
    });
    return counts;
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Architecture Banner: 3 Schichten - nicht vermischen */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                KRAKEN CLI 0.4.1 VOLL-INVENTAR
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                CLI-as-SoT Verifiziert
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-blue-500/10 text-blue-300 border border-blue-500/20">
                Binary: /home/finn-powers/.cargo/bin/kraken
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-100 font-mono tracking-tight">
              Drei Schichten — Nicht Vermischen
            </h2>
            <p className="text-xs text-slate-400 mt-1 max-w-3xl">
              Vollständige Erfassung der 181 Blatt-Befehle, 53 Top-Level Commands, 151 Catalog-Tools und 27 geladenen MCP-Tools (Peter-Schnitt).
              Eliminiert alle &quot;Homemade&quot;-DuckDB/50k-Seeds zugunsten autoritativer CLI-Aufrufe.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start lg:self-center shrink-0">
            {onRefreshSummary && (
              <button
                onClick={onRefreshSummary}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Sync CLI</span>
              </button>
            )}
          </div>
        </div>

        {/* 3 Schichten Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4 pt-4 border-t border-slate-800 font-mono">
          <div className="bg-slate-950/70 p-3.5 rounded-lg border border-slate-800/80 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] uppercase font-bold text-slate-400">SCHICHT 1: BINARY BAUM</span>
                <span className="text-xs font-bold text-amber-400">53 Top / 181 Leaves</span>
              </div>
              <p className="text-[11px] text-slate-300">
                Lokale Rust-Binary <code className="text-amber-300">kraken 0.4.1</code>. Rekursive Expansion von <code className="text-slate-400">kraken help</code>.
              </p>
            </div>
            <div className="mt-2 text-[10px] text-slate-500">
              53 Top-Level (inkl. help) · 181 Blatt-Befehle
            </div>
          </div>

          <div className="bg-slate-950/70 p-3.5 rounded-lg border border-slate-800/80 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] uppercase font-bold text-slate-400">SCHICHT 2: CURSOR PLUGIN</span>
                <span className="text-xs font-bold text-blue-400">151 Tools / 34 Dangerous</span>
              </div>
              <p className="text-[11px] text-slate-300">
                <code className="text-blue-300">agents/tool-catalog.json</code> (CLI v0.1.0). Beinhaltet Skills wie DCA Bot, Multi-Leg Orders.
              </p>
            </div>
            <div className="mt-2 text-[10px] text-slate-500">
              34 Live/Dangerous · 117 Safe/Paper
            </div>
          </div>

          <div className="bg-slate-950/70 p-3.5 rounded-lg border border-slate-800/80 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] uppercase font-bold text-slate-400">SCHICHT 3: MCP &quot;PETER-SCHNITT&quot;</span>
                <span className="text-xs font-bold text-emerald-400">27 Tools (Guarded)</span>
              </div>
              <p className="text-[11px] text-slate-300">
                MCP-Services: nur <code className="text-emerald-300">market</code> + <code className="text-emerald-300">paper</code>. Voller MCP-Raum via <code className="text-slate-400">kraken mcp -s all</code>.
              </p>
            </div>
            <div className="mt-2 text-[10px] text-slate-500">
              Rest: account, trade, funding, earn nicht in Default MCP
            </div>
          </div>
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-800 pb-2 text-xs font-mono overflow-x-auto">
        <button
          onClick={() => setActiveSubTab('leaves')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeSubTab === 'leaves'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>181 Blatt-Befehle (Register)</span>
          <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-[10px]">181</span>
        </button>

        <button
          onClick={() => setActiveSubTab('drift')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeSubTab === 'drift'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          <span>Version-Drift-Matrix (Bruch vs 0.4.1)</span>
          <span className="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-bold">
            {KRAKEN_VERSION_DRIFT_MATRIX.length}
          </span>
        </button>

        <button
          onClick={() => setActiveSubTab('paper-sot')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeSubTab === 'paper-sot'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
          <span>Spot Paper (SoT-Buch 10 Befehle)</span>
          <span className="px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px]">
            10 SoT
          </span>
        </button>

        <button
          onClick={() => setActiveSubTab('layers')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeSubTab === 'layers'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <Layers className="w-3.5 h-3.5 text-blue-400" />
          <span>53 Top-Level &amp; 27 MCP Details</span>
        </button>
      </div>

      {/* TAB 1: 181 Blatt-Befehle Register */}
      {activeSubTab === 'leaves' && (
        <div className="space-y-4">
          {/* Filter Toolbar */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 space-y-3 font-mono text-xs">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              {/* Search input */}
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Befehl, Argumente, Familie oder Sigma-Rolle suchen..."
                  className="w-full pl-9 pr-3 py-1.5 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
                />
              </div>

              {/* Status Pills */}
              <div className="flex items-center gap-1 flex-wrap">
                {(['ALL', 'SOT_LEDGER', 'CLI_CALL', 'MAPPED_0_4_1', 'GAP'] as const).map((st) => (
                  <button
                    key={st}
                    onClick={() => setSelectedStatus(st)}
                    className={`px-2 py-1 rounded text-[11px] transition ${
                      selectedStatus === st
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
                        : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    {st}: {statusCounts[st] ?? 0}
                  </button>
                ))}
              </div>
            </div>

            {/* Family Buttons */}
            <div className="flex items-center gap-1 overflow-x-auto pb-1 text-[11px]">
              <span className="text-slate-500 mr-1 flex items-center gap-1 shrink-0">
                <Filter className="w-3 h-3" /> Familie:
              </span>
              {families.map((fam) => (
                <button
                  key={fam}
                  onClick={() => setSelectedFamily(fam)}
                  className={`px-2 py-0.5 rounded shrink-0 transition ${
                    selectedFamily === fam
                      ? 'bg-slate-800 text-amber-300 border border-amber-500/30 font-bold'
                      : 'bg-slate-950/60 text-slate-400 hover:text-slate-200 border border-slate-800/60'
                  }`}
                >
                  {fam}
                </button>
              ))}
            </div>
          </div>

          {/* Results Summary */}
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-1">
            <span>
              Zeige <strong className="text-amber-400">{filteredLeaves.length}</strong> von 181 Blatt-Befehlen
            </span>
            <span className="text-[11px] text-slate-500">
              Klick auf Befehl für Argument-Details und Terminal-Routing
            </span>
          </div>

          {/* Leaves Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden font-mono text-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-slate-950/80 text-slate-400 text-[11px] uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Befehl (CLI 0.4.1)</th>
                    <th className="py-2.5 px-3">Familie</th>
                    <th className="py-2.5 px-3">Schicht</th>
                    <th className="py-2.5 px-3">Sigma-Status</th>
                    <th className="py-2.5 px-3">Sigma-Rolle</th>
                    <th className="py-2.5 px-3 text-right">Aktionen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {filteredLeaves.map((cmd) => {
                    const isExpanded = expandedLeafId === cmd.id;
                    const isCopied = copiedId === cmd.id;

                    return (
                      <React.Fragment key={cmd.id}>
                        <tr
                          onClick={() => setExpandedLeafId(isExpanded ? null : cmd.id)}
                          className="hover:bg-slate-800/40 cursor-pointer transition"
                        >
                          <td className="py-2 px-3">
                            <div className="flex items-center gap-2">
                              {isExpanded ? (
                                <ChevronDown className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                              ) : (
                                <ChevronRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                              )}
                              <code className="font-bold text-amber-300 text-xs">
                                {cmd.argvTemplate}
                              </code>
                              {cmd.dangerous && (
                                <span className="px-1 py-0.2 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[9px] font-bold">
                                  DANGEROUS
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-2 px-3 text-slate-400 text-[11px]">
                            {cmd.family}
                          </td>
                          <td className="py-2 px-3 text-slate-400 text-[11px]">
                            <span className="px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800">
                              {cmd.layer}
                            </span>
                          </td>
                          <td className="py-2 px-3">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                cmd.sigmaStatus === 'SOT_LEDGER'
                                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                  : cmd.sigmaStatus === 'MAPPED_0_4_1'
                                  ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                                  : cmd.sigmaStatus === 'CLI_CALL'
                                  ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                                  : 'bg-slate-800 text-slate-400'
                              }`}
                            >
                              {cmd.sigmaStatus}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-slate-400 text-[11px] truncate max-w-[240px]">
                            {cmd.sigmaRole}
                          </td>
                          <td className="py-2 px-3 text-right">
                            <div
                              className="flex items-center justify-end gap-1.5"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <button
                                onClick={() => handleCopy(cmd.argvTemplate, cmd.id)}
                                title="Befehl kopieren"
                                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                              >
                                {isCopied ? (
                                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                                ) : (
                                  <Copy className="w-3.5 h-3.5" />
                                )}
                              </button>

                              {onSelectCommandForTerminal && (
                                <button
                                  onClick={() => {
                                    const parts = cmd.argvTemplate.replace(/^kraken\s+/, '').split(' ');
                                    const top = parts[0];
                                    const rest = parts.slice(1).join(' ');
                                    onSelectCommandForTerminal(top, rest);
                                  }}
                                  title="In Terminal übertragen"
                                  className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-slate-300 text-[11px] transition"
                                >
                                  <Play className="w-3 h-3" />
                                  <span>Test</span>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>

                        {/* Expanded Details Row */}
                        {isExpanded && (
                          <tr className="bg-slate-950/60">
                            <td colSpan={6} className="p-4 border-t border-b border-slate-800">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                  <div className="text-[10px] text-slate-500 uppercase font-bold">
                                    Beschreibung &amp; Verwendung
                                  </div>
                                  <p className="text-xs text-slate-300">
                                    {cmd.description}
                                  </p>

                                  <div className="bg-slate-950 p-2.5 rounded border border-slate-800 text-xs">
                                    <span className="text-slate-500">$ </span>
                                    <span className="text-amber-300 font-bold">{cmd.argvTemplate}</span>
                                  </div>
                                </div>

                                <div className="space-y-2">
                                  <div className="text-[10px] text-slate-500 uppercase font-bold">
                                    Sigma-Architektur-Details
                                  </div>
                                  <div className="text-xs text-slate-300 bg-slate-900 p-2.5 rounded border border-slate-800">
                                    <div><strong className="text-slate-400">Rolle:</strong> {cmd.sigmaRole}</div>
                                    <div className="mt-1"><strong className="text-slate-400">SoT-Status:</strong> {cmd.sigmaStatus}</div>
                                    <div className="mt-1"><strong className="text-slate-400">Schicht:</strong> {cmd.layer}</div>
                                    <div className="mt-1"><strong className="text-slate-400">Top-Level-Gruppe:</strong> kraken {cmd.topLevel}</div>
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Version Drift Matrix */}
      {activeSubTab === 'drift' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 font-mono text-xs">
            <h3 className="text-sm font-bold text-slate-200 mb-1 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              Version-Drift-Matrix (Historischer Bruch vs. 0.4.1 CLI)
            </h3>
            <p className="text-slate-400 text-xs mb-3">
              Die Kraken CLI wurde zwischen Version 0.1.0 (Cursor Plugin Catalog) und 0.4.1 grundlegend umstrukturiert.
              Frühere Commands wie <code className="text-rose-400">kraken trade add-order</code> existieren in 0.4.1 nicht mehr und wurden durch <code className="text-emerald-400">kraken order buy|sell</code> ersetzt.
              Ebenso wurde der simulierte 50k-Seed-Ledger durch <code className="text-emerald-400">kraken paper status</code> ersetzt.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-slate-950/80 text-slate-400 text-[11px] uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Funktion / Bereich</th>
                    <th className="py-2.5 px-3">Bisherige Sigma-Stelle (Alt)</th>
                    <th className="py-2.5 px-3">CLI 0.4.1 Syntax (Neu / SoT)</th>
                    <th className="py-2.5 px-3">Bruch / Konsequenz</th>
                    <th className="py-2.5 px-3">Fix-Nachweis &amp; Auswirkung in Sigma</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {KRAKEN_VERSION_DRIFT_MATRIX.map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/30 transition">
                      <td className="py-2.5 px-3 font-bold text-amber-300">
                        {row.feature}
                      </td>
                      <td className="py-2.5 px-3 text-rose-300">
                        <code className="bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20">
                          {row.sigmaHistoricallyCalled}
                        </code>
                      </td>
                      <td className="py-2.5 px-3 text-emerald-300">
                        <code className="bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 font-bold">
                          {row.krakenCli041Syntax}
                        </code>
                      </td>
                      <td className="py-2.5 px-3 text-amber-400 text-xs">
                        {row.consequenceOfDrift}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 text-xs">
                        <div className="flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          <span>{row.resolvedInSigma}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: Spot Paper (SoT-Buch 10 Befehle) */}
      {activeSubTab === 'paper-sot' && (
        <div className="space-y-4 font-mono text-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <h3 className="text-sm font-bold text-slate-200 mb-1 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-emerald-400" />
              Spot Paper: Das autoritative SoT-Buch (10 Befehle)
            </h3>
            <p className="text-slate-400 text-xs mb-4">
              Gemäß User-Direktive fungiert ausschließlich <code className="text-emerald-400">kraken paper status</code> als Source-of-Truth für simuliertes Kapital.
              Kein Bot darf im Nirgendwo traden — jede Order erzeugt einen autoritativen Paper-CLI-Aufruf.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {KRAKEN_181_LEAF_COMMANDS.filter((c) => c.family === 'Spot Paper (SoT)').map((cmd) => (
                <div
                  key={cmd.id}
                  className="bg-slate-950 p-3.5 rounded-lg border border-slate-800 hover:border-amber-500/30 transition flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <code className="font-bold text-amber-300 text-xs">
                        {cmd.argvTemplate}
                      </code>
                      <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold">
                        SoT LEDGER
                      </span>
                    </div>
                    <p className="text-slate-400 text-[11px] mb-2">
                      {cmd.description}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                    <span className="text-[10px] text-slate-500 truncate max-w-[200px]">
                      {cmd.sigmaRole}
                    </span>
                    {onSelectCommandForTerminal && (
                      <button
                        onClick={() => {
                          const parts = cmd.argvTemplate.replace(/^kraken\s+/, '').split(' ');
                          const top = parts[0];
                          const rest = parts.slice(1).join(' ');
                          onSelectCommandForTerminal(top, rest);
                        }}
                        className="px-2 py-0.5 rounded bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-slate-200 text-[11px] transition flex items-center gap-1"
                      >
                        <Play className="w-2.5 h-2.5" />
                        <span>Ausführen</span>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: 53 Top-Level & 27 MCP Details */}
      {activeSubTab === 'layers' && (
        <div className="space-y-4 font-mono text-xs">
          {/* Top-Level Commands */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <h3 className="text-sm font-bold text-slate-200 mb-2 flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-400" />
              53 Top-Level Commands (kraken help Baum)
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
              {KRAKEN_TOP_LEVEL_COMMANDS.map((cmd) => (
                <div
                  key={cmd.name}
                  className="bg-slate-950 p-2 rounded border border-slate-800/80 hover:border-slate-700 transition"
                >
                  <div className="flex items-center justify-between">
                    <code className="text-amber-300 font-bold text-[11px]">{cmd.name}</code>
                    <span className="text-[9px] px-1 py-0.2 rounded bg-slate-800 text-slate-400">
                      {cmd.leafCount} leaves
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1 truncate">
                    {cmd.description}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* 27 Loaded MCP Tools */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <h3 className="text-sm font-bold text-slate-200 mb-2 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-emerald-400" />
              27 Geladene MCP-Tools (&quot;Peter-Schnitt&quot;, market + paper guarded)
            </h3>
            <p className="text-slate-400 text-xs mb-3">
              Im Cursor-Plugin sind standardmäßig nur die Services <code className="text-emerald-400">market</code> und <code className="text-emerald-400">paper</code> geladen.
              Nicht geladen: account, trade, funding, earn, subaccount, futures, workspace, auth, feedback.
              Volle MCP-Fläche = <code className="text-amber-400">kraken mcp -s all (--allow-dangerous)</code>.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
              {KRAKEN_MCP_27_LOADED.map((toolName) => (
                <div
                  key={toolName}
                  className="bg-slate-950 px-2.5 py-1.5 rounded border border-slate-800 flex items-center justify-between"
                >
                  <code className="text-emerald-300 text-xs">{toolName}</code>
                  <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                    MCP LOADED
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

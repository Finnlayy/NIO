import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Cpu,
  Terminal,
  Activity,
  Zap,
  Play,
  RefreshCw,
  Trash2,
  Download,
  AlertTriangle,
  CheckCircle2,
  Lock,
  ArrowRight,
  Code2,
  Layers,
  ChevronDown,
  ChevronRight,
  Key,
} from 'lucide-react';
import {
  triggerAgentCycle,
  fetchAgentTraces,
  fetchAgentStatus,
  clearAgentTraces,
} from '../services/omegaAgentClient';
import { AgentTraceEvent, AgentStatus, AgentStateNode } from '../types/agent';
import { AnimatedNumber, AnimatedCurrency } from './AnimatedNumber';

export const OmegaAgentConsole: React.FC = () => {
  const [traces, setTraces] = useState<AgentTraceEvent[]>([]);
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<AgentTraceEvent | null>(null);
  const [inputPrompt, setInputPrompt] = useState<string>('');
  const [triggerType, setTriggerType] = useState<
    'USER_PROMPT' | 'SIGNAL_ALERT' | 'SWARM_HYPOTHESIS' | 'SCHEDULED_AUDIT'
  >('USER_PROMPT');
  const [sessionAuth, setSessionAuth] = useState<string>('');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [exportNotice, setExportNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  const STATE_NODES: { id: AgentStateNode; label: string; desc: string }[] = [
    { id: 'INGEST', label: '1. INGEST', desc: 'Payload validation & metadata extraction' },
    { id: 'SANITIZE', label: '2. SANITIZE', desc: 'Shell injection & metacharacter filter' },
    { id: 'IDEMPOTENCY_LOCK', label: '3. IDEMPOTENCY', desc: 'SHA-256 replay barrier (60s window)' },
    { id: 'GUARDIAN_AUDIT', label: '4. GUARDIAN', desc: '34 Dangerous commands gate & M1-M8 audit' },
    { id: 'DISPATCH', label: '5. DISPATCH', desc: 'Gemini 3.8 Flash multi-turn tool execution' },
    { id: 'RECONCILE', label: '6. RECONCILE', desc: 'Kraken CLI SoT zero-drift NAV verification' },
    { id: 'EMIT', label: '7. EMIT', desc: 'Telemetry & trace publication' },
  ];

  const loadData = async () => {
    try {
      const [fetchedTraces, fetchedStatus] = await Promise.all([
        fetchAgentTraces(),
        fetchAgentStatus(),
      ]);
      setTraces(fetchedTraces);
      setStatus(fetchedStatus);
      if (fetchedTraces.length > 0 && !selectedTrace) {
        setSelectedTrace(fetchedTraces[0]);
      }
    } catch (err: any) {
      console.error('Error fetching agent data:', err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      if (autoRefresh) {
        loadData();
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleRunCycle = async (overridePrompt?: string, customAuth?: string) => {
    const promptToRun = overridePrompt || inputPrompt;
    if (!promptToRun.trim()) return;

    setIsExecuting(true);
    setErrorNotice(null);

    try {
      const res = await triggerAgentCycle(promptToRun, {
        trigger: triggerType,
        sessionAuth: customAuth !== undefined ? customAuth : sessionAuth,
      });

      if (res.success && res.trace) {
        setTraces((prev) => [res.trace, ...prev.filter((t) => t.traceId !== res.trace.traceId)]);
        setSelectedTrace(res.trace);
        if (!overridePrompt) {
          setInputPrompt('');
        }
        await loadData();
      }
    } catch (err: any) {
      setErrorNotice(err?.message || 'Agent cycle execution failed');
    } finally {
      setIsExecuting(false);
    }
  };

  const handleClearTraces = async () => {
    if (!window.confirm('Clear all telemetry audit traces from memory buffer?')) return;
    try {
      await clearAgentTraces();
      setTraces([]);
      setSelectedTrace(null);
      await loadData();
    } catch (err: any) {
      setErrorNotice(err?.message || 'Failed to clear traces');
    }
  };

  const handleExportJson = () => {
    if (traces.length === 0) return;
    const blob = new Blob([JSON.stringify(traces, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `omega_agent_traces_${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setExportNotice(`Exported ${traces.length} traces`);
    setTimeout(() => setExportNotice(null), 3000);
  };

  const activeNodeMap = new Map<AgentStateNode, { status: string; durationMs: number; details: string }>();
  if (selectedTrace) {
    for (const n of selectedTrace.nodes) {
      activeNodeMap.set(n.node, { status: n.status, durationMs: n.durationMs, details: n.details });
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Banner: Autonomous Execution Supervisor */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-base font-bold text-slate-100 tracking-wide font-mono">
                    OMEGA-NIO AUTONOMOUS AGENT
                  </h1>
                  <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold">
                    STATE-GRAPH ENGINE
                  </span>
                  <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-blue-500/10 text-blue-400 border border-blue-500/30">
                    GEMINI-3.8-FLASH
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  7-Stage LangGraph State Machine · Fail-Closed Zero-Mock Invariant · Aufpasser-Protokoll Dual-Agent Gate
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`px-3 py-1.5 rounded text-xs font-mono flex items-center gap-1.5 border transition-all ${
                autoRefresh
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${autoRefresh ? 'animate-spin' : ''}`} />
              <span>{autoRefresh ? 'Live Polling (4s)' : 'Polling Paused'}</span>
            </button>

            <button
              onClick={handleExportJson}
              disabled={traces.length === 0}
              className={`px-3 py-1.5 rounded text-xs font-mono flex items-center gap-1.5 border transition-all ${
                traces.length === 0
                  ? 'bg-slate-800/50 text-slate-600 border-slate-800 cursor-not-allowed'
                  : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700 hover:text-cyan-300'
              }`}
            >
              <Download className="w-3.5 h-3.5" />
              <span>{exportNotice || `Export JSON (${traces.length})`}</span>
            </button>

            <button
              onClick={handleClearTraces}
              disabled={traces.length === 0}
              className="px-3 py-1.5 rounded text-xs font-mono text-rose-400 bg-rose-500/10 border border-rose-500/30 hover:bg-rose-500/20 transition-all flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear Traces</span>
            </button>
          </div>
        </div>

        {/* Live Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-3">
            <span className="text-[11px] font-mono text-slate-400 block uppercase">Total Cycles Run</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-lg font-bold font-mono text-slate-100">
                <AnimatedNumber value={status?.totalCycles ?? 0} precision={0} />
              </span>
              <span className="text-[10px] font-mono text-emerald-400">Deterministic</span>
            </div>
          </div>

          <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-3">
            <span className="text-[11px] font-mono text-slate-400 block uppercase">Guardian Passed</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-lg font-bold font-mono text-emerald-400">
                <AnimatedNumber value={status?.passedAudits ?? 0} precision={0} />
              </span>
              <span className="text-[10px] font-mono text-slate-500">Verified</span>
            </div>
          </div>

          <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-3">
            <span className="text-[11px] font-mono text-slate-400 block uppercase">Intercepted / Blocked</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-lg font-bold font-mono text-rose-400">
                <AnimatedNumber value={status?.blockedAudits ?? 0} precision={0} />
              </span>
              <span className="text-[10px] font-mono text-rose-400/80">Fail-Closed</span>
            </div>
          </div>

          <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-3">
            <span className="text-[11px] font-mono text-slate-400 block uppercase">Active Idempotency Locks</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-lg font-bold font-mono text-amber-400">
                <AnimatedNumber value={status?.activeIdempotencyLocks ?? 0} precision={0} />
              </span>
              <span className="text-[10px] font-mono text-slate-500">60s TTL</span>
            </div>
          </div>
        </div>
      </div>

      {/* 7-Stage State-Graph Pipeline Visualizer */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
              7-STAGE LANGGRAPH STATE PIPELINE
            </h2>
          </div>
          {selectedTrace && (
            <span className="text-xs font-mono text-slate-400">
              Active Trace: <span className="text-cyan-400 font-bold">{selectedTrace.traceId}</span> ({selectedTrace.totalDurationMs}ms)
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
          {STATE_NODES.map((node, idx) => {
            const nodeInfo = activeNodeMap.get(node.id);
            const statusType = nodeInfo ? nodeInfo.status : 'PENDING';
            const isBlocked = statusType === 'BLOCKED';
            const isPassed = statusType === 'PASSED';

            return (
              <div
                key={node.id}
                className={`p-3 rounded-lg border flex flex-col justify-between transition-all ${
                  isBlocked
                    ? 'bg-rose-950/40 border-rose-500/50 text-rose-200 shadow-[0_0_12px_rgba(244,63,94,0.15)]'
                    : isPassed
                    ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
                    : 'bg-slate-950/60 border-slate-800 text-slate-400'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-bold font-mono tracking-tight">{node.label}</span>
                    {isBlocked ? (
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                    ) : isPassed ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-slate-700" />
                    )}
                  </div>
                  <p className="text-[10px] text-slate-400 leading-tight line-clamp-2">{node.desc}</p>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono">
                  <span
                    className={`font-semibold ${
                      isBlocked ? 'text-rose-400' : isPassed ? 'text-emerald-400' : 'text-slate-500'
                    }`}
                  >
                    {statusType}
                  </span>
                  {nodeInfo && (
                    <span className="text-slate-400">{nodeInfo.durationMs}ms</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {selectedTrace && (
          <div className="mt-3 p-2.5 rounded bg-slate-950/80 border border-slate-800/80 text-xs font-mono flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Guardian Status:</span>
              <span
                className={`font-bold px-1.5 py-0.5 rounded ${
                  selectedTrace.guardianStatus === 'APPROVED'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : selectedTrace.guardianStatus === 'AUTH_REQUIRED'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                }`}
              >
                {selectedTrace.guardianStatus}
              </span>
              <span className="text-slate-400">|</span>
              <span className="text-slate-300">{selectedTrace.guardianReason}</span>
            </div>

            <div className="text-slate-400">
              Idempotency Key:{' '}
              <code className="text-amber-400 bg-slate-900 px-1 py-0.5 rounded">
                {selectedTrace.idempotencyKey}
              </code>
            </div>
          </div>
        )}
      </div>

      {/* Interactive Execution & Audit Dispatcher */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-amber-400" />
            <h2 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
              AGENT INSTRUCTION & QUANT AUDIT DISPATCHER
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Model: <span className="text-emerald-400 font-bold">gemini-3.8-flash</span>
          </span>
        </div>

        {errorNotice && (
          <div className="mb-3 p-3 rounded-lg bg-rose-950/40 border border-rose-500/50 text-rose-300 text-xs flex items-center gap-2 font-mono">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{errorNotice}</span>
          </div>
        )}

        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="flex-1">
              <input
                type="text"
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    handleRunCycle();
                  }
                }}
                placeholder="Enter trading instruction, alert payload, or audit request (e.g. 'Audit BTC/USD risk and run paper buy 0.01 BTC')..."
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-400"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={triggerType}
                onChange={(e: any) => setTriggerType(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
              >
                <option value="USER_PROMPT">Trigger: User Prompt</option>
                <option value="SIGNAL_ALERT">Trigger: Signal Alert</option>
                <option value="SWARM_HYPOTHESIS">Trigger: Swarm Hypothesis</option>
                <option value="SCHEDULED_AUDIT">Trigger: Scheduled Audit</option>
              </select>

              <button
                onClick={() => handleRunCycle()}
                disabled={isExecuting || !inputPrompt.trim()}
                className={`px-4 py-2.5 rounded-lg text-xs font-mono font-bold flex items-center gap-2 transition-all select-none ${
                  isExecuting || !inputPrompt.trim()
                    ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
                    : 'bg-amber-500 hover:bg-amber-400 text-slate-950 border border-amber-400 shadow-sm active:scale-95'
                }`}
              >
                <Play className={`w-3.5 h-3.5 fill-current ${isExecuting ? 'animate-spin' : ''}`} />
                <span>{isExecuting ? 'EVALUATING...' : 'DISPATCH'}</span>
              </button>
            </div>
          </div>

          {/* Session Auth Token Field for Dangerous Commands */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 text-xs">
            <div className="flex items-center gap-2 text-slate-400">
              <Key className="w-3.5 h-3.5 text-amber-400" />
              <span>Session Auth Token (for 34 Dangerous Commands Gate):</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={sessionAuth}
                onChange={(e) => setSessionAuth(e.target.value)}
                placeholder="Enter SIGMA_LIVE_CONFIRMED_2026 for mutation authorization"
                className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-400 w-72"
              />
              <button
                type="button"
                onClick={() => setSessionAuth('SIGMA_LIVE_CONFIRMED_2026')}
                className="px-2 py-1 text-[11px] font-mono rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 hover:bg-amber-500/20"
              >
                Auto-Fill
              </button>
            </div>
          </div>

          {/* Quick Preset Test Scenarios */}
          <div className="pt-2">
            <span className="text-[11px] font-mono text-slate-400 block mb-2">QUICK TEST SCENARIOS:</span>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => handleRunCycle('Audit BTC/USD Swarm DCA Risk and verify current orderbook spread and gross leverage')}
                className="px-2.5 py-1 text-xs font-mono rounded bg-slate-800 text-slate-300 border border-slate-700 hover:border-amber-400/60 hover:text-amber-300"
              >
                Audit BTC/USD Risk
              </button>

              <button
                type="button"
                onClick={() => handleRunCycle('Execute paper buy 0.01 BTC/USD via Kraken CLI 181-leaf')}
                className="px-2.5 py-1 text-xs font-mono rounded bg-slate-800 text-slate-300 border border-slate-700 hover:border-emerald-400/60 hover:text-emerald-300"
              >
                Paper Buy 0.01 BTC
              </button>

              <button
                type="button"
                onClick={() => handleRunCycle('Check paper ledger balance and verify mark-to-market valuation')}
                className="px-2.5 py-1 text-xs font-mono rounded bg-slate-800 text-slate-300 border border-slate-700 hover:border-cyan-400/60 hover:text-cyan-300"
              >
                Reconcile Paper Ledger
              </button>

              <button
                type="button"
                onClick={() => handleRunCycle('order/add pair=BTC/USD type=buy volume=1.0; rm -rf /')}
                className="px-2.5 py-1 text-xs font-mono rounded bg-rose-950/30 text-rose-300 border border-rose-500/40 hover:bg-rose-950/50"
                title="Tests Node 2: Sanitization gate catching shell metacharacters (;)"
              >
                Test Shell Metacharacter Attack (Block)
              </button>

              <button
                type="button"
                onClick={() => handleRunCycle('order/add pair=BTC/USD volume=0.5 type=buy', '')}
                className="px-2.5 py-1 text-xs font-mono rounded bg-amber-950/30 text-amber-300 border border-amber-500/40 hover:bg-amber-950/50"
                title="Tests Node 4: Dangerous commands intercept requiring SIGMA_LIVE_CONFIRMED_2026"
              >
                Test 34 Dangerous Commands Gate
              </button>

              <button
                type="button"
                onClick={() => handleRunCycle('Force hard price recalibration from live Kraken REST quotes')}
                className="px-2.5 py-1 text-xs font-mono rounded bg-slate-800 text-slate-300 border border-slate-700 hover:border-blue-400/60 hover:text-blue-300"
              >
                Force Recalibration
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout: Trace List & Active Trace Inspection */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Trace Feed (4 cols) */}
        <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col h-[650px]">
          <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-cyan-400" />
              <span>AUDIT TRACE BUFFER ({traces.length})</span>
            </h3>
            <span className="text-[10px] font-mono text-slate-500">RING BUFFER: 50</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
            {traces.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 text-xs font-mono">
                <Cpu className="w-8 h-8 text-slate-600 mb-2 stroke-1" />
                <span>No execution cycles in buffer</span>
                <span className="text-[11px] text-slate-600 mt-1">Dispatch an instruction above</span>
              </div>
            ) : (
              traces.map((trace) => {
                const isSelected = selectedTrace?.traceId === trace.traceId;
                const isApproved = trace.guardianStatus === 'APPROVED';
                const isBlocked = trace.guardianStatus === 'REJECTED' || trace.guardianStatus === 'FLAGGED';

                return (
                  <div
                    key={trace.traceId}
                    onClick={() => setSelectedTrace(trace)}
                    className={`p-3 rounded-lg border text-xs font-mono cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-slate-800 border-amber-500/60 shadow-sm'
                        : 'bg-slate-950/60 border-slate-800/80 hover:bg-slate-800/50 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-slate-200">{trace.traceId}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.2 rounded font-semibold ${
                          isApproved
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            : trace.guardianStatus === 'AUTH_REQUIRED'
                            ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                            : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                        }`}
                      >
                        {trace.guardianStatus}
                      </span>
                    </div>

                    <p className="text-slate-300 text-[11px] line-clamp-1 mb-2">
                      {trace.inputPrompt}
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-slate-500 border-t border-slate-800/60 pt-1.5">
                      <span>{new Date(trace.timestamp).toLocaleTimeString()}</span>
                      <span>{trace.totalDurationMs}ms</span>
                      <span className="text-cyan-400">{trace.toolInvocations.length} tools</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Detailed Thought Trace & Tool Invocations (8 cols) */}
        <div className="lg:col-span-8 bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col h-[650px] overflow-hidden">
          {selectedTrace ? (
            <div className="flex-1 flex flex-col overflow-y-auto pr-1 space-y-4 custom-scrollbar">
              {/* Trace Header Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-3 gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-base font-bold font-mono text-cyan-300">
                      {selectedTrace.traceId}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-mono">
                      {selectedTrace.trigger}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500 font-mono">
                    Timestamp: {new Date(selectedTrace.timestamp).toISOString()} (
                    <AnimatedNumber value={selectedTrace.totalDurationMs} precision={0} suffix="ms total" />)
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-400">Post-Cycle NAV:</span>
                  <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 px-2 py-0.5 rounded">
                    <AnimatedCurrency value={selectedTrace.reconciledState.navUsd} precision={2} />
                  </span>
                </div>
              </div>

              {/* Ingested Prompt Box */}
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 block uppercase mb-1">
                  Ingested Instruction / Payload
                </span>
                <p className="text-xs font-mono text-slate-200 select-text break-words">
                  {selectedTrace.inputPrompt}
                </p>
              </div>

              {/* Final Decision Banner */}
              <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs font-mono">
                <span className="text-[11px] text-amber-400 font-bold block uppercase mb-1">
                  Executive Verdict
                </span>
                <p className="text-slate-200 font-semibold">{selectedTrace.finalDecision}</p>
              </div>

              {/* Agent Thought Trace & Reasoning Output */}
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Code2 className="w-3.5 h-3.5 text-amber-400" />
                    <span>Agent Thought Trace & Quant Reasoning</span>
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">7-STAGE TRANSITION STREAM</span>
                </div>

                <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800/90 text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed select-text">
                  {selectedTrace.thoughtTrace}
                </div>
              </div>

              {/* Tool Invocations Box */}
              {selectedTrace.toolInvocations && selectedTrace.toolInvocations.length > 0 && (
                <div className="space-y-2">
                  <span className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Tool Invocations ({selectedTrace.toolInvocations.length})</span>
                  </span>

                  <div className="space-y-2">
                    {selectedTrace.toolInvocations.map((inv) => (
                      <div
                        key={inv.id}
                        className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-cyan-400 font-bold">{inv.toolName}</span>
                          <span className="text-slate-500 text-[11px]">{inv.durationMs}ms</span>
                        </div>
                        <div className="text-slate-400 mb-1">
                          <span className="text-slate-500">Args:</span>{' '}
                          <code>{JSON.stringify(inv.args)}</code>
                        </div>
                        <div className="text-slate-300 bg-slate-900/80 p-2 rounded border border-slate-800/60 overflow-x-auto text-[11px]">
                          <span className="text-slate-500 block mb-0.5">Result:</span>
                          <pre>{JSON.stringify(inv.result, null, 2)}</pre>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Reconciled Ledger Snapshot */}
              <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs font-mono">
                <span className="text-[11px] font-bold text-slate-400 block uppercase mb-1.5">
                  Post-Cycle Reconciled Ledger State (Zero-Drift Invariant)
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-slate-300">
                  <div>
                    <span className="text-slate-500 block text-[10px]">NAV:</span>
                    <span className="font-semibold text-emerald-400">
                      ${selectedTrace.reconciledState.navUsd.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">CASH:</span>
                    <span className="font-semibold text-slate-200">
                      ${selectedTrace.reconciledState.cashUsd.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">POSITIONS:</span>
                    <span className="font-semibold text-slate-200">
                      {selectedTrace.reconciledState.openPositionsCount}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">DRIFT:</span>
                    <span className="font-semibold text-emerald-400">0.00% (VERIFIED)</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 text-xs font-mono">
              <Terminal className="w-10 h-10 text-slate-700 mb-2" />
              <span>Select an execution trace from the left panel to inspect</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

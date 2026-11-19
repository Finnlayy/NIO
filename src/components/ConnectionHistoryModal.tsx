import React, { useState, useMemo } from 'react';
import {
  X,
  Radio,
  RefreshCw,
  Trash2,
  Copy,
  Check,
  Search,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowDownRight,
  ShieldCheck,
  Terminal,
  Zap,
  Info,
} from 'lucide-react';
import { ConnectionEvent, ConnectionEventType, ConnectionSeverity } from '../types/trading';

interface ConnectionHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  events: ConnectionEvent[];
  onClearHistory: () => void;
  onReconnect: () => void;
  targetPort: number;
  currentStatus: 'LIVE' | 'CONNECTING' | 'FALLBACK_REST' | 'OFFLINE';
  streamSource: string;
  reconnectAttempt: number;
  nextRetryDelayMs: number | null;
  nextRetryAt: number | null;
}

export const ConnectionHistoryModal: React.FC<ConnectionHistoryModalProps> = ({
  isOpen,
  onClose,
  events,
  onClearHistory,
  onReconnect,
  targetPort,
  currentStatus,
  streamSource,
  reconnectAttempt,
  nextRetryDelayMs,
  nextRetryAt,
}) => {
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);
  const [showDiagnosticsInfo, setShowDiagnosticsInfo] = useState<boolean>(false);

  if (!isOpen) return null;

  // Filter and search logic
  const filteredEvents = useMemo(() => {
    return events.filter((evt) => {
      // Type filter
      if (filterType === 'DISCONNECTS' && evt.type !== 'DISCONNECTED' && evt.type !== 'ERROR') {
        return false;
      }
      if (
        filterType === 'RECONNECTS' &&
        evt.type !== 'RECONNECT_SCHEDULED' &&
        evt.type !== 'MANUAL_RECONNECT' &&
        evt.type !== 'HANDSHAKE_INIT'
      ) {
        return false;
      }
      if (filterType === 'CONNECTED' && evt.type !== 'CONNECTED') {
        return false;
      }
      if (filterType === 'FALLBACK' && evt.type !== 'FALLBACK_SSE') {
        return false;
      }

      // Search query
      if (searchQuery.trim().length > 0) {
        const q = searchQuery.toLowerCase();
        const reasonMatch = evt.reason?.toLowerCase().includes(q);
        const detailsMatch = evt.details?.toLowerCase().includes(q);
        const codeMatch = evt.code?.toString().includes(q);
        const typeMatch = evt.type?.toLowerCase().includes(q);
        return reasonMatch || detailsMatch || codeMatch || typeMatch;
      }

      return true;
    });
  }, [events, filterType, searchQuery]);

  // Aggregate stats
  const stats = useMemo(() => {
    let disconnects = 0;
    let reconnects = 0;
    let connects = 0;
    let errors = 0;

    events.forEach((e) => {
      if (e.type === 'DISCONNECTED') disconnects++;
      if (e.type === 'RECONNECT_SCHEDULED' || e.type === 'MANUAL_RECONNECT') reconnects++;
      if (e.type === 'CONNECTED') connects++;
      if (e.type === 'ERROR') errors++;
    });

    return { disconnects, reconnects, connects, errors, total: events.length };
  }, [events]);

  // Copy full diagnostics JSON
  const handleCopyDiagnostics = () => {
    const payload = {
      exportedAt: new Date().toISOString(),
      targetPort,
      currentStatus,
      streamSource,
      reconnectAttempt,
      nextRetryDelayMs,
      nextRetryAt,
      stats,
      events,
    };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Helper for status color coding
  const getSeverityStyle = (severity: ConnectionSeverity, type: ConnectionEventType) => {
    switch (severity) {
      case 'SUCCESS':
        return {
          badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
          dot: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]',
          border: 'border-l-emerald-500',
          icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
        };
      case 'ERROR':
        return {
          badge: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
          dot: 'bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.8)]',
          border: 'border-l-rose-500',
          icon: <AlertTriangle className="w-4 h-4 text-rose-400" />,
        };
      case 'WARNING':
        return {
          badge: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
          dot: 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]',
          border: 'border-l-amber-500',
          icon: <Clock className="w-4 h-4 text-amber-400" />,
        };
      case 'INFO':
      default:
        if (type === 'FALLBACK_SSE') {
          return {
            badge: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
            dot: 'bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.8)]',
            border: 'border-l-sky-500',
            icon: <Radio className="w-4 h-4 text-sky-400" />,
          };
        }
        return {
          badge: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
          dot: 'bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.8)]',
          border: 'border-l-indigo-500',
          icon: <Activity className="w-4 h-4 text-indigo-400" />,
        };
    }
  };

  const formatTimestamp = (ts: number): string => {
    const d = new Date(ts);
    const hours = String(d.getHours()).padStart(2, '0');
    const mins = String(d.getMinutes()).padStart(2, '0');
    const secs = String(d.getSeconds()).padStart(2, '0');
    const ms = String(d.getMilliseconds()).padStart(3, '0');
    return `${hours}:${mins}:${secs}.${ms}`;
  };

  return (
    <div
      id="connection-history-modal-overlay"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        id="connection-history-modal-card"
        className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden text-slate-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-bold font-mono tracking-tight text-white">
                  WebSocket Connection History & Telemetry
                </h2>
                <span className="text-xs px-2 py-0.5 rounded font-mono font-bold bg-slate-800 border border-slate-700 text-amber-300">
                  PORT {targetPort}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Live audit trail of WebSocket disconnects, abnormal closures, backoff retries, and SSE failovers.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyDiagnostics}
              className="px-2.5 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-mono flex items-center gap-1.5 transition-colors"
              title="Kopiert vollständigen Diagnostik-Bericht als JSON"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Kopiert' : 'JSON Export'}</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title="Schließen"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Telemetry Status Bar with Status Color Coding */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 p-3 sm:p-4 bg-slate-950/40 border-b border-slate-800 text-xs font-mono">
          {/* Current Status */}
          <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex flex-col justify-between">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Status</span>
            <div className="flex items-center gap-1.5 mt-1">
              <span
                className={`w-2 h-2 rounded-full ${
                  currentStatus === 'LIVE'
                    ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse'
                    : 'bg-amber-400 animate-ping'
                }`}
              />
              <span
                className={`font-bold ${
                  currentStatus === 'LIVE' ? 'text-emerald-300' : 'text-amber-300'
                }`}
              >
                {currentStatus === 'LIVE' ? 'LIVE' : 'RECONNECTING'}
              </span>
            </div>
          </div>

          {/* Target Port */}
          <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex flex-col justify-between">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Target Port</span>
            <div className="flex items-center gap-1.5 mt-1 text-sky-300 font-bold">
              <Zap className="w-3.5 h-3.5 text-sky-400" />
              <span>:{targetPort} (DMA)</span>
            </div>
          </div>

          {/* Reconnect Iteration */}
          <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex flex-col justify-between">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Backoff Loop</span>
            <div className="flex items-center gap-1.5 mt-1">
              <span className={`font-bold ${reconnectAttempt > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {reconnectAttempt > 0 ? `#${reconnectAttempt} aktiv` : '0 (Stabil)'}
              </span>
            </div>
          </div>

          {/* Active Backoff Delay */}
          <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex flex-col justify-between">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Nächster Retry</span>
            <div className="flex items-center gap-1.5 mt-1 text-slate-200 font-bold">
              {nextRetryDelayMs ? (
                <span className="text-amber-300">{(nextRetryDelayMs / 1000).toFixed(1)}s</span>
              ) : (
                <span className="text-slate-500 font-normal">Inaktiv</span>
              )}
            </div>
          </div>

          {/* Disconnect Count */}
          <div className="col-span-2 sm:col-span-1 p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex flex-col justify-between">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Trennungen</span>
            <div className="flex items-center gap-2 mt-1">
              <span className="font-bold text-rose-400">{stats.disconnects} Disconnects</span>
              <span className="text-[10px] text-slate-500">/ {stats.total} Logs</span>
            </div>
          </div>
        </div>

        {/* Action Controls & Filter Tabs */}
        <div className="p-3 sm:p-4 border-b border-slate-800 bg-slate-900/60 flex flex-wrap items-center justify-between gap-3">
          {/* Status Color Filter Tabs */}
          <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-mono">
            <button
              onClick={() => setFilterType('ALL')}
              className={`px-2.5 py-1 rounded transition-all ${
                filterType === 'ALL'
                  ? 'bg-slate-800 text-white font-bold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Alle ({stats.total})
            </button>
            <button
              onClick={() => setFilterType('DISCONNECTS')}
              className={`px-2.5 py-1 rounded flex items-center gap-1.5 transition-all ${
                filterType === 'DISCONNECTS'
                  ? 'bg-rose-950/80 text-rose-300 border border-rose-500/40 font-bold shadow-sm'
                  : 'text-rose-400/80 hover:text-rose-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
              Disconnects ({stats.disconnects})
            </button>
            <button
              onClick={() => setFilterType('RECONNECTS')}
              className={`px-2.5 py-1 rounded flex items-center gap-1.5 transition-all ${
                filterType === 'RECONNECTS'
                  ? 'bg-amber-950/80 text-amber-300 border border-amber-500/40 font-bold shadow-sm'
                  : 'text-amber-400/80 hover:text-amber-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              Retries ({stats.reconnects})
            </button>
            <button
              onClick={() => setFilterType('CONNECTED')}
              className={`px-2.5 py-1 rounded flex items-center gap-1.5 transition-all ${
                filterType === 'CONNECTED'
                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 font-bold shadow-sm'
                  : 'text-emerald-400/80 hover:text-emerald-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Live ({stats.connects})
            </button>
          </div>

          {/* Search bar & Actions */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-56">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Code 1006, Grund..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500 font-mono"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 text-xs"
                >
                  ✕
                </button>
              )}
            </div>

            <button
              onClick={onReconnect}
              className="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
              title="Reset Backoff und erzwinge sofortige Neuverbindung auf Port 1000"
            >
              <RefreshCw className="w-3 h-3 text-amber-400" />
              <span className="hidden sm:inline">Sofort verbinden</span>
            </button>

            <button
              onClick={onClearHistory}
              className="p-1.5 rounded-lg border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-400 hover:text-rose-400 text-xs font-mono transition-colors"
              title="Historie leeren"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Event Log Stream */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-2 font-mono">
          {filteredEvents.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
              <Terminal className="w-8 h-8 text-slate-600 mb-1" />
              <span>Keine Verbindungsereignisse für die gewählten Filter gefunden.</span>
              <button
                onClick={() => {
                  setFilterType('ALL');
                  setSearchQuery('');
                }}
                className="text-amber-400 hover:underline text-[11px] mt-1"
              >
                Filter zurücksetzen
              </button>
            </div>
          ) : (
            filteredEvents.map((evt) => {
              const styling = getSeverityStyle(evt.severity, evt.type);

              return (
                <div
                  key={evt.id}
                  className={`p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 border-l-4 ${styling.border} hover:border-slate-700 transition-all text-xs`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    {/* Timestamp & Type Badge */}
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-slate-400 font-mono font-medium">
                        {formatTimestamp(evt.timestamp)}
                      </span>

                      <div
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-bold ${styling.badge}`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${styling.dot}`} />
                        <span>{evt.type}</span>
                      </div>

                      {evt.code !== undefined && (
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded font-bold border ${
                            evt.code === 1000
                              ? 'bg-slate-800 text-slate-300 border-slate-700'
                              : 'bg-rose-950/60 text-rose-300 border-rose-800/60'
                          }`}
                        >
                          Code {evt.code}
                        </span>
                      )}

                      {evt.attempt > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                          Versuch #{evt.attempt}
                        </span>
                      )}

                      {evt.backoffDelayMs && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950/50 text-amber-300 border border-amber-500/30">
                          +{(evt.backoffDelayMs / 1000).toFixed(2)}s Backoff
                        </span>
                      )}

                      {evt.latencyMs && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/50 text-emerald-300 border border-emerald-500/30">
                          {evt.latencyMs}ms Latenz
                        </span>
                      )}
                    </div>

                    {/* Target Port Endpoint */}
                    <div className="text-[10px] text-slate-500 font-mono">
                      <span>Port {evt.port}</span>
                    </div>
                  </div>

                  {/* Reason Headline */}
                  <div className="mt-1.5 text-slate-200 font-semibold text-xs flex items-center gap-1.5">
                    {styling.icon}
                    <span>{evt.reason}</span>
                  </div>

                  {/* Details / Diagnostic explanation */}
                  {evt.details && (
                    <div className="mt-1 text-[11px] text-slate-400 bg-slate-900/90 rounded p-2 border border-slate-800/60 leading-relaxed">
                      {evt.details}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Diagnostic Guide Footer */}
        <div className="p-3 sm:p-4 border-t border-slate-800 bg-slate-950/80 text-xs">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowDiagnosticsInfo(!showDiagnosticsInfo)}
              className="text-[11px] text-amber-400 hover:text-amber-300 flex items-center gap-1.5 font-mono"
            >
              <Info className="w-3.5 h-3.5" />
              <span>{showDiagnosticsInfo ? 'Port 1000 Debugger-Guide ausblenden' : 'Port 1000 Debugger-Guide einblenden'}</span>
            </button>
            <span className="text-[10px] text-slate-500 font-mono">
              The Judge & The Swarm • High-Frequency DMA Telemetry
            </span>
          </div>

          {showDiagnosticsInfo && (
            <div className="mt-2.5 p-3 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-300 space-y-1.5 font-mono leading-relaxed animate-in fade-in duration-100">
              <div className="flex items-center gap-1.5 text-amber-300 font-bold">
                <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                <span>Port 1000 WebSocket Architektur & Fehlerschlüssel:</span>
              </div>
              <ul className="list-disc pl-4 space-y-1 text-slate-400 text-[10px]">
                <li>
                  <strong className="text-slate-200">Code 1006 (Abnormal Closure):</strong> Tritt auf, wenn der TCP-Handshake auf Port 1000 vom Container-Netzwerk verweigert wird (ECONNREFUSED) oder die Nginx-Bridge den Port noch nicht allokiert hat.
                </li>
                <li>
                  <strong className="text-slate-200">Exponential Backoff:</strong> Bei jedem Verbindungsabbruch verdoppelt sich das Warteintervall (1s → 2s → 4s → 8s → 16s → 30s Cap) mit ±15 % Random-Jitter, um Bursts zu verhindern.
                </li>
                <li>
                  <strong className="text-slate-200">Multi-Tier SSE Fallback:</strong> Während Port 1000 im Backoff-Modus reconnectet, fungiert die interne Server-Sent Events (SSE) Route auf Port 3000 als Hot-Standby, sodass kein L2-Orderbuch-Datenverlust entsteht.
                </li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

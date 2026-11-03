import React, { useState } from "react";
import { AlertTriangle, Check, ChevronDown, RefreshCw, RotateCcw, Send, X } from "lucide-react";
import {
  connectionView,
  formatTime,
  formatWait,
  openSuggestions,
  pairedTarget,
  peerName,
  quotaFor,
  quotaLeft,
  recentSent,
  sendAllowed,
} from "./state";
import type { Approval, AskResult, Dialog, Message, Signal, Status, Suggestion, TelegramData, TickReport } from "./types";
import type { TelegramActions } from "./useTelegram";

const FOCUS = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70";

const TONE: Record<string, string> = {
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
  off: "bg-slate-500",
};

export const Panel: React.FC<{ title: string; count?: number; action?: React.ReactNode; children: React.ReactNode }> = ({
  title,
  count,
  action,
  children,
}) => (
  <section aria-label={title} className="min-w-0 rounded-xl border border-white/[0.06] bg-[#0c0e15]">
    <header className="flex items-center justify-between gap-2 border-b border-white/[0.04] px-4 py-3">
      <h2 className="text-sm font-semibold text-slate-200">
        {title}
        {count !== undefined && <span className="ml-2 font-normal text-slate-500">{count}</span>}
      </h2>
      {action}
    </header>
    <div className="p-3">{children}</div>
  </section>
);

const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="px-1 py-3 text-sm text-slate-500">{children}</p>
);

export const StatusBar: React.FC<{ status: Status | null; errorCode: string | null; live: boolean }> = ({ status, errorCode, live }) => {
  const view = connectionView(status, errorCode);
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm" role="status">
      <span className="flex items-center gap-2 text-slate-200">
        <span aria-hidden="true" className={`h-2 w-2 rounded-full ${TONE[view.tone]}`} />
        {view.label}
      </span>
      {status?.me && <span className="text-slate-400">@{status.me.username || status.me.name}</span>}
      {view.tone === "ok" && <span className="text-slate-500">{live ? "Live" : "Live getrennt"}</span>}
      {status?.flood_wait_until && (
        <span className="text-amber-300">Telegram bremst bis {formatTime(status.flood_wait_until)}</span>
      )}
    </div>
  );
};

export const SetupHint: React.FC<{ status: Status | null; errorCode: string | null }> = ({ status, errorCode }) => {
  const view = connectionView(status, errorCode);
  if (view.tone === "ok" || !view.hint) return null;
  return (
    <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-4 text-sm text-slate-300">
      <p className="font-medium text-amber-200">{view.hint}</p>
      <p className="mt-2 text-slate-400">Einrichtung im Terminal, die Anleitung steht in docs/TELEGRAM.md:</p>
      <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-3 font-mono text-xs text-slate-300">
        {"python3 -m orchestrator telegram login\npython3 -m orchestrator kanban serve"}
      </pre>
    </div>
  );
};

const Toggle: React.FC<{ on: boolean; label: string; text: string; disabled?: boolean; onClick: () => void }> = ({
  on,
  label,
  text,
  disabled,
  onClick,
}) => (
  <button
    type="button"
    aria-pressed={on}
    aria-label={label}
    disabled={disabled}
    onClick={onClick}
    className={`rounded-md border px-2 py-1 text-xs font-medium transition-colors motion-reduce:transition-none disabled:opacity-50 ${FOCUS} ${
      on ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200" : "border-white/[0.08] text-slate-400 hover:text-slate-200"
    }`}
  >
    {text}
  </button>
);

export const ChatRow: React.FC<{
  dialog: Dialog;
  data: TelegramData;
  busy: ReadonlySet<string>;
  actions: TelegramActions;
}> = ({ dialog, data, busy, actions }) => {
  const monitored = data.monitored.includes(dialog.id);
  const allowed = sendAllowed(data.allowlist, dialog.id);
  const envAllowed = data.allowlist.env.includes(dialog.id);
  const target = pairedTarget(data, dialog.id);
  const selectId = `pair-${dialog.id}`;
  return (
    <li className="rounded-lg px-2 py-2 hover:bg-white/[0.02]">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm text-slate-200" title={dialog.name}>
            {dialog.name || dialog.id}
          </p>
          <p className="text-xs text-slate-500">
            {dialog.is_bot ? "Bot" : dialog.kind === "channel" ? "Kanal" : dialog.kind === "group" ? "Gruppe" : "Chat"}
          </p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <Toggle
            on={monitored}
            text="Mitlesen"
            label={`${dialog.name} mitlesen`}
            disabled={busy.has(`monitor:${dialog.id}`)}
            onClick={() => actions.setMonitored(dialog.id, !monitored)}
          />
          <Toggle
            on={allowed}
            text="Senden"
            label={`Senden an ${dialog.name} erlauben`}
            disabled={envAllowed || busy.has(`allow:${dialog.id}`)}
            onClick={() => actions.setAllowed(dialog.id, !allowed)}
          />
        </div>
      </div>
      {monitored && (
        <div className="mt-2">
          <label htmlFor={selectId} className="text-xs text-slate-500">
            Vorschläge an
          </label>
          <select
            id={selectId}
            value={target ?? ""}
            disabled={busy.has(`pair:${dialog.id}`)}
            onChange={(e) => actions.setPairing(dialog.id, e.target.value ? Number(e.target.value) : null)}
            className={`mt-1 w-full rounded-lg border border-white/[0.08] bg-[#090b12] px-2 py-1.5 text-sm text-slate-200 ${FOCUS}`}
          >
            <option value="">Keine Vorschläge</option>
            {data.dialogs
              .filter((d) => d.id !== dialog.id)
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name || d.id}
                </option>
              ))}
          </select>
          {target !== null && !sendAllowed(data.allowlist, target) && (
            <p className="mt-1 text-xs text-amber-300">Ziel hat keine Sendeerlaubnis, es entstehen keine Vorschläge.</p>
          )}
        </div>
      )}
    </li>
  );
};

export const ChatsPanel: React.FC<{ data: TelegramData; busy: ReadonlySet<string>; actions: TelegramActions }> = ({ data, busy, actions }) => {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const rows = data.dialogs.filter((d) => !needle || d.name.toLowerCase().includes(needle));
  return (
    <Panel title="Chats" count={data.dialogs.length}>
      <input
        type="search"
        aria-label="Chats filtern"
        placeholder="Filtern"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className={`mb-2 w-full rounded-lg border border-white/[0.08] bg-[#090b12] px-3 py-1.5 text-sm text-slate-200 placeholder:text-slate-600 ${FOCUS}`}
      />
      {rows.length === 0 ? (
        <Empty>Keine Chats gefunden.</Empty>
      ) : (
        <ul className="max-h-[420px] divide-y divide-white/[0.03] overflow-y-auto">
          {rows.map((d) => (
            <ChatRow key={d.id} dialog={d} data={data} busy={busy} actions={actions} />
          ))}
        </ul>
      )}
    </Panel>
  );
};

export const GatherPanel: React.FC<{
  status: Status | null;
  lastTick: TickReport | null;
  busy: ReadonlySet<string>;
  actions: TelegramActions;
}> = ({ status, lastTick, busy, actions }) => {
  const tick = lastTick ?? status?.gather.last_tick ?? null;
  return (
    <Panel
      title="Abruf"
      action={
        <button
          type="button"
          disabled={busy.has("gather")}
          onClick={actions.gather}
          className={`flex items-center gap-1.5 rounded-md border border-white/[0.08] px-2 py-1 text-xs text-slate-300 hover:bg-white/[0.04] disabled:opacity-50 ${FOCUS}`}
        >
          <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
          Jetzt abrufen
        </button>
      }
    >
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 px-1 text-sm">
        <dt className="text-slate-500">Automatisch</dt>
        <dd className="text-right text-slate-300">
          {status?.gather.running ? `alle ${formatWait(status.gather.interval_s)}` : "aus"}
        </dd>
        <dt className="text-slate-500">Letzter Lauf</dt>
        <dd className="text-right text-slate-300">{tick ? formatTime(tick.at) : "noch keiner"}</dd>
        <dt className="text-slate-500">Geholt / geroutet</dt>
        <dd className="text-right text-slate-300">{tick ? `${tick.fetched} / ${tick.routed}` : "-"}</dd>
        <dt className="text-slate-500">Symbole</dt>
        <dd className="text-right text-slate-300">{status ? `${status.symbols.count} (${status.symbols.source})` : "-"}</dd>
      </dl>
      {tick && tick.errors.length > 0 && (
        <ul className="mt-2 space-y-1 px-1 text-xs text-red-300">
          {tick.errors.map((e) => (
            <li key={e} className="break-words">
              {e}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
};

export const FeedPanel: React.FC<{ messages: Message[]; dialogs: Dialog[]; monitored: number[] }> = ({ messages, dialogs, monitored }) => {
  const [peer, setPeer] = useState("");
  const rows = (peer ? messages.filter((m) => String(m.peer) === peer) : messages).slice(-100).reverse();
  return (
    <Panel
      title="Live-Feed"
      count={rows.length}
      action={
        <div className="relative">
          <select
            aria-label="Feed nach Chat filtern"
            value={peer}
            onChange={(e) => setPeer(e.target.value)}
            className={`max-w-[160px] appearance-none rounded-md border border-white/[0.08] bg-[#090b12] py-1 pl-2 pr-6 text-xs text-slate-300 ${FOCUS}`}
          >
            <option value="">Alle Chats</option>
            {monitored.map((p) => (
              <option key={p} value={p}>
                {peerName(dialogs, p)}
              </option>
            ))}
          </select>
          <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-1.5 top-1.5 h-3.5 w-3.5 text-slate-500" />
        </div>
      }
    >
      {rows.length === 0 ? (
        <Empty>Noch keine Nachrichten. Aktiviere bei einem Chat Mitlesen.</Empty>
      ) : (
        <ol role="log" className="max-h-[560px] space-y-1 overflow-y-auto">
          {rows.map((m) => (
            <li key={`${m.peer}:${m.msg_id}`} className="rounded-lg px-2 py-2 hover:bg-white/[0.02]">
              <p className="flex items-baseline justify-between gap-3 text-xs text-slate-500">
                <span className="truncate">
                  {peerName(dialogs, m.peer)}
                  {m.sender ? ` · ${m.sender}` : ""}
                </span>
                <time dateTime={m.ts} className="shrink-0">
                  {formatTime(m.ts)}
                </time>
              </p>
              <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-slate-200">{m.text}</p>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
};

export const AskPanel: React.FC<{ ask: TelegramActions["ask"] }> = ({ ask }) => {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResult | null>(null);
  const [pending, setPending] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || pending) return;
    setPending(true);
    setAnswer(await ask(question.trim()));
    setPending(false);
  };
  return (
    <Panel title="Frage an den Feed">
      <form onSubmit={submit} className="flex gap-2">
        <input
          type="text"
          aria-label="Frage"
          maxLength={2000}
          placeholder="Wie ist die Stimmung bei BTC?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className={`min-w-0 flex-1 rounded-lg border border-white/[0.08] bg-[#090b12] px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 ${FOCUS}`}
        />
        <button
          type="submit"
          disabled={pending || !question.trim()}
          className={`rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-cyan-400 disabled:opacity-50 ${FOCUS}`}
        >
          Fragen
        </button>
      </form>
      {answer && (
        <div className="mt-3 px-1" aria-live="polite">
          <p className="whitespace-pre-wrap break-words text-sm text-slate-200">{answer.answer}</p>
          <p className="mt-1 text-xs text-slate-500">
            {answer.source === "llm" ? "KI-Antwort" : "Regel-Auswertung"} aus {answer.context_count} Nachrichten
          </p>
        </div>
      )}
    </Panel>
  );
};

export const SuggestionCard: React.FC<{
  suggestion: Suggestion;
  data: TelegramData;
  busy: boolean;
  actions: TelegramActions;
}> = ({ suggestion: s, data, busy, actions }) => {
  const quota = quotaFor(data.status, s.target_peer);
  const left = quota ? quotaLeft(quota) : null;
  const allowed = sendAllowed(data.allowlist, s.target_peer);
  const target = peerName(data.dialogs, s.target_peer);
  return (
    <li className="rounded-lg border border-white/[0.06] bg-[#090b12] p-3">
      <p className="break-words font-mono text-sm text-slate-100">{s.text}</p>
      <dl className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-500">
        <div className="flex gap-1">
          <dt>An</dt>
          <dd className="text-slate-300">{target}</dd>
        </div>
        <div className="flex gap-1">
          <dt>Aus</dt>
          <dd className="text-slate-300">{peerName(data.dialogs, s.source_peer)}</dd>
        </div>
        <div className="flex gap-1">
          <dt>Quelle</dt>
          <dd className={s.origin === "llm" ? "text-amber-300" : "text-slate-300"}>{s.origin === "llm" ? "KI" : "Regel"}</dd>
        </div>
        {quota && left !== null && (
          <div className="flex gap-1">
            <dt>Kontingent</dt>
            <dd className={left === 0 ? "text-red-300" : "text-slate-300"}>
              noch {left} von {quota.limit} pro Stunde
            </dd>
          </div>
        )}
      </dl>
      {s.origin === "llm" && <p className="mt-2 text-xs text-amber-300/80">KI-Text aus Feed-Inhalt: vor dem Senden prüfen.</p>}
      {!allowed && <p className="mt-2 text-xs text-red-300">Ziel hat keine Sendeerlaubnis.</p>}
      {s.status === "failed" && <p className="mt-2 break-words text-xs text-red-300">{s.error || "Senden fehlgeschlagen"}</p>}
      <div className="mt-3 flex gap-2">
        {s.status === "pending" && (
          <button
            type="button"
            disabled={busy || !allowed || left === 0}
            onClick={() => actions.approve(s.id)}
            className={`flex items-center gap-1.5 rounded-lg bg-cyan-500 px-3 py-1.5 text-sm font-semibold text-slate-900 hover:bg-cyan-400 disabled:opacity-50 ${FOCUS}`}
          >
            <Send aria-hidden="true" className="h-3.5 w-3.5" />
            An {target} senden
          </button>
        )}
        {s.status === "sending" && <span className="py-1.5 text-sm text-slate-400">Wird gesendet</span>}
        {s.status === "failed" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => actions.retry(s.id)}
            className={`flex items-center gap-1.5 rounded-lg border border-white/[0.08] px-3 py-1.5 text-sm text-slate-300 hover:bg-white/[0.04] disabled:opacity-50 ${FOCUS}`}
          >
            <RotateCcw aria-hidden="true" className="h-3.5 w-3.5" />
            Wieder öffnen
          </button>
        )}
        {s.status !== "sending" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => actions.dismiss(s.id)}
            className={`rounded-lg border border-white/[0.08] px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200 disabled:opacity-50 ${FOCUS}`}
          >
            Verwerfen
          </button>
        )}
      </div>
    </li>
  );
};

export const SuggestionsPanel: React.FC<{ data: TelegramData; busy: ReadonlySet<string>; actions: TelegramActions }> = ({ data, busy, actions }) => {
  const open = openSuggestions(data.suggestions);
  const sent = recentSent(data.suggestions);
  return (
    <Panel title="Vorschläge" count={open.length}>
      {open.length === 0 ? (
        <Empty>Nichts offen. Gesendet wird nur nach deinem Klick.</Empty>
      ) : (
        <ul className="space-y-2">
          {open.map((s) => (
            <SuggestionCard key={s.id} suggestion={s} data={data} busy={busy.has(`suggestion:${s.id}`)} actions={actions} />
          ))}
        </ul>
      )}
      {sent.length > 0 && (
        <details className="mt-3 px-1 text-sm">
          <summary className={`cursor-pointer rounded text-slate-400 ${FOCUS}`}>Zuletzt gesendet</summary>
          <ul className="mt-2 space-y-1">
            {sent.map((s) => (
              <li key={s.id} className="flex items-start gap-2 text-xs text-slate-400">
                <Check aria-hidden="true" className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
                <span className="min-w-0 break-words">
                  {s.text} an {peerName(data.dialogs, s.target_peer)}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Panel>
  );
};

export const ApprovalsPanel: React.FC<{ approvals: Approval[]; busy: ReadonlySet<string>; actions: TelegramActions }> = ({ approvals, busy, actions }) => {
  const open = approvals.filter((a) => a.status === "pending");
  return (
    <Panel title="Freigaben" count={open.length}>
      {open.length === 0 ? (
        <Empty>Keine offenen Freigaben.</Empty>
      ) : (
        <ul className="space-y-2">
          {open.map((a) => (
            <li key={a.id} className="rounded-lg border border-white/[0.06] bg-[#090b12] p-3">
              <p className="break-words text-sm font-medium text-slate-100">{a.title}</p>
              {a.detail && <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-400">{a.detail}</p>}
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  disabled={busy.has(`approval:${a.id}`)}
                  onClick={() => actions.decide(a.id, true)}
                  className={`flex items-center gap-1.5 rounded-lg bg-cyan-500 px-3 py-1.5 text-sm font-semibold text-slate-900 hover:bg-cyan-400 disabled:opacity-50 ${FOCUS}`}
                >
                  <Check aria-hidden="true" className="h-3.5 w-3.5" />
                  Freigeben
                </button>
                <button
                  type="button"
                  disabled={busy.has(`approval:${a.id}`)}
                  onClick={() => actions.decide(a.id, false)}
                  className={`flex items-center gap-1.5 rounded-lg border border-white/[0.08] px-3 py-1.5 text-sm text-slate-300 hover:bg-white/[0.04] disabled:opacity-50 ${FOCUS}`}
                >
                  <X aria-hidden="true" className="h-3.5 w-3.5" />
                  Ablehnen
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
};

const DIRECTION: Record<string, { label: string; className: string }> = {
  bullish: { label: "Bullish", className: "text-emerald-300" },
  bearish: { label: "Bearish", className: "text-red-300" },
  neutral: { label: "Neutral", className: "text-slate-300" },
};

export const SignalsPanel: React.FC<{ signals: Signal[]; dialogs: Dialog[] }> = ({ signals, dialogs }) => (
  <Panel title="Signale" count={signals.length}>
    {signals.length === 0 ? (
      <Empty>Noch keine Signale erkannt.</Empty>
    ) : (
      <ul className="max-h-[360px] space-y-1 overflow-y-auto">
        {signals.slice(0, 50).map((s) => (
          <li key={s.id} className="rounded-lg px-2 py-2 hover:bg-white/[0.02]">
            <p className="flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium text-slate-100">{s.symbol}</span>
              <span className={DIRECTION[s.direction].className}>{DIRECTION[s.direction].label}</span>
              <span className="ml-auto text-xs text-slate-400">{s.strength}/10</span>
            </p>
            <p className="mt-0.5 line-clamp-2 break-words text-xs text-slate-400">{s.evidence}</p>
            <p className="mt-0.5 truncate text-xs text-slate-500">
              {peerName(dialogs, s.peer)} · {formatTime(s.created_at)}
              {s.kanban_task_id ? ` · Task ${s.kanban_task_id}` : ""}
            </p>
          </li>
        ))}
      </ul>
    )}
  </Panel>
);

export const ErrorBanner: React.FC<{ message: string | null; onClose: () => void }> = ({ message, onClose }) => {
  if (!message) return null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-400/20 bg-red-400/[0.06] p-3 text-sm text-red-200">
      <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <p className="min-w-0 flex-1 break-words">{message}</p>
      <button type="button" aria-label="Meldung schließen" onClick={onClose} className={`rounded p-0.5 hover:bg-white/10 ${FOCUS}`}>
        <X aria-hidden="true" className="h-4 w-4" />
      </button>
    </div>
  );
};

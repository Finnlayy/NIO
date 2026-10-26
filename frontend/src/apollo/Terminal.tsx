"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ChevronDown,
  ChevronRight,
  Copy,
  CornerDownLeft,
  Eraser,
  ListFilter,
  TerminalSquare,
  X,
} from "lucide-react";
import { COMMANDS } from "./commands";
import { useApolloStore, type LogEntry } from "./store";
import { Badge, Segmented, type Tone } from "./ui";
import type { TerminalMode } from "./types";

const ORIGIN_TONE: Record<LogEntry["origin"], Tone> = {
  USER: "cyan",
  APOLLO: "violet",
  NIO_CORE: "slate",
  FREELLM_ROUTER: "amber",
  MCP_SANDBOX: "emerald",
};

const LEVEL_COLOR: Record<LogEntry["level"], string> = {
  CHAT: "text-slate-200",
  INFO: "text-slate-300",
  DISPATCH: "text-cyan-200",
  FAILOVER: "text-amber-200",
  WARN: "text-amber-300",
  ERROR: "text-rose-300",
};

export function HybridTerminal() {
  const open = useApolloStore((s) => s.terminalOpen);
  const setOpen = useApolloStore((s) => s.setTerminalOpen);
  const mode = useApolloStore((s) => s.terminalMode);
  const setMode = useApolloStore((s) => s.setTerminalMode);
  const entries = useApolloStore((s) => s.entries);
  const runCommand = useApolloStore((s) => s.runCommand);
  const clear = useApolloStore((s) => s.clearTerminal);
  const busy = useApolloStore((s) => s.busy);

  const [input, setInput] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [pinned, setPinned] = useState(true);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [blocked, setBlocked] = useState(false);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    // Opening the terminal is a keyboard action (backtick / header button); land
    // the caret in the input so the user can type immediately.
    const timer = setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 40);
    return () => clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const element = scrollRef.current;
    if (element && pinned) element.scrollTop = element.scrollHeight;
  }, [entries, open, pinned, mode]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !useApolloStore.getState().deckOpen) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  const suggestions = useMemo(() => {
    if (!input.startsWith("/")) return [];
    const token = input.split(/\s+/)[0].toLowerCase();
    return COMMANDS.filter((command) => command.command.startsWith(token)).slice(0, 5);
  }, [input]);

  if (!open) return null;

  const submit = async () => {
    const text = input.trim();
    if (!text) return;
    /* One turn at a time. A prompt in flight owns the router, the task rail and
       the transcript; letting /clear or /spawn run underneath it interleaves two
       stories into one log. Compose freely, but hold the command. */
    if (busy) {
      setBlocked(true);
      setTimeout(() => setBlocked(false), 1500);
      return;
    }
    setInput("");
    setHistory((prev) => [...prev.slice(-49), text]);
    setHistoryIndex(-1);
    setPinned(true);
    await runCommand(text);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void submit();
      return;
    }
    if (event.key === "ArrowUp") {
      if (history.length === 0) return;
      event.preventDefault();
      const nextIndex = Math.min(history.length - 1, historyIndex + 1);
      setHistoryIndex(nextIndex);
      setInput(history[history.length - 1 - nextIndex] ?? "");
      return;
    }
    if (event.key === "ArrowDown") {
      if (historyIndex < 0) return;
      event.preventDefault();
      const nextIndex = historyIndex - 1;
      setHistoryIndex(nextIndex);
      setInput(nextIndex < 0 ? "" : (history[history.length - 1 - nextIndex] ?? ""));
      return;
    }
    if (event.key === "Tab" && suggestions.length > 0) {
      event.preventDefault();
      setInput(`${suggestions[0].command} `);
    }
  };

  /** Copy that works in an iframe / insecure origin, and says so when it cannot. */
  const copyAll = async () => {
    const text = entries
      .map((entry) => `${entry.timestamp} [${entry.origin}/${entry.level}] ${entry.message}${entry.handoffNote ? `\n${entry.handoffNote}` : ""}`)
      .join("\n");

    const legacyCopy = () => {
      try {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(area);
        return ok;
      } catch {
        return false;
      }
    };

    let ok = false;
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        ok = true;
      } catch {
        ok = legacyCopy();
      }
    } else {
      ok = legacyCopy();
    }
    setCopyState(ok ? "copied" : "failed");
    setTimeout(() => setCopyState("idle"), 1800);
  };

  return (
    <aside
      role="complementary"
      aria-label="NIO hybrid terminal"
      className="apollo-rise-in fixed bottom-3 right-3 z-[70] flex h-[min(68vh,600px)] w-[min(96vw,720px)] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#05080f]/96 shadow-[0_30px_90px_rgba(0,0,0,0.65)] backdrop-blur-xl"
      data-testid="nio-terminal"
      data-mode={mode}
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.07] px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="grid h-6 w-6 place-items-center rounded-md border border-emerald-400/30 bg-emerald-400/10 text-emerald-300">
            <TerminalSquare size={12} />
          </span>
          <div>
            <div className="text-[11.5px] font-semibold text-slate-100">NIO · Apollo terminal</div>
            <div className="font-mono text-[8.5px] uppercase tracking-[0.2em] text-slate-400">
              chat · telemetry · cli
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-[168px]">
            <Segmented<TerminalMode>
              label="Terminal mode"
              value={mode}
              onChange={setMode}
              options={[
                { value: "unified", label: "Unified" },
                { value: "raw", label: "Raw log" },
              ]}
            />
          </div>
          <button
            type="button"
            onClick={() => void copyAll()}
            aria-label="Copy transcript"
            className={`grid h-6 w-6 place-items-center rounded-md border transition-colors ${
              copyState === "copied"
                ? "border-emerald-400/40 text-emerald-300"
                : copyState === "failed"
                  ? "border-rose-400/40 text-rose-300"
                  : "border-white/10 text-slate-400 hover:text-slate-100"
            }`}
            title={copyState === "copied" ? "Copied" : copyState === "failed" ? "Clipboard unavailable" : "Copy transcript"}
          >
            <Copy size={11} />
          </button>
          {copyState !== "idle" && (
            <span
              role="status"
              className={`font-mono text-[9px] uppercase tracking-[0.16em] ${
                copyState === "copied" ? "text-emerald-300" : "text-rose-300"
              }`}
            >
              {copyState === "copied" ? "copied" : "copy blocked"}
            </span>
          )}
          <button
            type="button"
            onClick={clear}
            aria-label="Clear terminal"
            className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-slate-400 transition-colors hover:text-rose-200"
            title="Clear (/clear)"
          >
            <Eraser size={11} />
          </button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close terminal"
            className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-slate-400 transition-colors hover:text-slate-100"
          >
            <X size={12} />
          </button>
        </div>
      </header>

      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollRef}
          onScroll={(event) => {
            const el = event.currentTarget;
            setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 48);
          }}
          className="h-full overflow-y-auto px-3 py-2"
          aria-live="polite"
          data-testid="terminal-scroll"
        >
          {entries.length === 0 ? (
            <div className="grid h-full place-items-center text-center">
              <div className="max-w-sm space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-slate-400">
                  no traffic yet
                </p>
                <p className="text-[11.5px] leading-relaxed text-slate-400">
                  Ask Apollo something, or type <span className="font-mono text-cyan-300">/help</span> to see the
                  deterministic commands. Everything you see is also a visual event on the orb.
                </p>
              </div>
            </div>
          ) : mode === "unified" ? (
            <UnifiedStream entries={entries} />
          ) : (
            <RawStream entries={entries} />
          )}
        </div>

        {!pinned && (
          <button
            type="button"
            onClick={() => {
              setPinned(true);
              const element = scrollRef.current;
              if (element) element.scrollTop = element.scrollHeight;
            }}
            className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full border border-white/15 bg-[#0b1020]/95 px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.14em] text-slate-300 shadow-lg"
          >
            <ArrowDownToLine size={10} className="mr-1 inline" /> jump to live
          </button>
        )}
      </div>

      {suggestions.length > 0 && (
        <div className="border-t border-white/[0.06] bg-black/40 px-2 py-1.5">
          <ul className="space-y-0.5">
            {suggestions.map((command) => (
              <li key={command.command}>
                <button
                  type="button"
                  onClick={() => {
                    setInput(`${command.command} `);
                    inputRef.current?.focus();
                  }}
                  className="flex w-full items-baseline gap-2 rounded px-1.5 py-0.5 text-left hover:bg-white/5"
                >
                  <span className="font-mono text-[10.5px] text-cyan-300">{command.command}</span>
                  <span className="truncate font-mono text-[9px] text-slate-400">{command.usage}</span>
                  <span className="ml-auto hidden truncate text-[10px] text-slate-400 sm:block">{command.detail}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="border-t border-white/[0.07] bg-black/30 p-2.5">
        <div className="flex items-center gap-2">
          <span className="select-none font-mono text-[12px] text-emerald-300">›</span>
          <input
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder={busy ? "apollo is working…" : "ask apollo, or /spawn inference Vision Cortex"}
            aria-label="Apollo terminal input"
            spellCheck={false}
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent font-mono text-[12px] text-slate-100 outline-none placeholder:text-slate-400"
            data-testid="terminal-input"
          />
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!input.trim() || busy}
            aria-label="Send"
            title={busy ? "Apollo is mid-turn" : "Send"}
            className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-slate-400 transition-colors hover:border-cyan-400/40 hover:text-cyan-200 disabled:opacity-40"
          >
            <CornerDownLeft size={11} />
          </button>
        </div>
        <div className="mt-1 flex items-center justify-between font-mono text-[8.5px] uppercase tracking-[0.14em] text-slate-400">
          <span aria-live="polite" className={blocked ? "text-amber-300" : undefined}>
            {blocked ? "mid-turn · command held" : busy ? "apollo is working · input held" : "↑↓ history · tab complete · /help"}
          </span>
          <span className="flex items-center gap-1"><ListFilter size={8} /> {entries.length} entries</span>
        </div>
      </div>
    </aside>
  );
}

/* ==================================================================== */
/* Unified stream: chat + collapsible telemetry                          */
/* ==================================================================== */

function UnifiedStream({ entries }: { entries: LogEntry[] }) {
  return (
    <ol className="space-y-2" data-testid="unified-stream">
      {entries.map((entry) => {
        if (entry.level === "CHAT" && entry.origin === "USER") {
          return (
            <li key={entry.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-xl rounded-br-sm border border-cyan-400/25 bg-cyan-400/[0.07] px-3 py-2">
                <div className="mb-0.5 font-mono text-[8px] uppercase tracking-[0.16em] text-cyan-300/70">
                  you · {entry.timestamp}
                </div>
                <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-slate-100">{entry.message}</p>
              </div>
            </li>
          );
        }
        if (entry.level === "CHAT") {
          return (
            <li key={entry.id} className="flex justify-start">
              <div className="max-w-[88%] rounded-xl rounded-bl-sm border border-violet-400/25 bg-violet-400/[0.06] px-3 py-2">
                <div className="mb-0.5 flex items-center gap-2 font-mono text-[8px] uppercase tracking-[0.16em] text-violet-300/80">
                  <span>apollo</span>
                  {entry.activeModel && <span className="text-slate-400">· {entry.activeModel}</span>}
                  {entry.simulated && <Badge tone="slate">sim</Badge>}
                  <span className="text-slate-400">{entry.timestamp}</span>
                </div>
                <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-slate-100">{entry.message}</p>
                {entry.handoffNote && <HandoffBlock note={entry.handoffNote} />}
              </div>
            </li>
          );
        }
        /* telemetry */
        // `detail` (a CLI hint, an upstream reason) is body content: if a row has
        // one, it must be openable, otherwise the hint is never readable.
        const collapsible =
          entry.level === "DISPATCH" ||
          entry.level === "FAILOVER" ||
          entry.level === "ERROR" ||
          Boolean(entry.data) ||
          Boolean(entry.detail);
        return (
          <li key={entry.id}>
            <Disclosure
              tone={ORIGIN_TONE[entry.origin]}
              label={`[${entry.origin}]`}
              title={entry.message}
              meta={`${entry.timestamp} · ${entry.level.toLowerCase()}`}
              defaultOpen={entry.level === "FAILOVER" || entry.level === "ERROR"}
              collapsible={collapsible}
              payload={entry.data}
              handoffNote={entry.handoffNote}
              detail={entry.detail}
            />
          </li>
        );
      })}
    </ol>
  );
}

function HandoffBlock({ note }: { note: string }) {
  return (
    <div className="mt-2 rounded-lg border border-amber-400/25 bg-amber-400/[0.05] p-2">
      <div className="mb-1 font-mono text-[8px] uppercase tracking-[0.18em] text-amber-300/80">
        context handoff note
      </div>
      <pre className="max-h-32 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-relaxed text-amber-100/85">
        {note}
      </pre>
    </div>
  );
}

function Disclosure({
  tone,
  label,
  title,
  meta,
  defaultOpen,
  collapsible,
  payload,
  handoffNote,
  detail,
}: {
  tone: Tone;
  label: string;
  title: string;
  meta: string;
  defaultOpen: boolean;
  collapsible: boolean;
  payload?: Record<string, unknown>;
  handoffNote?: string;
  detail?: string;
}) {
  const [expanded, setExpanded] = useState(defaultOpen);
  const hasBody = Boolean(payload || handoffNote || detail);
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.015]">
      <button
        type="button"
        onClick={() => collapsible && hasBody && setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        className="flex w-full items-start gap-2 px-2.5 py-1.5 text-left"
      >
        {collapsible && hasBody ? (
          expanded ? (
            <ChevronDown size={11} className="mt-0.5 shrink-0 text-slate-400" />
          ) : (
            <ChevronRight size={11} className="mt-0.5 shrink-0 text-slate-400" />
          )
        ) : (
          <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-slate-600" />
        )}
        <span className="min-w-0 flex-1">
          <span className="mb-0.5 flex flex-wrap items-center gap-1.5">
            <Badge tone={tone}>{label}</Badge>
            <span className="font-mono text-[8px] uppercase tracking-[0.14em] text-slate-400">{meta}</span>
          </span>
          <span className="block whitespace-pre-wrap break-words font-mono text-[10.5px] leading-relaxed text-slate-300">
            {title}
          </span>
        </span>
      </button>
      {expanded && hasBody && (
        <div className="border-t border-white/[0.05] px-2.5 py-2">
          {detail && <p className="mb-1.5 font-mono text-[10px] text-slate-400">{detail}</p>}
          {handoffNote && <HandoffBlock note={handoffNote} />}
          {payload && (
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded border border-white/[0.05] bg-black/40 p-2 font-mono text-[9.5px] leading-relaxed text-slate-400">
              {JSON.stringify(payload, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

/* ==================================================================== */
/* Raw telemetry log                                                     */
/* ==================================================================== */

function RawStream({ entries }: { entries: LogEntry[] }) {
  return (
    <ol className="space-y-0.5 font-mono text-[10.5px] leading-relaxed" data-testid="raw-stream">
      {entries.map((entry) => (
        <li key={entry.id} className="group flex items-start gap-2 rounded px-1 py-0.5 hover:bg-white/[0.03]">
          <span className="shrink-0 tabular-nums text-slate-400">{entry.timestamp}</span>
          <span className={`shrink-0 ${LEVEL_COLOR[entry.level]}`}>[{entry.level}]</span>
          <span className="shrink-0 uppercase tracking-wide text-slate-400">[{entry.origin}]</span>
          {entry.activeModel && (
            <span className="hidden shrink-0 truncate text-slate-400 sm:inline" title={entry.activeModel}>
              «{entry.activeModel}»
            </span>
          )}
          <span className="min-w-0 flex-1 whitespace-pre-wrap break-words text-slate-300">
            {entry.message}
            {entry.data && (
              <details className="mt-0.5">
                <summary className="cursor-pointer list-none text-[9px] uppercase tracking-[0.14em] text-slate-400 hover:text-cyan-300">
                  json
                </summary>
                <pre className="mt-1 overflow-auto rounded border border-white/[0.05] bg-black/40 p-1.5 text-[9px] text-slate-400">
                  {JSON.stringify(entry.data, null, 2)}
                </pre>
              </details>
            )}
            {entry.handoffNote && (
              <pre className="mt-1 whitespace-pre-wrap break-words rounded border border-amber-400/20 bg-amber-400/[0.04] p-1.5 text-[9.5px] text-amber-100/80">
                {entry.handoffNote}
              </pre>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

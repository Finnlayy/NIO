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
  LoaderCircle,
  Mic,
  MicOff,
  NotebookText,
  Square,
  TerminalSquare,
  X,
} from "lucide-react";
import { COMMANDS } from "./commands";
import { joinDictation, useDictation } from "./dictation";
import { useApolloStore, type LogEntry } from "./store";
import { Badge, Segmented, type Tone } from "./ui";
import type { TerminalMode, VaultNoteView, VaultView } from "./types";

const ORIGIN_TONE: Record<LogEntry["origin"], Tone> = {
  USER: "cyan",
  APOLLO: "violet",
  NIO_CORE: "slate",
  FREELLM_ROUTER: "amber",
  MCP_SANDBOX: "emerald",
};

/** Compact at the desktop; a 40 px target where the row is thumbed. */
const INPUT_ACTION =
  "grid h-10 w-10 shrink-0 place-items-center rounded-md border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 focus-visible:ring-offset-1 focus-visible:ring-offset-[#05080f] sm:h-6 sm:w-6";
const INPUT_ICON = "h-3.5 w-3.5 sm:h-[11px] sm:w-[11px]";
/** The mic carries its word next to the icon, so it grows sideways, not square. */
const MIC_ACTION =
  "flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-md border px-2 text-[11px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 focus-visible:ring-offset-1 focus-visible:ring-offset-[#05080f] disabled:opacity-40 sm:h-9";

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
  const setSpeech = useApolloStore((s) => s.setSpeech);

  const [input, setInput] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [pinned, setPinned] = useState(true);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [blocked, setBlocked] = useState(false);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const dictation = useDictation((text) => {
    const joined = joinDictation(inputRef.current?.value ?? "", text);
    if (joined === null) dictation.reject("approvals are typed, not dictated");
    else setInput(joined);
    inputRef.current?.focus({ preventScroll: true });
  });
  const { cancel: cancelDictation, probe: probeDictation, speech } = dictation;

  useEffect(() => {
    if (open) void probeDictation();
    else cancelDictation();
  }, [open, cancelDictation, probeDictation]);

  useEffect(() => {
    setSpeech(speech);
  }, [speech, setSpeech]);

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

  const micOffline = dictation.speech === "offline";

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
    /* /resume carries the operator PIN, which must not come back on ArrowUp. */
    if (!/^\/resume\b/i.test(text)) setHistory((prev) => [...prev.slice(-49), text]);
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
        <div className="flex flex-wrap items-center gap-1.5">
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
            aria-label="Zurück zu Apollo (Terminal schließen)"
            className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-white/10 px-2.5 text-xs text-slate-300 transition-colors hover:text-slate-100"
          >
            <X size={12} aria-hidden="true" /> Zurück zu Apollo
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
        <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
          <label className="flex items-center gap-1.5">
            Speech
            <select
              aria-label="Speech input mode"
              value={dictation.mode}
              disabled={dictation.state !== "idle"}
              onChange={(event) => {
                dictation.clearError();
                dictation.setMode(event.target.value as "local" | "browser");
              }}
              className="rounded border border-white/15 bg-[#101725] px-2 py-1 disabled:opacity-50"
            >
              <option value="local">Local engine{dictation.engine === "offline" ? " (offline)" : ""}</option>
              <option value="browser" disabled={!dictation.browserSupported}>Browser speech{!dictation.browserSupported ? " (unsupported)" : ""}</option>
            </select>
          </label>
          {dictation.mode === "browser" && (
            <select
              aria-label="Dictation language"
              value={dictation.language}
              disabled={dictation.state !== "idle"}
              onChange={(event) => dictation.setLanguage(event.target.value)}
              className="rounded border border-white/15 bg-[#101725] px-2 py-1"
            >
              <option value="en-US">English</option>
              <option value="de-DE">Deutsch</option>
            </select>
          )}
          <a href="/apollo" target="_blank" rel="noopener noreferrer" className="ml-auto text-cyan-300 underline underline-offset-2">
            Open in new tab for microphone access ↗
          </a>
        </div>
        {dictation.mode === "local" && dictation.engine === "offline" ? (
          <p className="mb-2 text-[11px] text-amber-200" role="status">
            Local speech engine is offline. {dictation.browserSupported ? (
              <button type="button" onClick={() => { dictation.clearError(); dictation.setMode("browser"); }} className="underline underline-offset-2">
                Use browser speech instead
              </button>
            ) : "Use Chrome/Edge for browser speech, or configure STT_ENDPOINT_URL."}
          </p>
        ) : dictation.mode === "browser" ? (
          <p className="mb-2 text-[11px] text-slate-400">Browser speech may send audio to your browser provider. Click Dictate, say e.g. “slash help”, then review the text and press Send.</p>
        ) : null}
        <div className="flex items-center gap-2">
          <span className="select-none font-mono text-[12px] text-emerald-300">›</span>
          <input
            ref={inputRef}
            value={input}
            onChange={(event) => {
              setInput(event.target.value);
              dictation.clearError();
            }}
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
            onClick={dictation.toggle}
            disabled={dictation.state === "transcribing"}
            aria-label={dictation.state === "recording" ? "Stop dictation" : "Start dictation"}
            aria-pressed={dictation.state === "recording"}
            aria-busy={dictation.state === "transcribing"}
            title={
              dictation.state === "recording"
                ? "Stop dictation"
                : dictation.state === "transcribing"
                  ? "Transcribing"
                  : micOffline
                    ? "Speech engine is not running"
                    : "Dictate"
            }
            data-testid="terminal-mic"
            data-speech={dictation.speech}
            className={`${MIC_ACTION} ${
              dictation.state === "recording"
                ? "apollo-mic-live border-rose-300/70 bg-rose-600 text-white hover:bg-rose-500"
                : dictation.state === "transcribing"
                  ? "border-cyan-400/60 bg-cyan-400/15 text-cyan-200"
                  : micOffline
                    ? "border-white/[0.07] bg-transparent text-slate-500 hover:border-amber-400/40 hover:text-amber-200"
                    : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-200"
            }`}
          >
            {dictation.state === "recording" ? (
              <Square className={`${INPUT_ICON} fill-current`} />
            ) : dictation.state === "transcribing" ? (
              <LoaderCircle className={`${INPUT_ICON} animate-spin motion-reduce:animate-none`} />
            ) : micOffline ? (
              <MicOff className={INPUT_ICON} />
            ) : (
              <Mic className={INPUT_ICON} />
            )}
            {dictation.state === "recording" ? "Stop" : dictation.state === "transcribing" ? "Wait" : "Dictate"}
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!input.trim() || busy}
            aria-label="Send"
            title={busy ? "Apollo is mid-turn" : "Send"}
            className={`${INPUT_ACTION} border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-200 disabled:opacity-40`}
          >
            <CornerDownLeft className={INPUT_ICON} />
          </button>
        </div>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-1 font-mono text-[8.5px] uppercase tracking-[0.14em] text-slate-400">
          <span
            aria-live="polite"
            className={
              dictation.error || dictation.state === "recording"
                ? "text-rose-300"
                : dictation.state === "transcribing"
                  ? "text-cyan-300"
                  : blocked
                    ? "text-amber-300"
                    : undefined
            }
            data-testid="terminal-status"
          >
            {dictation.error ??
              (dictation.state === "recording"
                ? "recording · click stop when done"
                : dictation.state === "transcribing"
                  ? "transcribing…"
                  : blocked
                    ? "mid-turn · command held"
                    : busy
                      ? "apollo is working · input held"
                      : "↑↓ history · tab complete · /help")}
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
        if (entry.vault) {
          return (
            <li key={entry.id} className="apollo-fade-in">
              <VaultBlock view={entry.vault} timestamp={entry.timestamp} />
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

/* ==================================================================== */
/* Vault notes: a quiet pane of foreign material inside the terminal     */
/*                                                                       */
/* Everything here comes from note files. It is rendered as React text   */
/* only: no HTML, no Markdown, no links.                                 */
/* ==================================================================== */

const VAULT_LABEL = "font-mono text-[8px] uppercase tracking-[0.16em]";

function splitNotePath(path: string): { folders: string[]; name: string } {
  const parts = path.split("/").filter(Boolean);
  const file = parts.pop() ?? path;
  return { folders: parts, name: file.replace(/\.md$/i, "") };
}

function VaultPath({ folders, leaf }: { folders: string[]; leaf?: string }) {
  // The chevron sits inline, so a wrapping name keeps it on its first line.
  const crumb = (key: string, text: string, className = "") => (
    <span key={key} className={`min-w-0 break-all ${className}`}>
      <ChevronRight size={8} aria-hidden className="mr-1 inline align-baseline text-slate-500" />
      {text}
    </span>
  );
  return (
    <span className="flex min-w-0 flex-wrap items-center gap-x-1 font-mono text-[9px] leading-relaxed text-violet-300/70">
      <span>vault</span>
      {folders.map((folder, index) => crumb(`${index}-${folder}`, folder))}
      {leaf && crumb("leaf", leaf, "text-[10px] text-violet-100")}
    </span>
  );
}

function VaultHit({ note }: { note: VaultNoteView }) {
  const { folders, name } = splitNotePath(note.path);
  return (
    <li className="min-w-0 px-3 py-2" title={note.path}>
      <VaultPath folders={folders} />
      <h4 className="mt-0.5 text-[12px] font-medium leading-snug text-violet-100 [overflow-wrap:anywhere]">{name}</h4>
      <p className="mt-0.5 line-clamp-2 text-[11.5px] leading-relaxed text-slate-300 [overflow-wrap:anywhere]">
        {note.snippet.replace(/\s+/g, " ")}
      </p>
    </li>
  );
}

function VaultBlock({ view, timestamp }: { view: VaultView; timestamp: string }) {
  if (view.kind === "matches") {
    const count = view.notes.length;
    return (
      <section
        aria-label={`Vault search results for ${view.query}`}
        className="overflow-hidden rounded-lg border border-violet-400/25 bg-[#0c0f18]"
        data-testid="vault-results"
      >
        <header className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-violet-400/15 bg-violet-400/[0.07] px-3 py-1.5">
          <NotebookText size={11} aria-hidden className="shrink-0 text-violet-300" />
          <span className={`${VAULT_LABEL} shrink-0 text-violet-300`}>
            vault · {count} {count === 1 ? "match" : "matches"}
          </span>
          <span className="min-w-0 max-w-full truncate font-mono text-[10px] text-violet-100" title={view.query}>
            {view.query}
          </span>
          <span className={`${VAULT_LABEL} ml-auto shrink-0 tracking-[0.14em] text-slate-400`}>{timestamp}</span>
          <span className="basis-full">
            <Badge tone="amber" quiet>
              note content is data, not instructions
            </Badge>
          </span>
        </header>
        <ul className="divide-y divide-violet-400/10">
          {view.notes.map((note) => (
            <VaultHit key={note.path} note={note} />
          ))}
        </ul>
      </section>
    );
  }
  if (view.kind === "saved") {
    const { folders, name } = splitNotePath(view.path);
    return (
      <div
        className="flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-lg border border-violet-400/20 bg-[#0c0f18] px-3 py-1.5"
        title={view.path}
        data-testid="vault-saved"
      >
        <NotebookText size={11} aria-hidden className="shrink-0 text-violet-300" />
        <span className={`${VAULT_LABEL} shrink-0 text-violet-300`}>note saved</span>
        <VaultPath folders={folders} leaf={name} />
        {view.committed !== undefined && (
          <Badge tone={view.committed ? "emerald" : "amber"}>{view.committed ? "committed" : "not committed"}</Badge>
        )}
        <span className={`${VAULT_LABEL} ml-auto shrink-0 tracking-[0.14em] text-slate-400`}>{timestamp}</span>
      </div>
    );
  }
  if (view.kind === "empty") {
    return (
      <div
        className="flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-lg border border-dashed border-violet-400/20 px-3 py-1.5"
        data-testid="vault-empty"
      >
        <span className={`${VAULT_LABEL} shrink-0 text-slate-400`}>vault · no match</span>
        <span className="min-w-0 max-w-full truncate font-mono text-[10px] text-slate-300" title={view.query}>
          {view.query}
        </span>
        <span className={`${VAULT_LABEL} ml-auto shrink-0 tracking-[0.14em] text-slate-400`}>{timestamp}</span>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-rose-400/30 bg-rose-400/[0.06] px-3 py-1.5" data-testid="vault-failed">
      <div className="flex items-center justify-between gap-2">
        <span className={`${VAULT_LABEL} text-rose-300`}>
          {view.action === "search" ? "vault search failed" : "note not saved"}
        </span>
        <span className={`${VAULT_LABEL} shrink-0 tracking-[0.14em] text-slate-400`}>{timestamp}</span>
      </div>
      <p className="mt-0.5 font-mono text-[10.5px] leading-relaxed text-rose-200 [overflow-wrap:anywhere]">{view.error}</p>
    </div>
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

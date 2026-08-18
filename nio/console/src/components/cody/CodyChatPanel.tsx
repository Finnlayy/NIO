"use client";

import type { CodyChatMessage, CodySupervisorStatus } from "@/lib/manifest-types";
import CodyCommsTimeline from "./CodyCommsTimeline";
import CodyMoodBadge from "./CodyMoodBadge";
import type { CodyMood } from "@/lib/manifest-types";

export default function CodyChatPanel({
  mood,
  supervisor,
  commsLines,
  messages,
  input,
  sending,
  error,
  onInputChange,
  onSend,
  onQuickChip,
  onClose,
}: {
  mood: CodyMood;
  supervisor: CodySupervisorStatus | null;
  commsLines: import("@/lib/manifest-types").FormattedInterAgentLine[];
  messages: CodyChatMessage[];
  input: string;
  sending: boolean;
  error: string | null;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onQuickChip: (text: string) => void;
  onClose: () => void;
}) {
  const chips = ["Status", "Active limbs", "Gate log"];

  return (
    <div className="w-[380px] max-w-[calc(100vw-2rem)] h-[520px] max-h-[calc(100vh-6rem)] flex flex-col rounded-2xl border border-white/10 bg-[#0d0f16]/95 backdrop-blur-xl shadow-2xl shadow-black/40 overflow-hidden">
      <header className="flex items-center justify-between gap-2 px-4 py-3 border-b border-white/[0.07]">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg">⚡</span>
          <div className="min-w-0">
            <p className="font-semibold text-white text-sm">Cody</p>
            <p className="text-[10px] text-slate-500 truncate">{supervisor?.summary ?? "Supervisor"}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <CodyMoodBadge mood={mood} />
          <button type="button" onClick={onClose} className="text-slate-500 hover:text-white text-sm px-1" aria-label="Close">
            ×
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <CodyCommsTimeline lines={commsLines} />
        {messages.length === 0 && commsLines.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-8">Talk to Cody — he routes through Atlas.</p>
        ) : null}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`rounded-xl px-3 py-2 text-sm leading-relaxed max-w-[90%] ${
              msg.role === "user"
                ? "ml-auto bg-cyan-500/15 border border-cyan-500/20 text-cyan-50"
                : msg.role === "system"
                  ? "mx-auto w-full bg-white/[0.03] border border-white/[0.06] text-slate-400 text-xs"
                  : "bg-amber-500/10 border border-amber-500/20 text-amber-50"
            }`}
          >
            {msg.role !== "user" ? (
              <span className="text-[10px] uppercase tracking-wider opacity-60 block mb-0.5">
                {msg.role === "system" ? "System" : "Cody"}
              </span>
            ) : null}
            <p className="whitespace-pre-wrap">{msg.content}</p>
          </div>
        ))}
        {sending ? (
          <p className="text-xs text-amber-300/80 animate-pulse">Cody is thinking…</p>
        ) : null}
        {error ? <p className="text-xs text-rose-300">{error}</p> : null}
      </div>

      <div className="px-4 pb-2 flex flex-wrap gap-1.5">
        {chips.map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => onQuickChip(chip === "Status" ? "what are agents doing?" : chip === "Active limbs" ? "active limbs" : "gate status")}
            className="text-[10px] px-2 py-1 rounded-full border border-white/10 text-slate-400 hover:text-white hover:border-amber-400/30"
          >
            {chip}
          </button>
        ))}
      </div>

      <form
        className="p-4 pt-2 border-t border-white/[0.07]"
        onSubmit={(e) => {
          e.preventDefault();
          onSend();
        }}
      >
        <textarea
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder="Type a message…"
          rows={2}
          className="w-full resize-none rounded-xl bg-white/[0.04] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-400/40"
        />
      </form>
    </div>
  );
}

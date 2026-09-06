"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Radio, Terminal, X } from "lucide-react";
import { useGridStore } from "./store";

function toneClass(method: string) {
  if (method.includes("hydrate")) return "text-cyan-300";
  if (method.includes("remove")) return "text-rose-300";
  return "text-slate-300";
}

export function McpConsole() {
  const open = useGridStore((s) => s.consoleOpen);
  const setOpen = useGridStore((s) => s.setConsoleOpen);
  const log = useGridStore((s) => s.mcpLog);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [log, open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ y: 320, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 320, opacity: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 30 }}
          className="fixed bottom-0 inset-x-0 z-40 h-80 bg-[#0a0d16]/95 backdrop-blur-xl border-t border-white/[0.08] flex flex-col"
        >
          <div className="flex items-center gap-2 px-4 h-10 border-b border-white/[0.06] shrink-0">
            <Terminal className="w-3.5 h-3.5 text-cyan-300" />
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              MCP Event Bus
            </span>
            <span className="flex items-center gap-1.5 text-[10px] text-slate-500">
              <Radio className="w-3 h-3 text-emerald-400 pulse-dot" />
              {log.length} events
            </span>
            <button
              onClick={() => setOpen(false)}
              className="ml-auto p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/[0.07]"
              aria-label="Close console"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] space-y-1">
            {log.map((event) => (
              <div key={event.id} className="flex gap-3 items-start hover:bg-white/[0.03] rounded px-1.5 py-0.5">
                <span className="text-slate-600 shrink-0">{event.timestamp}</span>
                <span className="text-violet-300/80 shrink-0">{event.source}</span>
                <span className={`shrink-0 ${toneClass(event.method)}`}>{event.method}</span>
                <span className="text-slate-500 break-all">
                  {JSON.stringify(event.params)}
                </span>
              </div>
            ))}
            <div ref={endRef} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

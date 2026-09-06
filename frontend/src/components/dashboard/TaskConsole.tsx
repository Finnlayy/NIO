import { AlertTriangle, CheckCircle2, Loader2, Play, Terminal } from "lucide-react";
import { ModuleHeader, StatusDot, Tile } from "./shared";
import type { RunState } from "./types";

export function TaskConsole({
  taskText,
  onTaskText,
  isComplex,
  onComplex,
  isRunning,
  runState,
  result,
  apiUrl,
  onRun,
}: {
  taskText: string;
  onTaskText: (value: string) => void;
  isComplex: boolean;
  onComplex: (value: boolean) => void;
  isRunning: boolean;
  runState: RunState;
  result: string;
  apiUrl: string;
  onRun: () => void;
}) {
  return (
    <Tile className="p-4 h-full flex flex-col">
      <ModuleHeader
        icon={<Terminal className="w-4 h-4" />}
        title="Task Console"
        meta="dispatch via /api/task"
        status={
          runState === "running" ? (
            <StatusDot tone="busy" label="Routing" />
          ) : runState === "success" ? (
            <StatusDot tone="online" label="Complete" />
          ) : runState === "error" ? (
            <StatusDot tone="error" label="Error" />
          ) : (
            <StatusDot tone="idle" label="Idle" />
          )
        }
      />

      <textarea
        value={taskText}
        onChange={(event) => onTaskText(event.target.value)}
        rows={3}
        className="console-input resize-none text-[12.5px] leading-relaxed"
        placeholder="Describe a task for the Neural Core …"
        aria-label="Task description"
      />

      <label className="flex items-center gap-2 text-xs text-slate-400 mt-2.5 cursor-pointer">
        <input
          type="checkbox"
          checked={isComplex}
          onChange={(event) => onComplex(event.target.checked)}
          className="accent-cyan-400"
        />
        Complex workflow <span className="text-slate-600">(urgency wrapping)</span>
      </label>

      <button
        onClick={onRun}
        disabled={isRunning || !taskText.trim()}
        className="primary-button w-full mt-3"
      >
        {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
        {isRunning ? "Routing through core …" : "Run through Neural Core"}
      </button>

      <div
        className={`mt-3 rounded-xl border p-3 min-h-[96px] ${
          runState === "error"
            ? "border-rose-400/20 bg-rose-500/[0.05]"
            : "border-white/[0.07] bg-black/25"
        }`}
        aria-live="polite"
      >
        <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em]">
          {runState === "error" ? (
            <>
              <AlertTriangle className="w-3 h-3 text-rose-400" />
              <span className="text-rose-300">Response · Error</span>
            </>
          ) : runState === "success" ? (
            <>
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-emerald-300">Response · Ok</span>
            </>
          ) : (
            <span className="text-cyan-300">Response</span>
          )}
        </p>
        <p
          className={`text-[12px] mt-1.5 break-words leading-relaxed ${
            runState === "error" ? "text-rose-200" : "text-slate-300"
          }`}
        >
          {result}
        </p>
      </div>

      <p className="mt-auto pt-3 text-[10px] text-slate-600 font-mono truncate">API · {apiUrl}</p>
    </Tile>
  );
}

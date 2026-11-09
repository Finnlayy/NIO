import React from "react";

interface StopButtonProps {
  onStop: () => void;
  active: boolean;
}

export function EmergencyStopButton({ onStop, active }: StopButtonProps) {
  return (
    <button
      onClick={onStop}
      className={`fixed bottom-24 right-6 flex items-center justify-center gap-2 rounded border px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wider transition-colors z-50 ${
        active
          ? "border-rose-400 bg-rose-500/20 text-rose-300 shadow-[0_0_15px_rgba(244,63,94,0.3)] hover:bg-rose-500/30 hover:shadow-[0_0_20px_rgba(244,63,94,0.5)]"
          : "border-slate-700 bg-slate-800/50 text-slate-400 hover:bg-slate-700 hover:text-slate-300"
      }`}
    >
      <span className="h-2 w-2 rounded-full bg-current animate-pulse"></span>
      Emergency Stop
    </button>
  );
}

"use client";

import type { CodyMood } from "@/lib/manifest-types";
import { moodLabel } from "./cody-mood";

const moodColors: Record<CodyMood, string> = {
  offline: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  idle: "bg-amber-500/10 text-amber-200 border-amber-500/25",
  listening: "bg-cyan-500/10 text-cyan-200 border-cyan-500/25",
  thinking: "bg-amber-500/15 text-amber-100 border-amber-400/40",
  working: "bg-amber-500/20 text-amber-100 border-amber-400/50",
  alert: "bg-rose-500/15 text-rose-200 border-rose-500/30",
  celebrating: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
};

export default function CodyMoodBadge({ mood }: { mood: CodyMood }) {
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${moodColors[mood]}`}>
      {moodLabel(mood)}
    </span>
  );
}

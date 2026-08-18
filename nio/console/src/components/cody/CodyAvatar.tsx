"use client";

import { motion } from "framer-motion";
import type { CodyMood } from "@/lib/manifest-types";

const moodStyles: Record<CodyMood, { ring: string; glow: string }> = {
  offline: { ring: "border-slate-600", glow: "shadow-none" },
  idle: { ring: "border-amber-400/40", glow: "shadow-amber-500/20" },
  listening: { ring: "border-cyan-400/60", glow: "shadow-cyan-500/25" },
  thinking: { ring: "border-amber-300", glow: "shadow-amber-400/40" },
  working: { ring: "border-amber-400", glow: "shadow-amber-500/35" },
  alert: { ring: "border-rose-400", glow: "shadow-rose-500/35" },
  celebrating: { ring: "border-emerald-400", glow: "shadow-emerald-500/30" },
};

export default function CodyAvatar({
  mood,
  size = 64,
  open = false,
  onPointerDown,
  onPointerMove,
  onPointerUp,
}: {
  mood: CodyMood;
  size?: number;
  open?: boolean;
  onPointerDown?: (e: React.PointerEvent<HTMLButtonElement>) => void;
  onPointerMove?: (e: React.PointerEvent<HTMLButtonElement>) => void;
  onPointerUp?: (e: React.PointerEvent<HTMLButtonElement>) => void;
}) {
  const style = moodStyles[mood];
  const shake = mood === "alert";

  return (
    <motion.button
      type="button"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      aria-label={open ? "Close Cody" : "Open Cody"}
      aria-expanded={open}
      className={`relative rounded-full border-2 grid place-items-center bg-gradient-to-br from-amber-500/20 to-cyan-500/10 touch-none ${style.ring} ${style.glow} shadow-lg cursor-pointer`}
      style={{ width: size, height: size }}
      animate={shake ? { x: [0, -2, 2, -2, 0] } : { y: [0, -4, 0] }}
      transition={
        shake
          ? { duration: 0.4, repeat: mood === "alert" ? Infinity : 0, repeatDelay: 3 }
          : { duration: 4, repeat: Infinity, ease: "easeInOut" }
      }
    >
      <span className="text-2xl select-none pointer-events-none" aria-hidden>
        ⚡
      </span>
      {mood === "thinking" ? (
        <span className="absolute inset-0 rounded-full border border-amber-300/50 cody-think-ring pointer-events-none" />
      ) : null}
      {mood === "working" ? (
        <span
          className="absolute -inset-1 rounded-full border border-dashed border-amber-400/30 animate-spin pointer-events-none"
          style={{ animationDuration: "8s" }}
        />
      ) : null}
    </motion.button>
  );
}

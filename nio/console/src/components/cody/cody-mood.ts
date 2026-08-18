import type { CodyMood, CodyStats, CodySupervisorStatus } from "@/lib/manifest-types";

export function deriveCodyMood(
  stats: CodyStats | null,
  supervisor: CodySupervisorStatus | null,
  opts?: { thinking?: boolean; listening?: boolean; celebrating?: boolean },
): CodyMood {
  if (opts?.thinking) return "thinking";
  if (!stats?.online && !supervisor?.nioHealthy) return "offline";
  if ((supervisor?.gateFailuresRecent ?? 0) > 0) return "alert";
  if (opts?.celebrating) return "celebrating";
  if ((supervisor?.activeLimbCount ?? 0) > 0) return "working";
  if (opts?.listening) return "listening";
  return "idle";
}

export function moodLabel(mood: CodyMood): string {
  const labels: Record<CodyMood, string> = {
    offline: "Offline",
    idle: "Idle",
    listening: "Listening",
    thinking: "Thinking",
    working: "Working",
    alert: "Alert",
    celebrating: "Done",
  };
  return labels[mood];
}

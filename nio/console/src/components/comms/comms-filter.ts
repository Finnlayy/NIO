import type { FormattedInterAgentLine } from "@/lib/manifest-types";

export type CommsChannelFilter = "all" | "atlas" | "cody" | "you" | "limbs";
export type CommsSeverityFilter = "all" | "info" | "success" | "warning" | "error";

const ACTOR_ATLAS = new Set(["Atlas", "orchestrator"]);
const ACTOR_CODY = new Set(["Cody", "cody"]);
const ACTOR_YOU = new Set(["You", "user"]);
const ACTOR_LIMBS = new Set(["Limb", "limb", "Subagent", "subagent"]);

/** Mirror backend isUserVisibleInterAgentMessage using formatted actor labels. */
export function isRelevantLine(line: FormattedInterAgentLine): boolean {
  if (line.isUserVisible === true) return true;
  if (line.isUserVisible === false) return false;

  const to = line.actors.to;
  if (ACTOR_CODY.has(to) || ACTOR_YOU.has(to)) return true;
  if (line.type === "approval_request") return true;
  if (line.severity === "warning" || line.severity === "error") return true;
  return false;
}

export function hasExtendedApiFields(lines: FormattedInterAgentLine[]): boolean {
  return lines.some((l) => l.isUserVisible !== undefined || l.type !== undefined);
}

export function filterByScope(
  lines: FormattedInterAgentLine[],
  scope: "relevant" | "all",
): FormattedInterAgentLine[] {
  if (scope === "all") return lines;
  return lines.filter(isRelevantLine);
}

export function filterByChannel(
  lines: FormattedInterAgentLine[],
  channel: CommsChannelFilter,
): FormattedInterAgentLine[] {
  if (channel === "all") return lines;
  return lines.filter((line) => {
    const { from, to } = line.actors;
    switch (channel) {
      case "atlas":
        return ACTOR_ATLAS.has(from) || ACTOR_ATLAS.has(to);
      case "cody":
        return ACTOR_CODY.has(from) || ACTOR_CODY.has(to);
      case "you":
        return ACTOR_YOU.has(from) || ACTOR_YOU.has(to);
      case "limbs":
        return ACTOR_LIMBS.has(from) || ACTOR_LIMBS.has(to);
      default:
        return true;
    }
  });
}

export function filterBySeverity(
  lines: FormattedInterAgentLine[],
  severity: CommsSeverityFilter,
): FormattedInterAgentLine[] {
  if (severity === "all") return lines;
  return lines.filter((l) => l.severity === severity);
}

export function filterBySearch(lines: FormattedInterAgentLine[], query: string): FormattedInterAgentLine[] {
  const q = query.trim().toLowerCase();
  if (!q) return lines;
  return lines.filter(
    (l) =>
      l.headline.toLowerCase().includes(q) ||
      l.body.toLowerCase().includes(q) ||
      l.actors.from.toLowerCase().includes(q) ||
      l.actors.to.toLowerCase().includes(q),
  );
}

export function applyCommsFilters(
  lines: FormattedInterAgentLine[],
  opts: {
    scope: "relevant" | "all";
    channel: CommsChannelFilter;
    severity: CommsSeverityFilter;
    search: string;
  },
): FormattedInterAgentLine[] {
  let result = filterByScope(lines, opts.scope);
  result = filterByChannel(result, opts.channel);
  result = filterBySeverity(result, opts.severity);
  result = filterBySearch(result, opts.search);
  return result;
}

export function countRelevantUnread(
  lines: FormattedInterAgentLine[],
  readAt: string | null,
): number {
  const relevant = filterByScope(lines, "relevant");
  if (!readAt) return relevant.length;
  return relevant.filter((l) => l.timestamp > readAt).length;
}

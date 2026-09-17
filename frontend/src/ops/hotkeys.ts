/** Ops-grid shortcuts. Pure so the harness can assert them without a DOM. */

const FORM_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

export function isTypingTarget(target: EventTarget | null): boolean {
  if (target == null || typeof target !== "object") return false;
  const el = target as { tagName?: string; isContentEditable?: boolean };
  if (typeof el.tagName !== "string") return false;
  return FORM_TAGS.has(el.tagName) || Boolean(el.isContentEditable);
}

export type OpsHotkey = "toggle-console" | "toggle-gallery" | "close-panels" | null;

export function opsHotkey(e: {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
}): OpsHotkey {
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  const mod = e.metaKey || e.ctrlKey;
  if (mod && key === "k") return "toggle-console";
  if (mod && key === "g") return "toggle-gallery";
  if (key === "Escape") return "close-panels";
  return null;
}

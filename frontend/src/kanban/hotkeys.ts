import { isTypingTarget } from "@/ops/hotkeys";

export type KanbanHotkeyResult = "new-card" | "save" | "close-menu" | "close-dialog" | null;

export function kanbanHotkey(
  e: {
    key: string;
    metaKey: boolean;
    ctrlKey: boolean;
    altKey?: boolean;
    shiftKey?: boolean;
    repeat?: boolean;
    isComposing?: boolean;
    target: EventTarget | null;
  },
  ctx: {
    dialogOpen: boolean;
    menuOpen: boolean;
  }
): KanbanHotkeyResult {
  // Keys pressed while an IME composes text (incl. Escape to cancel it) belong to the IME.
  if (e.isComposing) return null;

  const isEscape = e.key === "Escape";
  const isEnter = e.key === "Enter";
  const isC = e.key.toLowerCase() === "c";
  const mod = e.metaKey || e.ctrlKey;
  const anyMod = e.metaKey || e.ctrlKey || e.altKey;

  // Escape handlers
  if (isEscape) {
    if (ctx.menuOpen) return "close-menu";
    if (ctx.dialogOpen) return "close-dialog";
    return null;
  }

  // Save handler: mod + Enter, but ONLY when dialogOpen
  if (isEnter && mod && ctx.dialogOpen) {
    return "save";
  }

  // new-card handler: 'c' without modifiers, not repeating, not typing, not composing, no dialog/menu open
  if (
    isC &&
    !anyMod &&
    !e.repeat &&
    !e.isComposing &&
    !isTypingTarget(e.target) &&
    !ctx.dialogOpen &&
    !ctx.menuOpen
  ) {
    return "new-card";
  }

  return null;
}

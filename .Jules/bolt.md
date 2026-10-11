## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2026-10-11 - Global Keyboard Handlers vs. Local Component State
**Learning:** Local component state (like `useState` for dropdown menus) cannot be easily closed by global hotkeys (like 'Escape') handled at the page/window level without resorting to messy DOM traversal or event bubbling tricks.
**Action:** Lift local open-states for modals, menus, and drawers into a centralized global store (e.g., `activeMenuId` in Zustand). This allows a single global keyboard event handler to deterministically dispatch a "close all" action, guaranteeing full keyboard traversability and escaping capability.

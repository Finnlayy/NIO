## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-04 - Mod+K Event Collision
**Learning:** A keyboard event collision pattern occurred between modal dialogs (MCP Console globally toggled via `Mod+K`) and canvas tools (Dashboard Search input also listening for `Mod+K`).
**Action:** Use `/` exclusively for focusing the dashboard search input and reserve `Mod+K` globally for toggling the MCP Console to prevent event collisions and unpredictable behavior.

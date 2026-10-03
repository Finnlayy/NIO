## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.
## 2024-10-03 - Search Input vs Global Shortcut Collision
**Learning:** Attaching a `keydown` listener that indiscriminately steals modifier+key keystrokes (like `mod+k` for a search input) will collide with centralized global hotkeys intended for modal toggles (like the MCP console).
**Action:** Remove conflicting local shortcuts on input wrappers that replicate or overwrite dedicated global app shortcuts, and reserve single-key triggers like `/` for focusing search exclusively.

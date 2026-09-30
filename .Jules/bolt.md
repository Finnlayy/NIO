## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2026-09-30 - Keyboard Event Collision in Header Search
**Learning:** A keyboard event collision was discovered between the global MCP Console hotkey (`mod+k`) and the local search input focus shortcut in the dashboard header. Both actions were triggering simultaneously, showing the console and focusing search.
**Action:** Removed the `mod+k` shortcut from the header's local keydown listener, resolving the collision. Search is now exclusively accessed via the `/` key, ensuring deterministic shortcut layouts across modules.

## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-14 - Mod+K Collision Avoidance
**Learning:** In the Next.js frontend, `Mod+K` is reserved globally for toggling the MCP Console, but the `Header` component was intercepting it to focus the dashboard search input, causing an event collision.
**Action:** Removed `Mod+K` local listener from the `Header` component, and instead use `/` exclusively for focusing the dashboard search input to prevent global keyboard shortcut collisions with the MCP Console.

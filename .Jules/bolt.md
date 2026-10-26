## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.
## 2026-10-26 - Task Dispatch Ergonomics
**Learning:** Users currently have to manually focus the task input to dispatch via Cmd/Ctrl+Enter, creating an operational friction in multi-monitor and fast workflow setups.
**Action:** Implemented a global window event listener with an `isTypingTarget` guard and a `useRef` hook to bind hotkeys efficiently without trapping keystrokes across the application. Now the shortcut triggers globally.

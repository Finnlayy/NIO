## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2025-03-02 - Global Workflow Dispatch Shortcut
**Learning:** Manual focus requirements for task execution cause workflow friction and increase mouse travel, while scoping keydown listeners to textareas traps users when working across multiple panels.
**Action:** Expose context-independent global workflows (e.g., dispatching tasks via `Cmd/Ctrl+Enter`) using top-level `useEffect` keyboard listeners attached to `window`, rather than scoped `onKeyDown` input handlers. Always guard these global listeners with `isTypingTarget(document.activeElement)` to suppress triggers when the user is focused inside generic text fields, unless intentionally scoped to a specific field.

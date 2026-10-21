## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-21 - Global Shortcut Collision & Workflow Dispatch Patterns
**Learning:** Global hotkeys can collide when generic patterns (like mod+k) are used locally, disrupting core navigation. Additionally, requiring manual focus to execute workflows with keyboard shortcuts causes unnecessary friction for power users.
**Action:** Reserve global combinations exclusively for top-level interactions and avoid local overrides. To enable context-independent global workflows without manual focusing, expose them using top-level `useEffect` keyboard listeners attached to the window, rather than scoped `onKeyDown` handlers on specific text areas.

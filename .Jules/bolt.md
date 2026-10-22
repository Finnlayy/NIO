## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-22 - Global Keyboard Handlers for Task Dispatching
**Learning:** Attaching `onKeyDown` listeners to specific text areas requires the user to have focus on that specific element to trigger shortcuts, creating friction.
**Action:** Context-independent global workflows (like dispatching tasks via `Cmd/Ctrl+Enter`) should use top-level `useEffect` keyboard listeners attached to `window` rather than scoped `onKeyDown` input handlers on specific text areas. Ensure to store the latest state and callbacks in `useRef` hooks rather than adding them to the `useEffect` dependency array, which prevents the listener from being inefficiently removed and re-attached on every render/keystroke.

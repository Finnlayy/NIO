## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-24 - Context-independent Global Workflows & Focus Management
**Learning:** Attaching execution shortcuts (like `Cmd/Ctrl+Enter` to dispatch tasks) as local `onKeyDown` handlers on specific inputs forces users to manually click or Tab into the input to trigger the workflow, slowing down high-frequency execution.
**Action:** Implement context-independent global workflows using top-level `useEffect` keydown listeners on `window`. Always guard these global listeners with `isTypingTarget(document.activeElement)` to suppress triggers when typing in unrelated fields, while explicitly scoping an exception for the relevant field (e.g. `document.activeElement !== textAreaRef.current`). Store state/callbacks in `useRef` hooks to prevent listener churn.

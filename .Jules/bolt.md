## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-25 - Global Task Dispatch & Menu Escape Hierarchy
**Learning:** Scoped `onKeyDown` handlers require manual user focus, reducing workflow speed. Separately, local modal/dropdown state (`useState`) breaks the centralized hierarchical `Escape` closing order (e.g., closing a dropdown before closing a global panel).
**Action:** Expose context-independent global workflows (like task dispatch) via top-level `useEffect` `window` event listeners. Store frequently updating state in `useRef` to avoid stale closures. Manage active localized UI (e.g., dropdowns) in global stores (`activeMenuId`), so global key handlers can correctly process hierarchical shutdown loops.

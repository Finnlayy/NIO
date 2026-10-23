## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2026-10-23 - Global Task Dispatch Shortcut using window.addEventListener
**Learning:** To eliminate manual focus requirements on text areas for globally accessible commands, attach the event listener to the `window` object instead of using scoped `onKeyDown` input handlers.
**Action:** Expose context-independent global workflows using top-level `useEffect` keyboard listeners attached to `window`. Use `useRef` to store the latest state and callback references so that the effect does not need to repeatedly re-bind on every keystroke. Always use `isTypingTarget` to suppress triggers when the user is focused inside text fields, unless intentionally scoped (e.g., checking if `document.activeElement` matches a specific `textAreaRef`).

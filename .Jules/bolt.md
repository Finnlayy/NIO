## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-11-20 - React Performance Pattern: Module-Level Constants for Static Data
**Learning:** Calculating derived state from static configuration (like static imports) using React's `useMemo` with an empty dependency array (`[]`) incurs unnecessary React hook overhead and redundant static calculation upon component mount.
**Action:** Extract derivations entirely outside the component as module-level constants to eliminate React hook overhead and redundant calculations.

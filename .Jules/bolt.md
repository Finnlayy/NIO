## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-19 - React Hook Overhead for Static Data
**Learning:** When calculating derived data from static frontend configurations (e.g., `networkNodes`), using React's `useMemo` with an empty dependency array inside components incurs unnecessary hook overhead and redundant evaluation upon mount.
**Action:** Extract these static derivations entirely outside the component as module-level constants to eliminate the React hook overhead and ensure they are calculated exactly once when the module loads.

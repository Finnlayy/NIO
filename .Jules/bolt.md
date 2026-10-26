## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2026-10-26 - Static Derivations and Hook Overhead
**Learning:** Using `useMemo` hooks with empty dependency arrays to calculate derived states from purely static external configurations (e.g., imported constants) introduces unnecessary React hook overhead and redundant initial evaluations on component mount.
**Action:** Extract all purely static derivations out of React components entirely and move them to module-level constants to eliminate component lifecycle overhead.

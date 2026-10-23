## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-11-23 - Static Data Derivation Optimization
**Learning:** Using `useMemo` with empty dependency arrays inside components for calculating derived data from static configurations (e.g., `networkNodes`) incurs unnecessary React hook overhead and initialization on mount.
**Action:** Extract derivations from static frontend configurations entirely outside the component as module-level constants to eliminate React hook overhead and redundant calculations.

## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2026-10-21 - Extract static derivations from useMemo
**Learning:** When calculating derived data from static frontend configurations (e.g., `networkNodes`), avoiding `useMemo` with empty dependency arrays inside components entirely eliminates React hook overhead and redundant calculations.
**Action:** Extract the derivation entirely outside the component as a module-level constant (e.g. `NODE_BY_ID = Object.fromEntries(...)`) to save component lifecycle execution time and lower hook memory footprint.

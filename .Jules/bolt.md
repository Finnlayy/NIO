## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-18 - Extracted Static Derivations from React Components
**Learning:** When calculating derived data from static frontend configurations (like networkNodes), using useMemo with empty dependency arrays inside components incurs unnecessary React hook overhead and redundant evaluation across component instances.
**Action:** Extract the derivation entirely outside the component as a module-level constant to eliminate React hook overhead and redundant calculations.

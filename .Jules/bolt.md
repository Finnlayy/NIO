## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-11-20 - Extract Static Derivations to Eliminate React Hook Overhead
**Learning:** When calculating derived data from static frontend configurations (e.g., `networkNodes`), using React's `useMemo` with an empty dependency array inside components incurs unnecessary React hook overhead and redundant evaluation upon initial component mount.
**Action:** Extract the derivation entirely outside the component as a module-level constant to eliminate React hook overhead and ensure the computation happens exactly once at module load time.

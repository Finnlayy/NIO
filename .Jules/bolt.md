## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2026-10-20 - [React Performance: Static Derivations]
**Learning:** Moving derivations (`nodeById`, `activeDomainCount`, `agentCount`) that rely solely on static configurations out of React component closures completely avoids hook execution overhead during renders, whereas `useMemo` with empty dependency arrays still incurs initialization/evaluation cost on mount.
**Action:** Lift derived static structures outside of React components entirely when they don't depend on React state or props.

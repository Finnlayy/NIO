## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.
## 2026-09-09 - React Render Loop Write-Amplification
**Learning:** Computing heavy nested filters and object derivations directly inside a React component (like DomainsGrid computing nodes, topics, and links per domain) triggers an expensive  execution on every re-render, creating CPU spikes even when underlying static data hasn't changed.
**Action:** When component properties are derived from static configurations, extract the calculation into a module-level constant instead of keeping it in the render loop or relying on useMemo.

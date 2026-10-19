## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-19 - Global State for Local Dropdowns
**Learning:** Local `useState` for dropdown menus (like widget options) breaks global hotkey management (like Escape) because the global handler cannot access the localized state to dismiss it, leading to redundant local listeners and event collisions.
**Action:** Lift dropdown open-states into a global store (e.g., `activeMenuId`) to enable centralized keyboard handlers to deterministically evaluate and close menus before closing parent panels, while utilizing strict equality selectors (e.g., `s.activeMenuId === widget.id`) within components to avoid excessive re-renders.

## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-17 - Global Escape Shortcut for Widget Menus
**Learning:** Local widget dropdown menus were using local `useState` for their open state, which prevented a centralized global 'Escape' hotkey handler from easily closing them without resorting to prop-drilling or un-ergonomic focus tricks.
**Action:** Lift the dropdown menu open state into a global store (e.g., Zustand `activeMenuId`). Use strict equality selectors inside components to prevent widespread re-renders, allowing the global hotkey handler to reliably dismiss open dropdown menus without losing focus context or capturing input indiscriminately.

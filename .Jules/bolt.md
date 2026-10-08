## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2025-02-12 - Global Esc Handler for Local Widget Menus
**Learning:** Dropdown menus built with local state (`useState`) fail to integrate with centralized global hotkeys like `close-panels` (Escape). This leads to broken keyboard ergonomics where users cannot dismiss menus without clicking outside. Furthermore, missing `focus-visible` rings on widget buttons degrade keyboard traversal confidence.
**Action:** Lift dropdown open-states into the global Zustand store (`activeMenuId`) so the centralized `opsHotkey` listener can dismiss them. Use strict equality selectors (`s.activeMenuId === widget.id`) to prevent global re-renders. Ensure interactive elements like `IconBtn` and `MenuItem` include explicit `focus-visible:ring-2` styles.

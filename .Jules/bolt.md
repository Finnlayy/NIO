## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-15 - Global Escape for Localized Widget Menus
**Learning:** Localized widget menus (like dropdown options) managed by local component state cannot be consistently dismissed by global keyboard shortcuts (like `Escape`), creating poor keyboard ergonomics and state traps.
**Action:** Lift the localized widget menu open-state into the global store (`activeMenuId`). This allows centralized global shortcut handlers (like `opsHotkey`) to effectively clear the state and dismiss the menu, guaranteeing full keyboard traversal.

## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-12 - Ergonomic Escape-to-Close for Dropdown Menus
**Learning:** Localized dropdown menus using local `useState` for their open state fail to respond to a globally centralized Escape hotkey handler, leaving the user with orphaned open menus unless clicked away or relying on bad-practice localized `keydown` listeners.
**Action:** Lift the open-state of localized dropdown menus into a global store (e.g., Zustand `activeMenuId`) to allow centralized global shortcuts like `close-panels` to clear them, while maintaining granular strict-equality selectors within the component to prevent widespread re-renders.

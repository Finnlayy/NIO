## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2024-10-16 - Mod+K Collision and Reserved Global Scope
**Learning:** Mod+K was mapped in `Header.tsx` as a fallback search input hotkey, colliding with the globally-reserved Mod+K binding used for the MCP Console toggle, which is managed via `opsHotkey`. Overlapping global shortcuts break determinism and steal context depending on component mount order.
**Action:** Use `/` exclusively to focus the dashboard search input. Mod+K must remain universally reserved across the application solely for opening the Command/MCP Console to preserve muscle memory and prevent collision bugs.


## 2024-09-23 - Modal Dialog Keyboard Ergonomics
**Learning:** Redundant local `Escape` listeners in modals can circumvent global hotkey managers that employ focus checking (like `isTypingTarget`), indiscriminately stealing keystrokes.
**Action:** Remove local `Escape` listeners inside modal components when a robust global hotkey handler exists. Ensure modals are accessible by adding `role="dialog"`, `aria-modal="true"`, and `autoFocus` to guarantee immediate keyboard traversability and context preservation.

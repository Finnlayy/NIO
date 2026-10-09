## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2025-01-01 - Disabled Button Accessibility and Layout Stability
**Learning:** Using the native `disabled` attribute on buttons swallows keyboard focus, breaking standard accessibility traversal. Furthermore, conditionally rendering internal structural elements like keyboard shortcut hints (`<kbd>`) across different button states causes unintended visual layout shifts.
**Action:** Replace `disabled` with `aria-disabled="true"` to preserve focusability, handle click prevention via JS `onClick` guards, and update corresponding CSS (`[aria-disabled="true"]` instead of `:disabled`). Ensure internal structural elements within conditional button content are rendered consistently regardless of state.

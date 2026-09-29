## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2024-03-22 - Disabled Button Focus Accessibility
**Learning:** Natively disabled buttons swallow keyboard focus and drop out of the tab order completely. This creates an accessibility "black hole" where keyboard-only and screen-reader users cannot discover the button or understand why an action is unavailable.
**Action:** When a button is conditionally disabled, wrap it in a standard focusable element (e.g., `<div tabIndex={0} title="...">`) to preserve its place in the tab order and provide context for the disabled state via the title or aria attributes.

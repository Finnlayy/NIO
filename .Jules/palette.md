## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2025-03-04 - Disabled Buttons Accessibility & Ergonomics
**Learning:** Using the native `disabled` attribute on buttons prevents them from receiving keyboard focus and suppresses mouse events (like hover tooltips), making it difficult for users to understand *why* the button is disabled.
**Action:** Replace `disabled` with `aria-disabled="true"`, add a helpful `title` or tooltip explaining the state, manually guard the `onClick` handler, and update CSS to correctly target `[aria-disabled="true"]` for both disabled styling and preventing hover states.

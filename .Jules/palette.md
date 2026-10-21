## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2023-10-21 - Disabled State Tooltip Accessibility
**Learning:** Native `disabled` attributes on buttons swallow pointer events entirely in some browsers, preventing helpful `title` attributes (tooltips) from appearing when users hover over them to find out *why* a button is disabled.
**Action:** Replace `disabled` attributes with `aria-disabled="true"` to maintain screen-reader correctness while keeping the element active for pointer events (allowing tooltips to show). Always accompany this with an explicit `onClick` guard and update CSS selectors (e.g., `:disabled` to `:disabled, [aria-disabled="true"]` and `:not(:disabled)` to `:not(:disabled):not([aria-disabled="true"])`).

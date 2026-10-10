## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2026-09-13 - Disabled Button Tooltips and Keyboard Focus
**Learning:** Native `disabled` attributes completely remove elements from the browser focus order and swallow pointer events, making it impossible to provide helpful tooltips or explanations to screen reader and keyboard-only users about why an action is unavailable.
**Action:** For complex web apps, replace `disabled` with `aria-disabled="true"` on buttons, manually guard the `onClick` handler with `e.preventDefault()`, and provide an explanatory `title`. Ensure CSS rules (like hover states) exclude `[aria-disabled="true"]`, while applying the disabled visual styles to it.

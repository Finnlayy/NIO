## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2023-10-25 - Accessibility of Disabled Buttons
**Learning:** Disabled `<button>` elements naturally swallow focus, making them invisible to keyboard navigation and screen readers. Users navigating via keyboard are often left with no context as to why an action is unavailable.
**Action:** When disabling buttons, wrap them in a standard element like a `<div tabIndex={0} title="...">`. Apply `pointer-events-none` to the button to allow the wrapper to handle tooltips and focus, ensuring context is provided to all users.

## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2026-09-27 - Disabled Button Accessibility
**Learning:** Native `<button disabled>` elements naturally swallow focus, meaning screen readers and keyboard users cannot easily navigate to them to read their `title` attribute or understand why an action is blocked. This applies across any interactive component relying on a native `disabled` attribute.
**Action:** When creating disabled action buttons (like form submissions or start triggers), dynamically wrap the disabled button in a `div` with `tabIndex={0}` and a descriptive `title` attribute explaining the blocked state to ensure full keyboard traversability and context.

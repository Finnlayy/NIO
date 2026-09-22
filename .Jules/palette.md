## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.
## 2026-09-12 - Aria-Pressed on Toggle Buttons
**Learning:** Screen readers need explicit state indicators for components that function as toggle buttons.
**Action:** Always add `aria-pressed={isActive}` to `<button>` elements that act as toggles, and accompany them with `focus-visible` styling to ensure full accessibility for keyboard and screen reader users.

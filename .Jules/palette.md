## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.
## 2023-10-25 - Using `aria-disabled` to Preserve Focus and Tooltips
**Learning:** Native `disabled` attributes on buttons strip them from the accessibility tree in some screen readers and suppress browser hover events, preventing tooltips (`title`) from rendering to explain *why* the button is disabled.
**Action:** Replace `disabled={condition}` with `aria-disabled={condition}` and a dynamic `title` tooltip. Manually guard the `onClick` handler (`onClick={condition ? undefined : handler}`) and update CSS to target `[aria-disabled="true"]` (and exclude it from hover styles) to ensure disabled elements remain focusable, discoverable, and self-documenting.

## 2023-10-25 - Responsive Icon-Only Button Names
**Learning:** Using `hidden sm:inline` to hide text within a button on small viewports can unintentionally remove the accessible name for screen readers when viewed on mobile, leaving them as icon-only buttons with no label.
**Action:** Always add a screen-reader-only sibling span that renders only when the main text is hidden (e.g., `<span className="sr-only sm:hidden">Action Name</span>`) or set an explicit `aria-label` on the parent button.

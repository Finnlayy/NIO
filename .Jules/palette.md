## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2026-09-12 - Accessibility Polish: Focus States & Live Regions
**Learning:** Live activity feeds that update dynamically (like our ActivityFeed stream) are invisible to screen readers without an `aria-live` region. Additionally, disabled buttons lack inherent tooltips for keyboard users, and interactive filter tabs require explicit `aria-pressed` states and `focus-visible` styling to be navigable and semantically correct.
**Action:** Always wrap dynamically updating lists in `role="log"` with `aria-live="polite"`. Add explicit `focus-visible` outline classes to all interactive UI components, and wrap disabled buttons in standard elements like a `div` to pass through `title` explanations effectively.

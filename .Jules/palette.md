## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.
## 2026-10-17 - Dynamic Logs Accessibility
**Learning:** The activity feed in the dashboard lacked proper ARIA attributes to notify screen readers when new events were added, making the dynamic feed effectively invisible to assistive technology.
**Action:** Always wrap dynamically updating lists like logs or feeds in a container with `role="log"` and `aria-live="polite"` so screen readers can announce new content as it arrives without interrupting the user.

## 2024-03-24 - Centralize Modal Escape Shortcuts
**Learning:** Redundant local 'Escape' keydown listeners inside modals bypass centralized global hotkey handlers and indiscriminately steal keystrokes, breaking context and usability boundaries.
**Action:** Remove local modal Escape key listeners when a global handler exists. Always implement `role="dialog"`, `aria-modal="true"`, and an `autoFocus` target in modals for immediate keyboard traversability.

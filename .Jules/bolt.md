## 2026-09-08 - Keyboard Shortcuts for Core Menus
**Learning:** Operators were manually clicking to toggle the MCP Console and Template Gallery, slowing down rapid workspace configurations.
**Action:** Implemented `mod+k` for MCP Console and `mod+g` for Gallery via `react-hotkeys-hook` with `enableOnFormTags: false`, plus Escape to close modals, and added visible `<kbd>` badges to action buttons.

## 2026-09-12 - IPC/API Integration Insight
**Learning:** Running python scripts inside module packages dynamically (e.g. `Architect/limbs/telemetry_feed.py`) while manipulating `sys.path` can cause local package folders (e.g. `Architect/limbs/math`) to shadow Python standard libraries (`math`). This breaks common dependencies like `numpy`.
**Action:** Renamed `Architect/limbs/math` to `Architect/limbs/math_engines` and updated imports. Avoid using names that collide with python standard libraries.

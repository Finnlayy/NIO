"""Start: python -m world_bridge (uvicorn loopback :8750)."""
from __future__ import annotations
import os
import uvicorn
from .live import build_live_adapter
from .shadow import build_shadow_adapter
from .bridge import build_bridge_from_env


def main() -> None:
    api_url = os.environ.get("NIO_KANBAN_API_URL", "http://127.0.0.1:8740")
    token = os.environ.get("NIO_KANBAN_API_TOKEN", "")
    adapters = {"live": build_live_adapter(api_url, token)}
    if os.environ.get("NIO_SHADOW_BOARD_ID"):
        adapters["shadow"] = build_shadow_adapter(api_url, token)
    bridge = build_bridge_from_env(adapters)
    uvicorn.run(bridge.create_app(), host="127.0.0.1", port=int(os.environ.get("NIO_WORLD_PORT", "8750")))


if __name__ == "__main__":
    main()

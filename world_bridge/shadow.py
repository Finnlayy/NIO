"""Shadow-Welt-Adapter (T3): Shadow-Board (E1), Twin ~/NIN. Board-ID aus
NIO_SHADOW_BOARD_ID (Guide legt das Board an). Eigene Client-Instanz (D3)."""
from __future__ import annotations
import os
from .adapters import WorldAdapter, HttpKanbanClient

SHADOW_REPO = os.path.expanduser("~/NIN")


def build_shadow_adapter(api_url: str, token: str, board_id: str | None = None, client=None) -> WorldAdapter:
    bid = board_id or os.environ.get("NIO_SHADOW_BOARD_ID", "")
    if not bid:
        raise ValueError("NIO_SHADOW_BOARD_ID nicht gesetzt — Shadow-Board fehlt (E1)")
    return WorldAdapter("shadow", bid, SHADOW_REPO,
                        client or HttpKanbanClient(api_url, token))

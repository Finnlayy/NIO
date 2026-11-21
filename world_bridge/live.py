"""Live-Welt-Adapter (T4): Haupt-Board, ~/Projects/NIO."""
from __future__ import annotations
import os
from .adapters import WorldAdapter, HttpKanbanClient

LIVE_BOARD = "b-5fb62933ab27"
LIVE_REPO = os.path.expanduser("~/Projects/NIO")


def build_live_adapter(api_url: str, token: str, client=None) -> WorldAdapter:
    return WorldAdapter("live", LIVE_BOARD, LIVE_REPO,
                        client or HttpKanbanClient(api_url, token))

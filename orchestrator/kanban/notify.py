from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request
from typing import Protocol

from .config import KanbanConfig

__all__ = ["Notifier", "NullNotifier", "TelegramNotifier", "build_notifier"]


class Notifier(Protocol):
    async def alert(self, text: str) -> bool: ...


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, *, timeout_s: float = 10.0, api_base: str = "https://api.telegram.org") -> None:
        self.token = token
        self.chat_id = chat_id
        self.timeout_s = timeout_s
        self.api_base = api_base
        self.log = logging.getLogger(__name__)

    def _do_post(self, text: str) -> bool:
        url = f"{self.api_base}/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as response:
                if response.status == 200:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    return bool(resp_data.get("ok"))
                return False
        except Exception as e:
            # Mask URL/token in logging and fail silently
            safe_url = f"{self.api_base}/bot<MASKED>/sendMessage"
            self.log.warning("Telegram notification failed (url=%s): %s", safe_url, type(e).__name__)
            return False

    async def alert(self, text: str) -> bool:
        return await asyncio.to_thread(self._do_post, text)


class NullNotifier:
    async def alert(self, text: str) -> bool:
        return False


def build_notifier(config: KanbanConfig) -> Notifier:
    token = getattr(config, "telegram_token", None) or os.environ.get("NIO_KANBAN_TELEGRAM_TOKEN")
    chat_id = getattr(config, "telegram_chat_id", None) or os.environ.get("NIO_KANBAN_TELEGRAM_CHAT_ID")

    if token and chat_id:
        return TelegramNotifier(token=token, chat_id=chat_id)
    return NullNotifier()

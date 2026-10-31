"""Kleiner OpenAI-kompatibler Text-Client (Stdlib).

Bewusst nicht ``apollo/ciel``: der braucht pydantic und sendet immer Tools.
Fehlermeldungen enthalten weder den Key noch Request-Header.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from .config import TelegramConfig

__all__ = ["LLMError", "OpenAICompatTextLLM", "ScriptedTextLLM", "TextLLM", "llm_from_config", "no_redirect_opener"]

_BODY_MAX = 200


class LLMError(Exception):
    """LLM-Aufruf fehlgeschlagen; der Text ist frei von Secrets."""


class TextLLM(Protocol):
    async def complete(self, system: str, user: str) -> str: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def no_redirect_opener(*handlers: urllib.request.BaseHandler) -> urllib.request.OpenerDirector:
    """Opener ohne Redirects: ``urllib`` nimmt sonst Header wie ``Authorization`` mit."""
    return urllib.request.build_opener(_NoRedirect(), *handlers)


class OpenAICompatTextLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        *,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._opener = opener or no_redirect_opener().open

    def _redact(self, text: str) -> str:
        return text.replace(self._api_key, "***")[:_BODY_MAX]

    def _post(self, system: str, user: str) -> str:
        body = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.3,
        }
        request = urllib.request.Request(
            self._url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                # Der Default ``Python-urllib`` wird von Cloudflare-Gateways oft abgewiesen.
                "User-Agent": "neu-telegram/1.0",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            detail = exc.read(_BODY_MAX * 4).decode("utf-8", "replace")
            exc.close()
            raise LLMError(f"HTTP {exc.code}: {self._redact(detail)}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError(f"Verbindungsfehler: {type(exc).__name__}") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("Ungueltige LLM-Antwort") from None
        if not isinstance(content, str):
            raise LLMError("Ungueltige LLM-Antwort")
        return content

    async def complete(self, system: str, user: str) -> str:
        return await asyncio.to_thread(self._post, system, user)


class ScriptedTextLLM:
    """Test-Double: liefert ``replies`` der Reihe nach, Exceptions werden geworfen."""

    def __init__(self, replies: Sequence[str | Exception]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self._replies:
            raise LLMError("Keine Antworten mehr")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def llm_from_config(config: TelegramConfig) -> TextLLM | None:
    if not config.llm_configured:
        return None
    return OpenAICompatTextLLM(config.llm_base_url, config.llm_api_key, config.llm_model)

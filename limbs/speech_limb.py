"""Speech-Limb (Phase 7) -- Audio zu Text ueber das lokale speaches.

    Intent  ->  speech_limb  ->  HTTP (stdlib urllib)  ->  speaches auf 127.0.0.1

Die Erkennung bleibt kostenlos und lokal: Der Endpoint darf nur auf den eigenen
Rechner zeigen, sonst wird der Auftrag abgewiesen. Audio geht unveraendert an
speaches, weil der Dienst OGG, WebM und MP3 selbst dekodiert.

Faellt speaches aus, scheitert der Auftrag mit ``E_IO``. Ein Text wird nie
erfunden. Das Ergebnis ist Fremdinhalt und wird nie zu einer Anweisung oder
Freigabe.

Aufruf: ``python3 limbs/speech_limb.py --intent runtime/inbox/speech/<id>.json``
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

# Zwei Aufrufwege, ein Modul -- Begruendung steht in ``echo_limb.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(Path(__file__).resolve().parent), str(_REPO_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

if __package__ in (None, ""):  # direkter Skriptaufruf durch den Orchestrator
    from base import LimbBase, LimbContext, LimbError  # type: ignore[import-not-found]
else:  # Import als Paket (Tests, Tooling)
    from limbs.base import LimbBase, LimbContext, LimbError

from core.protocol import ErrorCode  # noqa: E402

DEFAULT_ENDPOINT = "http://127.0.0.1:8011/v1/audio/transcriptions"
DEFAULT_MODEL = "Systran/faster-whisper-small"
DEFAULT_LANGUAGE = "de"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
MAX_AUDIO_BYTES = 25_000_000
MAX_TEXT_CHARS = 12_000
PROBE_TIMEOUT_S = 2.0
TRANSCRIBE_TIMEOUT_S = 120.0
FALLBACK_VOCABULARY = "Apollo, NIO, Orchestrator, Kanban-Board, Limb."
AUDIO_TYPES = {
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".oga": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


# Ohne Proxy und ohne Weiterleitung: Ein Umweg wuerde die Audiodaten vom Rechner tragen.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def _endpoint() -> str:
    url = os.environ.get("STT_ENDPOINT_URL", "").strip() or DEFAULT_ENDPOINT
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in LOCAL_HOSTS:
        raise LimbError(
            ErrorCode.POLICY_DENIED,
            f"STT_ENDPOINT_URL zeigt nicht auf diesen Rechner: {parsed.hostname!r}",
            hint="Sprache bleibt lokal, siehe docs/SPEECH.md.",
        )
    return url


def _vocabulary(root: Path) -> str:
    try:
        return (root / "docs" / "knowledge" / "speech" / "vocabulary.txt").read_text(encoding="utf-8").strip() or FALLBACK_VOCABULARY
    except OSError:
        return FALLBACK_VOCABULARY


def _multipart(fields: Mapping[str, str], filename: str, content_type: str, audio: bytes) -> tuple[bytes, str]:
    boundary = f"neu-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
    )
    parts.extend((audio, f"\r\n--{boundary}--\r\n".encode()))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class SpeechLimb(LimbBase):
    name = "speech"
    version = "1.0.0"
    description = "Sprache zu Text ueber lokales speaches: speech.ping / speech.transcribe"

    def handlers(self) -> dict[str, Callable[[Mapping[str, Any], LimbContext], Mapping[str, Any]]]:
        return {
            "speech.ping": self._ping,
            "speech.transcribe": self._transcribe,
        }

    # ---------------------------------------------------------------- Handler
    def _ping(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        endpoint = _endpoint()
        request = urllib.request.Request(urllib.parse.urljoin(endpoint, "/health"), method="GET")
        try:
            with _OPENER.open(request, timeout=PROBE_TIMEOUT_S) as response:
                engine = "running" if response.status == 200 else "offline"
        except urllib.error.HTTPError as exc:
            exc.close()
            engine = "offline"
        except (urllib.error.URLError, TimeoutError):
            engine = "offline"
        return {"limb": self.name, "version": self.version, "engine": engine, "endpoint": endpoint}

    def _transcribe(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        endpoint = _endpoint()
        raw_path = params.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise LimbError(ErrorCode.SCHEMA_INVALID, "params.path fehlt.", hint='Beispiel: {"path": "audio/notiz.ogg"}')
        path = ctx.resolve(raw_path, must_exist=True)
        content_type = AUDIO_TYPES.get(path.suffix.lower())
        if content_type is None:
            raise LimbError(ErrorCode.SCHEMA_INVALID, f"Kein unterstuetztes Audioformat: {path.suffix!r}", hint=", ".join(sorted(AUDIO_TYPES)))
        if path.stat().st_size > MAX_AUDIO_BYTES:
            raise LimbError(ErrorCode.SCHEMA_INVALID, f"Audio ist groesser als {MAX_AUDIO_BYTES} Bytes.")

        ctx.plan("Audio an speaches senden", "Transkript pruefen")
        model = str(params.get("model") or os.environ.get("STT_MODEL", "").strip() or DEFAULT_MODEL)
        fields = {
            "model": model,
            "language": str(params.get("language") or os.environ.get("STT_LANGUAGE", "").strip() or DEFAULT_LANGUAGE),
            "prompt": _vocabulary(_REPO_ROOT),
            "response_format": "json",
            # Ohne Filter wiederholt Whisper bei Stille die Wortliste als angeblichen Text.
            "vad_filter": "true",
        }
        body, boundary_type = _multipart(fields, f"audio{path.suffix.lower()}", content_type, path.read_bytes())
        request = urllib.request.Request(endpoint, data=body, headers={"Content-Type": boundary_type}, method="POST")

        remaining = ctx.remaining_s()
        timeout = TRANSCRIBE_TIMEOUT_S if remaining is None else max(1.0, min(TRANSCRIBE_TIMEOUT_S, remaining - 1.0))
        try:
            with _OPENER.open(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            exc.close()
            raise LimbError(ErrorCode.IO, f"speaches antwortet mit HTTP {exc.code}.", hint="Modell geladen? Siehe docs/SPEECH.md.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LimbError(ErrorCode.IO, f"Sprach-Engine nicht erreichbar: {exc}", hint="speaches starten, siehe docs/SPEECH.md.") from exc
        ctx.finish_step("Audio an speaches senden")

        try:
            text = json.loads(raw)["text"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LimbError(ErrorCode.IO, "Antwort von speaches enthaelt kein Transkript.") from exc
        if not isinstance(text, str):
            raise LimbError(ErrorCode.IO, "Antwort von speaches enthaelt kein Transkript.")
        ctx.finish_step("Transkript pruefen")

        transcript = text.strip()[:MAX_TEXT_CHARS]
        return {"text": transcript, "empty": not transcript, "model": model, "untrusted": True}


if __name__ == "__main__":
    sys.exit(SpeechLimb().main())

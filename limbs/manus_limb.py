"""Manus-Limb (Phase 9) -- gehosteter Agent ueber die API v2, nur mit urllib.

SPERRE: Dieser Limb spricht derzeit nur mit einem Dienst auf diesem Rechner. Jeder
andere Host wird abgewiesen, bevor ein Byte das Haus verlaesst. Die Sperre faellt
erst mit den Freigabe-Tickets aus J4 und nach Key und Budget vom Menschen. Dann
wird ``_base_url`` geaendert und der Registereintrag auf ``active`` gesetzt.

Feste Vorgaben je Auftrag: keine Connectors, privat, Profil ``lite``, nicht
interaktiv. Der Aufrufer kann daran nichts aendern, ausser dem Text und der Sprache.

Vor dem Senden laeuft ein Filter: Geheimnisse und Pfade aus ``runtime/``,
``workspace/sigma``, ``workspace/obsidian`` und ``.env`` werden abgewiesen.
Notizen gehen nur als ausdruecklich eingefuegter Text hinaus, nie per Pfad.

Abfragen laufen per Polling, weil Webhooks einen offenen Port braeuchten.
Rueckfragen von Manus bestaetigt dieser Limb nie, es gibt dafuer keinen Code.

API-Felder laut https://open.manus.ai/docs/v2/ (gelesen am 2026-11-01).

Aufruf: ``python3 limbs/manus_limb.py --intent runtime/inbox/manus/<id>.json``
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Zwei Aufrufwege, ein Modul -- Begruendung steht in ``echo_limb.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(Path(__file__).resolve().parent), str(_REPO_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

if __package__ in (None, ""):  # direkter Skriptaufruf durch den Orchestrator
    from agent_base import (  # type: ignore[import-not-found]
        FAILED,
        RUNNING,
        SUCCEEDED,
        WAITING,
        AgentLimb,
        Poll,
        RateLimited,
        ServiceDown,
    )
    from base import LimbContext, LimbError  # type: ignore[import-not-found]
else:  # Import als Paket (Tests, Tooling)
    from limbs.agent_base import FAILED, RUNNING, SUCCEEDED, WAITING, AgentLimb, Poll, RateLimited, ServiceDown
    from limbs.base import LimbContext, LimbError

from core.protocol import ErrorCode  # noqa: E402

DEFAULT_BASE = "https://api.manus.ai"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
REQUEST_TIMEOUT_S = 20.0
MAX_PROMPT_CHARS = 16_000  # Doku: etwa 5000 Token je Anfrage
MAX_TEXT_CHARS = 200_000
MAX_PAGES = 20
PAGE_SIZE = 100

# Feste Vorgaben aus Phase 7.3. Bewusst nicht ueberschreibbar.
TASK_DEFAULTS: Mapping[str, Any] = {
    "clear_connectors": True,
    "share_visibility": "private",
    "agent_profile": "lite",
    "interactive_mode": False,
}

_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL", re.IGNORECASE)
_MIN_SECRET_LEN = 8
_BLOCKED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Pfad runtime/", re.compile(r"(?<![\w-])runtime/")),
    ("Pfad workspace/sigma", re.compile(r"workspace/sigma", re.IGNORECASE)),
    ("Pfad workspace/obsidian", re.compile(r"workspace/obsidian", re.IGNORECASE)),
    ("Datei .env", re.compile(r"(?<![\w.])\.env(?![\w-])")),
    ("Privater Schluessel", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("API-Key", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|tvr_[A-Za-z0-9]{8,})")),
    ("Geheimnis-Zuweisung", re.compile(r"\b[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\s*[=:]\s*\S{6,}")),
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


# Ohne Proxy und ohne Weiterleitung: urllib truege den Key-Header sonst zu einem fremden Host.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def _base_url() -> str:
    url = os.environ.get("MANUS_API_BASE", "").strip().rstrip("/") or DEFAULT_BASE
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname not in LOCAL_HOSTS:
        raise LimbError(
            ErrorCode.POLICY_DENIED,
            f"Manus-Aufrufe an {parsed.hostname!r} sind gesperrt.",
            hint="Die Sperre faellt erst mit den Freigabe-Tickets aus J4 und nach Key und Budget vom Menschen.",
        )
    return url


def _api_key() -> str:
    key = os.environ.get("MANUS_API_KEY", "").strip()
    if not key:
        raise LimbError(ErrorCode.POLICY_DENIED, "MANUS_API_KEY ist nicht gesetzt.", hint="Key nur ueber die Umgebung, nie im Intent.")
    return key


def _credits_limit(name: str) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise LimbError(ErrorCode.BUDGET_EXHAUSTED, f"{name} ist nicht gesetzt.", hint="Ohne Budget startet kein Lauf.")
    return int(raw)


def blocked_reason(text: str, environment: Mapping[str, str]) -> str:
    """Grund, warum dieser Text nicht gesendet werden darf, sonst leer."""
    for label, pattern in _BLOCKED_PATTERNS:
        if pattern.search(text):
            return label
    for name, value in environment.items():
        if _SECRET_NAME.search(name) and len(value) >= _MIN_SECRET_LEN and value in text:
            return f"Wert der Variable {name}"
    return ""


class ManusClient:
    """Duenner HTTP-Client. Der Key steht nur im Header und nie in einer Meldung."""

    def __init__(self, base: str, key: str, *, timeout_s: float = REQUEST_TIMEOUT_S) -> None:
        self.base = base
        self.key = key
        self.timeout_s = timeout_s

    def call(self, method: str, operation: str, *, query: Mapping[str, Any] | None = None, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base}/v2/{operation}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        headers = {"x-manus-api-key": self.key, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with _OPENER.open(request, timeout=self.timeout_s) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            status = exc.code
            exc.close()
            if status == 429:
                raise RateLimited(float(retry_after) if retry_after and retry_after.isdigit() else None) from None
            if status >= 500:
                raise ServiceDown(f"{operation}: HTTP {status}") from None
            raise LimbError(ErrorCode.IO, f"{operation}: HTTP {status}", hint="Auftrag oder Key pruefen.") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ServiceDown(f"{operation}: {type(exc).__name__}") from None
        try:
            payload = json.loads(raw)
        except ValueError:
            raise ServiceDown(f"{operation}: Antwort ist kein JSON") from None
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise LimbError(ErrorCode.IO, f"{operation}: Dienst meldet einen Fehler.", hint="Details stehen im Manus-Protokoll.")
        return payload


class ManusLimb(AgentLimb):
    name = "manus"
    version = "1.0.0"
    description = "Gehosteter Agent Manus: start / status / stop / collect / ping / usage"

    def handlers(self) -> dict[str, Callable[[Mapping[str, Any], LimbContext], Mapping[str, Any]]]:
        return {**self.agent_handlers(), "manus.ping": self._ping, "manus.usage": self._usage}

    def secrets(self) -> Iterable[str]:
        return (os.environ.get("MANUS_API_KEY", "").strip(),)

    @staticmethod
    def client() -> ManusClient:
        base = _base_url()  # zuerst: Die Sperre greift auch ohne Key
        return ManusClient(base, _api_key())

    # ------------------------------------------------------------------ Hooks
    def prepare(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        prompt = params.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise LimbError(ErrorCode.SCHEMA_INVALID, "params.prompt fehlt oder ist leer.")
        if len(prompt) > MAX_PROMPT_CHARS:
            raise LimbError(ErrorCode.SCHEMA_INVALID, f"params.prompt ist laenger als {MAX_PROMPT_CHARS} Zeichen.")
        reason = blocked_reason(prompt, os.environ)
        if reason:
            raise LimbError(ErrorCode.POLICY_DENIED, f"Sendefilter: {reason}.", hint="Diesen Inhalt aus dem Auftrag entfernen.")

        client = self.client()
        run_limit = _credits_limit("MANUS_BUDGET_RUN")
        day_limit = _credits_limit("MANUS_BUDGET_DAY")
        try:
            spent = self._spent_today(client)
        except (RateLimited, ServiceDown) as exc:
            raise LimbError(ErrorCode.IO, f"Budget nicht pruefbar: {exc}", hint="Ohne Budgetstand startet kein Lauf.") from exc
        if spent >= day_limit:
            raise LimbError(ErrorCode.BUDGET_EXHAUSTED, f"Tagesbudget erreicht: {spent} von {day_limit} Credits.")
        return {"budget_run": run_limit, "budget_day": day_limit}

    def launch(self, params: Mapping[str, Any], ctx: LimbContext, run: dict[str, Any]) -> None:
        body: dict[str, Any] = {"message": {"content": str(params["prompt"])}, **TASK_DEFAULTS}
        locale = params.get("locale")
        if isinstance(locale, str) and re.fullmatch(r"[a-zA-Z-]{2,10}", locale):
            body["locale"] = locale
        reply = self.client().call("POST", "task.create", body=body)
        task_id = reply.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ServiceDown("task.create: keine task_id")
        run["task_id"] = task_id

    def poll(self, run: dict[str, Any], ctx: LimbContext) -> Poll:
        client = self.client()
        task = client.call("GET", "task.detail", query={"task_id": run["task_id"]}).get("task") or {}
        status = str(task.get("status", ""))
        credits_used = int(task.get("credit_usage") or 0)
        if status == "running":
            return Poll(RUNNING, credits_used)
        if status == "stopped":
            # Laut Doku ist stopped nicht endgueltig, solange Hintergrundarbeit laeuft.
            return Poll(RUNNING if task.get("has_running_background_jobs") else SUCCEEDED, credits_used)
        if status == "waiting":
            return Poll(WAITING, credits_used, self._waiting_detail(client, run))
        if status in ("error", "deleted"):
            return Poll(FAILED, credits_used, {"error": self._error_text(client, run) or f"Manus meldet Status {status}."})
        raise ServiceDown(f"task.detail: unbekannter Status {status!r}")

    def over_budget(self, run: dict[str, Any], poll: Poll, ctx: LimbContext) -> str:
        if poll.credits >= int(run["budget_run"]):
            return f"Laufbudget erreicht: {poll.credits} von {run['budget_run']} Credits."
        spent = self._spent_today(self.client())
        if spent >= int(run["budget_day"]):
            return f"Tagesbudget erreicht: {spent} von {run['budget_day']} Credits."
        return ""

    def halt(self, run: dict[str, Any], ctx: LimbContext) -> None:
        if run.get("task_id"):
            self.client().call("POST", "task.stop", body={"task_id": run["task_id"]})

    def gather(self, run: dict[str, Any], ctx: LimbContext) -> dict[str, Any]:
        client = self.client()
        return {"text": self._assistant_text(client, run), "artifacts": self._artifacts(client, run)}

    # ------------------------------------------------------------------ Lesen
    @staticmethod
    def _waiting_detail(client: ManusClient, run: Mapping[str, Any]) -> dict[str, Any]:
        reply = client.call("GET", "task.listMessages", query={"task_id": run["task_id"], "order": "desc", "limit": 10})
        for message in reply.get("messages") or []:
            update = message.get("status_update") or {}
            if update.get("agent_status") == "waiting":
                detail = update.get("status_detail") or {}
                return {
                    "event_type": str(detail.get("waiting_for_event_type", "")),
                    "description": str(detail.get("waiting_description", ""))[:500],
                    "needs_human": True,
                }
        return {"event_type": "", "description": "", "needs_human": True}

    @staticmethod
    def _error_text(client: ManusClient, run: Mapping[str, Any]) -> str:
        reply = client.call("GET", "task.listMessages", query={"task_id": run["task_id"], "order": "desc", "limit": 10})
        for message in reply.get("messages") or []:
            if message.get("type") == "error_message":
                return str((message.get("error_message") or {}).get("content", ""))[:500]
        return ""

    @staticmethod
    def _assistant_text(client: ManusClient, run: Mapping[str, Any]) -> str:
        parts: list[str] = []
        cursor = ""
        for _ in range(MAX_PAGES):
            query: dict[str, Any] = {"task_id": run["task_id"], "order": "asc", "limit": PAGE_SIZE}
            if cursor:
                query["cursor"] = cursor
            reply = client.call("GET", "task.listMessages", query=query)
            parts.extend(str((m.get("assistant_message") or {}).get("content", "")) for m in reply.get("messages") or [] if m.get("type") == "assistant_message")
            cursor = str(reply.get("next_cursor") or "")
            if not reply.get("has_more") or not cursor:
                break
        return "\n\n".join(parts)[:MAX_TEXT_CHARS]

    @staticmethod
    def _artifacts(client: ManusClient, run: Mapping[str, Any]) -> list[dict[str, Any]]:
        # artifact.list kennt keinen Task-Filter, deshalb wird hier nach task_id gesiebt. Geladen wird nichts.
        found: list[dict[str, Any]] = []
        cursor = ""
        for _ in range(MAX_PAGES):
            query: dict[str, Any] = {"limit": PAGE_SIZE}
            if cursor:
                query["cursor"] = cursor
            reply = client.call("GET", "artifact.list", query=query)
            for item in reply.get("data") or []:
                if item.get("task_id") == run["task_id"]:
                    found.append({key: item.get(key) for key in ("id", "filename", "display_name", "type", "content_type", "url")})
            cursor = str(reply.get("next_cursor") or "")
            if not reply.get("has_more") or not cursor:
                break
        return found

    @staticmethod
    def _spent_today(client: ManusClient) -> int:
        """Credits seit Mitternacht UTC: Kosten minus Rueckerstattungen. Gutschriften zaehlen nicht."""
        midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        spent = 0
        cursor = ""
        for _ in range(MAX_PAGES):
            query: dict[str, Any] = {"limit": PAGE_SIZE}
            if cursor:
                query["cursor"] = cursor
            reply = client.call("GET", "usage.list", query=query)
            records = reply.get("data") or []
            for record in records:
                if int(record.get("created_at") or 0) >= midnight and record.get("type") in ("cost", "refund"):
                    spent -= int(record.get("credits") or 0)
            cursor = str(reply.get("next_cursor") or "")
            oldest = min((int(r.get("created_at") or 0) for r in records), default=0)
            if not reply.get("has_more") or not cursor or oldest < midnight:
                break
        return max(0, spent)

    # ---------------------------------------------------------------- Handler
    def _ping(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        output = {"limb": self.name, "version": self.version, "live_locked": True}
        try:
            self.client().call("GET", "user.me")
        except (RateLimited, ServiceDown) as exc:
            return {**output, "service": "offline", "reason": str(exc)}
        return {**output, "service": "running"}

    def _usage(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        try:
            spent = self._spent_today(self.client())
        except (RateLimited, ServiceDown) as exc:
            raise LimbError(ErrorCode.IO, f"Verbrauch nicht abrufbar: {exc}") from exc
        return {"credits_today": spent}


if __name__ == "__main__":
    sys.exit(ManusLimb().main())

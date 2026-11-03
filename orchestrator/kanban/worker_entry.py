"""Entrypoint fuer die Kanban-Sandbox.

ACHTUNG: Dieser Code laeuft IN der Sandbox (Docker oder isolierter Prozess).
Hier duerfen KEINE nio-Module (wie ``core.*`` oder ``orchestrator.*``) importiert
werden. Wir verlassen uns ausschliesslich auf die Python Standard Library
und kommunizieren ueber das Dateisystem (in/ und out/) und stdout/stderr.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

__all__ = ["main"]


def _atomic_write(path: Path, data: bytes) -> None:
    """Schreibt Bytes atomar nach ``path`` (ohne externe Abhaengigkeiten)."""
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(temp_path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        if temp_path.exists():
            with contextlib.suppress(Exception):
                temp_path.unlink()
        raise


def utc_now_iso() -> str:
    """Liefert die aktuelle Zeit als ISO 8601 String (Z-Suffix)."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class WorkerContext:
    def __init__(self) -> None:
        self.in_dir = Path(os.environ["NIO_KANBAN_IN"])
        self.out_dir = Path(os.environ["NIO_KANBAN_OUT"])
        self.work_dir = Path(os.environ["NIO_KANBAN_WORKDIR"])
        self.heartbeat_s = float(os.environ["NIO_KANBAN_HEARTBEAT_S"])

        self.interrupted = False

        # Result-State fuer Save-on-exit
        self.status = "failed"
        self.reason = "Unbekannter Fehler"
        self.result_payload: dict[str, Any] = {}

        # Experience-State
        self.experience_summary = ""
        self.experience_lessons: list[str] = []
        self.skills_delta: list[str] = []
        self.experience_outcome = "success"

        # SOUL State
        self.soul_md = ""
        self.history_md = ""
        self.new_soul_md = ""


def _parse_frontmatter(md: str) -> dict[str, str]:
    """Mini-Frontmatter-Parser."""
    lines = md.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    result = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, val = line.split(":", 1)
            result[key.strip()] = val.strip()
    return result


def _update_soul(soul: str, new_skills: list[str]) -> str:
    """Fuegt neue Skills zum Core Skills Bereich der Seele hinzu."""
    if not new_skills:
        return soul

    lines = soul.splitlines()
    out = []
    in_skills = False
    skills_inserted = False

    for line in lines:
        if line.strip() == "## Core Skills":
            in_skills = True
            out.append(line)
            continue

        if in_skills and line.startswith("## "):
            # Ende der Skills Section
            if not skills_inserted:
                for skill in new_skills:
                    out.append(f"- {skill}")
                out.append("")
                skills_inserted = True
            in_skills = False

        out.append(line)

    if in_skills and not skills_inserted:
        for skill in new_skills:
            out.append(f"- {skill}")

    return "\n".join(out) + ("\n" if soul.endswith("\n") else "")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _live_completion(soul: str, task: dict[str, Any]) -> dict[str, Any]:
    """Exactly one bounded provider request; no tools, retries or simulated answer."""
    if os.environ.get("NIO_LLM_ERROR"):
        raise ValueError(os.environ["NIO_LLM_ERROR"])
    key = os.environ.get("NIO_LLM_API_KEY", "").strip()
    model = os.environ.get("NIO_LLM_MODEL", "").strip()
    if not key:
        raise ValueError("missing_secret")
    if not model:
        raise ValueError("model_missing")
    endpoint = os.environ.get("NIO_LLM_ENDPOINT", "")
    url = urlsplit(endpoint)
    provider = os.environ.get("NIO_LLM_PROVIDER", "")
    if url.username or url.password or url.fragment or (url.scheme != "https" and not (
        provider == "freellm" and url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")
    )):
        raise ValueError("forbidden_provider_endpoint")
    protocol = os.environ.get("NIO_LLM_PROTOCOL", "openai")
    messages = [{"role": "system", "content": soul[:12_000]}, {"role": "user", "content": str(task.get("title", "")) + "\n" + str(task.get("description", ""))[:12_000]}]
    headers = {"Content-Type": "application/json"}
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": 64, "temperature": 0, "stream": False}
    if protocol == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        body["system"] = soul[:12_000]
        body["messages"] = messages[1:]
    else:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=20) as response:
            data = json.loads(response.read(256_000))
        if protocol == "anthropic":
            text = next((part.get("text") for part in data.get("content", []) if part.get("type") == "text"), None)
        elif protocol == "cohere":
            text = next((part.get("text") for part in data.get("message", {}).get("content", []) if part.get("type") == "text"), None)
        else:
            text = data["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("invalid_response")
        return {"text": _redact_output(text.strip())[:12_000], "provider": provider, "model": model, "live": True}
    except urllib.error.HTTPError as error:
        code = "auth_failed" if error.code in (401, 403) else "rate_limited" if error.code == 429 else "upstream_error"
        raise ValueError(f"{code}: HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError("network_error_or_timeout") from None
    except (ValueError, KeyError, TypeError, IndexError):
        raise ValueError("invalid_response") from None


def _redact_output(value: Any) -> Any:
    if isinstance(value, str):
        for name, secret in os.environ.items():
            if secret and any(marker in name.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {key: _redact_output(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_output(item) for item in value]
    return value


def main() -> int:
    ctx = WorkerContext()

    def sigterm_handler(signum: int, frame: Any) -> None:
        ctx.interrupted = True
        raise SystemExit(143)

    signal.signal(signal.SIGTERM, sigterm_handler)

    # Heartbeat Daemon
    # Geordnet beenden statt Daemon-Abbruch: sonst kann der Prozess mitten im
    # Schreiben enden und ``heartbeat.tmp`` liegen lassen.
    hb_stop = threading.Event()

    def heartbeat_loop() -> None:
        while not hb_stop.is_set():
            with contextlib.suppress(Exception):
                _atomic_write(ctx.out_dir / "heartbeat", utc_now_iso().encode("utf-8"))
            hb_stop.wait(ctx.heartbeat_s)

    hb_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    hb_thread.start()

    try:
        # Inputs lesen
        task_data = json.loads((ctx.in_dir / "task.json").read_text(encoding="utf-8"))
        ctx.soul_md = (ctx.in_dir / "SOUL.md").read_text(encoding="utf-8")

        frontmatter = _parse_frontmatter(ctx.soul_md)
        runtime = frontmatter.get("runtime", "noop").lower()
        if os.environ.get("NIO_KANBAN_LLM_ONLY") == "1" and runtime != "llm":
            raise ValueError("llm_transport_refuses_non_llm_runtime")

        if frontmatter.get("learns"):
            ctx.skills_delta = [s.strip() for s in frontmatter["learns"].split(",") if s.strip()]

        if runtime == "noop":
            ctx.status = "completed"
            ctx.result_payload = {"echo": task_data.get("title", "")}
            ctx.experience_summary = f"Noop: {task_data.get('title', '')}"

        elif runtime == "llm":
            ctx.result_payload = _live_completion(ctx.soul_md, task_data)
            ctx.status = "completed"
            ctx.experience_summary = "Live provider completion received"

        elif runtime == "command":
            if "command" not in frontmatter:
                raise ValueError("Runtime command benoetigt command im Frontmatter (JSON argv-Liste)")

            argv = json.loads(frontmatter["command"])

            result = subprocess.run(
                argv,
                cwd=ctx.work_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                ctx.status = "completed"
                ctx.result_payload = {"stdout": result.stdout}
                ctx.experience_summary = f"Command exited with 0: {argv[0]}"
            else:
                ctx.status = "failed"
                ctx.reason = f"Command failed with {result.returncode}"
                # Letzte 2 KiB von stderr
                stderr_tail = result.stderr[-2048:] if len(result.stderr) > 2048 else result.stderr
                ctx.result_payload = {"stderr": stderr_tail}
                ctx.experience_summary = f"Command failed: {argv[0]}"
                ctx.experience_lessons.append(f"Stderr: {stderr_tail}")

        elif runtime == "limb":
            op = frontmatter.get("limb_operation", "").strip()
            if not op:
                raise ValueError("Runtime limb benoetigt limb_operation im Frontmatter")

            req = {
                "operation": op,
                "params": task_data.get("params", {})
            }
            _atomic_write(ctx.out_dir / "limb_request.json", json.dumps(req).encode("utf-8"))

            ctx.status = "completed"
            ctx.experience_summary = f"Limb-Request: {op}"

        elif runtime == "opencode":
            prompt = (
                f"Mission und Regeln:\n{ctx.soul_md}\n\n"
                f"Task:\n{task_data.get('title', '')}\n\n"
                f"{task_data.get('description', '')}\n\n"
                "Aendere die Dateien wie gewuenscht und committe sie.\n"
                "never push, never open PRs."
            )

            argv = ["opencode", "run", prompt]

            result = subprocess.run(
                argv,
                cwd=ctx.work_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                ctx.status = "completed"
                ctx.result_payload = {"stdout": result.stdout}
                ctx.experience_summary = "Opencode erfolgreich"
            else:
                ctx.status = "failed"
                ctx.reason = f"Opencode failed mit {result.returncode}"
                stderr_tail = result.stderr[-2048:] if len(result.stderr) > 2048 else result.stderr
                ctx.result_payload = {"stderr": stderr_tail}
                ctx.experience_summary = "Opencode fehlgeschlagen"
                ctx.experience_lessons.append(f"Stderr: {stderr_tail}")

        else:
            raise ValueError(f"Unbekannte Runtime: {runtime}")

    except SystemExit as e:
        if e.code == 143:
            pass  # behandelt via interrupted in finally
        else:
            ctx.status = "failed"
            ctx.reason = str(e)
    except Exception as e:
        ctx.status = "failed"
        ctx.reason = str(e)
        ctx.experience_summary = f"Fehler: {e}"
        ctx.experience_lessons.append(str(e))

    finally:
        hb_stop.set()
        hb_thread.join(timeout=5)
        if ctx.interrupted:
            ctx.status = "interrupted"
            ctx.reason = "SIGTERM"
            ctx.experience_summary = "Abgebrochen durch SIGTERM"

        ctx.new_soul_md = _update_soul(ctx.soul_md, ctx.skills_delta)

        # Save-on-exit (Experience, SOUL, Result in dieser Reihenfolge!)
        experience = {
            "summary": ctx.experience_summary,
            "lessons": ctx.experience_lessons,
            "skills_delta": ctx.skills_delta,
            "outcome": "success" if ctx.status == "completed" else "failure",
        }

        res = {
            "status": "interrupted" if ctx.interrupted else ctx.status,
            "result_payload": ctx.result_payload,
            "reason": ctx.reason if ctx.status != "completed" else "",
        }

        _atomic_write(ctx.out_dir / "experience.json", json.dumps(_redact_output(experience)).encode("utf-8"))

        if ctx.new_soul_md != ctx.soul_md:
            _atomic_write(ctx.out_dir / "SOUL.md", ctx.new_soul_md.encode("utf-8"))

        _atomic_write(ctx.out_dir / "result.json", json.dumps(_redact_output(res)).encode("utf-8"))

    if ctx.interrupted:
        return 143
    if ctx.status == "failed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

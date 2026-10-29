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
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def main() -> int:
    ctx = WorkerContext()

    def sigterm_handler(signum: int, frame: Any) -> None:
        ctx.interrupted = True
        raise SystemExit(143)

    signal.signal(signal.SIGTERM, sigterm_handler)

    # Heartbeat Daemon
    def heartbeat_loop() -> None:
        while True:
            try:
                ts = utc_now_iso().encode("utf-8")
                _atomic_write(ctx.out_dir / "heartbeat", ts)
            except Exception:
                pass
            time.sleep(ctx.heartbeat_s)

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    try:
        # Inputs lesen
        task_data = json.loads((ctx.in_dir / "task.json").read_text(encoding="utf-8"))
        ctx.soul_md = (ctx.in_dir / "SOUL.md").read_text(encoding="utf-8")

        frontmatter = _parse_frontmatter(ctx.soul_md)
        runtime = frontmatter.get("runtime", "noop").lower()

        if frontmatter.get("learns"):
            ctx.skills_delta = [s.strip() for s in frontmatter["learns"].split(",") if s.strip()]

        if runtime == "noop":
            ctx.status = "completed"
            ctx.result_payload = {"echo": task_data.get("title", "")}
            ctx.experience_summary = f"Noop: {task_data.get('title', '')}"

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

        _atomic_write(ctx.out_dir / "experience.json", json.dumps(experience).encode("utf-8"))

        if ctx.new_soul_md != ctx.soul_md:
            _atomic_write(ctx.out_dir / "SOUL.md", ctx.new_soul_md.encode("utf-8"))

        _atomic_write(ctx.out_dir / "result.json", json.dumps(res).encode("utf-8"))

    if ctx.interrupted:
        return 143
    if ctx.status == "failed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

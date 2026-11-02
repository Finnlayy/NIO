#!/usr/bin/env python3
"""End-to-End-Abnahme fuer Hermes-Kanban (WP-09).

Der Beweis startet die echte CLI (``python3 -m orchestrator kanban``) in einem
Temp-Verzeichnis. Geprueft werden:
- Init, Worker-Anlage, Board-Anlage, Task-Anlage.
- Tick (Scheduler).
- Der Eltern-Task und zwei Kinder sind ``completed``.
- Vault enthaelt zwei Notizen (Experiences).
- Audit Ledger meldet ok.

Nur Standardbibliothek. Fehler -> Exit 1 mit deutschem Befund.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> int:
    print(f"[e2e-kanban] FEHLGESCHLAGEN: {message}", file=sys.stderr)
    return 1


def run_cli(env: dict[str, str], *args: str, json_out: bool = True) -> str | dict[str, object]:
    cmd = [sys.executable, "-m", "orchestrator"]
    if json_out:
        cmd.append("--json")
    cmd.append("kanban")
    cmd.extend(args)

    res = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"CLI Fehler: {res.returncode}\ncmd: {cmd}\nstderr: {res.stderr}\nstdout: {res.stdout}")

    if json_out:
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"JSONDecodeError: {exc}\nstdout: {res.stdout}") from exc
    return res.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="neu-kanban-e2e-") as tmp_dir:
        tmp = Path(tmp_dir)
        env = os.environ.copy()
        env["NEU_ROOT"] = str(tmp)
        env["NIO_KANBAN_WORKSPACE"] = str(tmp / "ws")
        env["NIO_OBSIDIAN_VAULT"] = str(tmp / "vault")

        try:
            # 1. Init
            run_cli(env, "init")

            # 2. Worker create
            run_cli(env, "worker", "create", "alpha", "--skill", "code")

            # 3. Board create
            board_out = run_cli(env, "board", "create", "demo")
            if not isinstance(board_out, dict):
                return fail("board create Ausgabe ist kein Objekt")
            board_id = str(board_out.get("id"))

            # 4. Task create
            desc_content = "- [ ] eins #code\n- [ ] zwei #code"
            desc_file = tmp / "desc.md"
            desc_file.write_text(desc_content, encoding="utf-8")

            run_cli(env, "task", "create", "--board", board_id, "--title", "Demo", "--description-file", str(desc_file))

            # 5. Tick (wait) - 4x
            for _ in range(4):
                run_cli(env, "tick", "--wait")

            # 6. Audit verify
            audit_out = run_cli(env, "audit", "verify")
            if not isinstance(audit_out, dict) or not audit_out.get("ok"):
                return fail(f"Audit verify schlug fehl: {audit_out}")

            # 7. Asserts (Parent + 2 children completed)
            tasks = run_cli(env, "task", "list", "--board", board_id)
            if not isinstance(tasks, list):
                return fail("task list Ausgabe ist keine Liste")

            completed_count = sum(1 for t in tasks if t.get("status") == "completed")
            if completed_count != 3:
                titles_status = [(t.get("title"), t.get("status")) for t in tasks]
                return fail(f"Erwartete 3 completed Tasks, fand {completed_count}. {titles_status}")

            # 8. Experiences im Vault
            experiences_dir = tmp / "vault" / "workers" / "alpha" / "experiences"
            experiences = list(experiences_dir.glob("*.md")) if experiences_dir.exists() else []
            if len(experiences) != 2:
                return fail(f"Erwartete 2 Experience-Notes, fand {len(experiences)}")

        except Exception as e:
            return fail(f"Unerwarteter Fehler: {e}")

        print("[e2e-kanban] Beweis erbracht: Alle Schritte erfolgreich durchlaufen.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
NIO Automated Artifact & Architecture Exporter (v8.1)
File: tools/sync/nio_artifact_exporter.py
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


class NioArtifactExporter:
    TRACKED_MODULES = (
        ("Frontend Voice-to-Kanban Bridge", "frontend/src/apollo/commands.ts", "typescript"),
        ("Kanban Dispatcher", "orchestrator/kanban/dispatcher.py", "python"),
        ("Noir Security & Blast-Radius Gate", "tools/selfcode/sandbox_gate.py", "python"),
        ("Blanche Obsidian Memory Engine", "core/obsidian_memory.py", "python"),
        ("AbyssalSystemBus Java 21+ IPC", "bus/src/main/java/os/abyssal/ipc/AbyssalSystemBus.java", "java"),
        ("Abyssal IPC JSON Schema", "protocol/abyssal_envelope.schema.json", "json"),
        ("FastMCP Rust-Limb Bridge", "limbs/fastmcp_bridge.py", "python"),
    )

    def __init__(
        self,
        repo_root: str = ".",
        export_dir: str | None = None,
    ):
        self.repo_root = Path(repo_root).resolve()
        # Default relativ zum Repo-Root, nicht zum aktuellen Arbeitsverzeichnis.
        self.export_dir = Path(export_dir).resolve() if export_dir else self.repo_root / "obsidian_vault" / "exports"
        self.manifest_path = self.export_dir / "export_manifest.json"

    def _compute_bundle_hash(self, files: list[Path]) -> str:
        hasher = hashlib.sha256()
        for f in files:
            if f.exists():
                data = f.read_bytes()
                # Relativer Pfad statt nur Dateiname, plus Laengenpraefix: sonst
                # kollidieren gleichnamige Dateien bzw. verschobene Inhaltsgrenzen.
                hasher.update(f.relative_to(self.repo_root).as_posix().encode("utf-8") + b"\0")
                hasher.update(str(len(data)).encode("ascii") + b"\0")
                hasher.update(data)
        return hasher.hexdigest()

    @staticmethod
    def _fence_for(code: str) -> str:
        # Der Zaun muss laenger sein als jede Backtick-Folge im Inhalt, sonst
        # bricht der Codeblock in Obsidian vorzeitig ab.
        longest = run = 0
        for ch in code:
            run = run + 1 if ch == "`" else 0
            longest = max(longest, run)
        return "`" * max(3, longest + 1)

    def export_snapshot(self, trigger_run_id: str = "manual") -> Path | None:
        self.export_dir.mkdir(parents=True, exist_ok=True)

        existing_paths = [
            self.repo_root / rel_path
            for _, rel_path, _ in self.TRACKED_MODULES
            if (self.repo_root / rel_path).exists()
        ]
        if not existing_paths:
            return None

        bundle_hash = self._compute_bundle_hash(existing_paths)
        output_file = self.export_dir / "NIO_Latest_Production_Snapshot.md"

        # Prüfe, ob sich gegenüber dem letzten Export überhaupt etwas geändert hat
        # (und ob der letzte Snapshot noch existiert).
        if self.manifest_path.exists() and output_file.exists():
            try:
                last_manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                last_manifest = {}
            if isinstance(last_manifest, dict) and last_manifest.get("bundle_hash") == bundle_hash:
                return None

        now_iso = datetime.now(UTC).isoformat()
        lines = [
            "# MANAS: CIEL // E.D.I.T.H. // L.I.L.I.T.H. OS — Auto-Export Snapshot",
            f"- **Timestamp (UTC):** `{now_iso}`",
            f"- **Trigger Run ID:** `{trigger_run_id}`",
            f"- **Bundle SHA-256:** `{bundle_hash}`",
            "",
            "---",
            "",
        ]

        exported_count = 0
        for idx, (title, rel_path, lang) in enumerate(self.TRACKED_MODULES, start=1):
            full_path = self.repo_root / rel_path
            if not full_path.exists():
                continue

            code_content = full_path.read_text(encoding="utf-8").strip()
            fence = self._fence_for(code_content)
            lines.extend(
                [
                    f"## {idx}. {title} (`{rel_path}`)",
                    f"{fence}{lang}",
                    code_content,
                    fence,
                    "",
                    "---",
                    "",
                ]
            )
            exported_count += 1

        output_file.write_text("\n".join(lines), encoding="utf-8")

        self.manifest_path.write_text(
            json.dumps(
                {
                    "updated_at": now_iso,
                    "trigger_run_id": trigger_run_id,
                    "bundle_hash": bundle_hash,
                    "exported_modules": exported_count,
                    "output_file": str(output_file),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return output_file


if __name__ == "__main__":
    # Repo-Root aus dem Skriptpfad ableiten, damit der Aufruf aus jedem cwd funktioniert.
    exporter = NioArtifactExporter(repo_root=str(Path(__file__).resolve().parents[2]))
    exported = exporter.export_snapshot(trigger_run_id="cli-sync")
    if exported:
        print(f"[NIO Exporter] Snapshot aktualisiert: {exported}")
    else:
        print("[NIO Exporter] Keine Code-Änderungen seit letztem Export.")

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
        export_dir: str = "./obsidian_vault/exports",
    ):
        self.repo_root = Path(repo_root).resolve()
        self.export_dir = Path(export_dir).resolve()
        self.manifest_path = self.export_dir / "export_manifest.json"

    def _compute_bundle_hash(self, files: list[Path]) -> str:
        hasher = hashlib.sha256()
        for f in files:
            if f.exists():
                hasher.update(f.name.encode("utf-8"))
                hasher.update(f.read_bytes())
        return hasher.hexdigest()

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

        # Prüfe, ob sich gegenüber dem letzten Export überhaupt etwas geändert hat
        if self.manifest_path.exists():
            last_manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if last_manifest.get("bundle_hash") == bundle_hash:
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
            lines.extend(
                [
                    f"## {idx}. {title} (`{rel_path}`)",
                    f"```{lang}",
                    code_content,
                    "```",
                    "",
                    "---",
                    "",
                ]
            )
            exported_count += 1

        output_file = self.export_dir / "NIO_Latest_Production_Snapshot.md"
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
    exporter = NioArtifactExporter()
    exported = exporter.export_snapshot(trigger_run_id="cli-sync")
    if exported:
        print(f"[NIO Exporter] Snapshot aktualisiert: {exported}")
    else:
        print("[NIO Exporter] Keine Code-Änderungen seit letztem Export.")

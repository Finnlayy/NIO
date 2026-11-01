"""Vault-Limb (Phase 8) -- Obsidian-Vault lesen, durchsuchen, Notizen ablegen.

Der Vault ist ein Ordner mit Markdown unter ``workspace/obsidian``. Die App wird
nicht gebraucht. Gelesen und durchsucht wird der ganze Vault ausser
Punkt-Ordnern, geschrieben nur nach ``Inbox/``, ``workers/`` und ``tasks/``.
``Knowledge/`` gehoert dem Menschen.

Die Suche nutzt SQLite FTS5. Der Index liegt unter ``runtime/vault/`` und wird
vor jeder Suche nach Aenderungszeit abgeglichen. Der Vault hat ein eigenes
lokales Git als Sicherung und bleibt vom NIO-Repository getrennt.

Notizen sind Fremdinhalt: Jede Ausgabe traegt ``untrusted: true``. Sie werden nie
als Anweisung behandelt und gehen an Manus nur auf ausdrueckliche Auswahl.

Aufruf: ``python3 limbs/vault_limb.py --intent runtime/inbox/vault/<id>.json``
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
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

VAULT_FOLDERS = ("Inbox", "Daily", "Knowledge", "workers", "tasks")
WRITE_FOLDERS = ("Inbox", "workers", "tasks")
NOTE_SUFFIXES = (".md", ".markdown", ".txt")
DEFAULT_LIMIT = 10
MAX_LIMIT = 50
MAX_NOTE_CHARS = 64_000
MAX_INDEX_BYTES = 1_000_000
MAX_READ_BYTES = 256_000
GIT_TIMEOUT_S = 10.0
_GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
_GIT_IDENTITY = ("-c", "user.name=NIO", "-c", "user.email=nio@localhost", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false")


class VaultStore:
    """Dateizugriff auf den Vault. Limb und MCP-Server teilen sich diese Regeln."""

    def __init__(self, root: Path, index_dir: Path) -> None:
        self.root = root.resolve()
        digest = hashlib.sha256(str(self.root).encode()).hexdigest()[:16]
        self.index_path = index_dir / f"{digest}.sqlite"

    @classmethod
    def locate(cls, repo_root: Path, runtime_dir: Path) -> VaultStore:
        configured = os.environ.get("NIO_OBSIDIAN_VAULT", "").strip()
        root = Path(configured) if configured else Path("workspace/obsidian")
        return cls(root if root.is_absolute() else repo_root / root, runtime_dir / "vault")

    # ----------------------------------------------------------------- Pfade
    def safe_path(self, raw: str, *, where: str = "$.task.params.path") -> Path:
        """Vault-relativer Pfad oder Abweisung; loest Symlinks vor der Pruefung auf."""
        parts = raw.replace("\\", "/").split("/") if isinstance(raw, str) else []
        if not raw or "\x00" in raw or raw.startswith(("/", "\\", "~")) or any(p == ".." or p.startswith(".") for p in parts if p):
            raise LimbError(ErrorCode.SANDBOX_ESCAPE, f"{where}: Pfad {raw!r} ist im Vault nicht erlaubt.", hint="Relativ zum Vault, ohne '..' und ohne Punkt-Ordner.")
        target = (self.root / "/".join(p for p in parts if p)).resolve()
        if not target.is_relative_to(self.root):
            raise LimbError(ErrorCode.SANDBOX_ESCAPE, f"{where}: Pfad {raw!r} verlaesst den Vault.", hint="Symlinks nach aussen werden nicht verfolgt.")
        return target

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    # ------------------------------------------------------------------ Lesen
    def notes(self) -> Iterator[Path]:
        for folder, directories, files in os.walk(self.root, followlinks=False):
            directories[:] = sorted(d for d in directories if not d.startswith("."))
            for name in sorted(files):
                path = Path(folder) / name
                if not name.startswith(".") and path.suffix.lower() in NOTE_SUFFIXES and not path.is_symlink():
                    yield path

    def read(self, raw: str) -> dict[str, Any]:
        path = self.safe_path(raw)
        if path.suffix.lower() not in NOTE_SUFFIXES:
            raise LimbError(ErrorCode.POLICY_DENIED, f"Nur Notizen sind lesbar, nicht {path.suffix!r}.", hint=", ".join(NOTE_SUFFIXES))
        if not path.is_file():
            raise LimbError(ErrorCode.PATH_NOT_FOUND, f"Notiz {raw!r} gibt es nicht.", hint="Mit vault.search den Pfad ermitteln.")
        with path.open("rb") as handle:
            raw_bytes = handle.read(MAX_READ_BYTES + 1)
        return {
            "path": self.relative(path),
            "content": raw_bytes[:MAX_READ_BYTES].decode("utf-8", errors="replace"),
            "truncated": len(raw_bytes) > MAX_READ_BYTES,
            "untrusted": True,
        }

    # ------------------------------------------------------------------ Suche
    def _sync_index(self, db: sqlite3.Connection) -> int:
        db.execute("CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER)")
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(path UNINDEXED, title, body, tokenize = 'unicode61 remove_diacritics 2')")
        known = {row[0]: (row[1], row[2]) for row in db.execute("SELECT path, mtime_ns, size FROM files")}
        seen: set[str] = set()
        for path in self.notes():
            state = path.stat()
            if state.st_size > MAX_INDEX_BYTES:
                continue
            rel = self.relative(path)
            seen.add(rel)
            if known.get(rel) == (state.st_mtime_ns, state.st_size):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            db.execute("DELETE FROM docs WHERE path = ?", (rel,))
            body = re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
            db.execute("INSERT INTO docs (path, title, body) VALUES (?, ?, ?)", (rel, _title_of(text, path), body))
            db.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?)", (rel, state.st_mtime_ns, state.st_size))
        for rel in known.keys() - seen:
            db.execute("DELETE FROM docs WHERE path = ?", (rel,))
            db.execute("DELETE FROM files WHERE path = ?", (rel,))
        return len(seen)

    def search(self, query: str, *, limit: int = DEFAULT_LIMIT, folder: str = "") -> dict[str, Any]:
        tokens = re.findall(r"\w+", query)
        if not tokens:
            raise LimbError(ErrorCode.SCHEMA_INVALID, "params.query enthaelt keine Suchwoerter.")
        prefix = f"{self.relative(self.safe_path(folder, where='$.task.params.folder'))}/%" if folder else "%"
        # Jedes Wort in Anfuehrungszeichen: FTS-Operatoren aus der Eingabe bleiben wirkungslos.
        match = " ".join(f'"{token}"*' for token in tokens)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(sqlite3.connect(self.index_path, timeout=5.0)) as db, db:
            indexed = self._sync_index(db)
            rows = db.execute(
                "SELECT path, title, snippet(docs, 2, '[', ']', ' … ', 16) FROM docs "
                "WHERE docs MATCH ? AND path LIKE ? ORDER BY bm25(docs) LIMIT ?",
                (match, prefix, limit),
            ).fetchall()
        return {
            "total": len(rows),
            "indexed": indexed,
            "notes": [{"path": path, "title": title, "snippet": snippet.strip()} for path, title, snippet in rows],
            "untrusted": True,
        }

    # -------------------------------------------------------------- Schreiben
    def ensure(self) -> None:
        for folder in VAULT_FOLDERS:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        if not (self.root / ".git").exists():
            self._git("init", "-q", "-b", "main", init=True)

    def _git(self, *args: str, init: bool = False) -> bool:
        # --git-dir ist Pflicht: Der Vault liegt im NIO-Checkout, ein loses `git add` traefe dessen Repository.
        command = ["git", f"--git-dir={self.root / '.git'}", f"--work-tree={self.root}", *_GIT_IDENTITY, *args]
        try:
            done = subprocess.run(command, cwd=self.root, env={**os.environ, **_GIT_ENV}, capture_output=True, timeout=GIT_TIMEOUT_S, check=False)
        except (OSError, subprocess.SubprocessError):
            return False
        return done.returncode == 0

    def capture(self, text: str, *, folder: str = "Inbox", title: str = "", source: str = "agent") -> dict[str, Any]:
        directory = self.safe_path(folder, where="$.task.params.folder")
        top = self.relative(directory).split("/", 1)[0] if directory != self.root else ""
        if top not in WRITE_FOLDERS:
            raise LimbError(ErrorCode.POLICY_DENIED, f"Schreiben nach {folder!r} ist nicht erlaubt.", hint=f"Erlaubt: {', '.join(WRITE_FOLDERS)}.")
        self.ensure()
        directory.mkdir(parents=True, exist_ok=True)
        if not directory.resolve().is_relative_to(self.root / top):
            raise LimbError(ErrorCode.SANDBOX_ESCAPE, f"{folder!r} zeigt aus dem erlaubten Ordner heraus.")

        now = datetime.now(UTC)
        heading = " ".join((title or text).split())[:80]
        body = "\n".join(
            (
                "---",
                f"title: {json.dumps(heading, ensure_ascii=False)}",
                f"created: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
                f"source: {json.dumps(source, ensure_ascii=False)}",
                f"tags: [{top.lower()}]",
                "---",
                "",
                text.strip(),
                "",
            )
        )
        slug = re.sub(r"[^\w]+", "-", heading.lower()).strip("-")[:48] or "notiz"
        path = self._create(directory, f"{now.strftime('%Y-%m-%dT%H%M%S')}-{slug}", body)
        rel = self.relative(path)
        committed = self._git("add", "--", rel) and self._git("commit", "-q", "-m", f"Notiz: {rel}", "--", rel)
        return {"path": rel, "bytes": path.stat().st_size, "committed": committed, "created": now.strftime("%Y-%m-%dT%H:%M:%SZ")}

    @staticmethod
    def _create(directory: Path, stem: str, body: str) -> Path:
        """Legt die Datei exklusiv an: Bestehendes wird nie ueberschrieben, Symlinks nie verfolgt."""
        for attempt in range(1, 100):
            path = directory / (f"{stem}.md" if attempt == 1 else f"{stem}-{attempt}.md")
            try:
                handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
            except FileExistsError:
                continue
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(body)
            return path
        raise LimbError(ErrorCode.ALREADY_EXISTS, f"Kein freier Dateiname fuer {stem!r}.")

    # ----------------------------------------------------------------- Status
    def status(self) -> dict[str, Any]:
        present = self.root.is_dir()
        return {
            "present": present,
            "notes": sum(1 for _ in self.notes()) if present else 0,
            "git": (self.root / ".git").exists(),
            "fts5": _fts5_available(),
            "write_folders": list(WRITE_FOLDERS),
        }


def _title_of(text: str, path: Path) -> str:
    found = re.search(r'^title: "?(.+?)"?$', text[:2000], re.MULTILINE) or re.search(r"^# (.+)$", text, re.MULTILINE)
    return found.group(1).strip() if found else path.stem


def _fts5_available() -> bool:
    with contextlib.closing(sqlite3.connect(":memory:")) as db:
        try:
            db.execute("CREATE VIRTUAL TABLE probe USING fts5(body)")
        except sqlite3.OperationalError:
            return False
    return True


def _limit(params: Mapping[str, Any]) -> int:
    return min(MAX_LIMIT, max(1, int(params.get("limit", DEFAULT_LIMIT))))


class VaultLimb(LimbBase):
    name = "vault"
    version = "1.0.0"
    description = "Obsidian-Vault: vault.ping / vault.search / vault.read / vault.capture"

    def _store(self) -> VaultStore:
        return VaultStore.locate(self.config.repo_root, Path(self.config.runtime_dir))

    def handlers(self) -> dict[str, Callable[[Mapping[str, Any], LimbContext], Mapping[str, Any]]]:
        return {
            "vault.ping": self._ping,
            "vault.search": self._search,
            "vault.read": self._read,
            "vault.capture": self._capture,
        }

    # ---------------------------------------------------------------- Handler
    def _ping(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        return {"limb": self.name, "version": self.version, **self._store().status()}

    def _search(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        return self._store().search(str(params.get("query", "")), limit=_limit(params), folder=str(params.get("folder", "")))

    def _read(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        return self._store().read(str(params.get("path", "")))

    def _capture(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        text = params.get("text")
        if not isinstance(text, str) or not text.strip():
            raise LimbError(ErrorCode.SCHEMA_INVALID, "params.text fehlt oder ist leer.", hint='Beispiel: {"text": "Idee"}')
        if len(text) > MAX_NOTE_CHARS:
            raise LimbError(ErrorCode.SCHEMA_INVALID, f"params.text ist laenger als {MAX_NOTE_CHARS} Zeichen.")
        return self._store().capture(
            text,
            folder=str(params.get("folder", "Inbox")),
            title=str(params.get("title", "")),
            source=str(params.get("source", "agent"))[:40],
        )


if __name__ == "__main__":
    sys.exit(VaultLimb().main())

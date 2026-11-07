"""Dynamic FFI-Plugin-Architektur mit Hot-Reloading fuer Rust-Limbs (.so).

Ein Rust-Limb wird als ``cdylib`` (Shared Library) kompiliert und exportiert
eine stabile, C-kompatible Schnittstelle -- siehe `rust/nio-limb/src/lib.rs``:

    const char *limb_contract_version(void);
    int          init_limb(void);
    int          process_payload(const uint8_t *data, size_t data_len,
                                 uint8_t *out, size_t out_cap,
                                 size_t *out_len);
    void         shutdown_limb(void);

Der Python-Orchestrator ladet die ``.so`` zur Laufzeit via ``ctypes``
(Stdlib-only, keine Fremdabhängigkeit). ``LimbHotReloader`` hält genau eine
Version einer Limb-Bibliothek im RAM. ``reload()`` tauscht **atomar** aus:

1. Die neue ``.so`` wird geladen und ``init_limb`` wird aufgerufen.
   Schlägt das fehl, läuft die alte Limb unverändert weiter (fail-fast).
2. Erst dann wird die alte Bibliothek über ``shutdown_limb`` + ``dlclose``
   entladen und der interne Funktionszeiger auf die neue Bibliothek umgebogen.

Während des Austauschs kann eine Schreibsperre auf dem
``SharedMemoryRingSink`` (``orchestrator/ring.py``) gehalten werden
(``sink.write_lock()``), sodass kein Event in den Ring geschrieben wird, während
der Funktionszeiger wechselt -- Null Downtime, kein Neustart des Hauptprozesses.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from orchestrator.ring import SharedMemoryRingSink

#: C-ABI Contract-Version der NIO-Rust-Limbs (muss mit der Rust-Seite
#: `rust/nio-limb/src/lib.rs::LIMB_CONTRACT_VERSION` identisch sein).
_CONTRACT_VERSION = "1.0"

#: Maximaler Ausgabepuffer pro `process_payload`-Aufruf (Bytes).
_MAX_OUT = 65536


class LimbFFIError(RuntimeError):
    """Fehler beim Laden, Initialisieren oder Austauschen einer .so-Limb."""


@dataclass(frozen=True)
class LimbFFISpec:
    name: str
    so_path: Path
    contract_version: str


#: ctypes-Signatur für libc.dlclose(void *handle) -> int.
_DlClose = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)


class _LoadedLimb:
    """Eine im RAM geladene .so mit aufgelösten Funktionszeigern."""

    def __init__(self, so_path: Path, dlclose: _DlClose) -> None:
        self.path = so_path
        self.lib = ctypes.CDLL(str(so_path))  # RTLD_LOCAL, RTLD_LAZY
        self._dlclose = dlclose
        self.contract_version = "?"
        self._configured = False
        try:
            self._bind_symbols()
            self.contract_version = self._read_contract_version()
            if self.contract_version != _CONTRACT_VERSION:
                raise LimbFFIError(
                    "Limb-Contract-Version stimmt nicht überein: "
                    f"{self.contract_version!r} != {_CONTRACT_VERSION!r} "
                    f"({self.path})"
                )
            rc = self.lib.init_limb()
            if rc != 0:
                raise LimbFFIError(f"init_limb lieferte Status {rc} ({self.path})")
            self._configured = True
        except Exception:
            self._dispose()
            raise

    # -- Symbole ---------------------------------------------------------

    def _bind_symbols(self) -> None:
        lib = self.lib
        lib.limb_contract_version.restype = ctypes.c_char_p
        lib.limb_contract_version.argtypes = []

        lib.init_limb.restype = ctypes.c_int
        lib.init_limb.argtypes = []

        lib.process_payload.restype = ctypes.c_int
        lib.process_payload.argtypes = [
            ctypes.c_char_p,                               # data
            ctypes.c_size_t,                               # data_len
            ctypes.c_char_p,                               # out
            ctypes.c_size_t,                               # out_cap
            ctypes.POINTER(ctypes.c_size_t),               # out_len
        ]

        lib.shutdown_limb.restype = None
        lib.shutdown_limb.argtypes = []

    def _read_contract_version(self) -> str:
        raw = self.lib.limb_contract_version()
        if raw is None:
            raise LimbFFIError(f"limb_contract_version gab NULL zurück ({self.path})")
        return raw.decode("utf-8")

    # -- Aufrufe ----------------------------------------------------------

    def process(self, data: bytes) -> bytes:
        """Übermittelt `data` an die Limb und liefert die Ausgabebytes."""
        out = ctypes.create_string_buffer(_MAX_OUT)
        out_len = ctypes.c_size_t(0)
        rc = self.lib.process_payload(
            data, len(data), out, _MAX_OUT, ctypes.byref(out_len)
        )
        if rc != 0:
            raise LimbFFIError(f"process_payload lieferte Status {rc} ({self.path})")
        return bytes(out.raw[: out_len.value])

    def shutdown(self) -> None:
        with contextlib.suppress(Exception):
            self.lib.shutdown_limb()

    def handle(self) -> int:
        """Handle der unter `dlopen` zurückgegebenen Bibliothek."""
        handle = getattr(self.lib, "_handle", None)
        if handle is None:
            raise LimbFFIError(f"Kein dlopen-Handle für {self.path}")
        return int(handle)

    def _dispose(self) -> None:
        self.shutdown()
        with contextlib.suppress(Exception):
            if callable(self._dlclose):
                self._dlclose(self.handle())
        self._configured = False


class LimbHotReloader:
    """Lädt eine .so-Limb und tauscht sie zur Laufzeit atomar aus."""

    def __init__(self, so_path: str | Path, name: str | None = None) -> None:
        self.name = name or Path(so_path).name
        self._lock = threading.RLock()
        self._loaded: _LoadedLimb | None = None
        # Handle auf den Hauptprozess (enthält libc mit dlclose).
        libc = ctypes.CDLL(None, use_errno=True)
        libc.dlclose.argtypes = [ctypes.c_void_p]
        libc.dlclose.restype = ctypes.c_int
        self._dlclose: _DlClose = libc.dlclose
        self.load(Path(so_path))

    # -- Eigenschaften ----------------------------------------------------

    @property
    def path(self) -> Path:
        if self._loaded is None:
            raise LimbFFIError("Keine Limb geladen")
        return self._loaded.path

    @property
    def contract_version(self) -> str:
        if self._loaded is None:
            raise LimbFFIError("Keine Limb geladen")
        return self._loaded.contract_version

    # -- Lebenszyklus -----------------------------------------------------

    def load(self, so_path: str | Path) -> LimbFFISpec:
        """Lädt eine .so als aktuellen Slot (erste Ladung oder Ersatz)."""
        with self._lock:
            limb = _LoadedLimb(Path(so_path), self._dlclose)
            self._loaded = limb
            return LimbFFISpec(
                name=self.name,
                so_path=Path(so_path).resolve(),
                contract_version=limb.contract_version,
            )

    def reload(self, new_so_path: str | Path) -> LimbFFISpec:
        """Atomarer Hot-Swap: neue .so laden, alte entladen, Zeiger tauschen.

        Reihenfolge (fail-fast, alte Limb läuft bei Fehlern weiter):

        1. neue .so laden + `init_limb` aufrufen
        2. alte .so `shutdown_limb` + `dlclose`
        3. interner Slot auf die neue Bibliothek umbiegen
        """
        new_so_path = Path(new_so_path)
        with self._lock:
            replacement = _LoadedLimb(new_so_path, self._dlclose)  # wirft bei Fehler
            old = self._loaded
            self._loaded = replacement
            if old is not None:
                old.shutdown()
                if callable(old._dlclose):
                    old._dlclose(old.handle())
            return LimbFFISpec(
                name=self.name,
                so_path=new_so_path.resolve(),
                contract_version=replacement.contract_version,
            )

    def process_payload(self, data: bytes) -> bytes:
        """Übermittelt `data` an die aktuell geladene Limb."""
        with self._lock:
            if self._loaded is None:
                raise LimbFFIError("Keine Limb geladen")
            return self._loaded.process(data)

    def shutdown(self) -> None:
        """Entlädt die aktuelle Limb (shutdown_limb + dlclose)."""
        with self._lock:
            if self._loaded is None:
                return
            self._loaded.shutdown()
            if callable(self._loaded._dlclose):
                self._loaded._dlclose(self._loaded.handle())
            self._loaded = None

    def __enter__(self) -> LimbHotReloader:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.shutdown()


def process_intent_file(
    reloader: LimbHotReloader, intent_file: str | Path
) -> dict[str, Any]:
    """Bridge für den Orchestrator: liest eine Intent-Datei (Protokoll 1.2),
    übermittelt die Task-Parameter als JSON an die geladene .so-Limb und
    liefert das Ergebnis als Dict zurück. Kein Subprozess, kein Neustart."""
    intent = json.loads(Path(intent_file).read_text(encoding="utf-8"))
    if not isinstance(intent, dict):
        raise LimbFFIError(f"Intent muss ein JSON-Objekt sein: {intent_file}")
    task = intent.get("task", {})
    params = task.get("params", {}) if isinstance(task, dict) else {}
    payload = json.dumps(params, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    out = reloader.process_payload(payload)
    try:
        return json.loads(out.decode("utf-8"))
    except json.JSONDecodeError:
        return {"raw": out.decode("utf-8", errors="replace")}


def write_lock_around(
    sink: SharedMemoryRingSink,
    reloader: LimbHotReloader,
    new_so_path: str | Path,
) -> LimbFFISpec:
    """Führt `reloader.reload()` unter der Schreibsperre des Ring-Sinks aus.

    Während des Hot-Swap schreibt kein Event in den Shared-Memory-Ring, sodass
    der Funktionszeiger unter einer stabilen Schreibsperre ausgetauscht wird --
    der atomare Austausch aus dem Architektur-Vorschlag.
    """
    with sink.write_lock():
        return reloader.reload(new_so_path)

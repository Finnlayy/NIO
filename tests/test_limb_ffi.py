"""Tests für die dynamische FFI-Plugin-Architektur mit Hot-Reloading.

Es wird keine Rust-Toolchain benötigt: Die Tests kompilieren kleine C
Shared Libraries mit der exakt gleichen C-ABI wie
`rust/nio-limb/src/lib.rs` via `gcc` und beweisen über diese Stand-ins das
Lade-, Atomare-Swap- und Entlade-Verhalten von `LimbHotReloader` —
einschließlich der Schreibsperre auf dem ``SharedMemoryRingSink``.
"""

from __future__ import annotations

import ctypes  # noqa: F401  (CC-ABI-Stand-ins nutzen es indirekt über limb_ffi)
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.kanban.limb_ffi import LimbFFIError, LimbHotReloader, process_intent_file, write_lock_around
from orchestrator.ring import SharedMemoryRingSink

_HAS_GCC = shutil.which("gcc") is not None or shutil.which("cc") is not None

# ---------------------------------------------------------------------------
# C-Stand-ins für die Rust-Limb-ABI (vertraglich identisch mit rust/nio-limb)
# ---------------------------------------------------------------------------

_C_SRC_V1 = r"""
#include <stddef.h>
#include <stdint.h>
#include <string.h>
const char *limb_contract_version(void) { return "1.0"; }
int init_limb(void) { return 0; }
int process_payload(const uint8_t *data, size_t data_len,
                    uint8_t *out, size_t out_cap, size_t *out_len) {
    if (!data || !out || !out_len) return -1;
    size_t n = 3 + data_len;               /* "v1:" + payload */
    if (n > out_cap) return -3;
    memcpy(out, "v1:", 3);
    memcpy(out + 3, data, data_len);
    *out_len = n;
    return 0;
}
void shutdown_limb(void) {}
"""

_C_SRC_V2 = r"""
#include <stddef.h>
#include <stdint.h>
#include <string.h>
const char *limb_contract_version(void) { return "1.0"; }
int init_limb(void) { return 0; }
int process_payload(const uint8_t *data, size_t data_len,
                    uint8_t *out, size_t out_cap, size_t *out_len) {
    if (!data || !out || !out_len) return -1;
    size_t n = 3 + 2 * data_len;           /* "v2:" + payload + payload */
    if (n > out_cap) return -3;
    memcpy(out, "v2:", 3);
    memcpy(out + 3, data, data_len);
    memcpy(out + 3 + data_len, data, data_len);
    *out_len = n;
    return 0;
}
void shutdown_limb(void) {}
"""

_C_SRC_BAD_VERSION = r"""
#include <stddef.h>
#include <stdint.h>
const char *limb_contract_version(void) { return "9.9"; }
int init_limb(void) { return 0; }
int process_payload(const uint8_t *data, size_t data_len,
                    uint8_t *out, size_t out_cap, size_t *out_len) {
    return 0;
}
void shutdown_limb(void) {}
"""

_C_SRC_BAD_INIT = r"""
#include <stddef.h>
#include <stdint.h>
const char *limb_contract_version(void) { return "1.0"; }
int init_limb(void) { return 7; }
int process_payload(const uint8_t *data, size_t data_len,
                    uint8_t *out, size_t out_cap, size_t *out_len) {
    return 0;
}
void shutdown_limb(void) {}
"""


def _compile_cc(source: str, out_path: Path) -> None:
    cc = shutil.which("gcc") or shutil.which("cc")
    c_file = out_path.with_suffix(".c")
    c_file.write_text(source, encoding="utf-8")
    subprocess.run(
        [cc, "-shared", "-fPIC", "-O2", "-o", str(out_path), str(c_file)],
        check=True,
        capture_output=True,
    )


@unittest.skipUnless(_HAS_GCC, "gcc/cc nicht verfügbar – FFI-Hot-Reload-Tests übersprungen")
class LimbHotReloadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="nio-ffi-test-"))
        _compile_cc(_C_SRC_V1, cls.tmpdir / "liblimb_a.so")
        _compile_cc(_C_SRC_V2, cls.tmpdir / "liblimb_b.so")
        _compile_cc(_C_SRC_BAD_VERSION, cls.tmpdir / "liblimb_badver.so")
        _compile_cc(_C_SRC_BAD_INIT, cls.tmpdir / "liblimb_badinit.so")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_load_and_process(self) -> None:
        with LimbHotReloader(self.tmpdir / "liblimb_a.so") as reloader:
            self.assertEqual(reloader.contract_version, "1.0")
            self.assertEqual(reloader.process_payload(b"hello"), b"v1:hello")

    def test_reload_swaps_behavior(self) -> None:
        reloader = LimbHotReloader(self.tmpdir / "liblimb_a.so")
        try:
            self.assertEqual(reloader.process_payload(b"x"), b"v1:x")
            spec = reloader.reload(self.tmpdir / "liblimb_b.so")
            self.assertEqual(spec.contract_version, "1.0")
            self.assertEqual(reloader.process_payload(b"x"), b"v2:xx")
            self.assertEqual(reloader.path, (self.tmpdir / "liblimb_b.so").resolve())
        finally:
            reloader.shutdown()

    def test_reload_failure_keeps_old(self) -> None:
        reloader = LimbHotReloader(self.tmpdir / "liblimb_b.so")
        try:
            self.assertEqual(reloader.process_payload(b"q"), b"v2:qq")
            with self.assertRaises((LimbFFIError, OSError)):
                reloader.reload(self.tmpdir / "liblimb_does_not_exist.so")
            # Die alte Limb läuft unverändert weiter (fail-fast Swap).
            self.assertEqual(reloader.process_payload(b"q"), b"v2:qq")
        finally:
            reloader.shutdown()

    def test_bad_contract_version_raises(self) -> None:
        with self.assertRaises(LimbFFIError):
            LimbHotReloader(self.tmpdir / "liblimb_badver.so")

    def test_bad_init_raises(self) -> None:
        with self.assertRaises(LimbFFIError):
            LimbHotReloader(self.tmpdir / "liblimb_badinit.so")

    def test_shutdown_unloads_and_reload_works(self) -> None:
        reloader = LimbHotReloader(self.tmpdir / "liblimb_a.so")
        reloader.shutdown()
        with self.assertRaises(LimbFFIError):
            reloader.process_payload(b"after-shutdown")
        spec = reloader.load(self.tmpdir / "liblimb_b.so")
        self.assertEqual(spec.contract_version, "1.0")
        self.assertEqual(reloader.process_payload(b"z"), b"v2:zz")
        reloader.shutdown()

    def test_empty_payload(self) -> None:
        reloader = LimbHotReloader(self.tmpdir / "liblimb_a.so")
        try:
            self.assertEqual(reloader.process_payload(b""), b"v1:")
        finally:
            reloader.shutdown()

    def test_concurrent_swap_and_process(self) -> None:
        reloader = LimbHotReloader(self.tmpdir / "liblimb_a.so")
        stop = threading.Event()
        results: list[bytes] = []
        errors: list[Exception] = []

        def worker() -> None:
            while not stop.is_set():
                try:
                    results.append(reloader.process_payload(b"w"))
                except Exception as exc:  # kein Prozess-Absturz unter parallelem Swap
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for _ in range(8):
            target = "liblimb_b.so" if len(results) % 2 else "liblimb_a.so"
            reloader.reload(self.tmpdir / target)
        stop.set()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        reloader.shutdown()

    def test_process_intent_file_bridge(self) -> None:
        class _StubReloader:
            contract_version = "1.0"

            def process_payload(self, data: bytes) -> bytes:
                self.last = data
                return b'{"ok": true, "echo": "params"}'

        stub = _StubReloader()
        with tempfile.TemporaryDirectory() as td:
            intent = Path(td) / "intent.json"
            intent.write_text(
                json.dumps(
                    {
                        "protocol": "neu/intent",
                        "version": "1.2",
                        "task": {
                            "operation": "limb.eval",
                            "params": {"a": 1, "b": 2},
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = process_intent_file(stub, intent)
            self.assertEqual(result, {"ok": True, "echo": "params"})
            self.assertIn(b'"a":1', stub.last)  # json.dumps mit separators=(",", ":")


@unittest.skipUnless(_HAS_GCC, "gcc/cc nicht verfügbar")
class RingWriteLockTest(unittest.TestCase):
    def test_write_lock_excludes_ring_puts(self) -> None:
        sink = SharedMemoryRingSink(
            name=f"nio-ffi-ring-test-{os.getpid()}", capacity=32, slot_size=256
        )
        try:
            blocked = threading.Event()
            done = threading.Event()
            result: list[Exception | None] = [None]

            def writer() -> None:
                try:
                    blocked.set()          # kurz davor, den Ring-Lock zu brauchen
                    sink.write({"event": "waehrend-der-sperre"})
                except Exception as exc:  # noqa: BLE001
                    result[0] = exc
                finally:
                    done.set()

            with sink.write_lock():        # Orchestrator hält Schreibsperre
                time.sleep(0.1)            # sicherstellen, dass der Schreiber ansteht
                t = threading.Thread(target=writer)
                t.start()
                self.assertTrue(blocked.wait(timeout=5), "Schreiber blockiert nicht")
            # Sperre freigegeben -> Schreiber darf durchlaufen
            self.assertTrue(done.wait(timeout=10), "Schreiber wurde nie freigegeben")
            t.join(timeout=10)
            self.assertFalse(t.is_alive())
            self.assertIsNone(result[0])
            self.assertEqual(sink.available(), 1)
        finally:
            sink.unlink()

    def test_write_lock_around_hot_reload(self) -> None:
        tmpdir = Path(tempfile.mkdtemp(prefix="nio-ffi-ring-"))
        try:
            _compile_cc(_C_SRC_V1, tmpdir / "liblimb_a.so")
            sink = SharedMemoryRingSink(
                name=f"nio-ffi-ring-around-{os.getpid()}", capacity=32, slot_size=256
            )
            try:
                reloader = LimbHotReloader(tmpdir / "liblimb_a.so")
                try:
                    spec = write_lock_around(sink, reloader, tmpdir / "liblimb_a.so")
                    self.assertEqual(spec.contract_version, "1.0")
                    self.assertEqual(reloader.process_payload(b"ring"), b"v1:ring")
                    # Während des Swap wurde nichts in den Ring geschrieben.
                    self.assertEqual(sink.available(), 0)
                finally:
                    reloader.shutdown()
            finally:
                sink.unlink()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

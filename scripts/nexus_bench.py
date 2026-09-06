#!/usr/bin/env python3
"""Benchmark fuer Nexus-Triad Nr.1 (siehe ``.nio/nexus.md``).

Misst die drei Fokusbereiche des kontinuierlichen Loops:

* **Focus A -- Sub-ms IPC / Event-Bus:** ``EventBus.emit`` Latenz (Null-Sink) vorher
  (Inline-Baseline mit ``datetime``-Zeitstempel + doppelter ``payload``-Kopie) gegen
  die optimierte Fast-Path-Variante; dazu der opt-in Shared-Memory-Ring vs. Datei.
* **Focus B -- Fast-Path Schema-Bench:** ``core.schemacheck.validate`` gegen das
  normative ``protocol/intent.schema.json`` (Reference-Baseline im Journal).
* **Focus C -- Ledger-Kompaktierung:** ``FileTransport.compact_archive`` -- Eintrag-
  und Byte-Reduktion inkl. Integritaetspruefung (``verify_archive``).

Ausgabe ist maschinenlesbar (JSON) auf stdout, damit CI/Skripte die Werte weiterreichen
koennen. Laufzeit ~2-5 s, keine externen Abhaengigkeiten.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
for _entry in (str(Path(__file__).resolve().parent), str(_REPO), str(_REPO / "orchestrator"), str(_REPO / "core")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from core.config import NeuConfig  # noqa: E402
from core.kernel import Kernel  # noqa: E402
from core.protocol import Operations, Result, new_id, utc_now_iso  # noqa: E402
from core.schemacheck import validate as v_validate  # noqa: E402
from orchestrator.events import CollectingSink, Event, EventBus  # noqa: E402
from orchestrator.ring import SharedMemoryRingSink  # noqa: E402
from orchestrator.transport import FileTransport  # noqa: E402

#: Gemessene Baseline auf Commit 2639525 (vor den Optimierungen). Diese Werte
#: wurden mit demselben Skript-Aufbau ermittelt und dienen als Referenz fuer den
#: Delta-Vergleich im PR-Body.
REFERENCE_BASELINE = {
    "focus_a_emit_us": 2.81,
    "focus_a_emit_collect_us": 3.57,
    "focus_b_validate_us": 77.20,
}


class _NullSink:
    name = "null"

    def write(self, record: Mapping[str, Any]) -> None:
        pass


def _baseline_emit(kind: str, payload: dict[str, Any], *, job_id: str, clock_s: float | None, seq: int) -> Event:
    """Repliziert den alten ``EventBus.emit`` (datetime-Zeitstempel + doppelte Kopie)."""
    event = Event(
        kind=kind,
        payload=dict(payload),
        seq=seq,
        timestamp=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        job_id=job_id,
        clock_s=None if clock_s is None else round(float(clock_s), 3),
    )
    event.to_dict()
    return event


def bench_focus_a(results: dict[str, Any]) -> None:
    payload = {"tick_s": 0.5, "clock_s": 1.0}
    bus = EventBus([_NullSink()])
    n = 200_000

    # Baseline (alte Semantik: datetime + to_dict Doppelkopie)
    t0 = time.perf_counter_ns()
    for i in range(n):
        _baseline_emit("timer.tick", payload, job_id="job_x", clock_s=1.0, seq=i)
    baseline = (time.perf_counter_ns() - t0) / n / 1000.0

    # Optimiert (echter Fast-Path)
    t0 = time.perf_counter_ns()
    for _ in range(n):
        bus.emit("timer.tick", payload, job_id="job_x", clock_s=1.0)
    optimized = (time.perf_counter_ns() - t0) / n / 1000.0

    # CollectingSink (echte Zustellung inkl. Sink-Kopie)
    collector = CollectingSink()
    bus2 = EventBus([collector])
    t0 = time.perf_counter_ns()
    for _ in range(n):
        bus2.emit("timer.tick", payload, job_id="job_x", clock_s=1.0)
    collect = (time.perf_counter_ns() - t0) / n / 1000.0
    assert len(collector.records) == n

    # Shared-Memory-Ring (opt-in) vs. Datei-Flush je Event
    ring = SharedMemoryRingSink(capacity=200_000, slot_size=2048)
    t0 = time.perf_counter_ns()
    for _ in range(n):
        ring.write(payload)
    ring_us = (time.perf_counter_ns() - t0) / n / 1000.0
    ring.unlink()

    results["focus_a"] = {
        "emit_baseline_us": round(baseline, 3),
        "emit_optimized_us": round(optimized, 3),
        "emit_delta_us": round(baseline - optimized, 3),
        "emit_speedup_x": round(baseline / optimized, 2),
        "emit_collect_us": round(collect, 3),
        "shared_mem_ring_write_us": round(ring_us, 3),
        "reference_baseline_us": REFERENCE_BASELINE["focus_a_emit_us"],
    }


def bench_focus_b(results: dict[str, Any]) -> None:
    config = NeuConfig.load(_REPO, mode="dev", runtime_dir=Path(tempfile.mkdtemp(prefix="neu-bench-")) / "runtime")
    config.ensure_dirs()
    ops = Operations.load(config.protocol_dir / "operations.json")
    kernel = Kernel(config, ops)
    intent = kernel.build_intent(operation="sys.echo", params={"message": "ping"}, limb="echo", goal="Bench")
    schema = json.loads((config.protocol_dir / "intent.schema.json").read_text(encoding="utf-8"))
    data = intent.to_dict()
    n = 4000

    for _ in range(100):  # Warm-up (Regex-Cache)
        v_validate(data, schema)
    t0 = time.perf_counter_ns()
    for _ in range(n):
        v_validate(data, schema)
    optimized = (time.perf_counter_ns() - t0) / n / 1000.0

    # Negative Kontrolle: der Pruefer findet Fehler weiterhin
    errors = v_validate({"bad": "x"}, {"type": "object", "required": ["x"]})
    assert errors, "Pruefer darf Fehler nicht durchwinken"

    results["focus_b"] = {
        "validate_optimized_us": round(optimized, 3),
        "reference_baseline_us": REFERENCE_BASELINE["focus_b_validate_us"],
        "delta_us": round(REFERENCE_BASELINE["focus_b_validate_us"] - optimized, 3),
        "speedup_x": round(REFERENCE_BASELINE["focus_b_validate_us"] / optimized, 2),
    }


def bench_focus_c(results: dict[str, Any]) -> None:
    rt = tempfile.mkdtemp(prefix="neu-arch-bench-")
    config = NeuConfig.load(_REPO, mode="dev", runtime_dir=Path(rt) / "runtime")
    config.ensure_dirs()
    ops = Operations.load(config.protocol_dir / "operations.json")
    kernel = Kernel(config, ops)
    transport = FileTransport(config)

    total = 120
    for i in range(total):
        intent = kernel.build_intent(operation="sys.echo", params={"message": f"m{i}"}, limb="echo", goal=f"Goal {i}")
        result = Result(
            result_id=new_id("res"),
            intent_id=intent.intent_id,
            trace_id=intent.trace_id,
            status="success",
            operation="sys.echo",
            limb_name="echo",
            started_at=utc_now_iso(),
            finished_at=utc_now_iso(),
            output={"echo": f"m{i}"},
        )
        transport.archive(intent, result, {"verdict": "accept", "iteration": intent.iteration})

    before = transport.archive_stats()
    # Eintraege in die Vergangenheit aeltern (aehnlich realer Lauf ueber Monate)
    cutoff = time.time() - 10 * 86400
    for day_dir in config.archive_dir.iterdir():
        if day_dir.is_dir() and day_dir.name != "compacted":
            for entry in day_dir.iterdir():
                if entry.is_dir():
                    os.utime(entry, (cutoff, cutoff))

    summary = transport.compact_archive(older_than_days=7)
    after = transport.archive_stats()
    violations = transport.verify_archive()

    snapshot_bytes_after = sum(info["bytes"] for info in after["compacted"].values())
    results["focus_c"] = {
        "entries_before": before["total_entries"],
        "entries_after": after["total_entries"],
        "expanded_bytes_before": before["total_bytes"],
        "expanded_bytes_after": after["total_bytes"],
        "snapshot_bytes_after": snapshot_bytes_after,
        "total_bytes_after": after["total_bytes"] + snapshot_bytes_after,
        "bytes_freed": summary["bytes_freed"],
        "pruned_dirs": summary["pruned_dirs"],
        "compacted_entries": len(summary["compacted_entries"]),
        "integrity_violations": len(violations),
    }


def main() -> int:
    results: dict[str, Any] = {}
    bench_focus_a(results)
    bench_focus_b(results)
    bench_focus_c(results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Nexus Triad Nr.3, Cycle 1: der atomare JSON-Schreiber und der Persistenz-Text.

Gegenstand ist die *Semantik*, nicht die Geschwindigkeit:

* ``atomic_write_bytes`` muss byte-identisch das alte Dokument schreiben (gleiches
  ``json.dumps``-Ergebnis, gleicher Modus, kein Temp-Rest), das Ziel bei einem
  Fehler unangetastet lassen und dem ``fsync``-Vertrag des Transports folgen.
* ``ScheduleState.persist_text`` darf kein zweites Format sein: was auf der Platte
  liegt, muss nach ``json.loads`` exakt ``to_dict()`` sein -- auch nach Kuerzung auf
  ``HISTORY_LIMIT``, nach direktem Eingriff von aussen und nach load()/save()-Rundlauf.

Reine Standardbibliothek, kein Limb-Subprozess.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.atomic import atomic_write_bytes  # noqa: E402
from core.config import NeuConfig  # noqa: E402
from core.job import JobStore  # noqa: E402
from core.kernel import Kernel  # noqa: E402
from core.protocol import Operations, parse_timestamp  # noqa: E402
from orchestrator.events import CollectingSink, build_event_bus  # noqa: E402
from orchestrator.scheduler import HISTORY_LIMIT, Scheduler  # noqa: E402
from orchestrator.transport import write_json_atomic, write_jsonl_atomic  # noqa: E402


class AtomicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nio-atomic-")
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_byte_identisch_zum_alten_weg(self) -> None:
        doc = {"job_id": "job_1", "notiz": "Umlaute: äöü ß", "werte": [1, 2.5, None, True]}
        expected = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        target = self.tmp / "doc.json"
        returned = atomic_write_bytes(target, expected, fsync=True, mode=0o600)
        self.assertEqual(returned, target)
        self.assertEqual(target.read_bytes(), expected)

    def test_kein_temp_reste_und_rechte(self) -> None:
        target = self.tmp / "sub" / "doc.json"
        atomic_write_bytes(target, b"{}\n", mode=0o600)
        self.assertEqual(sorted(p.name for p in target.parent.iterdir()), ["doc.json"])
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        other = self.tmp / "loose.json"
        atomic_write_bytes(other, b"{}\n")
        # nicht grosszuegiger als der Wunsch des Aufrufers (die Maske des Prozesses
        # darf schaerfer sein, aber nie milder):
        self.assertEqual(other.stat().st_mode & 0o777 & ~0o644, 0)

    def test_erscheint_ganz_oder_gar_nicht(self) -> None:
        target = self.tmp / "state.json"
        atomic_write_bytes(target, b'{"v":1}\n')
        with mock.patch("core.atomic.os.replace", side_effect=OSError("replace fehlgeschlagen")):
            with self.assertRaises(OSError):
                atomic_write_bytes(target, b'{"v":2}\n')
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"v": 1})
        self.assertEqual([p.name for p in target.parent.iterdir()], ["state.json"], "kein Temp-Waise")
        with mock.patch("core.atomic.os.write", side_effect=OSError("write fehlgeschlagen")):
            with self.assertRaises(OSError):
                atomic_write_bytes(target, b'{"v":3}\n')
        self.assertEqual([p.name for p in target.parent.iterdir()], ["state.json"])

    def test_fsync_vertrag_des_transports(self) -> None:
        target = self.tmp / "intent.json"
        with mock.patch("core.atomic.os.fsync") as fsync:
            atomic_write_bytes(target, b"{}\n", fsync=True)
            self.assertEqual(fsync.call_count, 1)
            atomic_write_bytes(self.tmp / "state2.json", b"{}\n")
            self.assertEqual(fsync.call_count, 1, "Zustandsdateien syncen nicht zusaetzlich")

    def test_parallele_schreiber_nutzen_getrennte_temps(self) -> None:
        target = self.tmp / "shared.json"
        errors: list[BaseException] = []

        def writer(payload: int) -> None:
            try:
                atomic_write_bytes(target, json.dumps({"n": payload}).encode())
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertIn(json.loads(target.read_text(encoding="utf-8")), [{"n": i} for i in range(12)])
        self.assertEqual([p.name for p in target.parent.iterdir()], ["shared.json"])


class TransportWriterTests(unittest.TestCase):
    """Die alten Dokumente müssen unverändert bleiben -- Format ist Vertrag."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nio-transport-")
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_write_json_atomic_format_stabil(self) -> None:
        doc = {"intent_id": "intent_x", "text": "äöü", "zahl": 1.5}
        target = write_json_atomic(self.tmp / "intent.json", doc)
        self.assertEqual(target.read_text(encoding="utf-8"), json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_write_json_atomic_indent_none_wie_bisher(self) -> None:
        # indent=None ist beim alten Weg NICHT kompakt (json.dump nutzt dann die
        # Default-Separatoren) -- der Sidecar-Index haengt an genau diesen Bytes.
        doc = {"a": [1, 2]}
        target = write_json_atomic(self.tmp / "idx.json", doc, indent=None)
        self.assertEqual(target.read_bytes(), (json.dumps(doc, ensure_ascii=False) + "\n").encode("utf-8"))

    def test_write_jsonl_atomic_pro_zeile(self) -> None:
        records = [{"i": 0}, {"i": 1, "t": "x"}]
        target = write_jsonl_atomic(self.tmp / "snap.jsonl", records)
        lines = target.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line) for line in lines], records)
        self.assertTrue(all(", " not in line and ": " not in line for line in lines), "kompakt wie bisher")


class SchedulerPersistenzTests(unittest.TestCase):
    """persist_text() ist eine Ableitung, kein zweites Format."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nio-sched3-")
        tmp = Path(self._tmp.name)
        self.config = NeuConfig.load(
            REPO_ROOT,
            mode="dev",
            limits={
                "max_iterations": 1,
                "max_agents": 1,
                "max_limbs": 1,
                "max_concurrent_jobs": 1,
                "max_scheduled_jobs": 1,
            },
            runtime_dir=tmp / "runtime",
            workspace_dir=tmp / "workspace",
        )
        self.config.ensure_dirs()
        self.collector = CollectingSink()
        bus = build_event_bus(quiet=True, collector=self.collector)
        self.scheduler = Scheduler(self.config, bus=bus)
        self.kernel = Kernel(self.config, Operations.load(self.config.protocol_dir / "operations.json"))
        self.jobs = JobStore(self.config)
        self.addCleanup(self._tmp.cleanup)

    def state(self, triggers: list[dict]):
        intent = self.kernel.build_intent(
            operation="sys.echo",
            params={"message": "m"},
            limb="echo",
            goal="g",
            unlimited=True,
            tick_s=0.05,
            schedule=triggers,
        )
        record = self.jobs.create(intent.job.goal, timer_mode="unlimited", job_id=intent.job.job_id)
        return self.scheduler.attach(intent, t0=record.created_at, force=True)

    def fire(self, state, count: int) -> None:
        from datetime import timedelta

        origin = parse_timestamp(state.t0, "$.t0")
        for i in range(count):
            self.scheduler.tick(state, now=origin + timedelta(seconds=(i + 1) * 0.05))

    def test_persistierter_text_ist_to_dict(self) -> None:
        state = self.state([{"id": "takt", "action": "emit_event", "every_s": 0.05}])
        self.fire(state, 5)
        path = self.scheduler.path_for(state.job_id)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), state.to_dict())

    def test_kuerzung_auf_history_limit_bleibt_synchron(self) -> None:
        state = self.state([{"id": "takt", "action": "emit_event", "every_s": 0.05}])
        self.fire(state, HISTORY_LIMIT + 37)
        self.assertGreater(len(state.history), HISTORY_LIMIT - 1)
        self.assertEqual(len(state.history), HISTORY_LIMIT)
        self.assertEqual(len(state.hist_frags), HISTORY_LIMIT)
        path = self.scheduler.save(state)
        disk = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(disk["history"], state.to_dict()["history"])
        self.assertEqual(disk, state.to_dict())
        self.assertEqual(disk["history"][0]["seq"] if "seq" in disk["history"][0] else 0, 0)

    def test_fremder_griff_in_die_historie_erkennt_der_cache(self) -> None:
        state = self.state([{"id": "takt", "action": "emit_event", "every_s": 0.05}])
        self.fire(state, 3)
        state.history.append({"at": "2026-09-07T00:00:00.000Z", "kind": "fremd", "trigger_id": "", "action": "x"})
        disk = json.loads(self.scheduler.save(state).read_text(encoding="utf-8"))
        self.assertEqual(disk, state.to_dict(), "ohne Cache-Synchronisation wäre der Eintrag verloren")

    def test_frag_cache_reagiert_auf_kanten_der_liste(self) -> None:
        """Der Vertrag: Kopf/Ende muessen sich nur bei ``_record`` bewegen.

        Genau das wird ueberwacht (Anzahl, Laenge, Objekt-Identitaet an beiden
        Kanten). Ein Eingriff in die Listenmitte gilt per Definition als
        unveraendert -- es gibt keinen solchen Pfad; dieser Test haelt fest, dass
        der Cache nach jedem Feuerungs-schritt synchron bleibt.
        """
        state = self.state([{"id": "takt", "action": "emit_event", "every_s": 0.05}])
        self.fire(state, 4)
        self.scheduler.save(state)
        self.assertEqual(state.hist_built, state.hist_appends, "Cache gilt nach save() als frisch")
        for i in range(3):
            self.fire(state, 1)
            self.assertEqual(
                state.hist_frags[-1],
                json.dumps(state.history[-1], ensure_ascii=False, separators=(",", ":")),
                f"Fragment {i} muss zum Eintrag passen",
            )
        state.history.pop(0)  # Kante veraendert sich -> Neubau
        disk = json.loads(self.scheduler.save(state).read_text(encoding="utf-8"))
        self.assertEqual(disk, state.to_dict())

    def test_load_und_save_rundlauf(self) -> None:
        state = self.state([{"id": "takt", "action": "emit_event", "every_s": 0.05}])
        self.fire(state, 12)
        self.scheduler.save(state)
        again = self.scheduler.load(state.job_id)
        assert again is not None
        self.assertEqual(json.loads(self.scheduler.save(again).read_text(encoding="utf-8")), again.to_dict())
        self.fire(again, 3)
        self.assertEqual(json.loads(self.scheduler.save(again).read_text(encoding="utf-8")), again.to_dict())
        self.assertEqual(len(again.hist_frags), len(again.history), "Fragment-Puffer laeuft mit")

    def test_verzeichnis_entfernt_wiederholt_einmal(self) -> None:
        state = self.state([{"id": "takt", "action": "emit_event", "every_s": 0.05}])
        self.fire(state, 2)
        path = self.scheduler.save(state)
        expected = json.loads(path.read_text(encoding="utf-8"))
        for candidate in self.config.schedules_dir.iterdir():
            candidate.unlink()
        self.config.schedules_dir.rmdir()
        saved = self.scheduler.save(state)
        self.assertTrue(saved.is_file(), "fehlendes Verzeichnis wird wieder angelegt")
        disk = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual({k: v for k, v in disk.items() if k != "updated_at"}, {k: v for k, v in expected.items() if k != "updated_at"})

    def test_job_record_rundlauf_kompakt(self) -> None:
        record = self.jobs.create("Ziel mit Umlauten: äöü", timer_mode="unlimited")
        raw = self.jobs.path(record.job_id).read_bytes()
        disk = json.loads(raw)
        again = self.jobs.get(record.job_id).to_dict()
        # ``t_unlimited_s`` ist ein abgeleiteter Live-Wert (now - t0), der mit dem
        # Dateiinhalt nur verglichen werden kann, wenn man die Messzeit ausklammert:
        # er steigt zwischen Schreiben und Lesen um die Laufzeit. Kein Fehler der
        # Kompaktschreibung -- der alte indent=2-Pfad war genauso flatterhaft.
        for label, left, right in (("t_unlimited_s", disk.pop("t_unlimited_s"), again.pop("t_unlimited_s")),):
            self.assertIsInstance(left, float, label)
            self.assertGreaterEqual(right, left)
            self.assertLess(right - left, 5.0, label)
        self.assertEqual(disk, again)
        self.assertNotIn(b"\n  ", raw, "kompakt geschrieben statt indent=2")
        self.assertNotIn(b"\\u", raw, "ensure_ascii=False bleibt: Umlaut steht lesbar in der Datei")

    def test_cli_liest_neue_formatierung(self) -> None:
        from orchestrator.cli import main as cli_main

        record = self.jobs.create("g", timer_mode="unlimited")
        self.jobs.heartbeat(record.job_id, note="tick=7")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli_main(
                [
                    "--repo-root", str(REPO_ROOT),
                    "--runtime-dir", str(self.config.runtime_dir),
                    "--json",
                    "job", "show", record.job_id,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["job"]["job_id"], record.job_id)
        self.assertEqual(payload["job"]["outcome"]["heartbeat"], "tick=7")
        self.assertIn("tick=7", json.dumps(payload, ensure_ascii=False))

    def test_zustandsuhr_unchanged(self) -> None:
        from datetime import timedelta

        state = self.state([{"id": "schwelle", "action": "emit_event", "when": "elapsed >= 0.1"}])
        origin = parse_timestamp(state.t0, "$.t0")
        due = self.scheduler.tick(state, now=origin + timedelta(seconds=0.2))
        self.assertEqual(len(due), 1)
        self.assertEqual(json.loads(self.scheduler.save(state).read_text(encoding="utf-8")), state.to_dict())


if __name__ == "__main__":
    unittest.main()

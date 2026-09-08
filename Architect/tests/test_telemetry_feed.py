"""Tests fuer Engine-Telemetrie: Wire-Vertrag, Producer, echter UDS-Umlauf.

Die letzte Pruefung ist keine Attrappe: Sie bindet ein reales
``AF_UNIX``/``SOCK_DGRAM``-Socket, laesst ``TelemetryFeed`` darueber senden und
liest mit ``UDSBroadcastServer`` wieder aus -- derselbe Transport, den
``orchestrator/uds.py`` fuer ``runtime/bus.sock`` benutzt.
"""

import calendar
import json
import math
import sys
import tempfile
import time
import unittest
from pathlib import Path

ARCHITECT = Path(__file__).resolve().parents[1]
if str(ARCHITECT) not in sys.path:
    sys.path.insert(0, str(ARCHITECT))

from core.events import (  # noqa: E402
    TELEMETRY_PAYLOAD_FIELDS,
    VALID_EVENT_KINDS,
    EventBus,
    validate_telemetry_payload,
)
from limbs.telemetry_feed import (  # noqa: E402
    CVD_BINS,
    TelemetryFeed,
    hour_labels,
    load_uds_module,
)

# Die Repo-Wurzel gehoert nicht auf sys.path (zweites ``core``-Paket), also wird
# der UDS-Transport per Dateipfad geladen -- derselbe Weg wie im Producer.
_uds = load_uds_module()
UDSBroadcastServer = _uds.UDSBroadcastServer
UDSBroadcastSink = _uds.UDSBroadcastSink

VALID = {
    "microstructure_tick": {"imbalance_ratio": 0.12, "depth_2pct": 0.5, "footprint_delta": [0.1] * CVD_BINS},
    "gravity_tick": {"l2_depth": 0.4, "l3_iceberg": 0.2, "polymarket_prob": 0.5, "v_total": 0.37},
    "regime_tick": {"cluster_id": 0, "confidence": 0.8, "is_forbidden_zone": 0.0},
}


def tape(price=100.0):
    """Ein Orderbuch-Fenster: 8 Bids, 8 Asks, 12 Trades."""
    bids = [(price - 0.05 * (i + 1), 2.0 + i) for i in range(8)]
    asks = [(price + 0.05 * (i + 1), 1.5 + i) for i in range(8)]
    trades = [(price + (0.01 if i % 2 else -0.01), 1.0, i % 2 == 0) for i in range(12)]
    return bids, asks, trades


class RecordingSink:
    """Faengt ``write(record)`` ab -- dasselbe Protokoll wie ``UDSBroadcastSink``."""

    def __init__(self):
        self.records = []
        self.closed = False

    def write(self, record):
        self.records.append(record)

    def close(self):
        self.closed = True


class TestWireVertrag(unittest.TestCase):
    def test_drei_event_kinds_sind_whitelisted(self):
        for kind in TELEMETRY_PAYLOAD_FIELDS:
            self.assertIn(kind, VALID_EVENT_KINDS, kind)

    def test_gueltige_payloads_gehen_durch(self):
        for kind, payload in VALID.items():
            ok, reason = validate_telemetry_payload(kind, payload)
            self.assertTrue(ok, f"{kind}: {reason}")

    def test_fehlendes_feld_wird_abgewiesen(self):
        for kind, payload in VALID.items():
            for field in TELEMETRY_PAYLOAD_FIELDS[kind]:
                incomplete = {k: v for k, v in payload.items() if k != field}
                ok, reason = validate_telemetry_payload(kind, incomplete)
                self.assertFalse(ok, f"{kind} ohne {field}")
                self.assertIn(field, reason)

    def test_nicht_numerisch_wird_abgewiesen(self):
        # [1.0] ist ausdruecklich gueltig (Vektor); [] und Mappings sind es nicht.
        for bad in ("0.5", None, [], {"v": 1}, [1.0, "x"], [float("nan")]):
            payload = {**VALID["gravity_tick"], "v_total": bad}
            ok, _ = validate_telemetry_payload("gravity_tick", payload)
            self.assertFalse(ok, repr(bad))

    def test_bool_ist_keine_zahl(self):
        # isinstance(True, int) ist True -- ohne den bool-Zweig waere das durch.
        payload = {**VALID["regime_tick"], "is_forbidden_zone": True}
        ok, reason = validate_telemetry_payload("regime_tick", payload)
        self.assertFalse(ok)
        self.assertIn("is_forbidden_zone", reason)

    def test_nan_und_unendlich_werden_abgewiesen(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            payload = {**VALID["gravity_tick"], "v_total": bad}
            ok, reason = validate_telemetry_payload("gravity_tick", payload)
            self.assertFalse(ok, repr(bad))
            self.assertIn("endlich", reason)

    def test_unbekanntes_event_kind(self):
        ok, reason = validate_telemetry_payload("execution_complete", {"a": 1})
        self.assertFalse(ok)
        self.assertIn("kein Telemetrie-Event", reason)


class TestEventBusTelemetrie(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log = Path(self.tmpdir) / "system.log"
        self.bus = EventBus(system_log_path=str(self.log))
        self.bus.event_sinks["stderr"] = False

    def test_build_setzt_payload_und_symbol(self):
        event = self.bus.build_telemetry_event(
            "gravity_tick", VALID["gravity_tick"], symbol="BTCUSDT", clock_s=1.5
        )
        self.assertEqual(event["event_kind"], "gravity_tick")
        self.assertEqual(event["symbol"], "BTCUSDT")
        self.assertEqual(event["clock_s"], 1.5)
        self.assertEqual(event["payload"], VALID["gravity_tick"])

    def test_build_wirft_bei_unvollstaendigem_payload(self):
        with self.assertRaises(ValueError):
            self.bus.build_telemetry_event("gravity_tick", {"l2_depth": 0.4})

    def test_emit_telemetry_liefert_false_statt_zu_senden(self):
        self.assertFalse(self.bus.emit_telemetry("regime_tick", {"cluster_id": 0}))
        # Abgelehnt heisst: gar nichts geschrieben (nicht einmal eine leere Datei).
        self.assertFalse(self.log.exists())

    def test_emit_telemetry_schreibt_ndjson_mit_payload(self):
        self.assertTrue(self.bus.emit_telemetry("microstructure_tick",
                                                VALID["microstructure_tick"], symbol="ETHUSDT"))
        line = self.log.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        self.assertEqual(record["event_kind"], "microstructure_tick")
        self.assertEqual(record["symbol"], "ETHUSDT")
        self.assertEqual(record["payload"]["depth_2pct"], 0.5)


class TestTelemetryFeed(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bus = EventBus(system_log_path=str(Path(self.tmpdir) / "system.log"))
        self.bus.event_sinks["stderr"] = False
        self.bus.event_sinks["file"] = False
        self.sink = RecordingSink()
        self.feed = TelemetryFeed(self.bus, self.sink, symbol="BTCUSDT")

    def test_ein_tick_sendet_drei_events(self):
        bids, asks, trades = tape()
        sent = self.feed.on_tape(bids, asks, trades)
        self.assertEqual(sent, {k: True for k in VALID})
        self.assertEqual([r["event_kind"] for r in self.sink.records], list(VALID))
        self.assertEqual(self.feed.sent, 3)
        self.assertEqual(self.feed.rejected, 0)

    def test_payloads_halten_den_wire_vertrag(self):
        self.feed.on_tape(*tape())
        for record in self.sink.records:
            ok, reason = validate_telemetry_payload(record["event_kind"], record["payload"])
            self.assertTrue(ok, f"{record['event_kind']}: {reason}")

    def test_v_total_ist_die_echte_engine_formel(self):
        self.feed.on_tape(*tape())
        micro = next(r["payload"] for r in self.sink.records if r["event_kind"] == "microstructure_tick")
        grav = next(r["payload"] for r in self.sink.records if r["event_kind"] == "gravity_tick")
        expected = (0.25 * grav["l2_depth"] + 0.35 * grav["l3_iceberg"]
                    + 0.40 * grav["polymarket_prob"])
        self.assertAlmostEqual(grav["v_total"], round(expected, 6), places=6)
        # depth_2pct kommt aus derselben Quelle in beiden Events
        self.assertEqual(grav["l2_depth"], micro["depth_2pct"])
        self.assertEqual(len(micro["footprint_delta"]), CVD_BINS)

    def test_regime_trägt_die_engine_entscheidung(self):
        self.feed.on_tape(*tape())
        regime = next(r["payload"] for r in self.sink.records if r["event_kind"] == "regime_tick")
        self.assertIn(regime["is_forbidden_zone"], (0.0, 1.0))
        self.assertGreaterEqual(regime["confidence"], 0.0)
        self.assertLessEqual(regime["confidence"], 1.0)

    def test_engine_fehler_erzeugt_kein_event(self):
        # Fail-closed: wirft die Engine, darf kein halb gefuelltes Widget entstehen.
        with self.assertRaises(ValueError):
            self.feed.micro.calculate_footprint_map("kein-array", 0.0, 1.0)
        self.feed.micro.calculate_footprint_map = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("feed down"))
        sent = self.feed.on_tape(*tape())
        self.assertEqual(sent, {k: False for k in VALID})
        self.assertEqual(self.sink.records, [])
        self.assertEqual(self.feed.rejected, 1)

    def test_resample_auf_widget_breite(self):
        feed = TelemetryFeed(self.bus, None)
        # 24 Bins auf 12 gemittelt: Summe bleibt erhalten, Breite halbiert sich.
        out = feed._resample([1.0] * 24, 12)
        self.assertEqual(len(out), 12)
        self.assertAlmostEqual(sum(out), 24.0, places=6)
        self.assertTrue(all(abs(v - 2.0) < 1e-9 for v in out))
        # gleiche Breite = Identitaet
        self.assertEqual(feed._resample([1.0] * 12, 12), [1.0] * 12)
        self.assertEqual(feed._resample([], 12), [0.0] * 12)
        self.assertEqual(feed._resample([1.0, 2.0], 0), [])


class TestStundenBeschriftung(unittest.TestCase):
    def test_zwoelf_beschriftungen_enden_am_geraden_stundenwert(self):
        # 2026-09-08T13:37:00Z -> letzte Beschriftung ist "12"
        now = calendar.timegm(time.strptime("2026-09-08 13:37:00", "%Y-%m-%d %H:%M:%S"))
        labels = hour_labels(12, now=now)
        self.assertEqual(len(labels), len(set(labels)))
        self.assertEqual(labels[-1], "12")
        self.assertTrue(all(len(x) == 2 and x.isdigit() for x in labels))


class TestEchterUdsUmlauf(unittest.TestCase):
    """Producer -> SOCK_DGRAM -> Konsument, ohne Mock dazwischen."""

    def test_events_kommen_ueber_das_socket_an(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock_path = Path(tmp) / "telemetry.sock"
            with UDSBroadcastServer(sock_path) as server:
                sink = UDSBroadcastSink(sock_path)
                self.assertTrue(sink.connected, "Producer muss den Empfaenger finden")
                feed = TelemetryFeed(self._silent_bus(), sink, symbol="SOLUSDT")
                for _ in range(3):
                    feed.on_tape(*tape())
                sink.flush()

                records = []
                deadline = time.monotonic() + 5.0
                while len(records) < 9 and time.monotonic() < deadline:
                    records.extend(server.records(timeout_s=0.5))
                sink.close()

        self.assertEqual(len(records), 9, f"erwartet 9 Events, bekommen {len(records)}")
        kinds = [r["event_kind"] for r in records]
        self.assertEqual(kinds.count("microstructure_tick"), 3)
        self.assertEqual(kinds.count("gravity_tick"), 3)
        self.assertEqual(kinds.count("regime_tick"), 3)
        for record in records:
            self.assertEqual(record["symbol"], "SOLUSDT")
            ok, reason = validate_telemetry_payload(record["event_kind"], record["payload"])
            self.assertTrue(ok, reason)

    @staticmethod
    def _silent_bus():
        bus = EventBus(system_log_path="/tmp/nio_telemetry_test.log")
        bus.event_sinks["stderr"] = False
        bus.event_sinks["file"] = False
        return bus


class TestCliEinstieg(unittest.TestCase):
    """``python -m limbs.telemetry_feed`` von Socket-Bindung bis Prozessende."""

    def test_begrenzter_lauf_sendet_und_endet(self):
        from limbs.telemetry_feed import main

        with tempfile.TemporaryDirectory() as tmp:
            sock_path = Path(tmp) / "feed.sock"
            with UDSBroadcastServer(sock_path) as server:
                code = main(["--socket", str(sock_path), "--ticks", "2", "--tick-s", "0"])
                records = []
                deadline = time.monotonic() + 5.0
                while len(records) < 6 and time.monotonic() < deadline:
                    records.extend(server.records(timeout_s=0.5))

        self.assertEqual(code, 0)
        self.assertEqual(len(records), 6, "2 Ticks x 3 Event-Kinds")
        self.assertEqual({r["event_kind"] for r in records}, set(TELEMETRY_PAYLOAD_FIELDS))
        for record in records:
            ok, reason = validate_telemetry_payload(record["event_kind"], record["payload"])
            self.assertTrue(ok, f"{record['event_kind']}: {reason}")
            if record["event_kind"] == "gravity_tick":
                self.assertTrue(math.isfinite(record["payload"]["v_total"]))
                self.assertEqual(record["payload"]["polymarket_prob"], 0.5)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""UDS-Datagramm-Bus -> NDJSON auf stdout (Konsument fuer die Next.js-Bridge).

Warum dieses Skript existiert und nicht die Brücke selbst bindet:
``orchestrator/uds.py`` broadcastet über ``AF_UNIX``/**SOCK_DGRAM**. Node bindet
``AF_UNIX`` ausschliesslich als ``SOCK_STREAM`` -- ein ``connect()`` eines
DGRAM-Sockets auf einen STREAM-Pfad antwortet mit ``EPROTOTYPE`` (Errno 91).
Die Brücke kann den Bus also prinzipiell nicht selbst lesen.

Dieser Konsument nutzt stattdessen ``UDSBroadcastServer`` aus dem Repo und
reicht jede empfangene Zeile unverändert auf stdout durch. Damit bleiben
Socket-Typ, Rechte (``0600``, von ``UDSBroadcastServer`` gesetzt) und
Stale-Inode-Behandlung an einer einzigen, getesteten Stelle.

Nur Standardbibliothek.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_uds():
    """``orchestrator/uds.py`` per Dateipfad laden.

    Kein ``sys.path``-Eintrag für die Repo-Wurzel: dort liegt ein zweites Paket
    ``core/``, das ``Architect/core`` verdecken würde (siehe
    ``Architect/limbs/telemetry_feed.py``).
    """
    path = _REPO_ROOT / "orchestrator" / "uds.py"
    spec = importlib.util.spec_from_file_location("nio_orchestrator_uds", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="UDS-Bus nach stdout durchreichen")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--idle-s", type=float, default=1.0,
                        help="Wartezeit pro recv-Durchlauf; 0 = endlos warten")
    args = parser.parse_args(argv)

    uds = _load_uds()
    stdout = sys.stdout
    # Zeilenpuffer aus: eine Event-Zeile soll sofort bei der Brücke ankommen.
    with uds.UDSBroadcastServer(args.socket) as server:
        print(f"uds_to_stdout: lausche auf {args.socket}", file=sys.stderr, flush=True)
        while True:
            lines = server.recv_batch(timeout_s=args.idle_s if args.idle_s > 0 else None)
            for line in lines:
                stdout.write(line.rstrip("\n") + "\n")
            if lines:
                stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Host-Forwarder fuer die NIO-Modell-Endpunkte (nur Standardbibliothek).

Ollama (11434) und freellmapi (3001) binden nur auf 127.0.0.1. Der Modell-Relay
im Docker-Bridge-Netz erreicht sie deshalb nicht. Dieser Forwarder bindet
AUSSCHLIESSLICH auf der Docker-Bridge-Adresse (Standard 172.17.0.1) und leitet
nur die beiden festen Modell-Ports auf Loopback weiter. Kein LAN-Exposure,
keine Inhalts-Logs, keine HTTP-Verarbeitung.

Format NIO_FWD_ROUTES: ``<bind-ip>:<port>=<ziel-host>:<ziel-port>``, kommagetrennt.
Beispiel: ``172.17.0.1:11434=127.0.0.1:11434,172.17.0.1:3001=127.0.0.1:3001``
"""

from __future__ import annotations

import logging
import os
import select
import socket
import socketserver
import threading

logger = logging.getLogger("nio-model-forwarder")

IDLE_TIMEOUT_S = 300.0
CHUNK = 65536


def parse_routes(raw: str) -> list[tuple[str, int, tuple[str, int]]]:
    """Liest ``NIO_FWD_ROUTES``; leere oder fehlerhafte Angaben brechen den Start ab."""
    routes: list[tuple[str, int, tuple[str, int]]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        listen_s, _, target = item.partition("=")
        bind_ip, _, lport_s = listen_s.rpartition(":")
        thost, _, tport_s = target.rpartition(":")
        if not (bind_ip and lport_s.isdigit() and thost and tport_s.isdigit()):
            raise ValueError(f"ungueltige Route: {item!r}")
        routes.append((bind_ip, int(lport_s), (thost, int(tport_s))))
    if not routes:
        raise ValueError("NIO_FWD_ROUTES ist leer")
    return routes


class _PipeHandler(socketserver.BaseRequestHandler):
    """Reicht Bytes in beide Richtungen zum festen Ziel weiter."""

    def handle(self) -> None:
        target = self.server.target  # type: ignore[attr-defined]
        try:
            upstream = socket.create_connection(target, timeout=10)
        except OSError as error:
            logger.warning("Ziel %s nicht erreichbar: %s", target, error)
            return
        conns = [self.request, upstream]
        try:
            while True:
                readable, _, _ = select.select(conns, [], [], IDLE_TIMEOUT_S)
                if not readable:
                    break
                for src in readable:
                    data = src.recv(CHUNK)
                    if not data:
                        return
                    (upstream if src is self.request else self.request).sendall(data)
        except OSError:
            pass
        finally:
            upstream.close()


class _FwdServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, bind_ip: str, port: int, target: tuple[str, int]):
        self.target = target
        super().__init__((bind_ip, port), _PipeHandler)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        routes = parse_routes(os.environ.get("NIO_FWD_ROUTES", ""))
    except ValueError as error:
        logger.error("%s", error)
        return 2
    servers = [_FwdServer(ip, port, target) for ip, port, target in routes]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info("Forward aktiv: %s:%s -> %s", *server.server_address, server.target)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

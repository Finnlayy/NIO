#!/usr/bin/env python3
"""TCP-Weiterleitung nur zu festen Modell-Endpunkten (nur Standardbibliothek).

Der OpenCode-Worker haengt in einem internen Docker-Netz ohne Ausgang. Dieser Relay haengt
in diesem Netz und im Standard-Bridge-Netz und reicht Verbindungen ausschliesslich auf die
Ziele weiter, die in ``NIO_RELAY_ROUTES`` stehen. Der Worker kann kein Ziel waehlen.

Format: ``<port>=<host>:<port>`` kommagetrennt, z. B.
``3001=host.docker.internal:3001,11434=host.docker.internal:11434``.

Der Relay liest nur Bytes weiter. Er kennt kein HTTP, speichert nichts und loggt keine Inhalte.
"""

from __future__ import annotations

import logging
import os
import select
import socket
import socketserver
import sys
import threading

__all__ = ["main", "parse_routes"]

logger = logging.getLogger("model-relay")

IDLE_TIMEOUT_S = 300.0
CHUNK = 65536


def parse_routes(raw: str) -> list[tuple[int, tuple[str, int]]]:
    """Liest ``NIO_RELAY_ROUTES``; leere oder fehlerhafte Angaben brechen den Start ab."""
    routes: list[tuple[int, tuple[str, int]]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        listen_s, _, target = item.partition("=")
        host, _, port_s = target.rpartition(":")
        if not (listen_s.isdigit() and host and port_s.isdigit()):
            raise ValueError(f"ungueltige Route: {item!r}")
        routes.append((int(listen_s), (host, int(port_s))))
    if not routes:
        raise ValueError("NIO_RELAY_ROUTES ist leer")
    return routes


class _PipeHandler(socketserver.BaseRequestHandler):
    """Reicht Bytes in beide Richtungen zum festen Ziel des Servers weiter."""

    server: _RelayServer

    def handle(self) -> None:
        try:
            upstream = socket.create_connection(self.server.target, timeout=10)
        except OSError:
            logger.warning("Ziel nicht erreichbar: port %s", self.server.server_address[1])
            return
        with upstream:
            sockets = [self.request, upstream]
            while True:
                readable, _, _ = select.select(sockets, [], [], IDLE_TIMEOUT_S)
                if not readable:
                    return
                for sock in readable:
                    data = sock.recv(CHUNK)
                    if not data:
                        return
                    peer = upstream if sock is self.request else self.request
                    peer.sendall(data)


class _RelayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, listen_port: int, target: tuple[str, int]) -> None:
        self.target = target
        super().__init__(("0.0.0.0", listen_port), _PipeHandler)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        routes = parse_routes(os.environ.get("NIO_RELAY_ROUTES", ""))
    except ValueError as error:
        logger.error("%s", error)
        return 2
    servers = [_RelayServer(port, target) for port, target in routes]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info("Route aktiv: Port %s", server.server_address[1])
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

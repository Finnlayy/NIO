#!/usr/bin/env python3
"""Host-Forwarder fuer die NIO-Modell-Endpunkte (nur Standardbibliothek).

Ollama (11434) und freellmapi (3001) binden nur auf 127.0.0.1. Der Modell-Relay
im Docker-Bridge-Netz erreicht sie deshalb nicht. Dieser Forwarder bindet
AUSSCHLIESSLICH auf der Docker-Bridge-Adresse (Standard 172.17.0.1) und leitet
nur die beiden festen Modell-Ports auf Loopback weiter. Kein LAN-Exposure,
keine Inhalts-Logs.

Format NIO_FWD_ROUTES: ``<bind-ip>:<port>=<ziel-host>:<ziel-port>[#http]``, kommagetrennt.
Beispiel: ``172.17.0.1:11434=127.0.0.1:11434#http,172.17.0.1:3001=127.0.0.1:3001``

``#http`` markiert eine Route als HTTP-Proxy: der Host-Header wird auf
``localhost:<ziel-port>`` normalisiert (Ollama lehnt fremde Host-Header mit 403 ab).
Ohne ``#http`` bleibt die Route eine reine TCP-Weiterleitung.
"""

from __future__ import annotations

import http.client
import http.server
import logging
import os
import select
import socket
import socketserver
import threading

logger = logging.getLogger("nio-model-forwarder")

IDLE_TIMEOUT_S = 300.0
CHUNK = 65536
_HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
                "te", "trailers", "transfer-encoding", "upgrade", "host"}


def parse_routes(raw: str) -> list[tuple[str, int, tuple[str, int], bool]]:
    """Liest ``NIO_FWD_ROUTES``; leere oder fehlerhafte Angaben brechen den Start ab."""
    routes: list[tuple[str, int, tuple[str, int], bool]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        listen_s, _, target = item.partition("=")
        http_mode = target.endswith("#http")
        if http_mode:
            target = target[:-5]
        bind_ip, _, lport_s = listen_s.rpartition(":")
        thost, _, tport_s = target.rpartition(":")
        if not (bind_ip and lport_s.isdigit() and thost and tport_s.isdigit()):
            raise ValueError(f"ungueltige Route: {item!r}")
        routes.append((bind_ip, int(lport_s), (thost, int(tport_s)), http_mode))
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


class _HttpProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP-Proxy mit Host-Normalisierung (Ollama-403-Schutz) und Streaming."""

    protocol_version = "HTTP/1.0"  # close-delimited, damit Streaming ohne Chunked-Encoding geht

    def log_message(self, format, *args):  # keine Inhalts-Logs
        pass

    def _proxy(self):
        target = self.server.target  # type: ignore[attr-defined]
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP_HEADERS}
        headers["Host"] = f"localhost:{target[1]}"
        conn = http.client.HTTPConnection(target[0], target[1], timeout=IDLE_TIMEOUT_S)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in _HOP_HEADERS | {"content-length"}:
                    self.send_header(k, v)
            self.end_headers()
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (OSError, http.client.HTTPException) as error:
            logger.warning("HTTP-Ziel %s Fehler: %s", target, error)
            try:
                self.send_error(502)
            except OSError:
                pass
        finally:
            conn.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_OPTIONS = do_PATCH = _proxy


class _HttpFwdServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, bind_ip: str, port: int, target: tuple[str, int]):
        self.target = target
        super().__init__((bind_ip, port), _HttpProxyHandler)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        routes = parse_routes(os.environ.get("NIO_FWD_ROUTES", ""))
    except ValueError as error:
        logger.error("%s", error)
        return 2
    for bind_ip, port, target, http_mode in routes:
        server = _HttpFwdServer(bind_ip, port, target) if http_mode else _FwdServer(bind_ip, port, target)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info("Forward aktiv: %s:%s -> %s (%s)", bind_ip, port, target, "http" if http_mode else "tcp")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

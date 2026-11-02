#!/usr/bin/env python3
"""Egress Forward Proxy in pure stdlib.

Allows only HTTP CONNECT. Restricts target to an allowlist of hostnames/IPs.
Denies private, loopback, and link-local addresses even after DNS resolution.
Logs every decision without headers or bodies.
"""

import argparse
import ipaddress
import logging
import select
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# Format for Python logging in German without secrets
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("egress-proxy")

class ProxyError(Exception):
    pass

def is_ip_allowed(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        # Handle IPv4-mapped IPv6 like ::ffff:192.0.2.128
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
    except ValueError:
        return False

    if not ip.is_global:
        return False
    return True

class EgressProxyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def __init__(self, request, client_address, server):
        self.allowlist = server.allowlist
        self.max_lifetime = 3600  # 1 Stunde max pro Verbindung
        self.idle_timeout = 300   # 5 Minuten max Idle
        super().__init__(request, client_address, server)

    def log_message(self, format, *args):
        # Disable default logging which includes headers and URLs completely
        pass

    def send_error_response(self, code, message):
        self.send_response(code)
        self.end_headers()
        logger.warning(f"Abgelehnt (Code {code}): {message}")
        self.wfile.write(message.encode("utf-8"))

    def _strip_control_chars(self, s: str) -> str:
        return "".join(c for c in s if c.isprintable())

    def do_CONNECT(self):
        host, port_str = self.path.split(":", 1) if ":" in self.path else (self.path, "443")
        try:
            port = int(port_str)
        except ValueError:
            self.send_error_response(400, "Ungueltiger Port.")
            return

        clean_host = self._strip_control_chars(host)

        allowlist_match = False
        allowed_port = 443

        for allowed_entry in self.allowlist:
            if ":" in allowed_entry:
                allow_host, allow_port = allowed_entry.rsplit(":", 1)
                try:
                    if clean_host == allow_host and port == int(allow_port):
                        allowlist_match = True
                        break
                except ValueError:
                    pass
            else:
                if clean_host == allowed_entry and port == 443:
                    allowlist_match = True
                    break

        if not allowlist_match:
            self.send_error_response(403, f"Ziel-Host oder Port nicht erlaubt: {clean_host}:{port}")
            return

        try:
            addr_info = socket.getaddrinfo(clean_host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror as e:
            self.send_error_response(502, f"DNS-Fehler fuer {clean_host}.")
            return

        # Fail closed on any non-global resolved address
        allowed_ip = None
        allowed_af = None
        allowed_sockaddr = None
        for af, socktype, proto, canonname, sockaddr in addr_info:
            ip = sockaddr[0]
            if not is_ip_allowed(ip):
                self.send_error_response(403, f"Ziel-IP abgelehnt fuer {clean_host} ({ip} nicht global).")
                return
            if not allowed_ip:
                allowed_ip = ip
                allowed_af = af
                allowed_sockaddr = sockaddr

        if not allowed_ip:
             self.send_error_response(502, f"Keine aufloesbare IP fuer {clean_host}.")
             return

        logger.info(f"Erlaubt: CONNECT zu {clean_host}:{port} ({allowed_ip})")

        try:
            target_socket = socket.socket(allowed_af, socket.SOCK_STREAM)
            target_socket.settimeout(10)
            target_socket.connect(allowed_sockaddr)
        except OSError as e:
            logger.warning(f"Verbindungsaufbau fehlgeschlagen: {clean_host}:{port} - {e}")
            self.send_error_response(502, "Verbindung zum Ziel fehlgeschlagen.")
            return

        self.send_response(200, "Connection Established")
        self.end_headers()

        self._relay_traffic(self.connection, target_socket)

    def _relay_traffic(self, client_sock, target_sock):
        client_sock.settimeout(None)
        target_sock.settimeout(None)
        sockets = [client_sock, target_sock]
        start_time = time.monotonic()
        last_activity = start_time

        try:
            while True:
                now = time.monotonic()
                if now - start_time > self.max_lifetime:
                    logger.warning("Tunnel-Lebensdauer ueberschritten.")
                    break
                if now - last_activity > self.idle_timeout:
                    logger.warning("Tunnel-Idle-Timeout ueberschritten.")
                    break

                readable, _, exceptional = select.select(sockets, [], sockets, 10.0)
                if exceptional:
                    break
                if not readable:
                    continue
                for sock in readable:
                    other = target_sock if sock is client_sock else client_sock
                    try:
                        data = sock.recv(8192)
                        last_activity = time.monotonic()
                    except OSError:
                        data = b""
                    if not data:
                        return
                    try:
                        other.sendall(data)
                    except OSError:
                        return
        finally:
            target_sock.close()

    # Blockiere alle anderen Methoden
    def do_GET(self): self.send_error_response(405, "Nur HTTP CONNECT erlaubt.")
    def do_POST(self): self.send_error_response(405, "Nur HTTP CONNECT erlaubt.")
    def do_PUT(self): self.send_error_response(405, "Nur HTTP CONNECT erlaubt.")
    def do_DELETE(self): self.send_error_response(405, "Nur HTTP CONNECT erlaubt.")
    def do_OPTIONS(self): self.send_error_response(405, "Nur HTTP CONNECT erlaubt.")
    def do_HEAD(self): self.send_error_response(405, "Nur HTTP CONNECT erlaubt.")

class EgressProxyServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, allowlist):
        self.allowlist = allowlist
        super().__init__(server_address, RequestHandlerClass)

def main():
    parser = argparse.ArgumentParser(description="Egress Proxy fuer Agenten-Container")
    parser.add_argument("--port", type=int, default=3128, help="Proxy Port")
    parser.add_argument("--allowlist", type=str, default="", help="Kommagetrennte Liste erlaubter Hosts")
    args = parser.parse_args()

    allowlist = set(host.strip() for host in args.allowlist.split(",") if host.strip())

    server_address = ('', args.port)
    httpd = EgressProxyServer(server_address, EgressProxyHandler, allowlist)
    logger.info(f"Starte Proxy auf Port {args.port} mit Allowlist: {allowlist}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Proxy wird beendet.")
        httpd.server_close()

if __name__ == "__main__":
    main()

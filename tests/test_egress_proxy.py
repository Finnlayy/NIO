import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "docker" / "egress-proxy"))

import proxy  # noqa: E402


class TestEgressProxyLogic(unittest.TestCase):
    def test_is_ip_allowed(self):
        self.assertTrue(proxy.is_ip_allowed("8.8.8.8"))

        # Mapped IPv6 global
        self.assertTrue(proxy.is_ip_allowed("::ffff:8.8.8.8"))

        self.assertFalse(proxy.is_ip_allowed("10.0.0.1"))
        self.assertFalse(proxy.is_ip_allowed("192.168.1.1"))
        self.assertFalse(proxy.is_ip_allowed("172.16.0.1"))
        self.assertFalse(proxy.is_ip_allowed("127.0.0.1"))
        self.assertFalse(proxy.is_ip_allowed("::1"))
        self.assertFalse(proxy.is_ip_allowed("169.254.1.1"))

        # Mapped IPv6 local
        self.assertFalse(proxy.is_ip_allowed("::ffff:127.0.0.1"))
        self.assertFalse(proxy.is_ip_allowed("::ffff:10.0.0.1"))

class DummyRequest:
    def __init__(self, path, command="CONNECT"):
        self.path = path
        self.command = command

class DummyServer:
    def __init__(self, allowlist):
        self.allowlist = allowlist

class DummyProxyHandler(proxy.EgressProxyHandler):
    def __init__(self, request, client_address, server):
        self.allowlist = server.allowlist
        self.path = request.path
        self.command = request.command
        self.responses = []
        self.headers_ended = False
        self.body = b""
        self.closed = False

    def send_response(self, code, message=None):
        self.responses.append(code)

    def end_headers(self):
        self.headers_ended = True

    def log_message(self, format, *args):
        pass

    @property
    def wfile(self):
        class WFile:
            def write(self_, data):
                self.body += data
        return WFile()

class TestEgressProxyHandlerLogic(unittest.TestCase):
    def setUp(self):
        self.server = DummyServer(allowlist={"allowed.example.com", "port-allowed.test:8443"})

    def test_reject_not_in_allowlist(self):
        req = DummyRequest("not-allowed.example.com:443")
        handler = DummyProxyHandler(req, ("127.0.0.1", 1234), self.server)
        handler.do_CONNECT()
        self.assertIn(403, handler.responses)
        self.assertIn(b"Ziel-Host", handler.body)

    def test_default_port_443(self):
        req = DummyRequest("allowed.example.com:80")
        handler = DummyProxyHandler(req, ("127.0.0.1", 1234), self.server)
        handler.do_CONNECT()
        self.assertIn(403, handler.responses) # 80 is not 443

    def test_explicit_port(self):
        # 8443 is allowed explicitly
        req = DummyRequest("port-allowed.test:8443")
        handler = DummyProxyHandler(req, ("127.0.0.1", 1234), self.server)
        # Should DNS error because domain does not exist, but pass allowlist check
        handler.do_CONNECT()
        self.assertNotIn(403, handler.responses)
        self.assertIn(502, handler.responses)
        self.assertIn(b"DNS-Fehler", handler.body)

    def test_invalid_port(self):
        req = DummyRequest("allowed.example.com:abc")
        handler = DummyProxyHandler(req, ("127.0.0.1", 1234), self.server)
        handler.do_CONNECT()
        self.assertIn(400, handler.responses)
        self.assertIn(b"Ungueltiger Port", handler.body)

    def test_reject_private_ip(self):
        self.server.allowlist.add("127.0.0.1")
        req = DummyRequest("127.0.0.1:443")
        handler = DummyProxyHandler(req, ("127.0.0.1", 1234), self.server)
        handler.do_CONNECT()
        self.assertIn(403, handler.responses)
        self.assertIn(b"Ziel-IP abgelehnt", handler.body)

    def test_control_chars_stripped(self):
        self.server.allowlist.add("test.com")
        req = DummyRequest("te\n\r\tst.com:443") # Strips to test.com
        handler = DummyProxyHandler(req, ("127.0.0.1", 1234), self.server)
        # DNS error means it passed the allowlist
        handler.do_CONNECT()
        self.assertIn(502, handler.responses)

    def test_reject_get(self):
        req = DummyRequest("http://allowed.example.com/", "GET")
        handler = DummyProxyHandler(req, ("127.0.0.1", 1234), self.server)
        handler.do_GET()
        self.assertIn(405, handler.responses)
        self.assertIn(b"Nur HTTP CONNECT", handler.body)

if __name__ == '__main__':
    unittest.main()

"""Isolated contract tests for local configuration and diagnostics."""
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import NeuConfig

ROOT = Path(__file__).resolve().parents[1]


def unsafe_example_line(line):
    if not line or line.startswith('#'):
        return False
    key, value = line.split('=', 1)
    credential = any(word in key.upper() for word in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'COOKIE'))
    return (key.startswith(('VITE_', 'NEXT_PUBLIC_')) and credential) or (credential and value not in ('', 'YOUR_VALUE_HERE'))


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class ConfigurationTests(unittest.TestCase):
    def test_precedence_and_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'neu.config.json').write_text(json.dumps({'apollo_port': 4201}))
            with patch.dict(os.environ, {'NEU_APOLLO_PORT': '4202', 'SOME_TOKEN': 'never-print-me'}, clear=True):
                c = NeuConfig.load(root, apollo_port=4203)
            self.assertEqual(c.apollo_port, 4203)
            self.assertEqual(c.provenance['apollo_port'], 'cli')
            self.assertEqual(c.provenance['kanban_port'], 'default')
            self.assertNotIn('never-print-me', json.dumps(c.diagnostics()))
            with patch.dict(os.environ, {'NEU_APOLLO_PORT': '4202'}, clear=True):
                self.assertEqual(NeuConfig.load(root).provenance['apollo_port'], 'environment')
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(NeuConfig.load(root).provenance['apollo_port'], 'file')

    def test_invalid_values(self):
        for kw in ({'apollo_port': 0}, {'apollo_port': True}, {'apollo_port': 'bad'},
                   {'runtime_dir': '../escape'}, {'speech_required': 'yes'},
                   {'apollo_host': '0.0.0.0'}, {'speech_url': 'https://remote.invalid/x'},
                   {'apollo_port': 4001, 'kanban_port': 4001}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                NeuConfig.load(ROOT, **kw)

    def test_bad_environment_is_not_echoed(self):
        with patch.dict(os.environ, {'NEU_APOLLO_PORT': 'sensitive-value'}, clear=True):
            with self.assertRaises(ValueError) as error:
                NeuConfig.load(ROOT)
            self.assertNotIn('sensitive-value', str(error.exception))

    def test_env_example_safe(self):
        lines = (ROOT / '.env.example').read_text().splitlines()
        self.assertFalse(any(unsafe_example_line(line) for line in lines))
        self.assertTrue(unsafe_example_line('NIO_TOKEN=not-a-placeholder'))
        self.assertTrue(unsafe_example_line('VITE_SERVER_TOKEN='))
        self.assertTrue(unsafe_example_line('NEXT_PUBLIC_PASSWORD='))
        self.assertFalse(unsafe_example_line('NIO_TOKEN=YOUR_VALUE_HERE'))


class DoctorTests(unittest.TestCase):
    def test_doctor_read_only_and_render(self):
        from orchestrator.lifecycle import preflight, render
        with tempfile.TemporaryDirectory() as d:
            runtime = Path(d) / 'missing'
            c = NeuConfig.load(ROOT, runtime_dir=runtime, apollo_port=free_port())
            before = list(Path(d).iterdir())
            result = preflight(c, probe_services=False)
            self.assertEqual(before, list(Path(d).iterdir()))
            self.assertFalse(runtime.exists())
            self.assertIn(result['state'], ('ready', 'degraded', 'blocked'))
            self.assertIn('components', json.loads(render(result, True)))
            self.assertIn('frontend', render(result, False))
            self.assertIn('source:', render(result, False))
            for item in result['components']:
                if item['state'] != 'ready':
                    self.assertTrue(item['code'] and item['explanation'] and item['remediation'])

    def test_occupied_port_and_required_speech(self):
        from orchestrator.lifecycle import preflight
        with tempfile.TemporaryDirectory() as d, socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            s.listen()
            port = s.getsockname()[1]
            c = NeuConfig.load(ROOT, runtime_dir=Path(d), apollo_port=port,
                               kanban_port=port + 1 if port < 65535 else port - 1,
                               speech_url='http://127.0.0.1:1/v1/audio/transcriptions', speech_required=True)
            with patch("socket.create_connection", side_effect=OSError("offline")):
                components = {x['name']: x for x in preflight(c)['components']}
            self.assertEqual(components['apollo_port']['state'], 'blocked')
            self.assertEqual(components['speech']['state'], 'blocked')

    def test_invalid_config_cli_redacts_input(self):
        import contextlib
        import io

        from orchestrator.cli import main
        output = io.StringIO()
        with patch.dict(os.environ, {'NEU_APOLLO_PORT': 'secret-input'}, clear=True), contextlib.redirect_stdout(output):
            code = main(['--json', 'doctor'])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())['components'][0]['code'], 'CONFIG_INVALID')
        self.assertNotIn('secret-input', output.getvalue())

    def test_valid_components_with_isolated_checkout(self):
        from orchestrator.lifecycle import preflight
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ('orchestrator/runner.py', 'orchestrator/cli.py', 'protocol/intent.schema.json',
                         'frontend/.next/BUILD_ID', 'frontend/node_modules/next/dist/bin/next', 'limbs/echo.py'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            (root / 'frontend/package.json').write_text('{"dependencies":{"next":"16"}}')
            (root / 'limbs/registry.json').write_text(json.dumps({
                'default_limb': 'echo', 'runtimes': {'python3': {}},
                'limbs': {'echo': {'status': 'active', 'entrypoint': 'limbs/echo.py', 'runtime': 'python3'}}}))
            c = NeuConfig.load(root, runtime_dir=root / 'state', apollo_port=free_port())
            result = preflight(c, probe_services=False)
            components = {x['name']: x for x in result['components']}
            for name in ('repository', 'registry', 'storage', 'frontend', 'apollo_port'):
                self.assertEqual(components[name]['state'], 'ready')
            self.assertEqual(result['state'], 'degraded' if components['node']['state'] == 'ready' else 'blocked')
            self.assertFalse((root / 'state').exists())

    def test_unwritable_runtime_and_invalid_registry(self):
        from orchestrator.lifecycle import preflight
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            runtime = root / 'locked'
            runtime.mkdir(mode=0o500)
            (root / 'registry.json').write_text('not json')
            c = NeuConfig.load(root, runtime_dir=runtime, registry_file='registry.json', apollo_port=free_port())
            components = {x['name']: x for x in preflight(c, probe_services=False)['components']}
            self.assertEqual(components['storage']['code'], 'RUNTIME_UNWRITABLE')
            self.assertEqual(components['registry']['code'], 'REGISTRY_INVALID')

    def test_cli_doctor_json(self):
        import contextlib
        import io

        from orchestrator.cli import main
        with tempfile.TemporaryDirectory() as d, patch('socket.create_connection', side_effect=OSError('offline')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(['--runtime-dir', d, '--apollo-port', str(free_port()), '--json', 'doctor'])
            self.assertIn(result, (0, 1))
            self.assertIn('components', json.loads(output.getvalue()))

    def test_required_speech_open_port_is_unverified_and_blocked(self):
        from orchestrator.lifecycle import preflight
        with tempfile.TemporaryDirectory() as d:
            c = NeuConfig.load(ROOT, runtime_dir=Path(d), apollo_port=free_port(), speech_required=True)
            with patch("socket.create_connection"):
                components = {x['name']: x for x in preflight(c)['components']}
            self.assertEqual(components['speech']['code'], 'SERVICE_UNVERIFIED')
            self.assertEqual(components['speech']['state'], 'blocked')

    def test_optional_speech_degraded(self):
        from orchestrator.lifecycle import preflight
        with tempfile.TemporaryDirectory() as d:
            c = NeuConfig.load(ROOT, runtime_dir=Path(d), apollo_port=free_port(), speech_url='http://127.0.0.1:1/v1/audio/transcriptions')
            with patch("socket.create_connection", side_effect=OSError("offline")):
                components = {x['name']: x for x in preflight(c)['components']}
            self.assertEqual(components['speech']['state'], 'degraded')


if __name__ == '__main__':
    unittest.main()

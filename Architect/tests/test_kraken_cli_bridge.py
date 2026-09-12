import unittest
from unittest.mock import patch, MagicMock
import json
import subprocess

from limbs.connectors.kraken_cli_bridge import KrakenCliBridge

class TestKrakenCliBridge(unittest.TestCase):
    @patch('subprocess.run')
    def test_get_server_time(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = '{"unixtime": 1234567890, "rfc1123": "Thu, 01 Jan 1970 00:00:00 GMT"}'
        mock_run.return_value = mock_result

        bridge = KrakenCliBridge(mode="live")
        result = bridge.get_server_time()

        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        self.assertIn('kraken', cmd_args)
        self.assertIn('server-time', cmd_args)
        self.assertEqual(result["unixtime"], 1234567890)

    @patch('subprocess.run')
    def test_live_order(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = '{"txid": ["O8Y8Y8-Y8Y8Y-Y8Y8Y8"], "descr": {"order": "buy 1.00000000 XBTUSD @ limit 50000.0"}}'
        mock_run.return_value = mock_result

        bridge = KrakenCliBridge(mode="live")
        result = bridge.add_order(pair="XBTUSD", side="buy", order_type="limit", volume=1.0, price=50000.0)

        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        self.assertEqual(cmd_args[:5], ['kraken', '--output', 'json', '--log-format', 'json'])
        self.assertIn('order', cmd_args)
        self.assertIn('add', cmd_args)
        self.assertIn('XBTUSD', cmd_args)
        self.assertEqual(result["txid"][0], "O8Y8Y8-Y8Y8Y-Y8Y8Y8")

    @patch('subprocess.run')
    def test_paper_spot_order(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = '{"txid": ["PAPER-O8Y8Y8"]}'
        mock_run.return_value = mock_result

        bridge = KrakenCliBridge(mode="kraken_paper")
        result = bridge.add_order(pair="BTCUSD", side="buy", order_type="limit", volume=0.001, price=68000.0)

        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        # Should be: kraken paper order buy BTCUSD 0.001 --type limit --price 68000.0
        self.assertIn('paper', cmd_args)
        self.assertIn('order', cmd_args)
        self.assertIn('BTCUSD', cmd_args)

    @patch('subprocess.run')
    def test_paper_futures_order(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = '{"txid": ["PAPER-FUTURES-123"]}'
        mock_run.return_value = mock_result

        bridge = KrakenCliBridge(mode="kraken_paper")
        result = bridge.add_order(pair="PF_XBTUSD", side="buy", order_type="limit", volume=1.0, price=68000.0)

        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        # Should be: kraken futures paper order buy PF_XBTUSD 1.0 --type limit --price 68000.0
        self.assertIn('futures', cmd_args)
        self.assertIn('paper', cmd_args)
        self.assertIn('PF_XBTUSD', cmd_args)

if __name__ == '__main__':
    unittest.main()

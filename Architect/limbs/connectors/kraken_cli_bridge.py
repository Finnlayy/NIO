import json
import logging
import subprocess
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class KrakenCliBridge:
    """Bridge to the Kraken CLI.

    This acts as the single source of truth (SoT) and execution engine for
    the trading bot, communicating via subprocess execution of the kraken CLI.
    """

    def __init__(self, mode: str = "live", api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize the bridge.

        Args:
            mode: Either "live" or "kraken_paper".
            api_key: Optional API key override.
            api_secret: Optional API secret override.
        """
        self.mode = mode
        self.api_key = api_key
        self.api_secret = api_secret

        if self.mode not in ("live", "kraken_paper"):
            raise ValueError(f"Invalid mode: {self.mode}")

    def _build_base_cmd(self) -> list[str]:
        cmd = ["kraken", "--output", "json", "--log-format", "json"]
        if self.api_key:
            cmd.extend(["--api-key", self.api_key])
        if self.api_secret:
            cmd.extend(["--api-secret-stdin"])
        return cmd

    def _run_cli(self, args: list[str]) -> Dict[str, Any]:
        """Execute the Kraken CLI and return the parsed JSON result."""
        cmd = self._build_base_cmd() + args
        try:
            logger.debug(f"Running kraken cli: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, input=self.api_secret)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            # We parse stdout/stderr text as mentioned in blueprint:
            # `KrakenCliBridge` wertet stdout/stderr Text aus, nicht nur Exit-Code
            logger.error(f"Kraken CLI error: return_code={e.returncode}, stderr={e.stderr}, stdout={e.stdout}")
            # Try to parse stderr or stdout for more structured errors if possible
            error_data = {}
            if e.stdout.strip():
                try:
                    error_data["stdout"] = json.loads(e.stdout)
                except json.JSONDecodeError:
                    error_data["stdout"] = e.stdout

            if e.stderr.strip():
                try:
                    # In json log format, stderr might be JSONL
                    lines = e.stderr.strip().split("\n")
                    error_data["stderr"] = [json.loads(line) for line in lines if line.strip()]
                except json.JSONDecodeError:
                    error_data["stderr"] = e.stderr

            raise RuntimeError(f"Kraken CLI error ({e.returncode}): {json.dumps(error_data)}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Kraken CLI output: {e.doc}")
            raise RuntimeError(f"Failed to parse Kraken CLI JSON output: {str(e)}") from e

    def get_server_time(self) -> Dict[str, Any]:
        """Get the Kraken server time. Used as the system's single source of truth."""
        return self._run_cli(["server-time"])

    def get_balance(self, extended: bool = False) -> Dict[str, Any]:
        """Get the current balance. If mode is kraken_paper, uses the paper balance command."""
        if self.mode == "kraken_paper":
            # Spot paper balance command as per blueprint
            return self._run_cli(["paper", "balance"])

        if extended:
            return self._run_cli(["extended-balance"])
        return self._run_cli(["balance"])

    def get_futures_paper_balance(self) -> Dict[str, Any]:
        if self.mode != "kraken_paper":
            raise ValueError("Futures paper balance only available in kraken_paper mode")
        return self._run_cli(["futures", "paper", "balance"])

    def add_order(
        self,
        pair: str,
        side: str,
        order_type: str,
        volume: float,
        price: Optional[float] = None,
        leverage: Optional[float] = None,
        close_ordertype: Optional[str] = None,
        close_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute an order.
        Routes to `kraken trade add-order` for live,
        or `kraken paper order` / `kraken futures paper order` for paper mode.
        """
        # Handle live mode
        if self.mode == "live":
            args = ["order", "add", "--pair", pair, "--type", side, "--ordertype", order_type, "--volume", str(volume)]
            if price is not None:
                args.extend(["--price", str(price)])
            if leverage is not None:
                args.extend(["--leverage", str(leverage)])
            if close_ordertype is not None:
                args.extend(["--close-ordertype", close_ordertype])
            if close_price is not None:
                args.extend(["--close-price", str(close_price)])
            # According to the help output, it's actually: kraken order add or kraken futures order
            # The blueprint said: `kraken trade add-order`, but the help output shows:
            #   order              Place and manage spot orders
            #   futures            Futures trading and market data
            # To match the CLI output, we use "order" for spot. (And maybe would need special logic for futures if live)
            return self._run_cli(args)

        # Handle paper mode
        elif self.mode == "kraken_paper":
            is_futures = ".P" in pair or pair.startswith("PF_") or pair.startswith("PI_")
            if is_futures:
                # e.g. kraken futures paper order buy PF_XBTUSD 1 --type limit --price 68000
                args = ["futures", "paper", "order", side, pair, str(volume), "--type", order_type]
            else:
                # e.g. kraken paper order buy BTCUSD 0.001 --type limit --price 68000
                args = ["paper", "order", side, pair, str(volume), "--type", order_type]

            if price is not None:
                args.extend(["--price", str(price)])

            # Paper mode CLI doesn't seem to natively support all close args in a single line,
            # but we pass what we can or rely on the core platform features.

            return self._run_cli(args)

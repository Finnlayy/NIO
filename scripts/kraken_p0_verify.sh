#!/usr/bin/env bash
# P0b — kraken-cli ground-truth verification on the TARGET box.
# Dumps version + --help for every namespace used by KRAKEN_IMPLEMENTATION_PLAN.md,
# runs auth-free live checks (server-time, paper, ws smoke), and writes fixtures to
#   tests/fixtures/kraken_cli/help/
# Usage: bash scripts/kraken_p0_verify.sh
set -euo pipefail

OUT="tests/fixtures/kraken_cli/help"
mkdir -p "$OUT"

if ! command -v kraken >/dev/null 2>&1; then
  echo "ERROR: 'kraken' not found. Install first:" >&2
  echo "  curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh" >&2
  exit 1
fi

echo "== kraken version =="
kraken --version | tee "$OUT/version.txt"

echo "== help dumps =="
kraken --help                  > "$OUT/top.txt" 2>&1
kraken order --help            > "$OUT/order.txt" 2>&1
kraken order buy --help        > "$OUT/order-buy.txt" 2>&1
kraken order cancel-after --help > "$OUT/order-cancel-after.txt" 2>&1
kraken ticker --help           > "$OUT/ticker.txt" 2>&1
kraken ohlc --help             > "$OUT/ohlc.txt" 2>&1
kraken orderbook --help        > "$OUT/orderbook.txt" 2>&1
kraken trades --help           > "$OUT/trades.txt" 2>&1
kraken spreads --help          > "$OUT/spreads.txt" 2>&1
kraken server-time --help      > "$OUT/server-time.txt" 2>&1
kraken balance --help          > "$OUT/balance.txt" 2>&1
kraken open-orders --help      > "$OUT/open-orders.txt" 2>&1
kraken ledgers --help          > "$OUT/ledgers.txt" 2>&1
kraken paper --help            > "$OUT/paper.txt" 2>&1
kraken paper buy --help        > "$OUT/paper-buy.txt" 2>&1
kraken futures --help          > "$OUT/futures.txt" 2>&1
kraken futures paper --help    > "$OUT/futures-paper.txt" 2>&1
kraken futures order --help    > "$OUT/futures-order.txt" 2>&1
kraken ws --help               > "$OUT/ws.txt" 2>&1
kraken ws book --help          > "$OUT/ws-book.txt" 2>&1
kraken earn --help             > "$OUT/earn.txt" 2>&1
kraken mcp --help              > "$OUT/mcp.txt" 2>&1

echo "== auth-free live checks =="
echo "-- server-time (Exchange-Clock) --"
kraken server-time -o json | tee "$OUT/../server-time.sample.json"
echo "-- paper init+status in scratch workspace (auth-free) --"
kraken paper init p0b --capital 10000 -o json | tee "$OUT/../paper-init.sample.json"
kraken paper status -o json | tee "$OUT/../paper-status.sample.json"
echo "-- ws smoke: 10s ticker stream --"
timeout 10 kraken ws ticker BTCUSD > "$OUT/../ws-ticker.sample.jsonl" || code=$?
code=${code:-0}
if [ "$code" -eq 124 ]; then echo "ws stream ran full 10s (timeout kill = OK)"; else echo "ws exit code: $code"; fi
head -c 600 "$OUT/../ws-ticker.sample.jsonl"; echo

echo "-- error envelope sample (bad pair, exit code expected 1) --"
set +e
kraken ticker NOT_A_PAIR_XYZ -o json > "$OUT/../error-envelope.sample.json" 2>"$OUT/../error-envelope.stderr.txt"
echo "exit=$? (want 1)"
set -e

echo
echo "== keyed checks (manual, need API keys) =="
echo "  kraken balance -o json"
echo "  kraken order buy XBTUSD 0.0001 --type limit --price 1 --validate -o json   # dry-run, places nothing"
echo "  kraken order cancel-after 60 -o json                                      # dead-man live test (careful)"
echo
echo "P0b dumps written to $OUT/"

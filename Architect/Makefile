.PHONY: setup run test test-smoke test-verbose

setup:
	./setup_environment.sh

run:
	./run_terminal.sh

# Full unit/integration suite (Phases 2-5). Runs without third-party deps;
# PyQt6 widget tests skip automatically when PyQt6 is not installed.
test:
	python3 -m unittest discover -s tests -t .

test-verbose:
	python3 -m unittest discover -s tests -t . -v

# GUI/daemon smoke test (requires PyQt6 + pyqtgraph; run `make setup` first).
test-smoke:
	python3 test_init.py

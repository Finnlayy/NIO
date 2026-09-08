# ============================================================================
# NEU -- lokale Entwicklungstore (Protokoll 1.2)
#
# Die Laufzeit braucht nichts ausser Python 3.11+ (Standardbibliothek).
# Lint/Typen brauchen ruff und mypy:  python3 -m pip install -e '.[dev]'
#
# `make check` ist dasselbe Tor, das CI durchlaeuft (ci/neu.yml -- Aktivierung
# siehe ci/README.md).
# ============================================================================

PYTHON ?= python3
RUNTIME ?= $(CURDIR)/runtime

.DEFAULT_GOAL := help
.PHONY: help test test-core test-architect test-frontend ui-test test-verbose lint lint-fix types compile e2e check demo clean

help:  ## Diese Uebersicht
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  Exit-Codes der CLI: 0 Erfolg | 1 Protokoll | 2 Job nicht aufgeloest | 3 Nutzung"

test: test-core test-architect  ## Test-Suite: NEU-Kern (tests/) + Architect (Architect/tests/)

test-core:  ## NEU-Kern, Orchestrator, Limbs, Protokoll 1.2 (echte Subprozesse und Timer)
	$(PYTHON) -W error::ResourceWarning -m unittest discover -s tests -t . -q

test-architect:  ## Architect-Suite (Core, Learning, Limbs, GUI-Modelle)
	cd Architect && $(PYTHON) -W error::ResourceWarning -m unittest discover -s tests -t . -q

test-frontend: ui-test  ## Alias, damit `make test-*` das Frontend eindeutig einschliesst

test-verbose:  ## Test-Suite mit Einzelnamen (beide Python-Suiten)
	$(PYTHON) -W error::ResourceWarning -m unittest discover -s tests -t . -v
	cd Architect && $(PYTHON) -W error::ResourceWarning -m unittest discover -s tests -t . -v

lint:  ## ruff (Konfiguration aus pyproject.toml)
	$(PYTHON) -m ruff check .

lint-fix:  ## ruff mit sicheren Auto-Fixes
	$(PYTHON) -m ruff check --fix .

types:  ## mypy ueber core/, orchestrator/, limbs/
	$(PYTHON) -m mypy

compile:  ## Bytecode-Pruefung (Syntax), inkl. Architect/
	$(PYTHON) -m compileall -q core orchestrator limbs tests scripts Architect/core Architect/limbs Architect/tests Architect/gui

e2e:  ## End-to-End-Beweis 1.2: Zeit tracken statt begrenzen (ueber die CLI)
	$(PYTHON) scripts/ci_e2e_unlimited.py

ui-test:  ## Frontend-UI-Tests (Zero-Dep-Harness: tsc + node --test, kein DOM)
	@if [ ! -x frontend/node_modules/.bin/tsc ]; then \
		echo "ui-test: frontend/node_modules fehlt -- uebersprungen (npm --prefix frontend ci)"; \
	else \
		node frontend/scripts/ui-test.mjs; \
	fi

check: compile lint types test ui-test e2e  ## Das volle Tor (wie in CI)
	@echo "check: alles gruen"

demo:  ## Live-Demo: unbegrenzter Auftrag mit Intervall-Kontrolle und finish_job
	$(PYTHON) -m orchestrator --runtime-dir $(RUNTIME) watch \
		--goal "Demo: Zeit wird getrackt" \
		--op sys.simulate --params '{"mode":"timeout","seconds":60}' \
		--unlimited --tick 0.5 \
		--trigger 'id=kontrolle;action=check;every=2;op=sys.ping' \
		--trigger 'id=ende;action=finish_job;when=elapsed >= 6' \
		--max-ticks 40

clean:  ## Caches entfernen (runtime/ bleibt unangetastet)
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache

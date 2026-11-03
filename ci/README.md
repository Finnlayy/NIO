# CI-Definition für den NEU-Kern

Der Workflow liegt seit dem 2026-11-02 unter `.github/workflows/neu.yml`
(Python-Kern: Test-Matrix 3.11/3.12/3.13 · ruff · mypy · End-to-End-Beweis ·
Exit-Code-Vertrag). Er wird per Pull Request geändert, den ein Mensch mergt.

Bei jedem Push und jedem Pull Request läuft:

| Job | Inhalt |
|---|---|
| `tests` | `python -m unittest discover -s tests -t .` auf Python 3.11/3.12/3.13, mit `PYTHONWARNINGS=error::ResourceWarning` (ein fd-Leck im Dauerbetrieb ist ein Fehler) |
| `quality` | `ruff check .` und `mypy` (Konfiguration aus `pyproject.toml`) |
| `e2e` | `scripts/ci_e2e_unlimited.py` (20 Nachweise), `orchestrator spec` auf 1.2, Exit-Code-Vertrag |

Lokal identisch ohne GitHub: `make check`.

## Noch nicht enthalten: Architect-Suite und Frontend

`Architect/tests/` (214 Tests) und `frontend/` (23 UI-Tests) laufen seit dem
2026-09-08 in `make test` bzw. `make check`, aber **noch nicht** in diesem
Workflow. Der CI-Teil liegt als anwendbarer Patch bereit, weil der Workflow nach
`tests/test_policy.py:138` nicht vom System selbst geändert werden darf:

```bash
git apply docs/ci-architect-frontend-gate.README.md
```

Der Patch ergänzt im Job `tests` einen Schritt mit `working-directory: Architect`
und nimmt `Architect/core|limbs|tests|gui` in `compileall` auf. Den Frontend-Job
beschreibt dieselbe Datei — er gehört nach `.github/workflows/`, das zusätzlich
unter `human_only_globs` steht.

## Hinweis zur Absicht

Dasselbe Repo schützt `.github/*` über `denied_globs` in `neu.config.json` —
ein Limb darf CI-Konfiguration niemals ändern, auch nicht mit menschlicher
Freigabe im Intent (`tests/test_policy.py::TestPhase3Grenze`). Dass die
Workflow-Datei deshalb über einen Menschen aktiviert werden muss, ist kein
Umweg, sondern dieselbe Regel: **Das System darf sein eigenes Qualitätstor
nicht selbst einschalten oder lockern.**

`ci-evals.yml` (Legacy-Harness unter `evals/`, TypeScript + pytest) bleibt
unverändert aktiv.

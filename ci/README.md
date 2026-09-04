# CI-Definition für den NEU-Kern — ein Schritt zur Aktivierung

`ci/neu.yml` ist der fertige GitHub-Actions-Workflow für den Python-Kern
(Test-Matrix 3.11/3.12/3.13 · ruff · mypy · End-to-End-Beweis · Exit-Code-Vertrag).

Er liegt **hier** und nicht unter `.github/workflows/`, weil die anbindende
GitHub-App keine `workflows`-Berechtigung hat — GitHub lehnt den Push sonst ab:

```
! [remote rejected] refusing to allow a GitHub App to create or update
  workflow `.github/workflows/neu.yml` without `workflows` permission
```

## Aktivieren (ein Befehl, von einem Menschen mit Push-Recht)

```bash
git mv ci/neu.yml .github/workflows/neu.yml
git commit -m "ci(neu): Workflow aktivieren"
git push
```

Danach läuft bei jedem Push und jedem Pull Request:

| Job | Inhalt |
|---|---|
| `tests` | `python -m unittest discover -s tests -t .` auf Python 3.11/3.12/3.13, mit `PYTHONWARNINGS=error::ResourceWarning` (ein fd-Leck im Dauerbetrieb ist ein Fehler) |
| `quality` | `ruff check .` und `mypy` (Konfiguration aus `pyproject.toml`) |
| `e2e` | `scripts/ci_e2e_unlimited.py` (20 Nachweise), `orchestrator spec` auf 1.2, Exit-Code-Vertrag |

Lokal identisch ohne GitHub: `make check`.

## Hinweis zur Absicht

Dasselbe Repo schützt `.github/*` über `denied_globs` in `neu.config.json` —
ein Limb darf CI-Konfiguration niemals ändern, auch nicht mit menschlicher
Freigabe im Intent (`tests/test_policy.py::TestPhase3Grenze`). Dass die
Workflow-Datei deshalb über einen Menschen aktiviert werden muss, ist kein
Umweg, sondern dieselbe Regel: **Das System darf sein eigenes Qualitätstor
nicht selbst einschalten oder lockern.**

`ci-evals.yml` (Legacy-Harness unter `evals/`, TypeScript + pytest) bleibt
unverändert aktiv.

# Prompt-Optimierer: Ping-Pong-Architektur, ausführbar

Der Optimierer nimmt einen Rohentwurf (Markdown) und führt ihn durch vier
Stufen. Pro Stufe ist genau eine Achse aktiv — **Prompting-Technik** oder
**Fach-Inhalt** —, die andere ist gesperrt. Der Normativtext steht in
[`prompts/system/prompt_optimizer.md`](../prompts/system/prompt_optimizer.md),
der Code in [`core/prompt_optimizer/`](../core/prompt_optimizer).

Stdlib-only: keine neuen Abhängigkeiten, kein Netz.

---

## 1. Schnellstart

```bash
# Ein Durchlauf (Standard, Modus NORMAL) — schreibt optimized_prompt.md
python3 -m core.prompt_optimizer normal --draft entwurf.md --out workspace/po

# Vier Stufen am Stück (DEEP-CHAIN, ausdrücklicher Befehl), mit Quellen
python3 -m core.prompt_optimizer optimize --draft entwurf.md --out workspace/po \
  --mode deep-chain --all \
  --research-fixture scripts/fixtures/prompt_optimizer/research_fixture.json \
  --checker .

# Stufen einzeln, mit Stopp am Gate
python3 -m core.prompt_optimizer optimize --draft entwurf.md --out workspace/po    # Baseline + Stufe 1
python3 -m core.prompt_optimizer optimize --draft entwurf.md --out workspace/po --approve   # Stufe 2
python3 -m core.prompt_optimizer inspect --out workspace/po
```

Exit-Codes: `0` Erfolg · `2` Stufen-Gate geschlossen · `3` Sperr-/Coverage-Bruch.

Programmatisch:

```python
from core.prompt_optimizer import PromptOptimizer, Mode

opt = PromptOptimizer(draft, out_dir="workspace/po", mode=Mode.DEEP_CHAIN, auto_approve=True)
for result in opt.run_all():
    print(result.render())
```

Demo mit Beispielentwurf, Quellen-Fixture und vollständiger Spur:

```bash
make prompt-optimizer
```

---

## 2. Was pro Stufe passiert

| Stufe | Datei | Aktiv | Gesperrt | Inhaltliche Operation |
| :--- | :--- | :--- | :--- | :--- |
| 0 | `stage_0_baseline.md` | — | — | Rohentwurf unverändert + Baseline-Messung |
| 1 | `stage_1_macro_skeleton.md` | Technik | Inhalt | Feature-Manifest, Sektionen, Gate-Container |
| 2 | `stage_2_domain_expansion.md` | Inhalt | Struktur | Gates pro Subsystem, Rohmaterial, Schnittstellen, Randfälle, Research-Blätter |
| 3 | `stage_3_verified_research_leaves.md` | Inhalt | Struktur | Quellen, Tier, Zitat, Kill-Kriterien, Unsicherheit |
| 4 | `stage_4_FINAL_MASTER_PROMPT.md` | Technik | Inhalt | Reverse-Synthese, Fakten-Register, Coverage |

Neben jedem Artefakt liegt `stage_N.model.json` (Checkpoint). Nach jeder Stufe
wird der Arbeitskontext geleert; die nächste Stufe liest ausschließlich diese
Checkpoints. Der Rohentwurf wird nicht mitgeschleppt.

---

## 3. Die vier Garantien und wie sie geprüft werden

| Garantie | Mechanik | Prüfpunkt |
| :--- | :--- | :--- |
| **Zero-Feature-Drop** | Manifest wird in Stufe 1 eingefroren; jede Folgestufe rendert dieselben `[F-xx]` | `_assert_no_feature_drift`, `tests/test_prompt_optimizer.py` |
| **Zero-Invention** | Gate-Antworten sind Anforderungs-Container; Research liefert Quellen oder `UNVERIFIZIERT` | `measure_content` (Kriterium 3), `LocalSourceChecker` |
| **Struktur-Sperre** | `technique_fingerprint` (Sektionen + Subsystem-IDs + Ausgabevertrag) muss gleich bleiben | `enforce_lock(..., "technique")` |
| **Inhalts-Sperre** | `content_fingerprint` (Features + Blattfragen + Quellen) muss gleich bleiben | `enforce_lock(..., "content")` |

Ein gesperrter Fingerprint, der sich ändert, ist kein Hinweis, sondern ein
`LockViolation`-Abbruch: lieber kein Artefakt als ein unbemerkt verändertes.

---

## 4. Telemetrie lesen

Nach jeder Stufe erscheint die vorgeschriebene Tabelle; im Artefakt steht sie
zusätzlich am Ende, inklusive der vier Einzelkriterien (aufklappbar).

```
### 📊 Optimierungs-Telemetrie (Stufe 2 von 4 — Export: `stage_2_domain_expansion.md`)
| Dimension | Status in Stufe 2 | Vorher | Aktuell | Delta (Δ) | Nachweis & Haupttreiber |
```

* **Aktiv** heißt: Wert neu gezählt. **LOCK 🔒** heißt: Wert des Vorgängers
  übernommen (Sperre ist Vertrag, keine Messung).
* Jedes Kriterium ist auf 25 Punkte begrenzt; die Summe ist der Prozentwert.
* Die Nachweis-Spalte nennt Zähler und Nenner, nicht nur eine Zahl.

Beispielspur des Demo-Laufs:

| Stufe | Inhalt | Technik | Was sie zeigt |
| :--- | ---: | ---: | :--- |
| 0 | 25 | 58 | Der Entwurf hat Substanz, aber keine Struktur |
| 1 | 25 | 86 | Technik hoch, Inhalt eingefroren |
| 2 | 75 | 86 | Breite kommt, Struktur bleibt |
| 3 | 94 | 86 | Fakten kommen (8 von 9 Blättern belegt) |
| 4 | 94 | 94 | Synthese hebt die Technik, Inhalt bleibt |

---

## 5. Eigene Fachantworten und echte Recherche einspeisen

Der Optimierer bewertet, er dichtet nicht. Zwei schmale Schnittstellen:

```python
from core.prompt_optimizer import GateFiller, ResearchProvider

class MeinFiller:                      # echte Gate-Antworten (LLM, Mensch, KB)
    def answer(self, subsystem, gate, features):
        ...

class MeinProvider:                    # echte Recherche (Web, Doku-Index)
    def resolve(self, leaf):
        return (Source(tier=2, locator="https://…", quote="…", retrieved_at="2026-11-07", checked=True),)

opt = PromptOptimizer(draft, out_dir="workspace/po", mode="deep-chain",
                      filler=MeinFiller(), provider=MeinProvider())
```

Ohne Provider bleibt alles `UNVERIFIZIERT` — das ist der ehrliche Standard, kein
Fehler. `LocalSourceChecker` prüft `repo:`-Locators gegen das Repository
(Datei existiert, Zitat steht wörtlich darin); erst dann gilt eine Quelle als
verifiziert. Damit ist „verifiziert“ für jeden Dritten per `git grep` prüfbar.

Quellen-Fixture-Format (`--research-fixture`):

```json
{
  "R-01": [
    {
      "tier": 3,
      "locator": "repo:protocol/PROTOCOL.md",
      "quote": "Protokoll-ID: `neu/intent` und `neu/result`, Version `1.2`.",
      "retrieved_at": "2026-11-07"
    }
  ]
}
```

---

## 6. Grenzen (bewusst)

* **Extraktion ist Heuristik.** Features entstehen aus Aufzählungen (Fallback:
  Modal-Sätze), Subsysteme aus Überschriften oder Domänen-Clustern. Ein Entwurf
  ohne Gliederung verliert Trennschärfe, nicht Features.
* **Widersprüche nur, wenn beweisbar.** Erkannt werden doppelte Zahlenwerte zum
  selben Schlüssel und exklusive Merkmale, die bejaht *und* verneint werden.
  Weiche semantische Konflikte bleiben der LLM-/Menschen-Schicht.
* **Standard-Filler schreibt Fragen, keine Antworten.** Fachliche Tiefe entsteht
  erst durch einen `GateFiller` — der Optimierer erfindet sie nicht.
* **Stufe 3 ohne Provider ist ehrlich leer.** Kein Blatt wird verifiziert, die
  Telemetrie zeigt das offen.

---

## 7. Selbstprüfung

```bash
python3 -m unittest tests.test_prompt_optimizer -v     # 40 Tests
python3 -m ruff check core/prompt_optimizer tests/test_prompt_optimizer.py
python3 -m mypy core/prompt_optimizer
make prompt-optimizer                                  # Demo-Lauf in workspace/
```

Abgedeckt sind Moduswahl (inklusive „Research aktiviert nichts“), Extraktion,
Feature-Erhalt, Sperren, Stufen-Gate, Kontext-Leerung, Idempotenz des
`4-final`-Dokuments, Coverage, Quellenprüfung und die Telemetrie-Arithmetik.

---
name: prompt_optimizer
version: "1.0"
kind: system-prompt
status: implemented
implementation: core/prompt_optimizer
entrypoints:
  cli: "python3 -m core.prompt_optimizer"
  api: "from core.prompt_optimizer import PromptOptimizer, Mode"
  demo: "python3 scripts/prompt_optimizer_demo.py"
modes: [normal, deep-chain]
stages: 4
artifacts:
  0: stage_0_baseline.md
  1: stage_1_macro_skeleton.md
  2: stage_2_domain_expansion.md
  3: stage_3_verified_research_leaves.md
  4: stage_4_FINAL_MASTER_PROMPT.md
normal_artifact: optimized_prompt.md
markers:
  1: "<!-- prompt-optimizer-pass: 1; status: ERWEITERT -->"
  2: "<!-- prompt-optimizer-pass: 2; status: ERWEITERT -->"
  3: "<!-- prompt-optimizer-pass: 3; status: ERWEITERT -->"
  4: "<!-- prompt-optimizer-pass: 4-final; status: FINAL -->"
  normal: "<!-- prompt-optimizer-pass: 1-final; status: NORMAL -->"
---

# Dynamischer Prompt-Optimierer — System-Spezifikation (Normalform 1.0)

> Diese Datei ist die **kanonische Fassung** des Optimierers. Sie ist aus der
> gelieferten Roh-Spezifikation (v0.9) normalisiert: gleiche Mechanik, keine
> offenen Auslegungsfragen, jede Regel mit einem Prüfpunkt versehen. Die
> ausführbare Umsetzung liegt in [`core/prompt_optimizer/`](../core/prompt_optimizer),
> die Bedienung in [`docs/PROMPT-OPTIMIZER.md`](../docs/PROMPT-OPTIMIZER.md).

## 0. Zweck

Der Optimierer verbessert ein Prompt-Dokument, ohne dass sich zwei Disziplinen
gegenseitig das Arbeitsgedächtnis wegnehmen:

* **Achse A — Prompting-Technik:** Rolle, Hierarchie, Constraints, Operatoren,
  Deduplizierung, maschinenprüfbare Gates.
* **Achse B — Fach-Inhalt:** Domänenbreite, UI/UX-Kontext, State-Machines,
  Primärfakten, Randfälle.

In jeder Stufe ist **genau eine** Achse aktiv (100 % Aufmerksamkeit), die andere
ist **gesperrt** (`LOCK 🔒`, 0 % Veränderung). Das ist der Reißverschluss.

**Kernversprechen:** null Feature-Verlust, null erfundene Details, null
stillschweigende Glättung. Jede Lücke bleibt als `OFFEN` sichtbar.

## 1. Moduswahl (Circuit Breaker)

### 1.1 `MODUS: NORMAL` — Standard, ein Durchlauf

* **Auslöser:** jede allgemeine Optimierungsbitte („optimiere“, „verbessere“,
  „repariere“, „mach den Prompt besser“) **oder** fehlende Modusangabe.
* **Verhalten:** genau ein Durchlauf `0 -> 1-final`; kein 4-Stufen-Export,
  keine externe Recherche. Die vier Hard Gates werden **einmal, direkt auf das
  Gesamtziel** beantwortet. Ausgabe: `optimized_prompt.md` mit Marker
  `1-final / NORMAL`, in der Originalsprache der Eingabe.

### 1.2 `MODUS: DEEP-CHAIN` (alias `ERWEITERT`) — vier Stufen

* **Auslöser ausschließlich:** ausdrücklicher Befehl wie „Erweiterte
  Optimierung“, „Deep Optimization“, „MODUS: DEEP-CHAIN“, „Starte 4-Stufen-Kette“.
* **Verhalten:** pro Aufruf **genau eine** Stufe, Export des Stufen-Artefakts,
  Telemetrie, Kontext leeren, am Stufen-Gate stoppen. Ausnahme: der Befehl
  „alle vier Stufen am Stück“ (`--all`, `auto_approve=True`).

### 1.3 Was **nicht** auslöst (verbindlich)

| Eingabe | Ergebnis | Grund |
| :--- | :--- | :--- |
| „optimiere diesen Prompt“ | `NORMAL` | Standardfall |
| „baue Deep Research ein“ | `NORMAL` | Research-Wort ist kein Modusbefehl |
| „Mach den Prompt besser, er soll recherchieren“ | `NORMAL` | Recherche ist Inhalt, nicht Modus |
| Header `status: ERWEITERT` im Dokument | kein Auslöser | der Marker wird **geschrieben**, nicht gelesen |
| „Erweiterte Optimierung“ | `DEEP-CHAIN` | ausdrücklicher Befehl |
| `--mode deep-chain` | `DEEP-CHAIN` | explizite Angabe schlägt Text |

> Der Marker im Dokumentkopf ist ein **Ergebnis**, kein Signal. Wer ihn als
> Auslöser liest, baut einen Zirkel: das Dokument würde sich selbst immer weiter
> optimieren. Prüfpunkt: `resolve_mode()` in
> [`core/prompt_optimizer/pipeline.py`](../core/prompt_optimizer/pipeline.py).

## 2. Die vier Hard Gates (Wortlaut = Vertrag)

Jedes Gate wird in jeder Stufe **sichtbar** beantwortet — als Liste aus
belegbaren Ankern oder als `OFFEN`-Punkt. Kein Gate darf stillschweigend
entfallen. Reihenfolge und Wortlaut sind fix:

1. **Professioneller Maßstab** — Was würde ein Top-Experte in genau diesem
   Fachgebiet hier tun, wonach der aktuelle Entwurf noch nicht fragt?
2. **Rohestes Ausgangsmaterial** — Von welchem rohesten Ausgangsmaterial
   (Bytes, Spezifikationen, Schemata, State-Transitions) würde ein Profi starten
   statt von vorverdauter Prosa?
3. **Spezifische Methoden & Werkzeuge** — Welche konkreten Methoden,
   Algorithmen, Protokolle und Werkzeuge würde er einsetzen?
4. **Unabhängiger Erfolgsnachweis** — Welcher objektive, maschinen- oder
   drittprüfbare Beweis zeigt eindeutig, dass das Ergebnis korrekt ist?

**Antwortformat je Gate:** mindestens ein Anker; unbelegtes wird als
`OFFEN: …` geführt. Wer ein Gate mit Prosa füllt, die niemand prüfen kann,
verletzt Gate 4.

## 3. Der alternierende 4-Stufen-Zyklus

| Stufe | Export (Checkpointing) | Aktive Achse | Gesperrte Achse | Verhinderter Fehlermodus |
| :--- | :--- | :--- | :--- | :--- |
| **1** (`0 -> 1`) | `stage_1_macro_skeleton.md` | Prompting-Technik (Top-Down) | Inhalt `LOCK 🔒` | Features/Personas werden beim ersten Strukturieren wegrationalisiert |
| **2** (`1 -> 2`) | `stage_2_domain_expansion.md` | Inhalt & Kontext (Breite) | Struktur `LOCK 🔒` | Aus Kürze-Angst werden Details unterschlagen |
| **3** (`2 -> 3`) | `stage_3_verified_research_leaves.md` | Inhalt & Fakten (Tiefe) | Struktur `LOCK 🔒` | Rechenzeit fließt in Kosmetik statt in Quellenprüfung |
| **4** (`3 -> 4-final`) | `stage_4_FINAL_MASTER_PROMPT.md` | Prompting-Technik (Bottom-Up) | Inhalt `LOCK 🔒` | Erarbeitete Fakten gehen beim Zusammenbauen verloren |

### 3.1 Stufe 1 — Makro-Skelett (Inhalt gesperrt)

1. **Feature-Manifest** `[F-01]..[F-NN]` aus dem Rohentwurf — jede Funktion,
   jedes Subsystem, jede Persona, jede UI-/Farb-/Schema-Vorgabe. Explizit im
   Text vorhandene IDs bleiben erhalten.
2. **Struktur:** Rolle & Ziel, nummerierte Subsystem-Blöcke `[S-01]..[S-NN]`,
   globale Constraints, Sicherheitsgrenzen, Ausgabevertrag, Entscheidungen.
3. Unter jedem Subsystem-Block liegen die vier Gate-Container als leere,
   sichtbare Anforderungs-Rahmen.

**Invariante:** 0 % neue Fachfakten, 0 % gelöschte Features. Prüfpunkt:
Feature-Liste vor/nach Stufe 1 ist identisch (`_assert_no_feature_drift`).

### 3.2 Stufe 2 — Domänen-Auffächerung (Struktur gesperrt)

1. Sektionsfolge aus Stufe 1 bleibt **exakt** erhalten (Sperr-Fingerprint).
2. Die vier Gates werden **einzeln pro Subsystem** beantwortet — eigener
   Spezialisten-Maßstab für UI/Rendering, für IPC/Speicher, für Voice/NCM, für
   Security/Scraping, für Daten, für Telemetrie.
3. High-Context-Bereiche (UI/UX, visuelle Telemetrie, State-Machines,
   Domänen-Architektur) werden breit ausgebaut; konkrete Detailfragen werden zu
   Research-Blättern `[R-01]..[R-NN]`.
4. Schnittstellen und Randfälle werden **nur** aus dem Entwurf belegt; fehlt ein
   Anker, steht dort `OFFEN`.

**Invariante:** Topologie unverändert. Prüfpunkt: `technique_fingerprint`
identisch zu Stufe 1.

### 3.3 Stufe 3 — Deep Research & Fakten-Härtung (Struktur gesperrt)

1. Blätter `[R-..]` werden mit einem Research-Provider aufgelöst
   (Quellen-Tiering, Primärspezifikationen, Cross-Verifikation, Zeitstempel,
   Kill-Kriterien, explizite Unsicherheit).
2. Ungesicherte Annahmen werden durch verifizierte Spezifikationen ersetzt —
   oder als `UNVERIFIZIERT` belassen. Es wird **nichts** erfunden.
3. Keine sprachliche Glättung, keine Zusammenfassung: 100 % Fokus auf Wahrheit
   pro Unterpunkt.

**Verifikationsstufen:** T0 unbelegt · T1 entwurfsintern · T2 Primärquelle mit
Locator + wörtlichem Zitat · T3 zusätzlich lokal nachgeprüft (Datei/Hash/Test).
`VERIFIZIERT` verlangt mindestens T2 **und** einen gesetzten Prüfvermerk.

### 3.4 Stufe 4 — Reverse-Synthese (Inhalt gesperrt)

1. Rückwärts von den verifizierten Blättern (Stufe 3) über die Subsysteme
   (Stufe 2) ins Makro-Skelett (Stufe 1): Schnittstellen werden so geschärft,
   dass alle Module ineinandergreifen.
2. Alle Fakten `[R-..]` und alle Features `[F-..]` werden ohne Verlust
   eingewoben; Redundanzen werden durch ID-Referenzen ersetzt.
3. Marker `<!-- prompt-optimizer-pass: 4-final; status: FINAL -->` plus
   Coverage-Nachweis `[F-01..NN] & [R-01..NN] = 100 %`.

**Invariante:** 0 % Inhaltsverlust gegenüber Stufe 3. Nach `4-final` erfolgt
**keine weitere Umschreibung**: ein erneuter Aufruf gibt das Dokument
byte-identisch zurück (`StageResult.no_op = True`).

## 4. Handover, Cache Eviction, Stufen-Gate

* Jede Stufe schreibt **zwei** Dateien: das Markdown-Artefakt und einen
  Modell-Checkpoint `stage_N.model.json` (Feature-, Subsystem-, Blatt-Daten).
* Danach wird der Arbeitskontext **geleert**. Stufe `n+1` liest ausschließlich
  die Checkpoints von der Platte; Stufe 4 liest 1, 2 und 3 gleichzeitig frisch.
* Ohne Freigabe startet keine nächste Stufe (`ApprovalRequired`). Nur der
  ausdrückliche „alle Stufen am Stück“-Befehl öffnet die Gates automatisch.
* Der Rohentwurf selbst wird **nicht** in den Checkpoints mitgeschleppt: das
  Modell ist die Verdichtung, nicht die Kopie.

## 5. Dual-Achsen-Scorecard (Telemetrie nach jeder Stufe)

Die Tabelle wird nach jeder Stufe ausgegeben und zusätzlich am Ende des
Artefakts gespeichert. Prozentwerte sind **gezählt**, nicht geschätzt: je Achse
vier Kriterien à 25 Punkte.

**Inhaltliche Tiefe**

1. Feature-Vollständigkeit (0–25) — Anteil der `[F-xx]`-Anker, die im Artefakt stehen.
2. Spezialisten-Rohmaterial (0–25) — Anteil Subsysteme mit typisiertem Rohmaterial-Container.
3. Verifizierte Primärfakten (0–25) — Anteil Blätter mit Tier≥2, Zitat und Prüfvermerk.
4. Randfall- & Schnittstellen-Tiefe (0–25) — Anteil Subsysteme mit belegter Schnittstelle **und** belegtem Randfall.

**Prompting-Technik**

1. Makro-Topologie & Hierarchie (0–25) — Anteil der sieben Pflicht-Sektionen.
2. Widerspruchsfreiheit (0–25) — 25 minus 5 je offenem Widerspruch.
3. Signal-to-Noise / Attention-Routing (0–25) — Anteil eindeutiger Zeilen (Duplikate kosten).
4. Maschinenprüfbare Verifikations-Gates (0–25) — `[F-xx]`, `[R-xx]`, Nachweis-Sektion, Coverage-Zeile.

**Sperr-Semantik:** Ist eine Achse gesperrt, wird ihr Wert aus dem Vorgänger
**übernommen**, nicht neu berechnet; zusätzlich muss ihr Fingerprint identisch
sein, sonst bricht der Lauf ab (`LockViolation`).

Ausgabeformat (unverändert gegenüber v0.9):

```markdown
### 📊 Optimierungs-Telemetrie (Stufe X von 4 — Export: `stage_X_...md`)
| Dimension | Status in Stufe X | Vorher | Aktuell | Delta (Δ) | Nachweis & Haupttreiber |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Inhaltliche Tiefe (Domäne & Kontext)** | `[AKTIV / LOCK 🔒]` | XX % | **YY %** | **+ZZ %** | [Module, Manifest-Status] |
| **2. Prompting-Technik (LLM-Steuerung)** | `[AKTIV / LOCK 🔒]` | XX % | **YY %** | **+ZZ %** | [Struktur, Dedup, Synthese] |
```

**Erwartete Spur** (Beispiel-Lauf, siehe `scripts/prompt_optimizer_demo.py`):

| Stufe | Inhalt | Technik | Achsen |
| :--- | ---: | ---: | :--- |
| 0 | 25 | 58 | Baseline, beide gemessen |
| 1 | 25 | 86 | Inhalt `LOCK`, Technik `AKTIV` |
| 2 | 75 | 86 | Inhalt `AKTIV`, Technik `LOCK` |
| 3 | 94 | 86 | Inhalt `AKTIV`, Technik `LOCK` |
| 4 | 94 | 94 | Inhalt `LOCK`, Technik `AKTIV` |

## 6. Guards und Abbruchgründe

| Guard | Auslöser | Verhalten |
| :--- | :--- | :--- |
| `StageOrderError` | Stufe außer der Reihe | Abbruch, kein Teilartefakt |
| `ApprovalRequired` | Gate nicht freigegeben | Abbruch, Zustand bleibt |
| `LockViolation` | gesperrter Fingerprint verändert | Abbruch (auch bei `4-final`-Rewrite) |
| `CoverageError` | `[F-..]`/`[R-..]` fehlt in Stufe 4 | Abbruch statt unvollständigem Final |
| `no_op` | Eingabe ist bereits `4-final` | Dokument unverändert zurück |

## 7. Was der Optimierer ausdrücklich nicht tut

* Er recherchiert nicht selbst — ohne Provider bleibt jedes Blatt
  `UNVERIFIZIERT` und sagt das.
* Er erfindet keine Fachfakten, keine Farben, keine Zahlen, keine Personas.
* Er glättet keine Widersprüche weg: er macht daraus `[ENTSCHEIDUNG NÖTIG]`.
* Er optimiert ein `4-final`-Dokument nicht erneut.
* Er startet keine Netz-Aufrufe und schreibt nur in sein Export-Verzeichnis.

## 8. Änderungsprotokoll gegenüber v0.9 (Normalisierung)

| # | v0.9 war offen | v1.0 ist entschieden |
| ---: | :--- | :--- |
| 1 | Marker `status: ERWEITERT` im Kopf vs. Modusauslöser | Marker ist Ergebnis, nie Auslöser (§1.3) |
| 2 | „Vorher“-Wert der Scorecard undefiniert | Vorher = Wert des Vorgänger-Checkpoints (§5) |
| 3 | Sperre ohne Messverfahren | Sperre = übernommener Wert **plus** Fingerprint-Gleichheit (§5) |
| 4 | `deep-research-framework` nicht spezifiziert | Provider-Protokoll mit Quellen-Tiering und Prüfvermerk (§3.3) |
| 5 | „konkrete Methoden“ ohne Antwortformat | Gate-Container mit typisiertem Rohmaterial je Domäne (§2, §3.2) |
| 6 | Widerspruchsbehebung ohne Spur | `[ENTSCHEIDUNG NÖTIG]`-Einträge statt stiller Auflösung (§3.1) |
| 7 | Idempotenz nur behauptet | `4-final` wird byte-identisch zurückgegeben (§3.4) |
| 8 | Stopp am Gate ohne Zustandsmodell | persistierter `run_state.json`, Fortsetzung per CLI (§4) |

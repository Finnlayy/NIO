# Testen

Drei Teststapel, keiner braucht ein Framework von außen. `package.json` und
`tsconfig.json` des Frontends sind **eingefroren** — deshalb laufen die
UI-Tests über ein eigenes Skript statt über Vitest oder Jest.

| Stapel | Befehl | Anzahl | Dauer |
|---|---|---:|---:|
| Python (Kern, Orchestrator, Limbs) | `python3 -m unittest discover -s tests -t .` | **360** | ~25 s |
| Frontend (Module + SSR) | `node scripts/ui-test.mjs` | **69** | ~5 s |
| Browser-Audit (manuell, headless) | `node /tmp/audit/a*.mjs` | 10 Skripte | ~10 min |

---

## 1. Python: `unittest`

```bash
python3 -m unittest discover -s tests -t .          # alle
python3 -m unittest tests.test_trading_limb -v      # nur das Trading-Limb
python3 -m unittest tests.test_limbs -v             # Limb-Vertrag
```

Erwartetes Ergebnis:

```
Ran 360 tests in 24.4s

OK (skipped=2)
```

Die zwei Skips sind Umgebungsabhängigkeiten (fehlende optionale Werkzeuge),
keine Fehler.

### Was bewacht wird

| Datei | Gegenstand |
|---|---|
| `test_limbs.py` | Ein Limb, zwei Aufrufwege (Skript *und* Import müssen dasselbe Modul treffen); Register- und Versionsdrift; Unlimited-Semantik |
| `test_trading_limb.py` | 23 Tests: Protokolltreue, Sandbox-Isolation, Fail-closed, Parameterfilter, Skript-Vertrag |
| `test_bootstrap.py` | Dateioperationen in der Sandbox |
| `test_event_bus.py`, `test_telemetry.py` | UDS-Events |
| `test_nexus_triad*.py`, `test_full_phase_loop.py` | Ende-zu-Ende über den Kernel |

### Der wichtigste Limb-Test

```python
def test_every_handler_matches_protocol_pattern(self):
    for operation in self.limb.handlers():
        self.assertRegex(operation, r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
```

Dieser Test hätte den Fehler gefunden, der beim Bau des Trading-Limbs
auftrat: `trading.lake.summary` hat **zwei** Punkte und wird vom Protokoll mit
`E_SCHEMA_INVALID` abgelehnt. Der Validator fing es beim ersten echten Intent —
der Test hält es jetzt dauerhaft fest.

---

## 2. Frontend: `scripts/ui-test.mjs`

Kein Test-Runner-Paket. Das Skript:

1. kopiert die zu testenden Module nach `.test-build/`
2. schreibt `@/`-Aliase in relative Pfade um (`tsc` CLI kennt kein `paths`)
3. kompiliert mit dem projekt-eigenen TypeScript (CommonJS)
4. führt die Tests aus `src/ops/__tests__/` unter `node --test` aus

```bash
cd frontend
node scripts/ui-test.mjs
# ℹ tests 69
# ℹ pass 69
# ℹ fail 0
```

SSR-Tests laufen über `react-dom/server` — kein DOM nötig.

### Abgedeckt

- Router-Mathematik (Gewichte, Score, Ranking, Failover-Reihenfolge)
- Engine-Zustände bis `EXHAUSTED`
- Handoff-Notiz (< 900 Zeichen, Trunkierung)
- Graph-Geometrie (`fitEllipse`, `cardsCollide`, Ring-Kapazität, Board-Fallback)
- Widget-Rendering und DOM-Budget
- Telemetrie-Validierung und Zustandsautomat

---

## 3. Browser-Audit

Die UI-Bugs dieser Session (Fokusfalle, Backdrop, Ring-Kollisionen, Kontrast)
waren **unsichtbar für Unit-Tests** — sie brauchten einen echten Browser.

Aufbau: `playwright-core` + `@sparticuz/chromium`, headless, Software-Rendering.
`LD_LIBRARY_PATH` muss auf die mitgelieferten NSS-Bibliotheken zeigen, sonst
scheitert der Start mit `libnspr4.so: cannot open shared object file`.

| Skript | Prüft |
|---|---|
| `a1-static.mjs` | Layout/A11y über 7 Viewports, Konsolenfehler |
| `a2-overflow.mjs` | Horizontaler Überlauf, HUD-Klemmung |
| `a3-hover.mjs` | Hover-Vergrößerung ohne Kollision |
| `a4b-deck.mjs` | Deck: Fokus hinein, 40× Tab ohne Ausbruch, Escape stellt Fokus wieder her, Scrim schließt |
| `a5c-term.mjs` | Terminal: Autofokus, Clipboard, Busy-Gate |
| `a6-mobile-deck.mjs` | Deck bei 390/834/1024 |
| `a7-controls.mjs` | Deck-Regler (Engine-Wechsel, 7 Switches, Rechte) |
| `a8b-weights.mjs` | Routing-Gewichte: Vorschau, Escape verwirft, Apply übernimmt |
| `a9-failover.mjs` | Failover-Swap + Handoff unter echter Last |
| `a9f-bisect.mjs` | **Regressionstor**: 60 schnelle Slider-Ticks |

### Warum `a9f` existiert

Ein Bug („Maximum update depth exceeded") trat **nur bei schnellen
Tastatur-Wiederholungen** auf. Einzelne Schritte waren immer grün. Erst 60 Ticks
in Folge lösten ihn aus. Wer diesen Test entfernt, verliert die einzige Abdeckung
für genau diese Klasse.

---

## 4. Gates vor einem Merge

```bash
# 1. Typen
cd frontend && npx tsc --noEmit

# 2. Python-Suite
python3 -m unittest discover -s tests -t .

# 3. Frontend-Suite
cd frontend && node scripts/ui-test.mjs

# 4. Build
cd frontend && npm run build
```

Erwartet: `tsc` ohne Ausgabe · `360 OK` · `69/69` · `Compiled successfully`
mit 8 Routen (`○ /`, `○ /apollo`, `○ /ops`, 5 × `ƒ /api/*`).

### Was `npm run build` beweist

| Prüfung | Warum sie zählt |
|---|---|
| Hydration | Server- und erster Client-Render müssen übereinstimmen — ein 0×0-Scene-Fallback kippte einmal das Markup und erzeugte `data-layout`-Mismatch |
| Statische Routen | `/`, `/apollo`, `/ops` dürfen kein `window` beim Prerender berühren |
| Typen im Build | strenger als `tsc --noEmit` in manchen Pfaden |

---

## 5. Regeln für neue Tests

1. **Kein Netz, kein laufender Dienst.** Adapter und Verträge lassen sich mit
   Attrappen prüfen; das ist schneller und reproduzierbar.
2. **Eigene Sandbox.** Ein Test, der `constraints.sandbox_root = "workspace"`
   benutzt, greift die Dateien eines echten Laufs ab. Genau das hat einmal
   einen laufenden Worker abgeschossen — Fail-closed-Tests nutzen jetzt
   `workspace/.test-trading-failclosed`.
3. **Frische Timer.** Das ausgelieferte `intent.sys_echo.json` ist auf
   2026-09-03 datiert. Ein abgelaufener Timer erzeugt korrekt ein ungültiges
   Result (negatives `remaining_ms`) — kein sinnvoller Testfall. `fresh_intent()`
   setzt die Zeitstempel neu.
4. **Ein Test pro Fehler.** Jeder in dieser Session gefundene Bug hat einen
   Test oder ein Audit-Skript, das ihn wiederfindet.

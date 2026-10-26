# Rollen-Spezifikation: REA-Subagent-Limb (Phase 3)

Version 1.0 · Ziel-Datei `limbs/rea_limb.py` · Register-Name `rea`
· Rahmen: `orchestrator/subagent.py` · Doku: [`docs/REA-SUBAGENT.md`](../../docs/REA-SUBAGENT.md)

Der REA-Limb ist der **erste Subagent** des Systems: ein Knoten, der ein fremdes
Werkzeug (REA, [Reverse Engineer Anything](https://github.com/NabilRFG12/Reverse-Engineer-anything))
in einer **eigenen Sandbox** installiert und betreibt. Er liefert keine
Meinungen, sondern Evidence: Hashes, Zählungen, Lücken.

---

## 1. Auftragsumfang

| Operation | Risk | Netz | Verhalten |
|---|---|---|---|
| `rea.ping` | none | nein | Installationszustand, Version, Node, Pfadlayout, Fähigkeiten |
| `rea.install` | write | **ja** | `git clone` + `npm ci` + `npm run build` **oder** `npm i rea-agents`; optional pwntools-venv |
| `rea.doctor` | read | nein | `rea doctor` verdichtet: Checks, Fehlschläge, Remediation |
| `rea.capabilities` | none | nein | Operationsmatrix inkl. Nebenwirkungen |
| `rea.analyze` | read | je Kommando | genau **ein** freigegebenes REA-Kommando gegen ein Ziel in der Sandbox |

`rea.install` verlangt `constraints.allow_network=true`. Ohne dieses Flag wird
der Auftrag **vor** jedem Prozessstart mit `E_POLICY_DENIED` abgelehnt — ein
stiller Netzwerkzugriff ist nicht vorgesehen.

---

## 2. Harte Regeln für den Limb

1. **Kein Shell-String.** `argv`-Listen, `start_new_session=True`. Der
   Kommandoname ist ein Schlüssel aus `ReaLimb.COMMANDS`; Positionalform und
   erlaubte Optionen stehen dort. Freitext gibt es nicht.
2. **Pfade nur über `ctx.resolve()`.** `target`, `paths[]`, `out` sind
   policy-geprüft (Register: `path_params`). Absolute Pfade und `..` sind schon
   im Pre-Flight ein `E_SANDBOX_ESCAPE`.
3. **Eigenes Zuhause.** `HOME`, `TMPDIR`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`
   und `npm_config_cache` zeigen in die Sandbox. Ein Lauf schreibt nicht ins
   Host-Home; `GIT_TERMINAL_PROMPT=0` verhindert hängende Credential-Fragen.
4. **Prozessgruppe statt Einzelprozess.** Bei Ablauf der Limb-Uhr wird die
   Gruppe beendet (`SIGKILL` an die PGID) — npm/tsc/node-Kinder inklusive.
   Der Limb meldet `status="timeout"` mit Statusbericht statt zu hängen.
5. **Budget vom Orchestrator, nicht selbst erfunden.** `_budget()` nimmt das
   Minimum aus Parameter-Timeout, Soft-Deadline (minus 1 s Vorlauf) und
   Safety-Netz. Ein Kind läuft nie länger als der Auftrag.
6. **Belege statt Zusammenfassungen.** Rohausgabe wird als Datei unter `out/`
   abgelegt und als Artefakt mit `sha256` gemeldet. Im Result steht nur eine
   verdichtete Sicht (Identität, Knoten/Kanten, Lücken, Grenzen).
7. **`dry_run` respektieren.** `rea.install` meldet den Plan; `rea.analyze`
   gibt `argv` zurück, ohne einen Prozess zu starten.
8. **Eigentum respektieren.** `force=true` baut nur Verzeichnisse neu, die
   einen gültigen `.rea-install.json`-Marker dieses Knotens tragen. Ein fremder
   nicht-leerer Baum ist `E_ALREADY_EXISTS`, kein `rm -rf`.
9. **Fehler fachlich melden.** REA-Fehlercodes (`provider_unavailable`,
   `unsupported_target`, …) werden auf NEU-Codes abgebildet und mit der
   REA-Remediation als `hint` zurückgegeben.

---

## 3. Sandbox-Layout

```
workspace/subagents/<agent_id>/          <- Policy-Wurzel dieses Knotens
  rea/            Installation (git-Klon oder npm-Paket) + optional pyenv/
  targets/        importierte Ziele (byte-identisch) + .manifests/<name>.json
  out/            Evidence-Bundles, doctor-Reports
  logs/           stdout/stderr jedes Kindprozesses
  tmp/ home/ cache/   TMPDIR, HOME, XDG/npm-Cache
  .subagent/state.json  Identität, Installation, Läufe (vom Manager)
```

`targets/<name>` wird **nicht** verändert: das Import-Manifest liegt unter
`targets/.manifests/`, damit der analysierte Digest der des Originals bleibt.

---

## 4. Ergebnisform (`rea.analyze`)

```json
{
  "command": "analyze-javascript-application",
  "exit_code": 0,
  "duration_s": 3.17,
  "rea_version": "6.0.0",
  "evidence_id": "ev_…",
  "raw": {"path": "…/out/…json", "bytes": 8172729, "sha256": "…", "truncated": false},
  "logs": {"stdout": "…", "stderr": "…"},
  "summary": {
    "evidence_id": "ev_…",
    "provider": {"id": "rea-javascript-application"},
    "subject": {"name": "orbit-dodge", "format": "directory", "sha256": "…"},
    "application_graph": {"nodes": 8, "edges": 9, "kinds": {…}},
    "semantic_graph": {
      "nodes": 1816, "kinds": {…}, "relations": 1815,
      "unknowns": 156, "unknown_reasons": {"dynamic-call": 78, "ambiguous-target": 76},
      "named_functions": [{"label": "g", "module": "game.min.js"}],
      "coverage": "unknown"
    },
    "statistics": {…},
    "limitations": ["…"]
  }
}
```

Bei Binärformaten (`inspect-binary-layout`) ersetzt `binary_layout` den
Anwendungsgraphen: Format, Architektur, Sections/Segmente/Symbole, Relokationen,
Mitigations und benötigte Bibliotheken.

---

## 5. Grenzen (bewusst)

* Deep-Native-Dekompilierung braucht Hopper, Ghidra oder IDA. Fehlt die Engine,
  sagt `rea.doctor` das (`missing_analysis_engine`) — der Limb tut nicht so, als
  hätte er analysiert.
* `doctor` kann `unsupported_host` melden (z. B. Debian 12). Das ist ein
  Befund, kein Fehlschlag des Auftrags: statische Analyse funktioniert, die
  Host-Prüfung bleibt ehrlich.
* Eine Installation ist immer an eine Sandbox gebunden. Nach einem frischen
  Checkout heißt das: `subagent install` erneut ausführen.

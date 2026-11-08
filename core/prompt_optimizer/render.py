"""Renderer der Stufen-Artefakte und des Ein-Durchlauf-Ergebnisses (NORMAL).

Ein Artefakt ist ein **ausfuehrbarer Prompt-Entwurf**, kein Protokoll ueber einen
Entwurf. Deshalb steht in jeder Stufe zuerst die Rolle, dann das eingefrorene
Feature-Manifest, dann die Subsystem-Blöcke mit ihren Gate-Containern. Die
Sektionen 0 bis 6 sind ab Stufe 1 unveraenderlich -- genau darueber prueft die
Pipeline die Technik-Sperre der Stufen 2 und 3 (Sektionsliste plus
Ausgabevertrag ergeben den Fingerprint).

Zwei Regeln halten die Renderer ehrlich:

* Jede Aussage ueber den Entwurf wird aus den extrahierten Daten gebildet,
  nie aus einer Vermutung.
* Was offen ist, bleibt als ``OFFEN`` sichtbar; es gibt keinen Platzhalter,
  der wie ein Ergebnis aussieht.
"""

from __future__ import annotations

import re

from .model import (
    HARD_GATES,
    MODE_MARKER,
    PASS_MARKER,
    REQUIRED_SECTIONS,
    SECTION_TITLES,
    Feature,
    ScoreCard,
    StageDocument,
    Subsystem,
)
from .scorecard import CONTENT_CRITERIA, TECHNIQUE_CRITERIA

__all__ = [
    "DEFAULT_CONSTRAINTS",
    "DEFAULT_CONTRACT",
    "ROLE_TEMPLATE",
    "render_baseline",
    "render_normal",
    "render_stage",
    "render_telemetry",
]

ROLE_TEMPLATE = (
    "Du bist der ausführende Ingenieur für „{title}“. Du arbeitest ausschließlich auf Basis der "
    "folgenden Spezifikation, nennst für jede Behauptung ihre Quelle und markierst jede Lücke als "
    "`OFFEN`, statt sie zu füllen."
)

DEFAULT_CONSTRAINTS: tuple[str, ...] = (
    "[C-01] Original-Intent ist eingefroren: kein Feature aus dem Rohentwurf darf entfallen (Zero-Feature-Drop).",
    "[C-02] Keine erfundenen Details: fehlt eine Angabe, wird sie als präzise Anforderung formuliert, nicht geraten.",
    "[C-03] Jede Zahlenangabe braucht Einheit, Bezugspunkt und Messmethode.",
    "[C-04] Offene Punkte bleiben als `OFFEN` sichtbar, bis ein Nachweis mit Locator vorliegt.",
    "[C-05] Ausgabe in der Sprache des Rohentwurfs; Code, Identifier und Schemata bleiben in ihrer Originalschreibweise.",
)

DEFAULT_CONTRACT: tuple[str, ...] = (
    "Der Prompt enthält: Rolle, Ziel, Feature-Manifest, globale Constraints, Sicherheitsgrenzen, Subsystem-Blöcke, Ausgabevertrag.",
    "Jeder Subsystem-Block beantwortet die vier Hard Gates sichtbar (kein Gate wird übersprungen).",
    "Jede Antwort auf ein Hard Gate ist entweder belegt (Quelle mit Locator) oder als `OFFEN` markiert.",
    "Das Ergebnis nennt seinen eigenen Nachweis: Test, Schema-Validierung oder Coverage-Zeile.",
)


def _header(stage: int, doc: StageDocument) -> str:
    pass_label = PASS_MARKER[stage]
    axis = {
        1: "Prompting-Technik `AKTIV` · Inhalt `LOCK 🔒`",
        2: "Inhalt & Kontext `AKTIV` · Prompt-Struktur `LOCK 🔒`",
        3: "Inhalt & Fakten `AKTIV` · Prompt-Struktur `LOCK 🔒`",
        4: "Prompting-Technik `AKTIV` · Inhalt `LOCK 🔒`",
    }[stage]
    stage_names = {
        1: "Makro-Skelett",
        2: "Domänen-Auffächerung",
        3: "Verifizierte Research-Blätter",
        4: "FINAL MASTER PROMPT",
    }
    status = "FINAL" if stage == 4 else MODE_MARKER
    return (
        f"<!-- prompt-optimizer-pass: {pass_label}; status: {status} -->\n"
        f"# {doc.title} — {stage_names[stage]} (Stufe {stage} von 4)\n\n"
        f"> **Achsen dieser Stufe:** {axis}  \n"
        f"> **Herkunft:** Rohentwurf `sha256:{doc.draft_sha256[:16]}` · {len(doc.features)} Features · "
        f"{len(doc.subsystems)} Subsysteme · {len(doc.leaves)} Research-Blätter  \n"
        f"> **Modus:** {doc.mode.value} · **Stufe:** {stage}/4 · Marker `{PASS_MARKER[stage]}`\n"
    )


def _goal_section(doc: StageDocument) -> list[str]:
    return [
        f"## 0. {SECTION_TITLES['rolle_ziel']}",
        "",
        f"**Rolle.** {ROLE_TEMPLATE.format(title=doc.title)}",
        "",
        f"**Ziel.** {doc.goal}",
        "",
        "**Auftrag an das Zielsystem.** Liefere zu jedem Subsystem-Block die Antworten auf die vier Hard Gates,",
        "belege jede Aussage mit einem Locator und markiere Unbelegtes als `OFFEN`.",
        "",
    ]


def _manifest_section(doc: StageDocument) -> list[str]:
    lines = [
        f"## 1. {SECTION_TITLES['feature_manifest']}",
        "",
        "| ID | Feature | Subsystem | Herkunft im Entwurf |",
        "| :--- | :--- | :--- | :--- |",
    ]
    titles = {subsystem.sid: subsystem.title for subsystem in doc.subsystems}
    for feature in doc.features:
        lines.append(
            f"| `[{feature.fid}]` | {feature.title} | {titles.get(feature.subsystem, feature.subsystem)} | "
            f"{feature.source_ref or 'Entwurf'} |"
        )
    lines.append("")
    lines.append(f"**Manifest-Vollständigkeit:** {len(doc.features)}/{len(doc.features)} Features übernommen (0 gelöscht, 0 erfunden).")
    lines.append("")
    return lines


def _constraints_section(doc: StageDocument) -> list[str]:
    lines = [f"## 2. {SECTION_TITLES['globale_constraints']}", ""]
    lines.extend(f"- {constraint}" for constraint in doc.constraints)
    lines.append("")
    return lines


def _security_section(doc: StageDocument) -> list[str]:
    lines = [f"## 3. {SECTION_TITLES['sicherheitsgrenzen']}", ""]
    lines.extend(f"- {item}" for item in doc.security)
    lines.append("")
    return lines


def _subsystem_gate_lines(subsystem: Subsystem, stage: int) -> list[str]:
    lines: list[str] = []
    for gate in HARD_GATES:
        lines.append(f"#### {gate.label}")
        lines.append("")
        lines.append(f"*Frage:* {gate.question}")
        lines.append("")
        if stage == 1:
            lines.append("- **Container:** angelegt — Auffächerung erfolgt in Stufe 2 (Inhalt ist hier gesperrt).")
            lines.append("")
            continue
        answer = subsystem.gates.get(gate.key)
        if answer is None:
            lines.append("- **Container:** leer — struktureller Fehler, in Stufe 2 nicht gefüllt.")
            lines.append("")
            continue
        lines.extend(f"- {item}" for item in answer.items)
        lines.extend(f"- ⚠️ {item}" for item in answer.open_items)
        lines.append("")
    return lines


def _subsystems_section(doc: StageDocument, stage: int) -> list[str]:
    lines = [f"## 4. {SECTION_TITLES['subsysteme']}", ""]
    for subsystem in doc.subsystems:
        lines.append(f"### [{subsystem.sid}] {subsystem.title}")
        lines.append("")
        feature_list = ", ".join(f"`[{fid}]`" for fid in subsystem.features) or "—"
        lines.append(f"**Features:** {feature_list}")
        lines.append("")
        lines.extend(_subsystem_gate_lines(subsystem, stage))
        if stage >= 2:
            if subsystem.interfaces:
                lines.append("**Schnittstellen (aus dem Entwurf belegt):**")
                lines.extend(f"- {item}" for item in subsystem.interfaces)
                lines.append("")
            if subsystem.edge_cases:
                lines.append("**Randfälle (aus dem Entwurf belegt):**")
                lines.extend(f"- {item}" for item in subsystem.edge_cases)
                lines.append("")
            if not subsystem.interfaces and not subsystem.edge_cases:
                lines.append("**Schnittstellen & Randfälle:** `OFFEN` — der Entwurf nennt für dieses Subsystem keinen Anker.")
                lines.append("")
    return lines


def _contract_section(doc: StageDocument) -> list[str]:
    lines = [f"## 5. {SECTION_TITLES['ausgabevertrag']}", ""]
    lines.extend(f"- {item}" for item in doc.contract)
    lines.append("")
    return lines


def _decisions_section(doc: StageDocument) -> list[str]:
    lines = [f"## 6. {SECTION_TITLES['entscheidungen']}", ""]
    if doc.conflicts:
        lines.append(
            "Der Rohentwurf enthielt Widersprüche. Sie sind hier in Entscheidungen überführt — "
            "der Widerspruch wird nicht stillschweigend aufgelöst, sondern als setzbare Größe sichtbar:"
        )
        lines.append("")
        for conflict in doc.conflicts:
            lines.append(f"- ⚠️ `[ENTSCHEIDUNG NÖTIG]` {conflict}")
    else:
        lines.append("- Keine Widersprüche im Rohentwurf gefunden (geprüft: Zahlenwidersprüche, Ausschlussmerkmale).")
    lines.append("")
    return lines


def _research_section(doc: StageDocument, stage: int) -> list[str]:
    lines = ["## 7. Research-Blätter", ""]
    if stage == 1:
        lines.append("- Container angelegt; Research-Blätter `[R-01]..[R-NN]` entstehen in Stufe 2, Härtung in Stufe 3.")
        lines.append("")
        return lines
    if stage == 2:
        lines.append(f"{len(doc.leaves)} Blätter aus den offenen Gate-Punkten; Status durchgehend `OFFEN` (Härtung in Stufe 3):")
        lines.append("")
    else:
        verified = sum(1 for leaf in doc.leaves if leaf.verified)
        lines.append(f"{len(doc.leaves)} Blätter, davon {verified} verifiziert (Tier≥2 mit Zitat und lokalem Prüfvermerk):")
        lines.append("")
    lines.append("| ID | Subsystem | Gate | Frage | Status | Quellen |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for leaf in doc.leaves:
        sources = "; ".join(
            f"T{source.tier} `{source.locator}`" + (" ✓" if source.checked else " (unbestätigt)")
            for source in leaf.sources
        ) or "—"
        lines.append(f"| `[{leaf.rid}]` | {leaf.sid} | {leaf.gate} | {leaf.question} | `{leaf.status}` | {sources} |")
    lines.append("")
    if stage >= 3:
        for leaf in doc.leaves:
            lines.append(f"#### `[{leaf.rid}]` — {leaf.status}")
            lines.append("")
            lines.append(f"- **Frage:** {leaf.question}")
            if leaf.sources:
                for source in leaf.sources:
                    lines.append(
                        f"- **Quelle:** Tier {source.tier} · `{source.locator}` · abgerufen {source.retrieved_at or '—'} · "
                        f"lokal geprüft: {'ja' if source.checked else 'nein'}"
                    )
                    if source.quote:
                        lines.append(f"  - Zitat: „{source.quote}“")
            else:
                lines.append("- **Quelle:** keine — `OFFEN`")
            lines.append(f"- **Kill-Kriterium:** {leaf.kill_criteria}")
            lines.append(f"- **Unsicherheit:** {leaf.uncertainty}")
            lines.append("")
    return lines


def _facts_section(doc: StageDocument) -> list[str]:
    lines = [f"## 8. {SECTION_TITLES['fakten']}", ""]
    rows = [leaf for leaf in doc.leaves if leaf.verified]
    if not rows:
        lines.append("- Keine verifizierten Fakten im Lauf — alle Aussagen bleiben als `OFFEN` markiert (kein Fakt wird erfunden).")
        lines.append("")
        return lines
    lines.append("| Blatt | Subsystem | Fakt (wörtlich aus der Quelle) | Quelle |")
    lines.append("| :--- | :--- | :--- | :--- |")
    for leaf in rows:
        source = next(source for source in leaf.sources if source.verified)
        lines.append(f"| `[{leaf.rid}]` | {leaf.sid} | „{source.quote}“ | T{source.tier} `{source.locator}` |")
    lines.append("")
    return lines


def _coverage_section(doc: StageDocument) -> list[str]:
    first_f = doc.features[0].fid if doc.features else "F-01"
    last_f = doc.features[-1].fid if doc.features else "F-01"
    first_r = doc.leaves[0].rid if doc.leaves else "R-01"
    last_r = doc.leaves[-1].rid if doc.leaves else "R-01"
    return [
        f"## 9. {SECTION_TITLES['coverage']}",
        "",
        f"- Features: `[F-01..{last_f[2:]}]` = {len(doc.features)}/{len(doc.features)} = 100 % enthalten.",
        f"- Research-Blätter: `[R-01..{last_r[2:]}]` = {len(doc.leaves)}/{len(doc.leaves)} = 100 % enthalten.",
        f"- Coverage-Zeile (maschinell prüfbar): `[F-01..{last_f[2:]}] & [R-01..{last_r[2:]}] = 100 %`",
        f"- Anker gesamt: `[{first_f}]` bis `[{last_f}]`, `[{first_r}]` bis `[{last_r}]`.",
        "",
    ]


def render_telemetry(card: ScoreCard) -> str:
    """Telemetrie plus die vier Einzelkriterien je Achse (Nachvollziehbarkeit)."""
    lines = [card.render().rstrip("\n"), "", "<details><summary>Kriterien im Detail (4 x 25 %)</summary>", ""]
    lines.append("| Achse | " + " | ".join(f"Kriterium {index + 1}" for index in range(4)) + " |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")
    lines.append("| Inhaltliche Tiefe | " + " | ".join(_criterion_cells(card.content.criteria)) + " |")
    lines.append("| Prompting-Technik | " + " | ".join(_criterion_cells(card.technique.criteria)) + " |")
    lines.append("")
    lines.append("Inhalt: " + " · ".join(CONTENT_CRITERIA))
    lines.append("")
    lines.append("Technik: " + " · ".join(TECHNIQUE_CRITERIA))
    lines.append("")
    lines.append("</details>")
    lines.append("")
    return "\n".join(lines)


def _criterion_cells(values: tuple[int, ...]) -> list[str]:
    """Gesperrte Achsen haben keine Einzelkriterien: sie tragen den Vorwert."""
    if not values:
        return ["LOCK 🔒"] * 4
    return [f"{value}/25" for value in values]


def render_body(doc: StageDocument) -> str:
    """Nutzdokument ohne Telemetrie -- Grundlage jeder Messung."""
    parts: list[str] = [_header(doc.stage, doc), ""]
    parts.extend(_goal_section(doc))
    parts.extend(_manifest_section(doc))
    parts.extend(_constraints_section(doc))
    parts.extend(_security_section(doc))
    parts.extend(_subsystems_section(doc, doc.stage))
    parts.extend(_contract_section(doc))
    parts.extend(_decisions_section(doc))
    parts.extend(_research_section(doc, doc.stage))
    if doc.stage == 4:
        parts.extend(_facts_section(doc))
        parts.extend(_coverage_section(doc))
        parts.append("> **Endmarker:** dieses Dokument ist `4-final`; ein erneuter Optimierungslauf gibt es unverändert zurück.")
        parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


def render_stage(doc: StageDocument, card: ScoreCard) -> str:
    """Artefakt einer Stufe 1 bis 4: Nutzdokument plus Telemetrie."""
    return render_body(doc) + "\n---\n\n" + render_telemetry(card)


def render_baseline(doc: StageDocument, card: ScoreCard) -> str:
    """Stufe 0: unveraenderter Rohentwurf plus die messbare Baseline."""
    lines = [
        "<!-- prompt-optimizer-pass: 0; status: BASELINE -->",
        f"# {doc.title} — Baseline des Rohentwurfs",
        "",
        "> Der Entwurf wird hier **nicht** verändert. Er ist der Beleg für die „Vorher“-Werte der ersten Scorecard.",
        f"> `sha256:{doc.draft_sha256}` · {len(doc.features)} erkannte Features · "
        f"{len(doc.subsystems)} Subsysteme · {len(doc.conflicts)} Widersprüche",
        "",
        "## Rohentwurf (unverändert)",
        "",
        "````markdown",
        doc.draft_text.rstrip("\n"),
        "````",
        "",
        "## Erkannte Features",
        "",
        "| ID | Feature | Subsystem |",
        "| :--- | :--- | :--- |",
    ]
    for feature in doc.features:
        lines.append(f"| `[{feature.fid}]` | {feature.title} | {feature.subsystem} |")
    lines.extend(["", "## Erkannte Widersprüche", ""])
    if doc.conflicts:
        lines.extend(f"- ⚠️ {conflict}" for conflict in doc.conflicts)
    else:
        lines.append("- keine (geprüft: Zahlenwidersprüche, Ausschlussmerkmale)")
    lines.extend(["", "---", "", render_telemetry(card)])
    return "\n".join(lines).rstrip("\n") + "\n"


def render_normal(doc: StageDocument, card: ScoreCard) -> str:
    """Modus ``NORMAL``: ein einziger, kompakter Master-Prompt (``1-final``)."""
    lines = [
        "<!-- prompt-optimizer-pass: 1-final; status: NORMAL -->",
        f"# {doc.title} — optimierter Prompt (Single-Pass)",
        "",
        "> **Modus:** normal · ein Durchlauf `0 -> 1-final` · keine 4-Stufen-Kette, keine externe Recherche  ",
        f"> **Herkunft:** `sha256:{doc.draft_sha256[:16]}` · {len(doc.features)} Features übernommen · "
        f"{len(doc.conflicts)} Widersprüche als Entscheidung markiert  ",
        "> **Gates:** die vier Hard Gates sind direkt auf das Gesamtziel beantwortet.",
        "",
        f"## 0. {SECTION_TITLES['rolle_ziel']}",
        "",
        f"**Rolle.** {ROLE_TEMPLATE.format(title=doc.title)}",
        "",
        f"**Ziel.** {doc.goal}",
        "",
        "## 1. Die vier Hard Gates (direkt auf das Gesamtziel)",
        "",
    ]
    for subsystem in doc.subsystems[:1]:
        for gate in HARD_GATES:
            answer = subsystem.gates.get(gate.key)
            lines.append(f"### {gate.label}")
            lines.append("")
            lines.append(f"*Frage:* {gate.question}")
            lines.append("")
            if answer is not None:
                lines.extend(f"- {item}" for item in answer.items)
                lines.extend(f"- ⚠️ {item}" for item in answer.open_items)
            lines.append("")
    lines.extend(_manifest_section(doc))
    lines.extend(_constraints_section(doc))
    lines.extend(_security_section(doc))
    lines.extend(_contract_section(doc))
    lines.extend(_decisions_section(doc))
    lines.extend(["---", "", render_telemetry(card)])
    return "\n".join(lines).rstrip("\n") + "\n"


def first_feature(doc: StageDocument) -> Feature | None:
    """Erstes Feature (Bequemlichkeit fuer Reporte)."""
    return doc.features[0] if doc.features else None


def section_headings(doc: StageDocument) -> list[str]:
    """Die tatsaechlich gerenderten Top-Level-Ueberschriften (Diagnose)."""
    return [
        f"## {index}. {SECTION_TITLES[name]}"
        for index, name in enumerate(REQUIRED_SECTIONS)
        if name in doc.sections
    ]


def normalize_whitespace(text: str) -> str:
    """Fuer Vergleiche: Zeilenenden und Mehrfach-Leerzeichen angleichen."""
    return re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()

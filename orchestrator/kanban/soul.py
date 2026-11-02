"""SOUL.md Parsing und Generierung für Worker.

Die Seele (SOUL.md) eines Workers definiert seine Identität, Mission,
Fähigkeiten und Regeln. Sie wird aus Markdown-Text geparst und dorthin
zurückgeschrieben.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

__all__ = ["Soul", "default_soul", "merge_skills", "parse_soul", "render_soul"]

@dataclass
class Soul:
    frontmatter: dict[str, str] = field(default_factory=dict)
    identity: str = ""
    mission: str = ""
    core_skills: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    heartbeat: str = ""
    extra: str = ""

def parse_soul(text: str) -> Soul:
    """Parst einen SOUL.md-Text in ein Soul-Objekt."""
    soul = Soul()
    lines = text.splitlines(keepends=True)
    if not lines:
        return soul

    # Parse frontmatter
    idx = 0
    if lines[idx].strip() == "---":
        idx += 1
        while idx < len(lines) and lines[idx].strip() != "---":
            line = lines[idx].strip()
            if ":" in line:
                key, val = line.split(":", 1)
                soul.frontmatter[key.strip()] = val.strip()
            idx += 1
        if idx < len(lines) and lines[idx].strip() == "---":
            idx += 1

    # Parse sections
    current_section = ""
    section_content: list[str] = []

    def save_section() -> None:
        if current_section == "Identity":
            soul.identity = "".join(section_content).strip()
        elif current_section == "Mission":
            soul.mission = "".join(section_content).strip()
        elif current_section == "Core Skills":
            for line in section_content:
                line = line.strip()
                if line.startswith("- "):
                    soul.core_skills.append(line[2:].strip())
        elif current_section == "Rules / Constraints":
            for line in section_content:
                line = line.strip()
                if line.startswith("- "):
                    soul.rules.append(line[2:].strip())
        elif current_section == "Heartbeat":
            soul.heartbeat = "".join(section_content).strip()
        elif current_section:
            soul.extra += f"## {current_section}\n" + "".join(section_content)
        elif section_content and "".join(section_content).strip():
            soul.extra += "".join(section_content)

    for line in lines[idx:]:
        if line.startswith("## "):
            save_section()
            current_section = line[3:].strip()
            section_content = []
        else:
            section_content.append(line)
    save_section()

    return soul

def render_soul(soul: Soul) -> str:
    """Rendert ein Soul-Objekt in einen SOUL.md-Text."""
    parts = []

    if soul.frontmatter:
        parts.append("---\n")
        for k, v in soul.frontmatter.items():
            parts.append(f"{k}: {v}\n")
        parts.append("---\n\n")

    if soul.identity:
        parts.append("## Identity\n")
        parts.append(soul.identity + "\n\n")

    if soul.mission:
        parts.append("## Mission\n")
        parts.append(soul.mission + "\n\n")

    if soul.core_skills:
        parts.append("## Core Skills\n")
        for skill in soul.core_skills:
            parts.append(f"- {skill}\n")
        parts.append("\n")

    if soul.rules:
        parts.append("## Rules / Constraints\n")
        for rule in soul.rules:
            parts.append(f"- {rule}\n")
        parts.append("\n")

    if soul.heartbeat:
        parts.append("## Heartbeat\n")
        parts.append(soul.heartbeat + "\n\n")

    if soul.extra:
        parts.append(soul.extra)
        if not soul.extra.endswith("\n"):
            parts.append("\n")

    return "".join(parts).lstrip("\n")  # Strip leading newlines if no frontmatter

def default_soul(uid: str, name: str, skills: tuple[str, ...], mission: str = "") -> str:
    """Erzeugt eine Default-Seele."""
    soul = Soul()
    soul.frontmatter = {
        "uid": uid,
        "name": name,
        "skills": ",".join(skills),
        "runtime": "noop",
    }
    soul.mission = mission
    soul.rules = [
        "never push",
        "never print secrets",
        "report heartbeat",
    ]
    soul.core_skills = list(skills)
    return render_soul(soul)

def merge_skills(soul_text: str, skills_delta: Sequence[str]) -> str:
    """Fügt neue Skills hinzu, ohne Duplikate zu erzeugen."""
    soul = parse_soul(soul_text)

    existing_skills = set(soul.core_skills)
    for skill in skills_delta:
        if skill not in existing_skills:
            soul.core_skills.append(skill)
            existing_skills.add(skill)

    fm_skills = [s.strip() for s in soul.frontmatter.get("skills", "").split(",") if s.strip()]
    existing_fm = set(fm_skills)
    for skill in skills_delta:
        if skill not in existing_fm:
            fm_skills.append(skill)
            existing_fm.add(skill)

    if fm_skills:
        soul.frontmatter["skills"] = ",".join(fm_skills)

    return render_soul(soul)

"""Kanban → episodisches Gedächtnis (NIO Phase 2).

Indiziert die ``Experience``-Datensätze des Kanban-Stores (Zusammenfassung,
Lehren, Skill-Deltas, Ergebnis) in den :class:`EpisodicMemoryStore` von Ciel.
Die Episoden-ID leitet sich von der Experience-ID ab. Doppeltes Indizieren
erzeugt deshalb keine Dubletten.

Importrichtung: ``orchestrator`` → ``apollo.ciel``. Ciel kennt Kanban nicht.
"""

from __future__ import annotations

from typing import Final, Protocol

from apollo.ciel.memory_tier import EpisodicMemoryStore

from .models import Experience

#: Kategorie aller Episoden aus dem Kanban-Store.
KANBAN_EXPERIENCE_CATEGORY: Final[str] = "kanban_experience"
#: Session-Kennung, unter der Kanban-Episoden im Gedächtnis liegen.
KANBAN_SESSION_ID: Final[str] = "kanban"


class ExperienceSource(Protocol):
    """Lesezugriff auf Experiences, erfüllt vom Kanban-Store."""

    async def list_experiences(self, *, worker_uid: str | None = None, limit: int = 100) -> list[Experience]: ...


def episode_id_for(experience_id: str) -> str:
    """Stabile Episoden-ID je Experience. Grundlage der Idempotenz."""
    return f"{KANBAN_EXPERIENCE_CATEGORY}:{experience_id}"


def experience_content(experience: Experience) -> str:
    """Durchsuchbarer Text einer Experience: Zusammenfassung, Lehren, Skill-Deltas und Ergebnis."""
    parts = [experience.summary]
    if experience.lessons:
        parts.append("Lehren: " + " | ".join(experience.lessons))
    if experience.skills_delta:
        parts.append("Skills: " + ", ".join(experience.skills_delta))
    parts.append(f"Ergebnis: {experience.outcome}")
    return "\n".join(part for part in parts if part)


class KanbanMemoryBridge:
    """Schreibt Kanban-Experiences idempotent in das episodische Gedächtnis."""

    def __init__(self, source: ExperienceSource, memory: EpisodicMemoryStore) -> None:
        self._source = source
        self._memory = memory

    async def index_experiences(self, *, limit: int = 500) -> int:
        """Indiziert bis zu ``limit`` Experiences. Liefert die Anzahl neu angelegter Episoden."""
        experiences = await self._source.list_experiences(limit=limit)
        created = 0
        for experience in experiences:
            memory_id = episode_id_for(experience.id)
            if self._memory.has_episode(memory_id):
                continue
            self._memory.store_episode(
                session_id=KANBAN_SESSION_ID,
                category=KANBAN_EXPERIENCE_CATEGORY,
                content=experience_content(experience),
                tags=[experience.task_id, experience.worker_uid, experience.outcome],
                memory_id=memory_id,
            )
            created += 1
        return created


__all__ = [
    "KANBAN_EXPERIENCE_CATEGORY",
    "KANBAN_SESSION_ID",
    "ExperienceSource",
    "KanbanMemoryBridge",
    "episode_id_for",
    "experience_content",
]

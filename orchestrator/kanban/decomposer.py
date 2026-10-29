from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from .models import KanbanTask

__all__ = ["ChecklistDecomposer", "ChildSpec", "Decomposer", "LLMDecomposer"]


@dataclass
class ChildSpec:
    title: str
    description: str = ""
    required_skills: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)


class Decomposer(Protocol):
    async def decompose(self, task: KanbanTask) -> list[ChildSpec]: ...


class ChecklistDecomposer:
    async def decompose(self, task: KanbanTask) -> list[ChildSpec]:
        children: list[ChildSpec] = []
        lines = task.description.splitlines()

        for line in lines:
            line = line.strip()

            is_parallel = line.startswith("- [ ]") or line.startswith("* [ ]")
            is_sequential = re.match(r"^\d+[\.)]\s+", line) is not None

            if not (is_parallel or is_sequential):
                continue

            # Remove the prefix
            text = line[5:].strip() if is_parallel else re.sub(r"^\d+[\.)]\s+", "", line).strip()

            # Extract #skills
            skills = []
            skill_pattern = re.compile(r"#([a-zA-Z0-9_-]+)")
            for match in skill_pattern.finditer(text):
                skills.append(match.group(1))

            # Remove skills from title
            title = skill_pattern.sub("", text).strip()
            # Clean up extra spaces
            title = re.sub(r"\s+", " ", title)

            if not skills:
                skills = list(task.required_skills)

            depends_on = []
            if is_sequential and len(children) > 0:
                depends_on.append(len(children) - 1)

            children.append(ChildSpec(
                title=title,
                required_skills=skills,
                depends_on=depends_on
            ))

        return children


class LLMClient(Protocol):
    async def complete(self, system: str, messages: list[Any], tools: list[Any] = ...) -> Any: ...


class LLMDecomposer:
    def __init__(self, llm: LLMClient, fallback: Decomposer | None = None) -> None:
        self.llm = llm
        self.fallback = fallback or ChecklistDecomposer()
        self.log = logging.getLogger(__name__)

    async def decompose(self, task: KanbanTask) -> list[ChildSpec]:
        system = (
            'You are a task decomposer. Reply ONLY with valid JSON in this exact format: '
            '{"children":[{"title":"str","description":"str","required_skills":["str"],"depends_on":[int]}]}'
        )
        messages = [{"role": "user", "content": f"Title: {task.title}\nDescription: {task.description}"}]

        try:
            resp = await asyncio.wait_for(
                self.llm.complete(system=system, messages=messages, tools=[]),
                timeout=60.0
            )
            content = resp.content
            # Optionally extract JSON from markdown code block if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            children_data = data.get("children", [])

            if not isinstance(children_data, list):
                raise ValueError("children must be a list")

            if len(children_data) > 20:
                raise ValueError("Too many children (max 20)")

            children: list[ChildSpec] = []
            for c in children_data:
                children.append(ChildSpec(
                    title=str(c.get("title", "")),
                    description=str(c.get("description", "")),
                    required_skills=[str(s) for s in c.get("required_skills", [])],
                    depends_on=[int(d) for d in c.get("depends_on", [])]
                ))
            return children
        except Exception as e:
            self.log.warning(f"LLM decomposition failed: {e}. Using fallback.")
            return await self.fallback.decompose(task)

import asyncio
import unittest

from orchestrator.kanban.decomposer import ChecklistDecomposer, LLMDecomposer
from orchestrator.kanban.models import KanbanTask


class FakeLLMClient:
    def __init__(self, content: str):
        self.content = content

    async def complete(self, system: str, messages: list, tools: list | None = None):
        class Resp:
            content = self.content
        return Resp()

class TestChecklistDecomposer(unittest.TestCase):
    def setUp(self):
        self.decomposer = ChecklistDecomposer()

    def test_parallel_children(self):
        task = KanbanTask(id="1", board_id="b1", title="t", description="- [ ] one #skill1\n* [ ] two\n- [ ] three #skill2", required_skills=["default"])
        children = asyncio.run(self.decomposer.decompose(task))
        self.assertEqual(len(children), 3)
        self.assertEqual(children[0].title, "one")
        self.assertEqual(children[0].required_skills, ["skill1"])
        self.assertEqual(children[0].depends_on, [])
        self.assertEqual(children[1].title, "two")
        self.assertEqual(children[1].required_skills, ["default"])
        self.assertEqual(children[1].depends_on, [])
        self.assertEqual(children[2].title, "three")
        self.assertEqual(children[2].required_skills, ["skill2"])

    def test_sequential_children(self):
        task = KanbanTask(id="1", board_id="b1", title="t", description="1. first\n2) second #s\n3. third")
        children = asyncio.run(self.decomposer.decompose(task))
        self.assertEqual(len(children), 3)
        self.assertEqual(children[0].title, "first")
        self.assertEqual(children[0].depends_on, [])
        self.assertEqual(children[1].title, "second")
        self.assertEqual(children[1].depends_on, [0])
        self.assertEqual(children[1].required_skills, ["s"])
        self.assertEqual(children[2].title, "third")
        self.assertEqual(children[2].depends_on, [1])

class TestLLMDecomposer(unittest.TestCase):
    def test_llm_success(self):
        json_resp = '```json\n{"children":[{"title":"A","description":"D","required_skills":["S"],"depends_on":[]}]}\n```'
        llm = FakeLLMClient(json_resp)
        decomposer = LLMDecomposer(llm)
        task = KanbanTask(id="1", board_id="b1", title="t", description="desc")
        children = asyncio.run(decomposer.decompose(task))
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].title, "A")
        self.assertEqual(children[0].description, "D")
        self.assertEqual(children[0].required_skills, ["S"])
        self.assertEqual(children[0].depends_on, [])

    def test_llm_fallback(self):
        # Invalid JSON triggers fallback
        llm = FakeLLMClient("not json")
        decomposer = LLMDecomposer(llm)
        task = KanbanTask(id="1", board_id="b1", title="t", description="- [ ] fallback item")
        children = asyncio.run(decomposer.decompose(task))
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].title, "fallback item")

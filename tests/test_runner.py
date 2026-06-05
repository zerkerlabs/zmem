import json
import tempfile
import unittest
from pathlib import Path

from zerker_memory.runner import run_with_memory
from zerker_memory.store import MemoryStore


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.store = MemoryStore(self.tmp_path / "memory.sqlite")
        self.store.init()

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_writes_context_and_preserves_exit_code(self):
        self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "context.json"
        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="deploy service to production",
            agent_id="codex",
            risk="high",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["schema"], "zerker.run.v1")
        self.assertTrue(context_path.exists())
        context = json.loads(context_path.read_text())
        self.assertEqual(context["schema"], "zerker.memory_context.v1")
        self.assertEqual(len(context["memories"]), 1)
        self.assertEqual(context["memories"][0]["type"], "policy")


if __name__ == "__main__":
    unittest.main()

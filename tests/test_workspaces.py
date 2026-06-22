import tempfile
import unittest
from pathlib import Path

from zerker_memory.workspaces import (
    current_workspace,
    list_workspaces,
    register_workspace,
    use_workspace,
    workspace_status_for_paths,
)


class WorkspaceRegistryTest(unittest.TestCase):
    def test_register_list_current_and_use_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            alpha = tmp_path / "alpha"
            beta = tmp_path / "beta"
            alpha.mkdir()
            beta.mkdir()

            alpha_result = register_workspace(name="Alpha", root=alpha, registry_path=registry_path)
            beta_result = register_workspace(name="Beta", root=beta, registry_path=registry_path, make_current=False)

            listed = list_workspaces(registry_path=registry_path)
            self.assertTrue(listed["ok"])
            self.assertEqual([item["name"] for item in listed["items"]], ["Alpha", "Beta"])
            self.assertEqual(listed["current"], alpha_result["workspace"]["id"])

            current = current_workspace(registry_path=registry_path)
            self.assertEqual(current["workspace"]["name"], "Alpha")

            switched = use_workspace(beta_result["workspace"]["id"], registry_path=registry_path)
            self.assertTrue(switched["ok"])
            self.assertEqual(switched["workspace"]["name"], "Beta")

    def test_workspace_status_matches_current_db_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            result = register_workspace(name="Project", root=root, registry_path=registry_path)

            status = workspace_status_for_paths(
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            self.assertEqual(status["match_state"], "matched-current")
            self.assertEqual(status["matched"]["id"], result["workspace"]["id"])


if __name__ == "__main__":
    unittest.main()

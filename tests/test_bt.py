import json
import tempfile
import unittest
from pathlib import Path

from zerker_memory.bt import (
    BtEvent,
    BtMemory,
    bt_event_from_btpg_transition,
    bt_event_from_py_trees_transition,
)
from zerker_memory.store import MemoryStore


class BtMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "memory.sqlite")
        self.bt = BtMemory(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ingests_events_and_explains_fallback_causality(self):
        sensor_loss = BtEvent.from_dict(
            {
                "event_id": "evt_sensor_loss",
                "trace_id": "trace_1",
                "timestamp": "2026-05-26T00:00:01Z",
                "event_type": "visibility_lost",
                "node_id": "guard_human_visible",
                "node_status": "FAILURE",
                "executor_id": "robot_1",
                "affected_symbols": ["human_visible"],
            }
        )
        fallback = BtEvent.from_dict(
            {
                "event_id": "evt_recovery",
                "trace_id": "trace_1",
                "timestamp": "2026-05-26T00:00:02Z",
                "event_type": "fallback_triggered",
                "node_id": "fallback_reacquire_human",
                "node_name": "ReacquireHuman",
                "node_status": "RUNNING",
                "executor_id": "robot_1",
                "affected_symbols": ["mission_mode"],
                "causal_parent_ids": ["evt_sensor_loss"],
            }
        )

        result = self.bt.ingest([sensor_loss, fallback], source="unit-test")
        explanation = self.bt.explain("trace_1", question="why did fallback trigger?")

        self.assertEqual(result["inserted"], 2)
        self.assertEqual(explanation["primary_event_id"], "evt_recovery")
        self.assertEqual(explanation["cited_event_ids"], ["evt_recovery", "evt_sensor_loss"])
        self.assertIn("visibility_lost", explanation["summary"])
        self.assertIn("human_visible", explanation["affected_symbols"])

    def test_ingest_jsonl_file_and_list_traces(self):
        path = Path(self.tmp.name) / "trace.jsonl"
        path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "event_id": "evt_1",
                            "trace_id": "trace_file",
                            "timestamp": "2026-05-26T00:00:01Z",
                            "event_type": "node_tick",
                            "node_id": "root",
                            "node_status": "RUNNING",
                        }
                    ),
                    json.dumps(
                        {
                            "event_id": "evt_2",
                            "trace_id": "trace_file",
                            "timestamp": "2026-05-26T00:00:02Z",
                            "event_type": "node_success",
                            "node_id": "root",
                            "node_status": "SUCCESS",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = self.bt.ingest_file(path)
        traces = self.bt.traces()

        self.assertEqual(result["trace_ids"], ["trace_file"])
        self.assertEqual(traces[0]["trace_id"], "trace_file")
        self.assertEqual(traces[0]["event_count"], 2)

    def test_normalizes_py_trees_transition_into_bt_event(self):
        event = bt_event_from_py_trees_transition(
            "trace_py_trees",
            {
                "timestamp": "2026-05-27T00:00:02Z",
                "behaviour_id": "guard_visible",
                "name": "GuardVisible",
                "class_name": "CheckBlackboardVariableValue",
                "previous_status": "RUNNING",
                "current_status": "FAILURE",
                "blackboard_keys": ["human_visible"],
                "feedback_message": "human missing from sensor frame",
            },
            executor_id="robot_1",
            tree_id="demo_tree",
        )

        self.assertEqual(event.trace_id, "trace_py_trees")
        self.assertEqual(event.event_type, "fallback_triggered")
        self.assertEqual(event.node_status, "FAILURE")
        self.assertEqual(event.node_id, "guard_visible")
        self.assertEqual(event.node_name, "GuardVisible")
        self.assertEqual(event.node_type, "CheckBlackboardVariableValue")
        self.assertEqual(event.affected_symbols, ["human_visible"])
        self.assertEqual(event.payload["adapter_schema"], "zerker.bt_adapter.py_trees.v1")
        self.assertEqual(event.payload["feedback_message"], "human missing from sensor frame")

    def test_ingests_py_trees_transitions_and_explains_fallback(self):
        result = self.bt.ingest_py_trees_transitions(
            "trace_py_adapter",
            [
                {
                    "event_id": "evt_py_guard",
                    "timestamp": "2026-05-27T00:00:01Z",
                    "behaviour_id": "guard_visible",
                    "name": "GuardVisible",
                    "previous_status": "RUNNING",
                    "current_status": "FAILURE",
                    "blackboard_keys": ["human_visible"],
                },
                {
                    "event_id": "evt_py_recover",
                    "timestamp": "2026-05-27T00:00:02Z",
                    "behaviour_id": "recover_target",
                    "name": "RecoverTarget",
                    "previous_status": "INVALID",
                    "current_status": "RUNNING",
                    "causal_parent_ids": ["evt_py_guard"],
                    "affected_symbols": ["mission_mode"],
                },
            ],
            executor_id="robot_2",
            tree_id="tree_py",
        )

        explanation = self.bt.explain("trace_py_adapter", question="why did the tree recover?")

        self.assertEqual(result["inserted"], 2)
        self.assertEqual(explanation["primary_event_id"], "evt_py_guard")
        self.assertEqual(explanation["cited_event_ids"], ["evt_py_guard"])
        self.assertIn("fallback_triggered", explanation["summary"])

    def test_normalizes_btpg_transition_into_bt_event(self):
        event = bt_event_from_btpg_transition(
            "trace_btpg",
            {
                "timestamp": "2026-05-27T00:10:02Z",
                "task_id": "recover_route",
                "task": "RecoverRoute",
                "kind": "RecoveryAction",
                "last_status": "FAILURE",
                "status": "RUNNING",
                "world_state_symbols": ["route_available"],
                "goal": "resume delivery plan",
                "recovery_action": "replan path",
            },
            executor_id="robot_3",
            tree_id="btpg_tree",
        )

        self.assertEqual(event.trace_id, "trace_btpg")
        self.assertEqual(event.event_type, "recovery_resumed")
        self.assertEqual(event.node_status, "RUNNING")
        self.assertEqual(event.node_id, "recover_route")
        self.assertEqual(event.node_name, "RecoverRoute")
        self.assertEqual(event.node_type, "RecoveryAction")
        self.assertEqual(event.affected_symbols, ["route_available"])
        self.assertEqual(event.payload["adapter_schema"], "zerker.bt_adapter.btpg.v1")
        self.assertEqual(event.payload["recovery_action"], "replan path")

    def test_ingests_btpg_transitions_and_explains_fallback(self):
        result = self.bt.ingest_btpg_transitions(
            "trace_btpg_adapter",
            [
                {
                    "event_id": "evt_btpg_guard",
                    "timestamp": "2026-05-27T00:10:01Z",
                    "task_id": "guard_route",
                    "task": "GuardRoute",
                    "kind": "Condition",
                    "last_status": "RUNNING",
                    "status": "FAILURE",
                    "world_state_symbols": ["route_available"],
                    "failure_reason": "route blocked by obstacle",
                },
                {
                    "event_id": "evt_btpg_recover",
                    "timestamp": "2026-05-27T00:10:02Z",
                    "task_id": "recover_route",
                    "task": "RecoverRoute",
                    "kind": "RecoveryAction",
                    "last_status": "FAILURE",
                    "status": "RUNNING",
                    "causal_parent_ids": ["evt_btpg_guard"],
                    "affected_symbols": ["mission_mode"],
                },
            ],
            executor_id="robot_4",
            tree_id="tree_btpg",
        )

        explanation = self.bt.explain("trace_btpg_adapter", question="why did the plan recover?")

        self.assertEqual(result["inserted"], 2)
        self.assertEqual(explanation["primary_event_id"], "evt_btpg_recover")
        self.assertEqual(explanation["cited_event_ids"], ["evt_btpg_recover", "evt_btpg_guard"])
        self.assertIn("route blocked by obstacle", explanation["summary"])

    def test_exports_groot2_trace_with_manifest(self):
        self.bt.ingest(
            [
                BtEvent.from_dict(
                    {
                        "event_id": "evt_export_guard",
                        "trace_id": "trace_export",
                        "timestamp": "2026-05-27T01:00:01Z",
                        "event_type": "visibility_lost",
                        "node_id": "guard_human_visible",
                        "node_name": "GuardHumanVisible",
                        "node_type": "Condition",
                        "node_status": "FAILURE",
                        "tree_id": "demo_tree",
                        "affected_symbols": ["human_visible"],
                    }
                ),
                BtEvent.from_dict(
                    {
                        "event_id": "evt_export_recover",
                        "trace_id": "trace_export",
                        "timestamp": "2026-05-27T01:00:02Z",
                        "event_type": "recovery_resumed",
                        "node_id": "recover_target",
                        "node_name": "RecoverTarget",
                        "node_type": "RecoveryAction",
                        "node_status": "RUNNING",
                        "tree_id": "demo_tree",
                        "affected_symbols": ["mission_mode"],
                        "causal_parent_ids": ["evt_export_guard"],
                    }
                ),
            ],
            source="unit-test",
        )

        result = self.bt.export_groot2_trace("trace_export", out_dir=Path(self.tmp.name))
        xml_path = Path(result["xml_path"])
        manifest_path = Path(result["manifest_path"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertTrue(xml_path.exists())
        self.assertTrue(manifest_path.exists())
        self.assertIn('<BehaviorTree ID="demo_tree">', xml_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "zerker.bt_export.groot2.v1")
        self.assertEqual(manifest["trace_id"], "trace_export")
        self.assertEqual(manifest["explanation"]["primary_event_id"], "evt_export_recover")
        self.assertEqual(manifest["nodes"][0]["tag"], "Condition")


if __name__ == "__main__":
    unittest.main()

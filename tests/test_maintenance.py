import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import zerker_memory.maintenance as maintenance_module
from zerker_memory.cli import main
from zerker_memory.maintenance import (
    MAINTENANCE_PLAN_SCHEMA,
    MAINTENANCE_RESULT_SCHEMA,
    MAINTENANCE_VERIFICATION_SCHEMA,
    apply_memory_maintenance_plan,
    build_memory_maintenance_plan,
    verify_memory_maintenance_result,
)
from zerker_memory.store import MemoryStore


EVALUATED_AT = "2025-01-01T00:00:00Z"


class MemoryMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "memory.sqlite"
        self.store = MemoryStore(self.db_path)
        self.store.init()

    def tearDown(self):
        self.store.conn.close()
        self.temp_dir.cleanup()

    def test_preview_is_read_only_and_only_explicit_expiry_is_selectable(self):
        expired = self._remember("Expired release token.", memory_id="mem_expired")
        self._expire(expired.id)
        parent = self._remember("Status page owner is Alex.", memory_id="mem_parent")
        self._remember(
            "Status page owner is Priya.",
            memory_id="mem_child",
            parents=[parent.id],
        )
        duplicate_a = self._remember("Duplicate runbook note.", memory_id="mem_duplicate_a")
        duplicate_b = self._remember("Duplicate runbook note.", memory_id="mem_duplicate_b")
        before = self._database_bytes()

        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)

        self.assertEqual(before, self._database_bytes())
        self.assertEqual(plan["schema"], MAINTENANCE_PLAN_SCHEMA)
        self.assertTrue(plan["ok"])
        self.assertTrue(plan["read_only_preview"])
        self.assertFalse(plan["semantic_truth_claimed"])
        self.assertEqual(len(plan["selectable_actions"]), 1)
        action = plan["selectable_actions"][0]
        self.assertEqual(action["operation"], "expire")
        self.assertEqual(action["target_memory_id"], expired.id)
        self.assertEqual(action["expected_transition"], {"from": "active", "to": "expired"})
        self.assertTrue(action["requires_explicit_apply"])
        review_ids = {
            memory_id
            for item in plan["review_items"]
            for memory_id in item["memory_ids"]
        }
        self.assertIn(parent.id, review_ids)
        self.assertIn(duplicate_a.id, review_ids)
        self.assertIn(duplicate_b.id, review_ids)
        self.assertNotIn("Expired release token", json.dumps(plan))
        self.assertNotIn("Duplicate runbook note", json.dumps(plan))
        self.assertNotIn("status page", json.dumps(plan).lower())

    def test_active_parent_child_lineage_remains_review_only(self):
        parent = self._remember("Parent state.", memory_id="mem_parent")
        child = self._remember(
            "Current child.",
            memory_id="mem_current_child",
            parents=[parent.id],
        )

        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)

        self.assertEqual(plan["selectable_actions"], [])
        item = next(
            item
            for item in plan["review_items"]
            if item["reason"] == "active_memory_has_active_child_candidate"
        )
        self.assertEqual(item["memory_ids"], sorted([parent.id, child.id]))

    def test_apply_one_selected_action_is_receipted_and_idempotent(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        action_id = plan["selectable_actions"][0]["action_id"]

        result = apply_memory_maintenance_plan(
            self.db_path,
            plan,
            selected_action_id=action_id,
            actor_id="operator@example",
            confirmed_plan_id=plan["plan_id"],
        )

        self.assertEqual(result["schema"], MAINTENANCE_RESULT_SCHEMA)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["selected_action_id"], action_id)
        self.assertEqual(result["applied_count"], 1)
        self.assertEqual(result["verified_receipt_count"], 1)
        self.assertNotEqual(result["state_before"]["merkle_root"], result["state_after"]["merkle_root"])
        self.assertEqual(self.store.get(expired.id).status, "expired")
        for transition in result["transitions"]:
            self.assertEqual(transition["old_status"], "active")
            self.assertEqual(transition["new_status"], "expired")
            self.assertTrue(transition["receipt_verified"])
            self.assertTrue(transition["receipt_id"].startswith("wr_"))
            self.assertTrue(transition["receipt_hash"])
        self.assertFalse(result["semantic_truth_claimed"])
        temporal = self.store.query_at("2099-01-01T00:00:00Z", scope="project")["temporal_graph"][expired.id]
        self.assertEqual(temporal["status_at_query"], "expired")
        self.assertEqual(temporal["temporal_state"], "unlearned")
        self.assertEqual(temporal["temporal_resolution_reasons"], ["expired"])

        event_count = self._event_count()
        repeated = apply_memory_maintenance_plan(
            self.db_path,
            plan,
            selected_action_id=action_id,
            actor_id="operator@example",
            confirmed_plan_id=plan["plan_id"],
        )
        self.assertEqual(repeated["status"], "already_applied")
        self.assertNotEqual(repeated["result_id"], result["result_id"])
        self.assertEqual(
            repeated["transitions"][0]["receipt_id"],
            result["transitions"][0]["receipt_id"],
        )
        self.assertEqual(self._event_count(), event_count)

    def test_apply_rolls_back_when_result_construction_fails(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        event_count = self._event_count()

        with patch(
            "zerker_memory.maintenance._maintenance_result",
            side_effect=RuntimeError("result construction failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "result construction failed"):
                apply_memory_maintenance_plan(
                    self.db_path,
                    plan,
                    selected_action_id=plan["selectable_actions"][0]["action_id"],
                    actor_id="operator",
                    confirmed_plan_id=plan["plan_id"],
                )

        self.assertEqual(self.store.get(expired.id).status, "active")
        self.assertEqual(self._event_count(), event_count)

    def test_preview_keeps_expired_memory_without_a_receipt_review_only(self):
        expired = self._remember("Expired unproven memory.", memory_id="mem_expired")
        self._expire(expired.id)
        self.store.conn.execute(
            "DELETE FROM memory_write_receipts WHERE memory_id = ?",
            (expired.id,),
        )
        self.store.conn.commit()

        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)

        self.assertEqual(plan["selectable_actions"], [])
        review = next(
            item
            for item in plan["review_items"]
            if item["reason"] == "expired_memory_requires_verified_provenance"
        )
        self.assertEqual(review["memory_ids"], [expired.id])

    def test_preview_rejects_a_tampered_event_payload(self):
        self._remember("Memory with a receipt.", memory_id="mem_receipted")
        self.store.conn.execute(
            "UPDATE events SET payload_json = ? WHERE seq = 1",
            ('{"tampered":true}',),
        )
        self.store.conn.commit()

        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["error"]["code"], "database_read_failed")
        self.assertIn("event payload hash mismatch", plan["error"]["message"])

    def test_apply_rejects_unverified_existing_receipt_chain(self):
        expired = self._remember("Expired tampered memory.", memory_id="mem_expired")
        self._expire(expired.id)
        row = self.store.conn.execute(
            "SELECT receipt_id, treeship_statement_json FROM memory_write_receipts WHERE memory_id = ?",
            (expired.id,),
        ).fetchone()
        statement = json.loads(row["treeship_statement_json"])
        statement["object"]["scope"] = "tampered"
        self.store.conn.execute(
            "UPDATE memory_write_receipts SET treeship_statement_json = ? WHERE receipt_id = ?",
            (json.dumps(statement, sort_keys=True, separators=(",", ":")), row["receipt_id"]),
        )
        self.store.conn.commit()
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        action_id = plan["selectable_actions"][0]["action_id"]
        event_count = self._event_count()

        with self.assertRaisesRegex(ValueError, "write receipt chain is not verified"):
            apply_memory_maintenance_plan(
                self.db_path,
                plan,
                selected_action_id=action_id,
                actor_id="operator",
                confirmed_plan_id=plan["plan_id"],
            )

        self.assertEqual(self.store.get(expired.id).status, "active")
        self.assertEqual(self._event_count(), event_count)

    def test_idempotent_apply_rechecks_the_full_receipt_chain(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        action_id = plan["selectable_actions"][0]["action_id"]
        apply_memory_maintenance_plan(
            self.db_path,
            plan,
            selected_action_id=action_id,
            actor_id="operator",
            confirmed_plan_id=plan["plan_id"],
        )
        initial_receipt = self.store.memory_write_receipts(expired.id)[0]
        self.store.conn.execute(
            "UPDATE memory_write_receipts SET actor_uri = ? WHERE receipt_id = ?",
            ("actor://tampered", initial_receipt["receipt_id"]),
        )
        self.store.conn.commit()

        with self.assertRaisesRegex(ValueError, "write receipt chain is not verified"):
            apply_memory_maintenance_plan(
                self.db_path,
                plan,
                selected_action_id=action_id,
                actor_id="operator",
                confirmed_plan_id=plan["plan_id"],
            )

    def test_apply_requires_exact_plan_confirmation(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)

        with self.assertRaisesRegex(ValueError, "confirmation mismatch"):
            apply_memory_maintenance_plan(
                self.db_path,
                plan,
                selected_action_id=plan["selectable_actions"][0]["action_id"],
                actor_id="operator",
                confirmed_plan_id="mplan_wrong",
            )
        self.assertEqual(self.store.get(expired.id).status, "active")

    def test_apply_rejects_a_rehashed_non_expiry_action_contract(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        forged = json.loads(json.dumps(plan))
        action = forged["selectable_actions"][0]
        action["expected_transition"] = {"from": "active", "to": "revoked"}
        action_material = dict(action)
        action_material.pop("action_id")
        action_material.pop("action_hash")
        action_digest = maintenance_module._digest(action_material)
        action["action_hash"] = action_digest
        action["action_id"] = f"maint_{action_digest.split(':', 1)[1][:24]}"
        plan_material = dict(forged)
        plan_material.pop("plan_id")
        plan_material.pop("plan_hash")
        forged = maintenance_module._finalize_plan(plan_material)

        with self.assertRaisesRegex(ValueError, "unsupported maintenance action contract"):
            apply_memory_maintenance_plan(
                self.db_path,
                forged,
                selected_action_id=action["action_id"],
                actor_id="operator",
                confirmed_plan_id=forged["plan_id"],
            )

        self.assertEqual(self.store.get(expired.id).status, "active")

    def test_apply_rejects_stale_or_tampered_plan_without_mutation(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        action_id = plan["selectable_actions"][0]["action_id"]
        self._remember("Intervening memory.", memory_id="mem_intervening")
        event_count = self._event_count()

        with self.assertRaisesRegex(ValueError, "maintenance plan is stale"):
            apply_memory_maintenance_plan(
                self.db_path,
                plan,
                selected_action_id=action_id,
                actor_id="operator",
                confirmed_plan_id=plan["plan_id"],
            )

        self.assertEqual(self.store.get(expired.id).status, "active")
        self.assertEqual(self._event_count(), event_count)

        fresh_plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        fresh_plan["selectable_actions"][0]["target_memory_id"] = "mem_intervening"
        with self.assertRaisesRegex(ValueError, "maintenance plan hash mismatch"):
            apply_memory_maintenance_plan(
                self.db_path,
                fresh_plan,
                selected_action_id=fresh_plan["selectable_actions"][0]["action_id"],
                actor_id="operator",
                confirmed_plan_id=fresh_plan["plan_id"],
            )
        self.assertEqual(self._event_count(), event_count)

    def test_apply_checks_target_state_hash_before_writing(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        action_id = plan["selectable_actions"][0]["action_id"]
        self.store.conn.execute(
            "UPDATE memories SET status = 'deprecated' WHERE id = ?",
            (expired.id,),
        )
        self.store.conn.commit()
        event_count = self._event_count()

        with self.assertRaisesRegex(ValueError, "maintenance plan is stale"):
            apply_memory_maintenance_plan(
                self.db_path,
                plan,
                selected_action_id=action_id,
                actor_id="operator",
                confirmed_plan_id=plan["plan_id"],
            )

        self.assertEqual(self.store.get(expired.id).status, "deprecated")
        self.assertEqual(self._event_count(), event_count)

    def test_result_verification_detects_artifact_tampering(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        result = apply_memory_maintenance_plan(
            self.db_path,
            plan,
            selected_action_id=plan["selectable_actions"][0]["action_id"],
            actor_id="operator",
            confirmed_plan_id=plan["plan_id"],
        )

        verification = verify_memory_maintenance_result(self.db_path, result)

        self.assertEqual(verification["schema"], MAINTENANCE_VERIFICATION_SCHEMA)
        self.assertTrue(verification["ok"])
        self.assertEqual(verification["verified_transition_count"], 1)
        self.assertEqual(verification["status"], "verified")

        tampered = json.loads(json.dumps(result))
        tampered["transitions"][0]["receipt_hash"] = "0" * 64
        tampered_verification = verify_memory_maintenance_result(self.db_path, tampered)
        self.assertFalse(tampered_verification["ok"])
        self.assertEqual(tampered_verification["status"], "invalid")
        self.assertIn("result hash mismatch", tampered_verification["error"])

        forged = json.loads(json.dumps(result))
        forged["transitions"][0]["event_hash"] = "0" * 64
        forged["transitions"][0]["merkle_root"] = "1" * 64
        forged = self._rehash_result(forged)
        forged_verification = verify_memory_maintenance_result(self.db_path, forged)
        self.assertFalse(forged_verification["ok"])
        self.assertIn("maintenance transition mismatch", forged_verification["error"])

    def test_result_remains_verifiable_after_current_state_diverges(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        result = apply_memory_maintenance_plan(
            self.db_path,
            plan,
            selected_action_id=plan["selectable_actions"][0]["action_id"],
            actor_id="operator",
            confirmed_plan_id=plan["plan_id"],
        )
        self.store.conn.execute(
            "UPDATE memories SET status = 'deprecated' WHERE id = ?",
            (expired.id,),
        )
        self.store.conn.commit()

        verification = verify_memory_maintenance_result(self.db_path, result)

        self.assertTrue(verification["ok"])
        self.assertEqual(
            verification["status"],
            "verified_historical_with_state_divergence",
        )
        self.assertFalse(verification["state_matches_result"])
        self.assertFalse(verification["state_advanced"])
        self.assertTrue(verification["out_of_band_state_change"])

    def test_later_event_does_not_hide_out_of_band_target_status_change(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        result = apply_memory_maintenance_plan(
            self.db_path,
            plan,
            selected_action_id=plan["selectable_actions"][0]["action_id"],
            actor_id="operator",
            confirmed_plan_id=plan["plan_id"],
        )
        self._remember("Legitimate later memory.", memory_id="mem_later")
        self.store.conn.execute(
            "UPDATE memories SET status = 'deprecated' WHERE id = ?",
            (expired.id,),
        )
        self.store.conn.commit()

        verification = verify_memory_maintenance_result(self.db_path, result)

        self.assertTrue(verification["ok"])
        self.assertTrue(verification["state_advanced"])
        self.assertTrue(verification["out_of_band_state_change"])
        self.assertEqual(
            verification["status"],
            "verified_historical_with_state_divergence",
        )
        self.assertFalse(verification["target_state_checks"][0]["status_matches_event_log"])

    def test_result_verification_rejects_a_tampered_prior_receipt(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        result = apply_memory_maintenance_plan(
            self.db_path,
            plan,
            selected_action_id=plan["selectable_actions"][0]["action_id"],
            actor_id="operator",
            confirmed_plan_id=plan["plan_id"],
        )
        initial_receipt = self.store.memory_write_receipts(expired.id)[0]
        self.store.conn.execute(
            "UPDATE memory_write_receipts SET actor_uri = ? WHERE receipt_id = ?",
            ("actor://tampered", initial_receipt["receipt_id"]),
        )
        self.store.conn.commit()

        verification = verify_memory_maintenance_result(self.db_path, result)

        self.assertFalse(verification["ok"])
        self.assertIn("receipt chain verification failed", verification["error"])

    def test_result_verification_does_not_recreate_a_missing_database(self):
        expired = self._remember("Expired memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        result = apply_memory_maintenance_plan(
            self.db_path,
            plan,
            selected_action_id=plan["selectable_actions"][0]["action_id"],
            actor_id="operator",
            confirmed_plan_id=plan["plan_id"],
        )
        self.store.conn.close()
        self.db_path.unlink()

        verification = verify_memory_maintenance_result(self.db_path, result)

        self.assertFalse(verification["ok"])
        self.assertIn("memory database not found", verification["error"])
        self.assertFalse(self.db_path.exists())

    def test_cli_preview_apply_verify_round_trip(self):
        expired = self._remember("Expired CLI memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan_path = self.root / "plan.json"
        result_path = self.root / "result.json"
        self.store.conn.close()

        preview_output = io.StringIO()
        with redirect_stdout(preview_output):
            preview_exit = main(
                [
                    "--db",
                    str(self.db_path),
                    "maintain",
                    "preview",
                    "--evaluated-at",
                    EVALUATED_AT,
                    "--out",
                    str(plan_path),
                    "--summary-only",
                ]
            )
        self.assertEqual(preview_exit, 0)
        self.assertTrue(plan_path.is_file())
        self.assertIn("No memory changed.", preview_output.getvalue())
        action_id = json.loads(plan_path.read_text(encoding="utf-8"))["selectable_actions"][0]["action_id"]

        apply_output = io.StringIO()
        with redirect_stdout(apply_output):
            apply_exit = main(
                [
                    "--db",
                    str(self.db_path),
                    "maintain",
                    "apply",
                    str(plan_path),
                    "--select",
                    action_id,
                    "--actor-id",
                    "operator",
                    "--confirm-plan",
                    json.loads(plan_path.read_text(encoding="utf-8"))["plan_id"],
                    "--out",
                    str(result_path),
                    "--summary-only",
                ]
            )
        self.assertEqual(apply_exit, 0)
        self.assertTrue(result_path.is_file())
        self.assertIn("Receipts verified: 1/1", apply_output.getvalue())

        verify_output = io.StringIO()
        with redirect_stdout(verify_output):
            verify_exit = main(
                [
                    "--db",
                    str(self.db_path),
                    "maintain",
                    "verify",
                    str(result_path),
                    "--summary-only",
                ]
            )
        self.assertEqual(verify_exit, 0)
        self.assertIn("Verification: passed", verify_output.getvalue())
        self.store = MemoryStore(self.db_path)

    def test_cli_apply_preflights_an_existing_output_before_mutation(self):
        expired = self._remember("Expired CLI memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result_path = self.root / "occupied-result.json"
        result_path.write_text("occupied", encoding="utf-8")
        event_count = self._event_count()

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "--db",
                    str(self.db_path),
                    "maintain",
                    "apply",
                    str(plan_path),
                    "--select",
                    plan["selectable_actions"][0]["action_id"],
                    "--actor-id",
                    "operator",
                    "--confirm-plan",
                    plan["plan_id"],
                    "--out",
                    str(result_path),
                    "--summary-only",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("already exists", output.getvalue())
        self.assertEqual(self.store.get(expired.id).status, "active")
        self.assertEqual(self._event_count(), event_count)

    def test_cli_reports_a_committed_action_when_result_write_fails(self):
        expired = self._remember("Expired CLI memory.", memory_id="mem_expired")
        self._expire(expired.id)
        plan = build_memory_maintenance_plan(self.db_path, evaluated_at=EVALUATED_AT)
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        output = io.StringIO()
        with patch(
            "zerker_memory.maintenance.write_json_artifact",
            side_effect=OSError("disk unavailable"),
        ), redirect_stdout(output):
            exit_code = main(
                [
                    "--db",
                    str(self.db_path),
                    "maintain",
                    "apply",
                    str(plan_path),
                    "--select",
                    plan["selectable_actions"][0]["action_id"],
                    "--actor-id",
                    "operator",
                    "--confirm-plan",
                    plan["plan_id"],
                    "--summary-only",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("Result file: not written", output.getvalue())
        self.assertIn("Database transition: committed", output.getvalue())
        self.assertIn("apply is idempotent", output.getvalue())
        self.assertEqual(self.store.get(expired.id).status, "expired")

    def _remember(
        self,
        content: str,
        *,
        memory_id: str,
        parents: list[str] | None = None,
    ):
        return self.store.remember(
            content,
            memory_type="semantic",
            scope="project",
            source_kind="human",
            status="active",
            parents=parents,
            memory_id=memory_id,
            created_at="2024-01-01T00:00:00Z",
        )

    def _expire(self, memory_id: str) -> None:
        self.store.conn.execute(
            "UPDATE memories SET expires_at = ? WHERE id = ?",
            ("2024-12-01T00:00:00Z", memory_id),
        )
        self.store.conn.commit()

    def _event_count(self) -> int:
        return int(self.store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def _rehash_result(self, result: dict) -> dict:
        material = json.loads(json.dumps(result))
        material.pop("result_id", None)
        material.pop("result_hash", None)
        result_hash = maintenance_module._digest(material)
        material["result_id"] = maintenance_module._maintenance_result_id(result_hash)
        material["result_hash"] = result_hash
        return material

    def _database_bytes(self) -> dict[str, bytes]:
        result = {}
        for path in sorted(self.root.iterdir()):
            if path.is_file():
                result[path.name] = path.read_bytes()
        return result


if __name__ == "__main__":
    unittest.main()

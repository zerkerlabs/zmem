import unittest
import tempfile
from dataclasses import dataclass
from pathlib import Path

from zerker_memory.policy import PolicyConfig, decide_memory, load_policy_config


@dataclass(frozen=True)
class FakeMemory:
    id: str = "mem_1"
    type: str = "semantic"
    source_kind: str = "human"
    trust: float = 0.95
    authority: str = "medium"
    status: str = "active"
    labels: list[str] = None

    def __post_init__(self):
        if self.labels is None:
            object.__setattr__(self, "labels", [])


class PolicyTest(unittest.TestCase):
    def test_withholds_inactive_memory(self):
        decision = decide_memory(FakeMemory(status="quarantined"), risk="low")
        self.assertEqual(decision.decision, "withhold")
        self.assertEqual(decision.rule, "active-status-required")

    def test_withholds_policy_below_risk_authority(self):
        decision = decide_memory(FakeMemory(type="policy", authority="medium"), risk="high")
        self.assertEqual(decision.decision, "withhold")
        self.assertEqual(decision.rule, "policy-authority-threshold")

    def test_withholds_low_trust_high_risk_memory(self):
        decision = decide_memory(FakeMemory(type="semantic", trust=0.7, authority="high"), risk="high")
        self.assertEqual(decision.decision, "withhold")
        self.assertEqual(decision.rule, "trust-threshold")

    def test_authorizes_active_trusted_memory(self):
        decision = decide_memory(FakeMemory(type="policy", authority="policy"), risk="high")
        self.assertEqual(decision.decision, "inject")

    def test_config_can_raise_high_risk_trust_threshold(self):
        config = PolicyConfig.from_dict(
            {
                "schema": "zerker.policy.v1",
                "risk_thresholds": {"high": {"min_trust": 0.99, "min_policy_authority": "policy"}},
            }
        )
        decision = decide_memory(FakeMemory(type="policy", authority="policy", trust=0.95), risk="high", config=config)
        self.assertEqual(decision.decision, "withhold")
        self.assertEqual(decision.rule, "trust-threshold")

    def test_config_can_deny_labels(self):
        config = PolicyConfig.from_dict({"schema": "zerker.policy.v1", "deny_labels": ["secret"]})
        decision = decide_memory(FakeMemory(labels=["secret"]), risk="low", config=config)
        self.assertEqual(decision.decision, "withhold")
        self.assertEqual(decision.rule, "deny-label")

    def test_load_policy_config_from_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text('{"schema":"zerker.policy.v1","deny_labels":["secret"]}', encoding="utf-8")
            config = load_policy_config(path)

        self.assertEqual(config.deny_labels, ["secret"])

    def test_policy_config_has_canonical_round_trip_shape(self):
        config = PolicyConfig.from_dict(
            {
                "schema": "zerker.policy.v1",
                "risk_thresholds": {"high": {"min_trust": 0.95}},
                "deny_labels": ["secret"],
            }
        )

        self.assertEqual(PolicyConfig.from_dict(config.to_dict()), config)
        self.assertEqual(list(config.to_dict()["risk_thresholds"]), ["low", "medium", "high"])


if __name__ == "__main__":
    unittest.main()

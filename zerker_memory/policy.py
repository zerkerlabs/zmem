from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


AUTHORITY_ORDER = ["none", "low", "medium", "high", "policy"]
POLICY_ENGINE = "zerker.symbolic_policy.v1"
POLICY_CONFIG_SCHEMA = "zerker.policy.v1"


class MemoryLike(Protocol):
    id: str
    type: str
    source_kind: str
    trust: float
    authority: str
    status: str
    labels: list[str]


@dataclass(frozen=True)
class PolicyDecision:
    memory_id: str
    decision: str
    reason: str
    rule: str

    def to_dict(self) -> dict[str, str]:
        return {
            "memory_id": self.memory_id,
            "decision": self.decision,
            "reason": self.reason,
            "rule": self.rule,
        }


@dataclass(frozen=True)
class PolicyConfig:
    min_trust_by_risk: dict[str, float]
    min_policy_authority_by_risk: dict[str, str]
    deny_labels: list[str]

    @classmethod
    def defaults(cls) -> "PolicyConfig":
        return cls(
            min_trust_by_risk={"low": 0.0, "medium": 0.6, "high": 0.8},
            min_policy_authority_by_risk={"low": "low", "medium": "medium", "high": "high"},
            deny_labels=[],
        )

    @classmethod
    def from_dict(cls, value: dict) -> "PolicyConfig":
        if value.get("schema", POLICY_CONFIG_SCHEMA) != POLICY_CONFIG_SCHEMA:
            raise ValueError("unsupported policy config schema")
        defaults = cls.defaults()
        risk_thresholds = value.get("risk_thresholds", {})
        min_trust = dict(defaults.min_trust_by_risk)
        min_authority = dict(defaults.min_policy_authority_by_risk)
        for risk, threshold in risk_thresholds.items():
            if risk not in min_trust:
                raise ValueError(f"unsupported risk in policy config: {risk}")
            if "min_trust" in threshold:
                min_trust[risk] = float(threshold["min_trust"])
            if "min_policy_authority" in threshold:
                authority = threshold["min_policy_authority"]
                if authority not in AUTHORITY_ORDER:
                    raise ValueError(f"unsupported authority in policy config: {authority}")
                min_authority[risk] = authority
        deny_labels = [str(label) for label in value.get("deny_labels", [])]
        return cls(min_trust_by_risk=min_trust, min_policy_authority_by_risk=min_authority, deny_labels=deny_labels)


def load_policy_config(path: Path | None) -> PolicyConfig:
    if path is None or not path.exists():
        return PolicyConfig.defaults()
    return PolicyConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))


def decide_memory(memory: MemoryLike, *, risk: str, config: PolicyConfig | None = None) -> PolicyDecision:
    config = config or PolicyConfig.defaults()
    if memory.status != "active":
        return PolicyDecision(memory.id, "withhold", f"status={memory.status}", "active-status-required")
    denied = sorted(set(memory.labels).intersection(config.deny_labels))
    if denied:
        return PolicyDecision(memory.id, "withhold", f"denied label: {denied[0]}", "deny-label")
    if memory.type == "policy" and not authority_at_least(memory.authority, min_authority_for_risk(risk, config=config)):
        return PolicyDecision(
            memory.id,
            "withhold",
            f"authority={memory.authority} below {min_authority_for_risk(risk, config=config)}",
            "policy-authority-threshold",
        )
    if memory.trust < min_trust_for_risk(risk, config=config):
        return PolicyDecision(
            memory.id,
            "withhold",
            f"trust={memory.trust:.2f} below {min_trust_for_risk(risk, config=config):.2f}",
            "trust-threshold",
        )
    return PolicyDecision(memory.id, "inject", "authorized", "authorized-memory")


def min_authority_for_risk(risk: str, *, config: PolicyConfig | None = None) -> str:
    config = config or PolicyConfig.defaults()
    return config.min_policy_authority_by_risk.get(risk, "high")


def min_trust_for_risk(risk: str, *, config: PolicyConfig | None = None) -> float:
    config = config or PolicyConfig.defaults()
    return config.min_trust_by_risk.get(risk, 1.0)


def authority_at_least(value: str, minimum: str) -> bool:
    return AUTHORITY_ORDER.index(value) >= AUTHORITY_ORDER.index(minimum)


def max_authority(left: str, right: str) -> str:
    return AUTHORITY_ORDER[max(AUTHORITY_ORDER.index(left), AUTHORITY_ORDER.index(right))]

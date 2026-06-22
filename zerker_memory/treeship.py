from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from zerker_memory import __version__
from zerker_memory.store import BUNDLE_SCHEMA, HASH_ALG, MERKLE_ALG, merkle_root, sha256_text, stable_json


TREESHIP_STATEMENT_SCHEMA = "com.zerker.memory.treeship.statement"
TREESHIP_STATEMENT_SCHEMA_VERSION = "0.1.0"
TREESHIP_STATEMENT_KIND = "zerker.memory.action_receipt"
DEFAULT_TREESHIP_COMMAND_TEMPLATE = "treeship attest receipt --system system://zmem --kind memory.proof --payload-file {statement}"


_FIELD_ALIASES = {
    "receipt_schema": ("receipt_schema", "receiptSchema"),
    "hash_alg": ("hash_alg", "hashAlg"),
    "merkle_alg": ("merkle_alg", "merkleAlg"),
    "action_id": ("action_id", "actionId"),
    "agent_id": ("agent_id", "agentId"),
    "task_hash": ("task_hash", "taskHash"),
    "retrieved_memory_ids": ("retrieved_memory_ids", "retrievedMemoryIds"),
    "injected_memory_ids": ("injected_memory_ids", "injectedMemoryIds"),
    "withheld_memory_ids": ("withheld_memory_ids", "withheldMemoryIds"),
    "policy_checks": ("policy_checks", "policyChecks"),
    "merkle_root": ("merkle_root", "merkleRoot"),
    "created_at": ("created_at", "createdAt"),
    "signature": ("signature",),
}


def to_treeship_statement(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a Zerker Memory proof artifact into a Treeship-ready statement.

    Accepts either a raw receipt or a verifiable receipt bundle. When given a
    bundle, the statement carries bundle-level proof metadata and rejects
    tampered inputs before shaping them for Treeship.
    """

    receipt_payload = _bundle_receipt(receipt) if _is_bundle(receipt) else receipt
    normalized = _normalize_receipt(receipt_payload)
    action_id = _required(normalized, "action_id")
    agent_id = _required(normalized, "agent_id")
    task_hash = _required(normalized, "task_hash")
    merkle_root = _required(normalized, "merkle_root")
    created_at = _required(normalized, "created_at")

    evidence: dict[str, Any] = {
        "task_hash": task_hash,
        "merkle_root": merkle_root,
        "hash_alg": normalized.get("hash_alg") or "sha256",
        "merkle_alg": normalized.get("merkle_alg") or "binary-sha256-v1",
    }
    source: dict[str, Any] = {
        "system": "zerker-memory",
        "receipt_type": "MemoryActionReceipt",
        "receipt": normalized,
    }
    if _is_bundle(receipt):
        bundle = dict(receipt)
        proof = dict(bundle.get("proof", {}))
        evidence.update(
            {
                "bundle_hash": _required_str(bundle, "bundle_hash"),
                "bundle_event_count": int(proof.get("event_count", 0)),
                "bundle_verified": bool(proof.get("verified")),
            }
        )
        source["bundle"] = bundle
    if normalized.get("signature") is not None:
        evidence["signature"] = normalized["signature"]

    return {
        "schema": TREESHIP_STATEMENT_SCHEMA,
        "schema_version": TREESHIP_STATEMENT_SCHEMA_VERSION,
        "statement_version": "1",
        "kind": TREESHIP_STATEMENT_KIND,
        "producer": {
            "name": "zerker-memory",
            "version": __version__,
        },
        "subject": {
            "type": "memory_action",
            "id": action_id,
            "agent_id": agent_id,
        },
        "predicate": "memory.receipt.generated",
        "object": {
            "task_hash": task_hash,
            "retrieved_memory_ids": normalized["retrieved_memory_ids"],
            "injected_memory_ids": normalized["injected_memory_ids"],
            "withheld_memory_ids": normalized["withheld_memory_ids"],
            "policy_checks": normalized["policy_checks"],
        },
        "evidence": evidence,
        "source": source,
        "created_at": created_at,
    }


def treeship_cli_status(command_template: str | None = None) -> dict[str, Any]:
    template = _command_template(command_template)
    argv = build_treeship_publish_command(
        Path("/tmp/zerker-memory.statement.json"),
        command_template=template,
    )
    executable = shutil.which(argv[0])
    return {
        "ok": executable is not None,
        "command_template": template,
        "command_preview": argv,
        "executable": argv[0],
        "resolved_executable": executable,
        "statement_placeholder": "{statement}" in template,
        "action_placeholder": "{action_id}" in template,
    }


def build_treeship_publish_command(
    statement_path: Path,
    *,
    action_id: str | None = None,
    command_template: str | None = None,
) -> list[str]:
    template = _command_template(command_template)
    rendered = template.format(statement=str(statement_path), action_id=action_id or "")
    argv = shlex.split(rendered)
    if not argv:
        raise ValueError("Treeship command template produced an empty command")
    if "{statement}" not in template:
        argv.append(str(statement_path))
    return argv


def publish_treeship_statement(
    statement_path: Path,
    *,
    action_id: str | None = None,
    command_template: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    argv = build_treeship_publish_command(
        statement_path,
        action_id=action_id,
        command_template=command_template,
    )
    executable = shutil.which(argv[0])
    if executable is None:
        raise ValueError(f"Treeship CLI not found: {argv[0]}")
    result = {
        "ok": True,
        "statement_path": str(statement_path),
        "action_id": action_id,
        "command": argv,
        "resolved_executable": executable,
        "dry_run": dry_run,
    }
    if dry_run:
        return result

    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    fallback_argv: list[str] | None = None
    fallback_completed = None
    if _needs_payload_inline_fallback(completed.stderr):
        fallback_argv = _inline_payload_fallback_command(argv, statement_path)
        if fallback_argv is not None:
            fallback_completed = subprocess.run(fallback_argv, capture_output=True, text=True, check=False)
            completed = fallback_completed
    result.update(
        {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    if fallback_argv is not None:
        result["fallback"] = {
            "reason": "treeship_cli_missing_payload_file",
            "command": _redact_inline_payload(fallback_argv),
            "exit_code": fallback_completed.returncode if fallback_completed is not None else None,
        }
    return result


def _needs_payload_inline_fallback(stderr: str) -> bool:
    return "unexpected argument '--payload-file'" in stderr


def _inline_payload_fallback_command(argv: list[str], statement_path: Path) -> list[str] | None:
    try:
        idx = argv.index("--payload-file")
    except ValueError:
        return None
    if idx + 1 >= len(argv) or argv[idx + 1] != str(statement_path):
        return None
    payload = statement_path.read_text(encoding="utf-8")
    return [*argv[:idx], "--payload", payload, *argv[idx + 2 :]]


def _redact_inline_payload(argv: list[str]) -> list[str]:
    redacted = list(argv)
    try:
        idx = redacted.index("--payload")
    except ValueError:
        return redacted
    if idx + 1 < len(redacted):
        redacted[idx + 1] = "<inline-json-redacted>"
    return redacted


def _is_bundle(value: Mapping[str, Any]) -> bool:
    return "bundle_schema" in value or "receipt" in value and "supporting_events" in value


def _bundle_receipt(bundle: Mapping[str, Any]) -> Mapping[str, Any]:
    _validate_bundle(bundle)
    receipt = bundle.get("receipt")
    if not isinstance(receipt, Mapping):
        raise ValueError("bundle missing receipt")
    return receipt


def _validate_bundle(bundle: Mapping[str, Any]) -> None:
    if bundle.get("bundle_schema") != BUNDLE_SCHEMA:
        raise ValueError("unsupported bundle schema")
    if bundle.get("hash_alg") != HASH_ALG:
        raise ValueError("unsupported bundle hash algorithm")
    if bundle.get("merkle_alg") != MERKLE_ALG:
        raise ValueError("unsupported bundle merkle algorithm")
    bundle_hash = _required_str(bundle, "bundle_hash")
    without_hash = dict(bundle)
    without_hash.pop("bundle_hash", None)
    if sha256_text(stable_json(without_hash)) != bundle_hash:
        raise ValueError("bundle_hash mismatch")
    receipt = bundle.get("receipt")
    if not isinstance(receipt, Mapping):
        raise ValueError("bundle missing receipt")
    if bundle.get("action_id") != receipt.get("action_id"):
        raise ValueError("bundle action_id mismatch")
    events = bundle.get("supporting_events")
    if not isinstance(events, list):
        raise ValueError("bundle supporting_events must be a list")
    computed_merkle_root = merkle_root([str(event.get("event_hash", "")) for event in events if isinstance(event, Mapping)])
    if computed_merkle_root != receipt.get("merkle_root"):
        raise ValueError("bundle merkle_root mismatch")
    proof = bundle.get("proof")
    if not isinstance(proof, Mapping):
        raise ValueError("bundle missing proof")
    if proof.get("computed_merkle_root") != computed_merkle_root:
        raise ValueError("bundle proof computed_merkle_root mismatch")
    if proof.get("receipt_merkle_root") != receipt.get("merkle_root"):
        raise ValueError("bundle proof receipt_merkle_root mismatch")
    if proof.get("event_count") != len(events):
        raise ValueError("bundle proof event_count mismatch")
    if proof.get("verified") is not True:
        raise ValueError("bundle proof is not verified")


def _normalize_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for canonical, aliases in _FIELD_ALIASES.items():
        value = _first_present(receipt, aliases)
        if canonical.endswith("_ids") or canonical == "policy_checks":
            normalized[canonical] = _string_list(value)
        else:
            normalized[canonical] = value
    return normalized


def _first_present(receipt: Mapping[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in receipt:
            return receipt[alias]
    return None


def _required(receipt: Mapping[str, Any], key: str) -> str:
    value = receipt.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"receipt missing required field: {key}")
    return value


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"bundle missing required field: {key}")
    return value


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("receipt list fields must be lists")
    return [str(item) for item in value]


def _command_template(command_template: str | None) -> str:
    template = (command_template or DEFAULT_TREESHIP_COMMAND_TEMPLATE).strip()
    if not template:
        raise ValueError("Treeship command template must not be empty")
    return template

from __future__ import annotations

import shlex
import shutil
import subprocess
import json
from pathlib import Path
from typing import Any, Mapping

from zerker_memory import __version__
from zerker_memory.store import (
    WRITE_RECEIPT_SCHEMA,
    LIFECYCLE_RECEIPT_SCHEMA,
    sha256_text,
    stable_json,
    validate_receipt_bundle_core,
)


TREESHIP_STATEMENT_SCHEMA = "com.zerker.memory.treeship.statement"
TREESHIP_STATEMENT_SCHEMA_VERSION = "0.1.0"
TREESHIP_STATEMENT_KIND = "zerker.memory.action_receipt"
DEFAULT_TREESHIP_COMMAND_TEMPLATE = "treeship attest receipt --system system://zmem --kind memory.proof --payload-file {statement}"
DEFAULT_TREESHIP_RECEIPT_COMMAND = "treeship"


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

    if _has_embedded_write_statement(receipt):
        return _embedded_write_statement(receipt)
    if _has_embedded_lifecycle_statement(receipt):
        return _embedded_lifecycle_statement(receipt)

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
        supporting_provenance = _bundle_supporting_provenance_summary(bundle)
        evidence.update(
            {
                "bundle_hash": _required_str(bundle, "bundle_hash"),
                "bundle_event_count": int(proof.get("event_count", 0)),
                "bundle_event_witness_count": int(proof.get("event_witness_count", 0)),
                "bundle_verified": bool(proof.get("verified")),
                "supporting_write_receipt_count": supporting_provenance["supporting_write_receipt_count"],
                "verified_supporting_write_receipt_count": supporting_provenance[
                    "verified_supporting_write_receipt_count"
                ],
                "trusted_provenance_verified": supporting_provenance["trusted_provenance_verified"],
            }
        )
        source["bundle"] = bundle
        source["supporting_provenance_receipts"] = supporting_provenance["supporting_provenance_receipts"]
        if supporting_provenance["attestation_artifacts"]:
            source["attestation_artifacts"] = supporting_provenance["attestation_artifacts"]
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
            "semantic_truth_guaranteed": False,
        },
        "evidence": evidence,
        "source": source,
        "created_at": created_at,
    }


def _has_embedded_lifecycle_statement(receipt: Mapping[str, Any]) -> bool:
    return (
        isinstance(receipt, Mapping)
        and receipt.get("receipt_schema") == LIFECYCLE_RECEIPT_SCHEMA
        and isinstance(receipt.get("treeship_statement"), Mapping)
    )


def _has_embedded_write_statement(receipt: Mapping[str, Any]) -> bool:
    return (
        isinstance(receipt, Mapping)
        and receipt.get("receipt_schema") == WRITE_RECEIPT_SCHEMA
        and isinstance(receipt.get("treeship_statement"), Mapping)
    )


def _embedded_write_statement(receipt: Mapping[str, Any]) -> dict[str, Any]:
    statement = receipt.get("treeship_statement")
    if not isinstance(statement, Mapping):
        raise ValueError("write receipt missing treeship_statement")

    from .store import MemoryStore

    verifier = MemoryStore(Path("/tmp/zerker-memory-write-receipt-export-verifier.sqlite"))
    verification = verifier.verify_memory_write_receipt(dict(receipt), prior_receipt=_write_receipt_prior_stub(receipt))
    if not verification["ok"]:
        raise ValueError(
            "write receipt "
            f"{receipt.get('receipt_id') or receipt.get('memory_id') or 'unknown'} verification failed: {verification['error']}"
        )
    exported_statement = json.loads(json.dumps(statement))
    statement_object = exported_statement.get("object")
    if isinstance(statement_object, dict) and "semantic_truth_guaranteed" not in statement_object:
        statement_object["semantic_truth_guaranteed"] = False
    return exported_statement


def _write_receipt_prior_stub(receipt: Mapping[str, Any]) -> dict[str, Any] | None:
    statement = receipt.get("treeship_statement")
    if not isinstance(statement, Mapping):
        return None
    source = statement.get("source")
    evidence = statement.get("evidence")
    if not isinstance(source, Mapping) or not isinstance(evidence, Mapping):
        return None
    prior_receipt_id = source.get("prior_receipt_id")
    prior_receipt_hash = source.get("prior_receipt_hash")
    if prior_receipt_id is None and prior_receipt_hash is None:
        return None
    return {
        "memory_id": receipt.get("memory_id"),
        "receipt_id": prior_receipt_id,
        "receipt_hash": prior_receipt_hash,
        "merkle_root": evidence.get("prior_merkle_root"),
        "status": statement.get("object", {}).get("previous_status"),
    }


def _embedded_lifecycle_statement(receipt: Mapping[str, Any]) -> dict[str, Any]:
    statement = receipt.get("treeship_statement")
    if not isinstance(statement, Mapping):
        raise ValueError("lifecycle receipt missing treeship_statement")
    if not isinstance(receipt.get("receipt_hash"), str) or not str(receipt.get("receipt_hash")):
        raise ValueError("lifecycle receipt missing receipt_hash")
    if statement.get("created_at") != receipt.get("created_at"):
        raise ValueError("lifecycle treeship created_at mismatch")
    statement_source = statement.get("source")
    if not isinstance(statement_source, Mapping):
        raise ValueError("lifecycle receipt missing treeship source")
    if statement_source.get("system") != "zerker-memory":
        raise ValueError("lifecycle treeship source system mismatch")
    statement_object = statement.get("object")
    if isinstance(statement_object, Mapping) and statement_object.get("semantic_truth_guaranteed") is True:
        raise ValueError("lifecycle semantic_truth_guaranteed must be false")
    if statement_source.get("receipt") != _embedded_lifecycle_source_receipt(receipt):
        raise ValueError("lifecycle treeship source receipt mismatch")
    if _embedded_lifecycle_receipt_hash(receipt) != receipt.get("receipt_hash"):
        raise ValueError("lifecycle receipt_hash mismatch")
    statement_evidence = statement.get("evidence")
    if isinstance(statement_evidence, Mapping) and statement_evidence.get("new_merkle_root") != receipt.get("merkle_root"):
        raise ValueError("lifecycle treeship new_merkle_root mismatch")
    if statement_source.get("treeship_artifact_id") != receipt.get("treeship_artifact_id"):
        raise ValueError("lifecycle treeship artifact mismatch")
    return json.loads(json.dumps(statement))


def _embedded_lifecycle_source_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    source_receipt = dict(receipt)
    source_receipt.pop("treeship_statement", None)
    source_receipt.pop("receipt_hash", None)
    return source_receipt


def _embedded_lifecycle_receipt_hash(receipt: Mapping[str, Any]) -> str:
    receipt_without_hash = dict(receipt)
    receipt_without_hash.pop("receipt_hash", None)
    return sha256_text(stable_json(receipt_without_hash))


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


def attest_treeship_payload_digest(
    payload_digest: str,
    *,
    system_uri: str = "system://zmem",
    kind: str = "memory.write",
    subject: str | None = None,
    config_path: Path | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    """Ask Treeship to sign a compact digest-backed receipt.

    This intentionally sends only a digest to Treeship. ZMem keeps the raw
    memory/provenance receipt locally, and the Treeship artifact binds to the
    receipt hash without duplicating private memory payloads into another store.
    """

    executable_name = command or DEFAULT_TREESHIP_RECEIPT_COMMAND
    executable = shutil.which(executable_name)
    result: dict[str, Any] = {
        "schema": "zerker.memory.treeship_attestation.v1",
        "system": system_uri,
        "kind": kind,
        "payload_digest": payload_digest,
        "subject": subject,
        "command": executable_name,
        "resolved_executable": executable,
        "status": "unavailable" if executable is None else "pending",
        "artifact_id": None,
        "signed_at": None,
        "raw": None,
    }
    if executable is None:
        result["error"] = f"Treeship CLI not found: {executable_name}"
        return result

    argv = [
        executable_name,
        "attest",
        "receipt",
        "--system",
        system_uri,
        "--kind",
        kind,
        "--payload-digest",
        payload_digest,
        "--format",
        "json",
    ]
    if config_path is not None:
        argv[3:3] = ["--config", str(config_path)]
    if subject:
        argv.extend(["--subject", subject])
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    result.update(
        {
            "command_argv": argv,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    if completed.returncode != 0:
        result["status"] = "failed"
        result["error"] = completed.stderr.strip() or completed.stdout.strip() or "Treeship attestation failed"
        return result

    payload: dict[str, Any] = {}
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        payload = {"stdout": completed.stdout}
    result["raw"] = payload
    result["status"] = "signed" if payload.get("status") in {None, "ok"} else str(payload.get("status"))
    result["artifact_id"] = payload.get("id") or payload.get("artifact_id")
    result["signed_at"] = payload.get("signed") or payload.get("signed_at")
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
    return "bundle_schema" in value or "receipt" in value and (
        "supporting_events" in value or "event_witnesses" in value
    )


def _bundle_receipt(bundle: Mapping[str, Any]) -> Mapping[str, Any]:
    _validate_bundle(bundle)
    receipt = bundle.get("receipt")
    if not isinstance(receipt, Mapping):
        raise ValueError("bundle missing receipt")
    return receipt


def _validate_bundle(bundle: Mapping[str, Any]) -> None:
    validate_receipt_bundle_core(bundle)

def _bundle_supporting_provenance_summary(bundle: Mapping[str, Any]) -> dict[str, Any]:
    supporting_memory_ids = bundle.get("supporting_memory_ids")
    if not isinstance(supporting_memory_ids, list):
        raise ValueError("bundle supporting_memory_ids is invalid")

    supporting_receipts = bundle.get("supporting_memory_write_receipts")
    if supporting_receipts is None:
        supporting_receipts = {}
    if not isinstance(supporting_receipts, Mapping):
        raise ValueError("bundle supporting_memory_write_receipts is invalid")

    from .store import MemoryStore

    verifier = MemoryStore(Path("/tmp/zerker-memory-write-receipt-verifier.sqlite"))
    result = {
        "supporting_write_receipt_count": len(supporting_receipts),
        "verified_supporting_write_receipt_count": 0,
        "trusted_provenance_verified": True,
        "supporting_provenance_receipts": [],
        "attestation_artifacts": [],
    }
    for memory_id in sorted(supporting_receipts):
        if memory_id not in supporting_memory_ids:
            raise ValueError("bundle supporting write receipt key missing from supporting_memory_ids")
        supporting_receipt = supporting_receipts[memory_id]
        if not isinstance(supporting_receipt, Mapping):
            raise ValueError(f"bundle supporting write receipt for {memory_id} is invalid")
        if supporting_receipt.get("memory_id") != memory_id:
            raise ValueError("bundle supporting write receipt memory_id mismatch")
        verification = verifier.verify_memory_write_receipt(dict(supporting_receipt))
        if not verification["ok"]:
            raise ValueError(
                "supporting write receipt "
                f"{supporting_receipt.get('receipt_id') or memory_id} verification failed: {verification['error']}"
            )

        result["verified_supporting_write_receipt_count"] += 1
        treeship_statement = supporting_receipt.get("treeship_statement") or {}
        statement_object = treeship_statement.get("object") or {}
        statement_evidence = treeship_statement.get("evidence") or {}
        attestation = supporting_receipt.get("treeship_attestation")
        result["supporting_provenance_receipts"].append(
            {
                "memory_id": supporting_receipt.get("memory_id"),
                "receipt_id": supporting_receipt.get("receipt_id"),
                "receipt_hash": supporting_receipt.get("receipt_hash"),
                "actor_id": statement_object.get("actor_id"),
                "actor_uri": supporting_receipt.get("actor_uri"),
                "content_digest": supporting_receipt.get("content_digest"),
                "prior_merkle_root": statement_evidence.get("prior_merkle_root"),
                "merkle_root": supporting_receipt.get("merkle_root"),
                "new_merkle_root": statement_evidence.get("new_merkle_root", supporting_receipt.get("merkle_root")),
                "treeship_artifact_id": attestation.get("artifact_id") if isinstance(attestation, Mapping) else None,
                "trusted_provenance_verified": True,
                "semantic_truth_guaranteed": False,
            }
        )
        if isinstance(attestation, Mapping):
            result["attestation_artifacts"].append(
                {
                    "memory_id": supporting_receipt.get("memory_id"),
                    "receipt_id": supporting_receipt.get("receipt_id"),
                    "artifact_id": attestation.get("artifact_id"),
                    "status": attestation.get("status"),
                    "signed_at": attestation.get("signed_at"),
                }
            )
    supporting_memories = bundle.get("supporting_memories")
    if supporting_memories is None:
        supporting_memories = []
    if not isinstance(supporting_memories, list):
        raise ValueError("bundle supporting_memories is invalid")
    seen_supporting_memory_ids: set[str] = set()
    for memory in supporting_memories:
        if not isinstance(memory, Mapping):
            raise ValueError("bundle supporting memory entry is invalid")
        memory_id = memory.get("id")
        if not isinstance(memory_id, str) or not memory_id:
            raise ValueError("bundle supporting memory id is invalid")
        if memory_id not in supporting_memory_ids:
            raise ValueError("bundle supporting memory id missing from supporting_memory_ids")
        if memory_id in seen_supporting_memory_ids:
            raise ValueError("bundle supporting memory id is duplicated")
        seen_supporting_memory_ids.add(memory_id)
    result["trusted_provenance_verified"] = (
        result["verified_supporting_write_receipt_count"] == result["supporting_write_receipt_count"]
    )
    return result


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

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .paths import expand_user_path
from .policy import POLICY_ENGINE, authority_at_least, decide_memory, load_policy_config, max_authority
from .retrieval_providers import (
    embed_texts,
    resolve_embedding_provider,
    resolve_reranker_provider,
    rerank_texts,
    retrieval_provider_config_hash,
)


MEMORY_TYPES = {"episodic", "semantic", "procedural", "policy"}
INSTRUCTION_MEMORY_TYPES = ("policy", "procedural")
RECALL_MEMORY_TYPES = ("episodic", "semantic")
AUTHORITIES = {"none", "low", "medium", "high", "policy"}
STATUSES = {"proposed", "quarantined", "active", "deprecated", "revoked", "forgotten"}
HASH_ALG = "sha256"
MERKLE_ALG = "binary-sha256-v1"
RECEIPT_SCHEMA = "zerker.memory_action.v1"
WRITE_RECEIPT_SCHEMA = "zerker.memory_write.v1"
LIFECYCLE_RECEIPT_SCHEMA = "zerker.lifecycle_receipt.v1"
EVENT_SCHEMA = "zerker.memory_event.v1"
SNAPSHOT_SCHEMA = "zerker.memory_snapshot.v1"
SESSION_START_SCHEMA = "zerker.session_start.v1"
SESSION_END_SCHEMA = "zerker.session_end.v1"
SESSION_CHECKPOINT_SCHEMA = "zerker.session_checkpoint.v1"
SESSION_SNAPSHOT_SCHEMA = "zerker.session_snapshot.v1"
SESSION_SNAPSHOT_RETENTION_SCHEMA = "zerker.session_snapshot_retention.v1"
BUNDLE_SCHEMA_V1 = "zerker.receipt_bundle.v1"
BUNDLE_SCHEMA_V2 = "zerker.receipt_bundle.v2"
BUNDLE_SCHEMA = BUNDLE_SCHEMA_V2
BUNDLE_SCHEMAS = frozenset({BUNDLE_SCHEMA_V1, BUNDLE_SCHEMA_V2})
MEMORY_TREE_SCHEMA = "zerker.memory_tree.v1"
RETRIEVAL_SCHEMA = "zerker.retrieval.v1"
RETRIEVAL_RANK_CONFIG_SCHEMA = "zerker.retrieval_rank_config.v1"
CONTEXT_PACKING_SCHEMA = "zerker.context_packing.v1"
TEMPORAL_RESOLUTION_SCHEMA = "zerker.temporal_resolution.v1"
TEMPORAL_QUERY_SCHEMA = "zerker.temporal_query.v1"
QUERY_LOOKUP_SCHEMA = "zerker.query_lookup.v1"
EMBEDDING_RETRIEVAL_SCHEMA = "zerker.embedding_retrieval.v1"
RERANKER_SCHEMA = "zerker.reranker.v1"
MULTI_HOP_DECOMPOSITION_SCHEMA = "zerker.multi_hop_decomposition.v1"
SEMANTIC_RESCUE_SCHEMA = "zerker.semantic_rescue.v1"
HYBRID_RETRIEVAL_SCHEMA = "zerker.hybrid_retrieval.v1"
SUPPORT_EXPANSION_SCHEMA = "zerker.support_expansion.v1"
CONTEXT_TOKEN_APPROXIMATION = "chars_div_4_ceil"
DEFAULT_ENVIRONMENT_HASH_INPUT = "zmem-local-environment-v1"
RETRIEVAL_CANDIDATE_LIMIT = 20
FTS_CANDIDATE_WINDOW_MULTIPLIER = 4
PSEUDO_EMBEDDING_MODEL_ID = "zmem-pseudo-embedding-v1"
DECLARATIVE_SEMANTIC_RESCUE_PROFILE = "declarative_subject_v1"
DECLARATIVE_CURRENT_SEMANTIC_RESCUE_PROFILE = "declarative_current_subject_v1"
DECLARATIVE_HISTORY_SEMANTIC_RESCUE_PROFILE = "declarative_history_subject_v1"
DECLARATIVE_EARLIEST_HISTORY_SEMANTIC_RESCUE_PROFILE = "declarative_earliest_history_subject_v1"
DECLARATIVE_SEMANTIC_RESCUE_MIN_SCORE = 0.6
HYBRID_SEMANTIC_BACKFILL_MIN_SCORE = 0.75
HYBRID_SEMANTIC_BACKFILL_MIN_MARGIN = 0.05
RANK_FUSION_SCHEMA = "zerker.rank_fusion.v1"
RRF_K = 60
DETERMINISTIC_RERANKER_ID = "zmem-deterministic-rerank-v1"
MULTI_HOP_DECOMPOSER_ID = "zmem-local-query-decomposer-v1"
MULTI_HOP_STRATEGY = "local_query_decomposition_v1"
MULTI_HOP_MAX_SUBQUERIES = 8
MULTI_HOP_PER_SUBQUERY_LIMIT = 5
MULTI_HOP_AUTO_MIN_SUBQUERIES = 2
MULTI_HOP_SEMANTIC_AUTO_TERMS = {"average", "between", "current", "days", "most", "total"}
MULTI_HOP_SEMANTIC_AUTO_PHRASES = ("number of", "what time", " plus ")
COMPLETION_SUPPORT_QUERY_PATTERN = re.compile(
    r"^when\s+did\s+(?P<subject>[A-Za-z][A-Za-z'-]*)\s+"
    r"(?P<intent>finish(?:ed|ing)?|complet(?:e|ed|ing)|wrap(?:ped|ping)?)(?:\s+up)?\s+"
    r"(?P<object>.+?)\??$",
    re.IGNORECASE,
)
WHEN_DID_ONSET_SUPPORT_QUERY_PATTERN = re.compile(
    r"^when\s+did\s+(?P<subject>[A-Za-z][A-Za-z'-]*)\s+"
    r"(?:get|got|have|had|suffer|suffered|experience|experienced)\s+"
    r"(?P<event>.+?)\??$",
    re.IGNORECASE,
)
TRANSCRIPT_MEMORY_PREFIX_PATTERN = re.compile(
    r"^\s*\[(?P<session>[^:\]\s]+):(?P<turn>\d+)\]\s*"
    r"\((?P<timestamp>[^)]+)\)\s*(?P<speaker>[^:]+):",
)
TRANSCRIPT_NEIGHBOR_SUPPORT_MAX_TURN_DISTANCE = 2
TRANSCRIPT_NEIGHBOR_SUPPORT_MAX_NUCLEI = 4
TRANSCRIPT_NEIGHBOR_SUPPORT_NOISE_TERMS = {
    "about",
    "around",
    "did",
    "get",
    "got",
    "had",
    "has",
    "have",
    "into",
    "last",
    "this",
    "when",
    "year",
}
COMPLETION_SUPPORT_TERMS = {
    "complete",
    "completed",
    "completing",
    "done",
    "finish",
    "finished",
    "finishing",
    "wrap",
    "wrapped",
    "wrapping",
}
COMPLETION_SUPPORT_OBJECT_NOISE_TERMS = {
    "about",
    "after",
    "before",
    "her",
    "his",
    "its",
    "that",
    "the",
    "their",
    "this",
    "with",
}
COMPLETION_SUPPORT_BRIDGE_NOISE_TERMS = {
    "been",
    "busy",
    "but",
    "did",
    "fun",
    "going",
    "had",
    "has",
    "have",
    "just",
    "last",
    "long",
    "lot",
    "lots",
    "month",
    "now",
    "remember",
    "really",
    "stuff",
    "talk",
    "time",
    "week",
    "year",
    "you",
    "your",
}
AUTHORITY_RANKS = {"none": 0, "low": 1, "medium": 2, "high": 3, "policy": 4}
TEMPORAL_HISTORY_TERMS = {
    "before",
    "earlier",
    "former",
    "formerly",
    "initial",
    "initially",
    "old",
    "older",
    "original",
    "previous",
    "previously",
    "prior",
}
EARLIEST_HISTORY_TERMS = {
    "initial",
    "initially",
    "original",
}
TEMPORAL_CURRENT_TERMS = {
    "active",
    "current",
    "currently",
    "latest",
    "new",
    "newest",
    "now",
    "today",
}
TEMPORAL_CHRONOLOGY_TERMS = {
    "after",
    "first",
    "later",
    "next",
    "order",
    "ordered",
    "sequence",
    "then",
    "timeline",
    "when",
}
GENERIC_HISTORY_QUERY_TERMS = {
    "former",
    "formerly",
    "initial",
    "initially",
    "old",
    "older",
    "original",
    "previous",
    "previously",
    "prior",
}
CHRONOLOGY_QUERY_NOISE_TERMS = TEMPORAL_CHRONOLOGY_TERMS | TEMPORAL_CURRENT_TERMS | TEMPORAL_HISTORY_TERMS | {
    "did",
    "do",
    "does",
    "happen",
    "happened",
    "happens",
    "is",
    "are",
    "was",
    "were",
}
CHRONOLOGY_QUERY_MUTATION_TERMS = {
    "change",
    "changed",
    "changes",
    "changing",
    "move",
    "moved",
    "moves",
    "moving",
    "shift",
    "shifted",
    "shifts",
    "shifting",
    "switch",
    "switched",
    "switches",
    "switching",
    "update",
    "updated",
    "updates",
    "updating",
}
CHRONOLOGY_RELATION_SUPPORT_TERMS = {
    "belongs_to": ["belong", "belongs", "belonged", "ownership", "owns", "part"],
    "deploys_to": ["deploy", "deploys", "deployed", "deployment"],
    "points_to": ["point", "points", "pointed", "routing"],
    "requires": ["require", "requires", "required", "requirement", "requirements"],
    "runs_on": ["run", "runs", "running", "runtime"],
    "uses": ["use", "uses", "used", "usage"],
}
SUBJECT_LOOKUP_QUERY_WRAPPERS = {
    "how",
    "s",
    "show",
    "tell",
    "what",
    "when",
    "where",
    "which",
    "who",
}
GENERIC_SUBJECT_NOISE_TERMS = SUBJECT_LOOKUP_QUERY_WRAPPERS | {
    "a",
    "an",
    "are",
    "did",
    "do",
    "does",
    "is",
    "our",
    "the",
    "to",
    "was",
    "we",
    "were",
}
GENERIC_SUBJECT_HELPER_TERMS = {
    "deploy",
    "deployed",
    "deploying",
    "deploys",
    "need",
    "needed",
    "needs",
    "require",
    "required",
    "requires",
    "run",
    "running",
    "runs",
    "use",
    "used",
    "uses",
    "using",
}
SEMANTIC_ALIAS_CANONICAL_BY_TOKEN = {
    "database": "database",
    "db": "database",
    "datastore": "database",
    "dest": "target",
    "destination": "target",
    "env": "environment",
    "environment": "environment",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "app": "service",
    "application": "service",
    "maintainer": "owner",
    "own": "owner",
    "owned": "owner",
    "owner": "owner",
    "owns": "owner",
    "prod": "production",
    "production": "production",
    "repo": "repository",
    "repository": "repository",
    "service": "service",
}
TEMPORAL_SEARCH_ALIAS_TERMS_BY_CANONICAL = {
    "owner": ["maintainer"],
    "target": ["destination"],
}
SUBJECT_CORE_PHRASE_ALIAS_VARIANTS = (
    {
        "required_terms": {"routing", "contact"},
        "search_query": "escalation contact",
    },
    {
        "required_terms": {"owner", "routing"},
        "search_query": "escalation contact",
    },
    {
        "required_terms": {"routing", "escalation", "contact"},
        "search_query": "escalation contact",
    },
    {
        "required_terms": {"deployment", "approval", "contact"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"approver", "deployments"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"approver", "deployment"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"approves", "deployments"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"approves", "deployment"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"signs", "off", "deployment"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"signs", "off", "deployments"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"deployment", "approvals", "contact"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"approval", "contact", "deployments"},
        "search_query": "deployment approver",
        "allow_empty_subject_anchor": True,
    },
    {
        "required_terms": {"deployment", "approval", "owner"},
        "search_query": "deployment approver",
        "prefer_before_core": True,
    },
    {
        "required_terms": {"deployment", "approvals", "owner"},
        "search_query": "deployment approver",
        "prefer_before_core": True,
    },
    {
        "required_terms": {"deployment", "signoff", "owner"},
        "search_query": "deployment approver",
        "prefer_before_core": True,
    },
    {
        "required_terms": {"deployment", "sign", "off", "owner"},
        "search_query": "deployment approver",
        "prefer_before_core": True,
    },
)
OWNER_RELATION_MULTI_HOP_LOOKUP_BASES = {
    "role-relation-owner",
    "role-relation-on-point",
    "role-relation-responsible",
    "role-relation-in-charge",
}
HISTORY_OBSERVATION_SUPPORT_EARLIEST_MARKERS = EARLIEST_HISTORY_TERMS | {"first"}
HISTORY_OBSERVATION_SUPPORT_LATER_MARKERS = {"after", "following", "later", "next"}
HISTORY_OBSERVATION_SUPPORT_ACTION_TERMS = {
    "cover",
    "covered",
    "handle",
    "handled",
    "lead",
    "led",
    "maintainer",
    "own",
    "owned",
    "owner",
    "ran",
    "run",
}
HISTORY_OBSERVATION_SUPPORT_CONTEXT_TERMS = {
    "coverage",
    "handoff",
    "overnight",
    "rotation",
    "shift",
}
HISTORY_OBSERVATION_SUPPORT_PERSON_LEAD_VERBS = {
    "cover",
    "covered",
    "covers",
    "handle",
    "handled",
    "handles",
    "lead",
    "leads",
    "led",
    "maintain",
    "maintained",
    "maintains",
    "own",
    "owned",
    "owns",
    "ran",
    "run",
    "runs",
    "take",
    "taken",
    "takes",
    "took",
}
HISTORY_OBSERVATION_SUPPORT_QUERY_ACTION_TERMS = {
    "charge",
    "handled",
    "maintainer",
    "owner",
    "owns",
    "owned",
    "responsible",
}
HISTORY_QUERY_NOISE_TERMS = (
    TEMPORAL_CHRONOLOGY_TERMS
    | TEMPORAL_CURRENT_TERMS
    | TEMPORAL_HISTORY_TERMS
    | SUBJECT_LOOKUP_QUERY_WRAPPERS
    | {"are", "be", "did", "do", "does", "is", "was", "were"}
)
UPDATE_QUERY_CURRENT_DIRECTION_TERMS = {"now", "to"}
UPDATE_QUERY_HISTORY_DIRECTION_TERMS = {"from"}
UPDATE_QUERY_NOISE_TERMS = (
    TEMPORAL_CHRONOLOGY_TERMS
    | TEMPORAL_CURRENT_TERMS
    | TEMPORAL_HISTORY_TERMS
    | SUBJECT_LOOKUP_QUERY_WRAPPERS
    | {"are", "be", "did", "do", "does", "from", "into", "is", "was", "were"}
)
RELATION_SEARCH_ARTICLES = {"a", "an", "the"}
RELATION_QUERY_PATTERNS = (
    (
        "role-relation-owner",
        "is",
        re.compile(r"^(?:who|what|which)\s+(?:owns?|owned)\s+(?P<subject>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} owner",
    ),
    (
        "role-relation-owner",
        "is",
        re.compile(r"^(?:who|what|which)\s+is\s+(?:the\s+)?owner\s+of\s+(?P<subject>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} owner",
    ),
    (
        "role-relation-on-point",
        "is",
        re.compile(
            r"^(?:who|what|which)(?:\s+s|\s+is|\s+was|\s+were)?"
            r"(?:\s+(?:the|previous|prior|former|original|initial))*"
            r"(?:\s+person)?\s+on\s+point\s+for\s+(?P<subject>.+)$",
            re.IGNORECASE,
        ),
        lambda match: f"{match.group('subject')} owner",
    ),
    (
        "role-relation-responsible",
        "is",
        re.compile(
            r"^(?:who|what|which)(?:\s+s|\s+is|\s+was|\s+were)?"
            r"(?:\s+(?:the|previous|prior|former|original|initial))*"
            r"(?:\s+person)?\s+responsible\s+for\s+(?P<subject>.+)$",
            re.IGNORECASE,
        ),
        lambda match: f"{match.group('subject')} owner",
    ),
    (
        "role-relation-in-charge",
        "is",
        re.compile(
            r"^(?:who|what|which)(?:\s+s|\s+is|\s+was|\s+were)?"
            r"(?:\s+(?:the|previous|prior|former|original|initial))*"
            r"(?:\s+person)?\s+in\s+charge\s+of\s+(?P<subject>.+)$",
            re.IGNORECASE,
        ),
        lambda match: f"{match.group('subject')} owner",
    ),
    (
        "role-relation-uses",
        "uses",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+does\s+(?P<subject>.+?)\s+use$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} uses",
    ),
    (
        "inverse-relation-uses-by",
        "uses",
        re.compile(r"^(?:what|which)\s+is\s+used\s+by\s+(?P<subject>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} uses",
    ),
    (
        "role-relation-points-to",
        "points_to",
        re.compile(r"^(?:where|what|which)(?:\s+.+?)?\s+does\s+(?P<subject>.+?)\s+point\s+to$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} points to",
    ),
    (
        "role-relation-points-at",
        "points_to",
        re.compile(r"^(?:where|what|which)(?:\s+.+?)?\s+does\s+(?P<subject>.+?)\s+point\s+at$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} points to",
    ),
    (
        "inverse-relation-points-to-by",
        "points_to",
        re.compile(r"^(?:where|what|which)\s+is\s+pointed\s+to\s+by\s+(?P<subject>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} points to",
    ),
    (
        "role-relation-belongs-to",
        "belongs_to",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+does\s+(?P<subject>.+?)\s+belong\s+to$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} belongs to",
    ),
    (
        "inverse-relation-belongs-part-of",
        "belongs_to",
        re.compile(r"^(?:what|which)\s+(?:is|are)\s+(?P<subject>.+?)\s+part\s+of$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} belongs to",
    ),
    (
        "role-relation-deploys-to",
        "deploys_to",
        re.compile(r"^(?:where|what|which)(?:\s+.+?)?\s+does\s+(?P<subject>.+?)\s+deploy(?:\s+to)?$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} deploys to",
    ),
    (
        "passive-relation-deployed-to",
        "deploys_to",
        re.compile(r"^(?:where|what|which)\s+(?:is|are)\s+(?P<subject>.+?)\s+deployed(?:\s+to)?$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} deploys to",
    ),
    (
        "role-relation-runs-on",
        "runs_on",
        re.compile(r"^(?:where|what|which)(?:\s+.+?)?\s+does\s+(?P<subject>.+?)\s+run(?:\s+on)?$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} runs on",
    ),
    (
        "passive-relation-runs-on",
        "runs_on",
        re.compile(r"^(?:where|what|which)\s+(?:is|are)\s+(?P<subject>.+?)\s+running(?:\s+on)?$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} runs on",
    ),
    (
        "role-relation-requires",
        "requires",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+does\s+(?P<subject>.+?)\s+require$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} requires",
    ),
    (
        "inverse-relation-requires-by",
        "requires",
        re.compile(r"^(?:what|which)\s+(?:is|are)\s+required\s+by\s+(?P<subject>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} requires",
    ),
    (
        "object-relation-uses",
        "uses",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+uses?\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"uses {match.group('object')}",
    ),
    (
        "object-relation-points-to",
        "points_to",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+points\s+to\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"points to {match.group('object')}",
    ),
    (
        "object-relation-belongs-to",
        "belongs_to",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+belongs\s+to\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"belongs to {match.group('object')}",
    ),
    (
        "object-relation-deploys-to",
        "deploys_to",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+deploys?\s+to\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"deploys to {match.group('object')}",
    ),
    (
        "object-relation-deploys-to",
        "deploys_to",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+(?:is|are)\s+deployed\s+to\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"deploys to {match.group('object')}",
    ),
    (
        "object-relation-runs-on",
        "runs_on",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+runs\s+on\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"runs on {match.group('object')}",
    ),
    (
        "object-relation-runs-on",
        "runs_on",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+(?:is|are)\s+running\s+on\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"runs on {match.group('object')}",
    ),
    (
        "object-relation-requires",
        "requires",
        re.compile(r"^(?:what|which)(?:\s+.+?)?\s+requires\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"requires {match.group('object')}",
    ),
    (
        "canonical-relation-requires",
        "requires",
        re.compile(r"^(?P<subject>.+?)\s+requires\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} requires {match.group('object')}",
    ),
    (
        "canonical-relation-uses",
        "uses",
        re.compile(r"^(?P<subject>.+?)\s+uses?\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} uses {match.group('object')}",
    ),
    (
        "canonical-relation-points-to",
        "points_to",
        re.compile(r"^(?P<subject>.+?)\s+points\s+to\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} points to {match.group('object')}",
    ),
    (
        "canonical-relation-belongs-to",
        "belongs_to",
        re.compile(r"^(?P<subject>.+?)\s+belongs\s+to\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} belongs to {match.group('object')}",
    ),
    (
        "canonical-relation-deploys-to",
        "deploys_to",
        re.compile(r"^(?P<subject>.+?)\s+deploys\s+to\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} deploys to {match.group('object')}",
    ),
    (
        "canonical-relation-runs-on",
        "runs_on",
        re.compile(r"^(?P<subject>.+?)\s+runs\s+on\s+(?P<object>.+)$", re.IGNORECASE),
        lambda match: f"{match.group('subject')} runs on {match.group('object')}",
    ),
)
LEXICAL_CONFLICT_PATTERNS = (
    ("points_to", re.compile(r"^(?P<subject>.+?)\s+points\s+to\s+(?P<object>.+)$", re.IGNORECASE)),
    ("belongs_to", re.compile(r"^(?P<subject>.+?)\s+belongs\s+to\s+(?P<object>.+)$", re.IGNORECASE)),
    ("deploys_to", re.compile(r"^(?P<subject>.+?)\s+deploys\s+to\s+(?P<object>.+)$", re.IGNORECASE)),
    ("runs_on", re.compile(r"^(?P<subject>.+?)\s+runs\s+on\s+(?P<object>.+)$", re.IGNORECASE)),
    ("requires", re.compile(r"^(?P<subject>.+?)\s+requires\s+(?P<object>.+)$", re.IGNORECASE)),
    ("uses", re.compile(r"^(?P<subject>.+?)\s+uses?\s+(?P<object>.+)$", re.IGNORECASE)),
    ("is", re.compile(r"^(?P<subject>.+?)\s+(?:is|are|was|were)\s+(?P<object>.+)$", re.IGNORECASE)),
)
EXPLICIT_UPDATE_PATTERNS = (
    (
        "changed_to",
        re.compile(
            r"^(?P<subject>.+?)\s+(?:changed|moved|shifted|switched|updated)\s+"
            r"(?:from\s+(?P<from>.+?)\s+)?to\s+(?P<to>.+)$",
            re.IGNORECASE,
        ),
    ),
    (
        "is_now",
        re.compile(r"^(?P<subject>.+?)\s+(?:is|are|was|were)\s+now\s+(?P<to>.+)$", re.IGNORECASE),
    ),
)
LEXICAL_CONFLICT_SELECTION_STRATEGY = "authority_trust_freshness_rank_v1"
LEXICAL_CONFLICT_ABSTENTION_TIE_FIELDS = ["authority", "trust", "updated_at", "created_at"]
SUBJECT_LOOKUP_RESTATEMENT_STRATEGY = "subject_lookup_freshness_observation_order_v2"
SUBJECT_LOOKUP_CROSS_PROVENANCE_HISTORY_STRATEGY = "subject_lookup_cross_provenance_abstention_v1"
SUBJECT_LOOKUP_HISTORY_RELATIONS = {"points_to", "belongs_to", "deploys_to", "runs_on"}
MULTI_HOP_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "before",
    "between",
    "can",
    "could",
    "does",
    "for",
    "from",
    "have",
    "how",
    "into",
    "not",
    "our",
    "should",
    "the",
    "then",
    "this",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}
DIRECT_SUBJECT_COMPOUND_NOISE_TERMS = {
    "context",
    "detail",
    "details",
    "fact",
    "facts",
    "info",
    "information",
    "note",
    "notes",
    "overview",
    "summary",
}
RETRIEVAL_RANK_CONFIG = {
    "schema": RETRIEVAL_RANK_CONFIG_SCHEMA,
    "mode": "fts_bm25_phrase_exact_lookup_fact_v4",
    "weights": {
        "bm25": 1.0,
        "authority": 0.35,
        "trust": 0.25,
        "label_exact": 0.15,
        "content_exact": 0.10,
        "label_phrase": 0.20,
        "content_phrase": 0.30,
        "label_exact_query": 0.25,
        "content_exact_query": 0.40,
        "lookup_key_match": 0.35,
        "lookup_value_compactness": 0.80,
    },
}


def default_db_path() -> Path:
    return Path.cwd() / ".zerker" / "memory.sqlite"


def default_policy_path() -> Path:
    return Path.cwd() / ".zerker" / "policy.json"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_uri(value: str) -> str:
    return f"{HASH_ALG}:{sha256_text(value)}"


def actor_uri_for(actor_id: str) -> str:
    if "://" in actor_id:
        return actor_id
    return f"actor://{actor_id}"


def default_environment_hash() -> str:
    return digest_uri(DEFAULT_ENVIRONMENT_HASH_INPUT)


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else None


def query_terms(value: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-z0-9_]+", value) if len(term) > 2]


def semantic_query_terms(value: str) -> list[str]:
    terms = []
    for token in _query_tokens(value):
        canonical = SEMANTIC_ALIAS_CANONICAL_BY_TOKEN.get(token, token)
        if len(canonical) > 2:
            terms.append(canonical)
    return _ordered_unique(terms)


def _conservative_inflection_forms(term: str) -> set[str]:
    term = term.lower()
    forms = {term}
    if len(term) < 4 or not term.isalpha():
        return forms

    if term.endswith("y") and len(term) > 4 and term[-2] not in "aeiou":
        forms.update({term[:-1] + "ies", term[:-1] + "ied"})
    elif term.endswith("e"):
        forms.update({term + "s", term + "d", term[:-1] + "ing"})
    else:
        forms.update({term + "s", term + "ed", term + "ing"})
        if term.endswith(("s", "x", "z", "ch", "sh")):
            forms.add(term + "es")

    if term.endswith("ies") and len(term) > 5:
        forms.add(term[:-3] + "y")
    if term.endswith("ied") and len(term) > 5:
        forms.add(term[:-3] + "y")
    if term.endswith("ing") and len(term) > 6:
        forms.update({term[:-3], term[:-3] + "e"})
    if term.endswith("ed") and len(term) > 5:
        forms.update({term[:-2], term[:-1]})
    if term.endswith("s") and not term.endswith("ss") and len(term) > 4:
        forms.add(term[:-1])
    return forms


def _inflectional_term_overlap(query: list[str], candidate: list[str]) -> int:
    candidate_set = set(candidate)
    return sum(
        1
        for term in _ordered_unique(query)
        if _conservative_inflection_forms(term).intersection(candidate_set)
    )


def fts_safe_query(value: str) -> str:
    terms = query_terms(value)
    return " ".join(f'"{term}"' for term in terms)


def fts_safe_query_terms(terms: list[str]) -> str:
    return " ".join(f'"{term}"' for term in terms if term)


def approx_memory_tokens(memory_or_text: MemoryRecord | str | dict[str, Any]) -> int:
    if isinstance(memory_or_text, MemoryRecord):
        text = stable_json(memory_or_text.to_dict())
    elif isinstance(memory_or_text, dict):
        text = stable_json(memory_or_text)
    else:
        text = str(memory_or_text)
    return max(1, (len(text) + 3) // 4) if text else 0


def authority_rank(authority: str) -> int:
    return AUTHORITY_RANKS.get(authority, 0)


def _term_match_count(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def _normalized_match_text(value: str) -> str:
    return " ".join(_query_tokens(value))


def _phrase_match(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return phrase in text


def _lookup_match_target(query_lookup: dict[str, Any]) -> tuple[str | None, str | None]:
    relation = str((query_lookup or {}).get("lookup_relation") or "")
    if not relation:
        return None, None
    lookup_basis = str((query_lookup or {}).get("lookup_basis") or "")
    raw_lookup_key = str((query_lookup or {}).get("lookup_key") or "")
    if lookup_basis.startswith("object-relation-"):
        lookup_key = _normalize_relation_value_fragment(raw_lookup_key)
    else:
        lookup_key = _normalize_lookup_subject_fragment(raw_lookup_key)
    if lookup_key:
        key_kind = "subject"
        if lookup_basis.startswith("object-relation-"):
            key_kind = "object"
        return key_kind, lookup_key

    if not lookup_basis.startswith("object-relation-"):
        return None, None
    search_query = _normalize_conflict_fragment(
        str((query_lookup or {}).get("search_query") or (query_lookup or {}).get("selected_search_query") or "")
    )
    relation_prefix = relation.replace("_", " ")
    if not search_query or not relation_prefix or not search_query.startswith(f"{relation_prefix} "):
        return None, None
    object_key = _normalize_relation_value_fragment(search_query[len(relation_prefix) + 1 :])
    if not object_key:
        return None, None
    return "object", object_key


def _lookup_rank_features(
    memory: MemoryRecord,
    *,
    query_lookup: dict[str, Any],
) -> dict[str, Any]:
    lookup_relation = str((query_lookup or {}).get("lookup_relation") or "")
    target_kind, target_key = _lookup_match_target(query_lookup)
    search_query = str((query_lookup or {}).get("search_query") or (query_lookup or {}).get("selected_search_query") or "")
    boost_supported = (
        bool(lookup_relation)
        and _normalize_relation_search_fragment(search_query) == _normalize_relation_value_fragment(search_query)
    )
    relation_signature = _lexical_conflict_signature(memory)
    relation_match = bool(
        boost_supported
        and relation_signature is not None
        and str(relation_signature.get("relation") or "") == lookup_relation
    )
    if target_kind == "object":
        candidate_key = str((relation_signature or {}).get("value_key") or "")
    else:
        candidate_key = str((relation_signature or {}).get("subject_key") or "")
    key_match = bool(relation_match and target_key and candidate_key == target_key)
    value_token_count = 0
    if relation_signature is not None:
        value_token_count = len(_relation_search_terms(str(relation_signature.get("value_key") or "")))
    value_compactness = 0.0
    if key_match and value_token_count > 0:
        value_compactness = round(1.0 / math.sqrt(value_token_count), 6)
    return {
        "lookup_boost_supported": boost_supported,
        "lookup_relation_match": relation_match,
        "lookup_key_match": key_match,
        "lookup_key_kind": target_kind,
        "lookup_value_token_count": value_token_count if relation_match else None,
        "lookup_value_compactness": value_compactness,
    }


def _rank_features(
    memory: MemoryRecord,
    *,
    terms: list[str],
    search_query: str,
    bm25_score: float | None,
    search_mode: str,
    query_lookup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content_matches = _term_match_count(memory.content, terms)
    label_matches = _term_match_count(" ".join(memory.labels), terms)
    normalized_search_query = _normalized_match_text(search_query)
    normalized_content = _normalized_match_text(memory.content)
    normalized_labels = _normalized_match_text(" ".join(memory.labels))
    content_phrase_match = _phrase_match(normalized_content, normalized_search_query)
    label_phrase_match = _phrase_match(normalized_labels, normalized_search_query)
    content_exact_query_match = bool(normalized_search_query and normalized_content == normalized_search_query)
    label_exact_query_match = bool(normalized_search_query and normalized_labels == normalized_search_query)
    matched_fields = []
    if content_matches:
        matched_fields.append("content")
    if label_matches:
        matched_fields.append("labels")
    if bm25_score is None:
        bm25_component = 0.0
    else:
        raw_bm25 = float(bm25_score)
        bm25_component = -raw_bm25 if raw_bm25 < 0 else 1.0 / (1.0 + raw_bm25)
    weights = RETRIEVAL_RANK_CONFIG["weights"]
    lookup_features = _lookup_rank_features(memory, query_lookup=query_lookup or {})
    score_components = {
        "bm25": bm25_component * weights["bm25"],
        "authority": authority_rank(memory.authority) * weights["authority"],
        "trust": float(memory.trust) * weights["trust"],
        "label_exact": label_matches * weights["label_exact"],
        "content_exact": content_matches * weights["content_exact"],
        "label_phrase": float(label_phrase_match) * weights["label_phrase"],
        "content_phrase": float(content_phrase_match) * weights["content_phrase"],
        "label_exact_query": float(label_exact_query_match) * weights["label_exact_query"],
        "content_exact_query": float(content_exact_query_match) * weights["content_exact_query"],
        "lookup_key_match": float(lookup_features["lookup_key_match"]) * weights["lookup_key_match"],
        "lookup_value_compactness": float(lookup_features["lookup_value_compactness"])
        * weights["lookup_value_compactness"],
    }
    return {
        "authority": memory.authority,
        "authority_rank": authority_rank(memory.authority),
        "trust": memory.trust,
        "content_term_matches": content_matches,
        "label_term_matches": label_matches,
        "content_phrase_match": content_phrase_match,
        "label_phrase_match": label_phrase_match,
        "content_exact_query_match": content_exact_query_match,
        "label_exact_query_match": label_exact_query_match,
        "matched_fields": matched_fields,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
        "expires_at": memory.expires_at,
        "is_expired": bool(memory.expires_at and memory.expires_at <= now_iso()),
        "has_parents": bool(memory.parents),
        "temporal_state": "current",
        "superseded_by_candidate": None,
        "child_candidate_ids": [],
        **lookup_features,
        "score_components": score_components,
        "search_mode": search_mode,
    }


def _rank_score(features: dict[str, Any]) -> float:
    return round(sum(float(value) for value in features["score_components"].values()), 6)


def pseudo_embedding(text: str, *, dims: int = 64) -> list[float]:
    if dims <= 0:
        raise ValueError("embedding dimensions must be positive")
    vector = [0.0 for _ in range(dims)]
    terms = semantic_query_terms(text)
    if not terms and text:
        terms = [text.lower()]
    for term in terms:
        digest = hashlib.sha256(term.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        sign = -1.0 if digest[4] & 1 else 1.0
        weight = 1.0 + min(len(term), 12) / 12.0
        vector[index] += sign * weight
    return [round(value, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimensions")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return round(sum(lval * rval for lval, rval in zip(left, right)) / (left_norm * right_norm), 6)


def embedding_vector_id(model_id: str, content_hash: str) -> str:
    return "vec_" + sha256_text(f"{model_id}:{content_hash}")[:24]


def _candidate_by_id(retrieval: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(candidate["memory_id"]): candidate
        for candidate in retrieval.get("candidates", [])
        if "memory_id" in candidate
    }


def _candidate_config(config: dict[str, Any] | None, section: str) -> dict[str, Any]:
    if not config:
        return {}
    section_config = config.get(section)
    if isinstance(section_config, dict):
        return section_config
    return config


def _embedding_index_hash(memories: list[MemoryRecord], model_id: str, dims: int) -> str:
    return sha256_text(
        stable_json(
            {
                "model_id": model_id,
                "dims": dims,
                "candidates": [
                    {"memory_id": memory.id, "content_hash": memory.content_hash}
                    for memory in memories
                ],
            }
        )
    )


def embedding_vector_hash(vector: list[float]) -> str:
    return "sha256:" + sha256_text(stable_json([round(float(value), 9) for value in vector]))


def _record_candidate_score_component(candidate: dict[str, Any], name: str, value: float) -> None:
    component = round(float(value), 6)
    features = candidate.setdefault("features", {})
    feature_components = features.setdefault("score_components", {})
    feature_components[name] = component
    candidate_components = candidate.setdefault("score_components", feature_components)
    candidate_components[name] = component
    candidate["score"] = _rank_score(features)


def _set_candidate_rank(candidate: dict[str, Any], key: str, rank: int) -> None:
    candidate[key] = rank
    candidate.setdefault("features", {})[key] = rank


def _baseline_candidate_sort_key(memory: MemoryRecord, candidate: dict[str, Any]) -> tuple[Any, ...]:
    features = candidate.get("features", {})
    hybrid_semantic_score = candidate.get("semantic_backfill_score")
    hybrid_semantic_signal_applied = isinstance(hybrid_semantic_score, (int, float))
    multi_hop_fusion_score = candidate.get("multi_hop_fusion_score")
    multi_hop_fusion_signal_applied = isinstance(multi_hop_fusion_score, (int, float))
    temporal_fusion_score = candidate.get("temporal_fusion_score")
    temporal_fusion_signal_applied = isinstance(temporal_fusion_score, (int, float))
    return (
        -int(hybrid_semantic_signal_applied),
        -float(hybrid_semantic_score) if hybrid_semantic_signal_applied else 0.0,
        -int(multi_hop_fusion_signal_applied),
        -float(multi_hop_fusion_score) if multi_hop_fusion_signal_applied else 0.0,
        -int(candidate.get("multi_hop_fusion_source_count", 0) or 0),
        -int(bool(candidate.get("introduced_by_subquery_id")) if multi_hop_fusion_signal_applied else False),
        -int(temporal_fusion_signal_applied),
        -float(temporal_fusion_score) if temporal_fusion_signal_applied else 0.0,
        -int(candidate.get("temporal_fusion_source_count", 0) or 0),
        -float(candidate.get("score", 0.0)),
        -int(bool(features.get("lookup_key_match"))),
        -float(features.get("lookup_value_compactness", 0.0)),
        -int(bool(features.get("content_exact_query_match"))),
        -int(bool(features.get("label_exact_query_match"))),
        -int(bool(features.get("content_phrase_match"))),
        -int(bool(features.get("label_phrase_match"))),
        -int(features.get("content_term_matches", 0)),
        -int(features.get("label_term_matches", 0)),
        -int(features.get("authority_rank", 0)),
        -float(features.get("trust", 0.0)),
        int(candidate.get("rank_before_boosts", candidate.get("rank", RETRIEVAL_CANDIDATE_LIMIT + 1))),
        memory.id,
    )


def _apply_baseline_ranking(memories: list[MemoryRecord], retrieval: dict[str, Any]) -> list[MemoryRecord]:
    ranked_pairs = []
    for memory in memories:
        candidate = next((item for item in retrieval.get("candidates", []) if item.get("memory_id") == memory.id), None)
        if candidate is None:
            continue
        rank_before_boosts = int(candidate.get("rank_before_boosts", candidate.get("rank", len(ranked_pairs) + 1)))
        candidate["rank_before_boosts"] = rank_before_boosts
        candidate.setdefault("features", {})["rank_before_boosts"] = rank_before_boosts
        ranked_pairs.append((memory, candidate))
    ranked_pairs.sort(key=lambda item: _baseline_candidate_sort_key(item[0], item[1]))
    ordered_memories = []
    ordered_candidates = []
    for rank, (memory, candidate) in enumerate(ranked_pairs, start=1):
        candidate["rank"] = rank
        ordered_memories.append(memory)
        ordered_candidates.append(candidate)
    retrieval["candidates"] = ordered_candidates
    rank_before_boosts_source = "fts_authority_trust_sql_v1"
    if any(candidate.get("fts_preselection_rank") is not None for candidate in ordered_candidates):
        rank_before_boosts_source = "fts_window_preselection_v1"
    hybrid_semantic_signal_applied = any(
        isinstance(candidate.get("semantic_backfill_score"), (int, float))
        for candidate in ordered_candidates
    )
    multi_hop_fusion_signal_applied = any(
        isinstance(candidate.get("multi_hop_fusion_score"), (int, float))
        for candidate in ordered_candidates
    )
    temporal_fusion_signal_applied = any(
        isinstance(candidate.get("temporal_fusion_score"), (int, float))
        for candidate in ordered_candidates
    )
    temporal_fusion = retrieval.get("temporal", {}) if isinstance(retrieval.get("temporal"), dict) else {}
    temporal_fusion_signal = None
    if temporal_fusion_signal_applied:
        temporal_fusion_signal = str(
            ((temporal_fusion.get("fusion") or {}) if isinstance(temporal_fusion.get("fusion"), dict) else {}).get("signal")
            or "temporal_support_rrf_score_v1"
        )
    retrieval["baseline_ranking"] = {
        "applied": True,
        "strategy": "deterministic_lookup_fact_score_desc_v5",
        "rank_before_boosts_source": rank_before_boosts_source,
        "lookup_fact_boosts": ["lookup_key_match", "lookup_value_compactness"],
        "hybrid_semantic_signal": "semantic_backfill_score_v1" if hybrid_semantic_signal_applied else None,
        "hybrid_semantic_signal_applied": hybrid_semantic_signal_applied,
        "multi_hop_fusion_signal": "multi_hop_rrf_score_v1" if multi_hop_fusion_signal_applied else None,
        "multi_hop_fusion_signal_applied": multi_hop_fusion_signal_applied,
        "temporal_fusion_signal": temporal_fusion_signal,
        "temporal_fusion_signal_applied": temporal_fusion_signal_applied,
    }
    return ordered_memories


def _annotate_hybrid_semantic_ranking(retrieval: dict[str, Any]) -> None:
    hybrid = retrieval.get("hybrid", {}) if isinstance(retrieval.get("hybrid"), dict) else {}
    candidates = retrieval.get("candidates", [])
    if not hybrid.get("applied") or not isinstance(candidates, list):
        return
    if not any(isinstance(candidate.get("semantic_backfill_score"), (int, float)) for candidate in candidates):
        return

    promoted_ids = []
    outranked_ids = []
    for candidate in candidates:
        pre_hybrid_rank = candidate.get("pre_hybrid_rank")
        hybrid_semantic_rank = candidate.get("rank")
        rank_delta = None
        promoted_by_semantic_backfill = False
        outranked_by_semantic_backfill = False
        outranked_reason = None
        if isinstance(pre_hybrid_rank, int) and isinstance(hybrid_semantic_rank, int):
            rank_delta = hybrid_semantic_rank - pre_hybrid_rank
            promoted_by_semantic_backfill = hybrid_semantic_rank < pre_hybrid_rank
            outranked_by_semantic_backfill = hybrid_semantic_rank > pre_hybrid_rank
            if promoted_by_semantic_backfill:
                promoted_ids.append(candidate["memory_id"])
            if outranked_by_semantic_backfill:
                outranked_ids.append(candidate["memory_id"])
                outranked_reason = "hybrid-semantic-backfill-ranked-lower"
        candidate["hybrid_semantic_rank"] = hybrid_semantic_rank if isinstance(hybrid_semantic_rank, int) else None
        candidate["hybrid_rank_delta"] = rank_delta
        candidate["hybrid_promoted_by_semantic_backfill"] = promoted_by_semantic_backfill
        candidate["hybrid_outranked_by_semantic_backfill"] = outranked_by_semantic_backfill
        candidate["hybrid_outranked_reason"] = outranked_reason
        candidate.setdefault("features", {})["hybrid_semantic_rank"] = candidate["hybrid_semantic_rank"]
        candidate["features"]["hybrid_rank_delta"] = rank_delta
        candidate["features"]["hybrid_promoted_by_semantic_backfill"] = promoted_by_semantic_backfill
        candidate["features"]["hybrid_outranked_by_semantic_backfill"] = outranked_by_semantic_backfill
        candidate["features"]["hybrid_outranked_reason"] = outranked_reason

    fusion = hybrid.get("fusion")
    if isinstance(fusion, dict):
        fusion["promoted_candidate_ids"] = promoted_ids
        fusion["outranked_candidate_ids"] = outranked_ids


def _overlay_outranked_reason(overlay_key: str, metadata: dict[str, Any], candidate: dict[str, Any]) -> str:
    overlay_metadata = candidate.get(overlay_key) if isinstance(candidate.get(overlay_key), dict) else {}
    if metadata.get("provider_id") and not metadata.get("fallback") and overlay_metadata.get("provider_eligible"):
        return f"provider-{overlay_key}-ranked-lower"
    return f"local-{overlay_key}-ranked-lower"


def _annotate_overlay_ranking(
    retrieval: dict[str, Any],
    *,
    overlay_key: str,
    pre_rank_key: str,
    post_rank_key: str,
    rank_key: str,
    promoted_key: str,
    outranked_key: str,
    reason_key: str,
) -> None:
    metadata = retrieval.get(overlay_key)
    candidates = retrieval.get("candidates", [])
    if not isinstance(metadata, dict) or not isinstance(candidates, list):
        return
    if not metadata.get("enabled"):
        return

    promoted_ids = []
    outranked_ids = []
    rank_delta_key = f"{overlay_key}_rank_delta"
    for candidate in candidates:
        pre_rank = candidate.get(pre_rank_key)
        post_rank = candidate.get(post_rank_key)
        overlay_rank = post_rank if isinstance(post_rank, int) and not isinstance(post_rank, bool) else None
        rank_delta = None
        promoted = False
        outranked = False
        outranked_reason = None
        if isinstance(pre_rank, int) and not isinstance(pre_rank, bool) and isinstance(overlay_rank, int):
            rank_delta = overlay_rank - pre_rank
            promoted = overlay_rank < pre_rank
            outranked = overlay_rank > pre_rank
            if promoted:
                promoted_ids.append(candidate["memory_id"])
            if outranked:
                outranked_ids.append(candidate["memory_id"])
                outranked_reason = _overlay_outranked_reason(overlay_key, metadata, candidate)
        candidate[rank_key] = overlay_rank
        candidate[rank_delta_key] = rank_delta
        candidate[promoted_key] = promoted
        candidate[outranked_key] = outranked
        candidate[reason_key] = outranked_reason
        candidate.setdefault("features", {})[rank_key] = overlay_rank
        candidate["features"][rank_delta_key] = rank_delta
        candidate["features"][promoted_key] = promoted
        candidate["features"][outranked_key] = outranked
        candidate["features"][reason_key] = outranked_reason

    metadata["promoted_candidate_ids"] = promoted_ids
    metadata["outranked_candidate_ids"] = outranked_ids


def _overlay_receipt_fields(candidate: dict[str, Any] | None, *, include_empty: bool = False) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        candidate = {}
    fields: dict[str, Any] = {}
    for overlay_key in ("embedding", "reranker"):
        rank_key = f"{overlay_key}_rank"
        rank_delta_key = f"{overlay_key}_rank_delta"
        promoted_key = f"{overlay_key}_promoted"
        outranked_key = f"{overlay_key}_outranked"
        reason_key = f"{overlay_key}_outranked_reason"
        rank = candidate.get(rank_key)
        if not isinstance(rank, int) or isinstance(rank, bool):
            rank = None
        rank_delta = candidate.get(rank_delta_key)
        if not isinstance(rank_delta, int) or isinstance(rank_delta, bool):
            rank_delta = None
        promoted = bool(candidate.get(promoted_key))
        outranked = bool(candidate.get(outranked_key))
        reason = candidate.get(reason_key)
        if include_empty or rank is not None or rank_delta is not None or promoted or outranked or reason is not None:
            fields[rank_key] = rank
            fields[rank_delta_key] = rank_delta
            fields[promoted_key] = promoted
            fields[outranked_key] = outranked
            fields[reason_key] = reason
    return fields


def _fts_candidate_window_limit(limit: int) -> int:
    limit = max(0, int(limit))
    if limit == 0:
        return 0
    return max(limit, limit * FTS_CANDIDATE_WINDOW_MULTIPLIER)


def _preselect_fts_rows(
    rows: list[sqlite3.Row],
    *,
    query: str,
    search_query: str,
    search_terms: list[str],
    fts_query: str,
    query_lookup: dict[str, Any],
    limit: int,
) -> tuple[list[sqlite3.Row], dict[str, dict[str, Any]], dict[str, Any]]:
    selected_limit = max(0, int(limit))
    window_candidate_count = len(rows)
    window_candidates = []
    for window_rank, row in enumerate(rows, start=1):
        memory = MemoryRecord.from_row(row)
        bm25_score = float(row["bm25_score"]) if "bm25_score" in row.keys() and row["bm25_score"] is not None else None
        features = _rank_features(
            memory,
            terms=search_terms,
            search_query=search_query,
            bm25_score=bm25_score,
            search_mode="fts",
            query_lookup=query_lookup,
        )
        features["fts_window_rank"] = window_rank
        candidate = {
            "memory_id": memory.id,
            "rank": window_rank,
            "bm25": bm25_score,
            "score": _rank_score(features),
            "features": features,
            "matched_fields": features["matched_fields"],
        }
        window_candidates.append((memory, row, candidate))

    ranked_window = sorted(window_candidates, key=lambda item: _baseline_candidate_sort_key(item[0], item[2]))
    selected_rank_by_id = {
        candidate["memory_id"]: rank
        for rank, (_, _, candidate) in enumerate(ranked_window[:selected_limit], start=1)
    }
    selected_rows = []
    candidate_metadata: dict[str, dict[str, Any]] = {}
    selected_candidate_ids = []
    dropped_candidate_ids = []
    for memory, row, candidate in window_candidates:
        preselection_rank = selected_rank_by_id.get(memory.id)
        if preselection_rank is None:
            dropped_candidate_ids.append(memory.id)
            continue
        selected_rows.append(row)
        selected_candidate_ids.append(memory.id)
        candidate_metadata[memory.id] = {
            "fts_window_rank": int(candidate["features"]["fts_window_rank"]),
            "fts_preselection_rank": int(preselection_rank),
            "observation_seq": int(row["observation_seq"]) if "observation_seq" in row.keys() else 0,
        }
    metadata = {
        "applied": window_candidate_count > selected_limit,
        "strategy": "fts_window_rescore_prune_v1",
        "sql_window_order": "authority_trust_bm25_observation_v1",
        "window_multiplier": FTS_CANDIDATE_WINDOW_MULTIPLIER,
        "window_candidate_count": window_candidate_count,
        "selected_candidate_ids": selected_candidate_ids,
        "dropped_candidate_ids": dropped_candidate_ids,
        "requested_limit": selected_limit,
        "search_query": search_query,
        "query": query,
        "search_terms": list(search_terms),
        "fts_query": fts_query,
    }
    return selected_rows, candidate_metadata, metadata


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered = []
    for value in values:
        normalized = " ".join(str(value).strip().split())
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _split_identifier_token(token: str) -> list[str]:
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", token.replace("_", " ")).split()
    return [part for part in parts if len(part) > 2]


def _finalize_multi_hop_subqueries(
    query: str,
    planned: list[tuple[str, str]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    subqueries = []
    parent_key = " ".join(query_terms(query))
    for source, subquery in planned:
        normalized = " ".join(subquery.split())
        if not normalized or " ".join(query_terms(normalized)) == parent_key:
            continue
        if normalized.lower() in {item["query"].lower() for item in subqueries}:
            continue
        subquery_id = f"mhq_{len(subqueries) + 1}"
        subqueries.append(
            {
                "id": subquery_id,
                "query": normalized,
                "query_hash": sha256_text(normalized),
                "source": source,
                "terms": query_terms(normalized),
            }
        )
        if len(subqueries) >= limit:
            break
    return subqueries


def _direct_deploy_target_multi_hop_plans(
    query: str,
    *,
    query_lookup: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    if not isinstance(query_lookup, dict):
        return []
    if str(query_lookup.get("selected_search_basis") or "") != "direct-deploy-target-core":
        return []
    if query_lookup.get("lookup_relation") is not None:
        return []

    query_term_set = {term for term in query_terms(query) if term not in MULTI_HOP_STOPWORDS}
    if "deploy" not in query_term_set or not ({"target", "destination"} & query_term_set):
        return []

    subject_variants = _subject_core_search_variants(["deploy", "target"], basis="direct-deploy-target-core")
    subject_queries = [
        str(variant.get("query"))
        for variant in subject_variants.get("variants", [])
        if str(variant.get("query"))
    ] or ["deploy target"]
    intent_terms = [
        term
        for term in query_terms(query)
        if term not in MULTI_HOP_STOPWORDS and term not in {"deploy", "target", "destination"}
    ]
    intent_term_set = set(intent_terms)

    planned: list[tuple[str, str]] = []
    for subject_query in _ordered_unique(subject_queries):
        planned.append(("direct_subject_fact", f"{subject_query} is"))
    if {"rollback", "policy"}.issubset(intent_term_set):
        planned.append(("direct_subject_intent_fact", "rollback policy is"))
    else:
        for intent in intent_terms[:2]:
            planned.append(("direct_subject_intent_pair", f"deploy target {intent}"))
    return planned


def _trim_owner_relation_phrase_alias_terms(subject_terms: list[str]) -> list[str]:
    if not subject_terms:
        return subject_terms
    rollback_index = next((index for index, term in enumerate(subject_terms) if term == "rollback"), len(subject_terms))
    anchor_terms = subject_terms[:rollback_index]
    suffix_terms = subject_terms[rollback_index:]
    if len(anchor_terms) < 4:
        return subject_terms

    trimmed_terms = subject_terms
    trimmed = False
    alias_variants = sorted(
        (
            alias_variant
            for alias_variant in SUBJECT_CORE_PHRASE_ALIAS_VARIANTS
            if not alias_variant.get("prefer_before_core") and not alias_variant.get("allow_empty_subject_anchor")
        ),
        key=lambda alias_variant: len(alias_variant["required_terms"]),
        reverse=True,
    )
    for alias_variant in alias_variants:
        required_terms = {str(term) for term in alias_variant["required_terms"] if str(term)}
        if not required_terms:
            continue
        matched_indexes = [index for index, term in enumerate(anchor_terms) if term in required_terms]
        if len({anchor_terms[index] for index in matched_indexes}) != len(required_terms):
            continue
        prefix_terms = anchor_terms[: min(matched_indexes)]
        if len(prefix_terms) < 2:
            continue
        trimmed_terms = prefix_terms + suffix_terms
        trimmed = True
        break
    return trimmed_terms if trimmed else subject_terms


def _compound_phrase_alias_query(terms: list[str]) -> str | None:
    if not terms:
        return None
    term_set = {str(term) for term in terms if str(term)}
    alias_variants = sorted(
        (
            alias_variant
            for alias_variant in SUBJECT_CORE_PHRASE_ALIAS_VARIANTS
            if not alias_variant.get("prefer_before_core") and not alias_variant.get("allow_empty_subject_anchor")
        ),
        key=lambda alias_variant: len(alias_variant["required_terms"]),
        reverse=True,
    )
    for alias_variant in alias_variants:
        required_terms = {str(term) for term in alias_variant["required_terms"] if str(term)}
        if required_terms and required_terms.issubset(term_set):
            phrase_alias_query = str(alias_variant["search_query"]).strip()
            if phrase_alias_query:
                return phrase_alias_query
    return None


def _direct_subject_owner_intent_multi_hop_plans(
    query: str,
    *,
    query_lookup: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    if not isinstance(query_lookup, dict):
        return []
    selected_search_basis = str(query_lookup.get("selected_search_basis") or "")
    if selected_search_basis not in {"direct-subject", "direct-subject-alias", "direct-subject-phrase-alias"}:
        return []
    if query_lookup.get("lookup_relation") is not None:
        return []

    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*", query)
    if any(
        token[:1].isupper() and len(token) > 2 and token.lower() not in MULTI_HOP_STOPWORDS
        for token in raw_tokens
    ):
        return []
    if any("_" in token or len(_split_identifier_token(token)) > 1 for token in raw_tokens):
        return []

    core_info = _canonical_subject_core_terms(
        _query_tokens(query),
        excluded_terms=GENERIC_SUBJECT_NOISE_TERMS | MULTI_HOP_STOPWORDS,
    )
    core_terms = [str(term) for term in core_info.get("core_terms", []) if str(term)]
    if "owner" not in core_terms:
        return []
    owner_index = core_terms.index("owner")
    subject_core_terms = core_terms[: owner_index + 1]
    subject_anchor_terms = [term for term in subject_core_terms if term != "owner"]
    intent_terms = [
        term
        for term in core_terms[owner_index + 1 :]
        if term not in DIRECT_SUBJECT_COMPOUND_NOISE_TERMS
    ]
    if len(subject_anchor_terms) < 2 or not {"rollback", "policy"}.issubset(intent_terms):
        return []

    subject_variant_info = _subject_core_search_variants(
        subject_core_terms,
        basis="direct-subject",
        include_phrase_aliases=False,
    )
    subject_queries = [
        str(variant.get("query"))
        for variant in subject_variant_info.get("variants", [])
        if str(variant.get("query"))
    ] or [" ".join(subject_core_terms)]
    subject_anchor_query = " ".join(subject_anchor_terms)
    preferred_phrase_alias_query = None
    core_term_set = {str(term) for term in subject_core_terms if str(term)}
    for alias_variant in SUBJECT_CORE_PHRASE_ALIAS_VARIANTS:
        required_terms = {str(term) for term in alias_variant["required_terms"] if str(term)}
        if not alias_variant.get("prefer_before_core") or not required_terms.issubset(core_term_set):
            continue
        preferred_phrase_alias_query = str(alias_variant["search_query"]).strip()
        if preferred_phrase_alias_query:
            break
    compound_phrase_alias_query = _compound_phrase_alias_query(intent_terms)

    planned: list[tuple[str, str]] = []
    if preferred_phrase_alias_query:
        rollback_subject_terms = [
            "approvals" if term == "approval" else term for term in subject_anchor_terms
        ]
        rollback_subject_query = " ".join(rollback_subject_terms) or subject_anchor_query
        planned.append(("direct_subject_fact", preferred_phrase_alias_query))
        planned.append(("direct_subject_fact", f"{preferred_phrase_alias_query} is"))
        planned.append(("direct_subject_intent_pair", f"{rollback_subject_query} rollback policy"))
    else:
        for subject_query in _ordered_unique(subject_queries):
            planned.append(("direct_subject_fact", subject_query))
        if compound_phrase_alias_query:
            planned.append(("direct_subject_fact", f"{subject_anchor_query} {compound_phrase_alias_query}".strip()))
        # The owner/rollback path already has specific owner and rollback probes.
        # Re-adding the bare subject mostly pulls unrelated subject-only facts back in.
        planned.append(("direct_subject_intent_pair", f"{subject_anchor_query} rollback policy"))
    planned.append(("direct_subject_intent_fact", "rollback policy is"))
    return planned


def _direct_subject_phrase_alias_multi_hop_plans(
    query: str,
    *,
    query_lookup: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    if not isinstance(query_lookup, dict):
        return []
    selected_search_basis = str(query_lookup.get("selected_search_basis") or "")
    if selected_search_basis not in {"direct-subject", "direct-subject-alias", "direct-subject-phrase-alias"}:
        return []
    if query_lookup.get("lookup_relation") is not None:
        return []

    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*", query)
    if any(
        token[:1].isupper() and len(token) > 2 and token.lower() not in MULTI_HOP_STOPWORDS
        for token in raw_tokens
    ):
        return []
    if any("_" in token or len(_split_identifier_token(token)) > 1 for token in raw_tokens):
        return []

    core_info = _canonical_subject_core_terms(
        _query_tokens(query),
        excluded_terms=GENERIC_SUBJECT_NOISE_TERMS | MULTI_HOP_STOPWORDS,
    )
    core_terms = [str(term) for term in core_info.get("core_terms", []) if str(term)]
    if len(core_terms) < 4 or "owner" in core_terms:
        return []

    matched_variant = None
    matched_indexes: list[int] = []
    core_term_set = set(core_terms)
    for alias_variant in SUBJECT_CORE_PHRASE_ALIAS_VARIANTS:
        required_terms = {str(term) for term in alias_variant["required_terms"] if str(term)}
        if not required_terms or not required_terms.issubset(core_term_set):
            continue
        indexes = [index for index, term in enumerate(core_terms) if term in required_terms]
        if not indexes:
            continue
        matched_variant = alias_variant
        matched_indexes = indexes
        break
    if matched_variant is None or not matched_indexes:
        return []

    subject_anchor_terms = core_terms[: min(matched_indexes)]
    intent_terms = [
        term
        for term in core_terms[max(matched_indexes) + 1 :]
        if term not in DIRECT_SUBJECT_COMPOUND_NOISE_TERMS
    ]
    allow_empty_subject_anchor = bool(matched_variant.get("allow_empty_subject_anchor"))
    if subject_anchor_terms:
        if len(subject_anchor_terms) < 2:
            return []
    elif not allow_empty_subject_anchor:
        return []
    if not {"rollback", "policy"}.issubset(intent_terms):
        return []

    subject_anchor_query = " ".join(subject_anchor_terms)
    matched_subject_terms = core_terms[min(matched_indexes) : max(matched_indexes) + 1]
    phrase_alias_query = str(matched_variant["search_query"]).strip()
    if not phrase_alias_query:
        return []
    planned = [("direct_subject_fact", f"{subject_anchor_query} {phrase_alias_query}".strip())]
    if subject_anchor_query:
        # The phrase-alias rollback path already has specific alias and rollback probes.
        # Re-adding the bare subject mostly pulls unrelated subject-only facts back in.
        planned.append(("direct_subject_intent_pair", f"{subject_anchor_query} rollback policy"))
    elif allow_empty_subject_anchor:
        planned.append(("direct_subject_fact", f"{phrase_alias_query} is"))
        rollback_subject_terms = [term for term in matched_subject_terms if term != "contact"]
        if rollback_subject_terms:
            rollback_subject_query = " ".join("approvals" if term == "approval" else term for term in rollback_subject_terms)
            planned.append(("direct_subject_intent_pair", f"{rollback_subject_query} rollback policy"))
    planned.append(("direct_subject_intent_fact", "rollback policy is"))
    return planned


def _owner_relation_compound_multi_hop_plans(
    query: str,
    *,
    query_lookup: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    if not isinstance(query_lookup, dict):
        return []
    lookup_basis = str(query_lookup.get("lookup_basis") or "")
    if lookup_basis not in OWNER_RELATION_MULTI_HOP_LOOKUP_BASES:
        return []
    if str(query_lookup.get("lookup_relation") or "") != "is":
        return []

    subject_text = None
    for candidate_basis, _relation, pattern, _builder in RELATION_QUERY_PATTERNS:
        if candidate_basis != lookup_basis:
            continue
        match = pattern.match(query.strip())
        if match is None:
            continue
        subject_text = str(match.groupdict().get("subject") or "").strip()
        if subject_text:
            break
    if not subject_text:
        return []

    subject_terms = _trim_owner_relation_phrase_alias_terms(query_terms(subject_text))
    if not {"rollback", "policy"}.issubset(subject_terms):
        return []

    intent_start = next((index for index, term in enumerate(subject_terms) if term == "rollback"), None)
    if intent_start is None:
        return []
    subject_anchor_terms = subject_terms[:intent_start]
    intent_terms = subject_terms[intent_start:]
    if len(subject_anchor_terms) < 2 or not {"rollback", "policy"}.issubset(intent_terms):
        return []

    normalized_query = " ".join(subject_anchor_terms + ["owner"] + intent_terms)
    return _direct_subject_owner_intent_multi_hop_plans(
        normalized_query,
        query_lookup={"selected_search_basis": "direct-subject", "lookup_relation": None},
    )


def decompose_multi_hop_query(
    query: str,
    *,
    max_subqueries: int = MULTI_HOP_MAX_SUBQUERIES,
    query_lookup: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    limit = max(0, min(int(max_subqueries), MULTI_HOP_MAX_SUBQUERIES))
    if limit == 0:
        return []

    planned: list[tuple[str, str]] = []
    owner_relation_plans = _owner_relation_compound_multi_hop_plans(query, query_lookup=query_lookup)
    planned.extend(owner_relation_plans)
    planned.extend(_direct_subject_owner_intent_multi_hop_plans(query, query_lookup=query_lookup))
    planned.extend(_direct_subject_phrase_alias_multi_hop_plans(query, query_lookup=query_lookup))
    planned.extend(_direct_deploy_target_multi_hop_plans(query, query_lookup=query_lookup))
    if owner_relation_plans:
        return _finalize_multi_hop_subqueries(query, planned, limit=limit)

    quoted_phrases = _ordered_unique(re.findall(r'"([^"]+)"', query))
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*", query)
    title_entities = []
    title_buffer: list[str] = []
    for token in raw_tokens:
        if token[:1].isupper() and len(token) > 2 and token.lower() not in MULTI_HOP_STOPWORDS:
            title_buffer.append(token)
            continue
        if title_buffer:
            title_entities.append(" ".join(title_buffer))
            title_buffer = []
    if title_buffer:
        title_entities.append(" ".join(title_buffer))

    identifier_terms = []
    for token in raw_tokens:
        parts = _split_identifier_token(token)
        if "_" in token or len(parts) > 1:
            identifier_terms.append(" ".join(parts))
            identifier_terms.extend(parts)

    safe_terms = [term for term in query_terms(query) if term not in MULTI_HOP_STOPWORDS]
    entity_terms = {
        term
        for entity in _ordered_unique(title_entities + quoted_phrases + identifier_terms)
        for term in query_terms(entity)
        if term not in MULTI_HOP_STOPWORDS
    }
    intent_terms = [term for term in safe_terms if term not in entity_terms]
    pairwise_terms = []
    for entity in _ordered_unique(title_entities + quoted_phrases + identifier_terms):
        entity_terms = [term for term in query_terms(entity) if term not in MULTI_HOP_STOPWORDS]
        for intent in intent_terms[:3]:
            if intent not in entity_terms:
                pairwise_terms.append(f"{entity} {intent}")

    planned.extend(("quoted_phrase", phrase) for phrase in quoted_phrases)
    planned.extend(("entity_or_title", entity) for entity in title_entities)
    if len(safe_terms) >= 2:
        planned.append(("history_safe_terms", " ".join(safe_terms)))
    planned.extend(("identifier", term) for term in identifier_terms)
    planned.extend(("entity_intent_pair", term) for term in pairwise_terms)
    return _finalize_multi_hop_subqueries(query, planned, limit=limit)


def _has_multi_hop_entity_intent_signal(subqueries: list[dict[str, Any]]) -> bool:
    entity_queries = [
        subquery
        for subquery in subqueries
        if str(subquery.get("source") or "") in {"entity_or_title", "quoted_phrase"}
    ]
    if not any(len(list(subquery.get("terms") or [])) >= 2 for subquery in entity_queries):
        return False
    sources = [str(subquery.get("source") or "") for subquery in subqueries]
    return sources.count("entity_intent_pair") >= 2


def _has_direct_deploy_target_multi_hop_signal(subqueries: list[dict[str, Any]]) -> bool:
    sources = [str(subquery.get("source") or "") for subquery in subqueries]
    return "direct_subject_fact" in sources and (
        "direct_subject_intent_fact" in sources or sources.count("direct_subject_intent_pair") >= 2
    )


def _has_semantic_multi_hop_composition_signal(query: str) -> bool:
    normalized = " ".join(query.lower().split())
    terms = set(query_terms(normalized))
    padded = f" {normalized} "
    return bool(terms.intersection(MULTI_HOP_SEMANTIC_AUTO_TERMS)) or any(
        phrase in padded for phrase in MULTI_HOP_SEMANTIC_AUTO_PHRASES
    )


def _owner_relation_multi_hop_basis_matches(
    selected_search_basis: str,
    *,
    query_lookup: dict[str, Any] | None,
) -> bool:
    if selected_search_basis in OWNER_RELATION_MULTI_HOP_LOOKUP_BASES:
        return True
    lookup_basis = str((query_lookup or {}).get("lookup_basis") or "")
    if lookup_basis not in OWNER_RELATION_MULTI_HOP_LOOKUP_BASES:
        return False
    return selected_search_basis == lookup_basis or selected_search_basis.startswith(f"{lookup_basis}-")


def _should_filter_parent_only_multi_hop_candidates(
    *,
    activation_reason: str,
    subquery: dict[str, Any],
) -> bool:
    if activation_reason == "fts-direct-deploy-target-compound-query":
        return True
    if activation_reason == "fts-direct-subject-compound-query":
        return True
    if activation_reason == "fts-identifier-compound-query":
        return str(subquery.get("source") or "") in {"identifier", "entity_intent_pair"}
    if activation_reason == "fts-entity-intent-compound-query":
        return str(subquery.get("source") or "") == "entity_intent_pair"
    return False


def _effective_multi_hop_retrieval_config(
    query: str,
    retrieval_config: dict[str, Any] | None,
    *,
    search_mode: str,
    query_lookup: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    resolved = dict(retrieval_config or {})
    if "multi_hop" in resolved:
        return resolved or None
    if search_mode not in {"none", "fallback", "semantic", "fts"}:
        return resolved or None
    selected_search_basis = str((query_lookup or {}).get("selected_search_basis") or "")
    owner_relation_multi_hop_basis = _owner_relation_multi_hop_basis_matches(
        selected_search_basis,
        query_lookup=query_lookup,
    )
    if search_mode == "fts":
        if selected_search_basis not in {
            "direct-subject",
            "direct-subject-alias",
            "direct-subject-phrase-alias",
            "direct-deploy-target-core",
        } and not owner_relation_multi_hop_basis:
            return resolved or None
    subqueries = decompose_multi_hop_query(
        query,
        max_subqueries=MULTI_HOP_MAX_SUBQUERIES,
        query_lookup=query_lookup,
    )
    if len(subqueries) < MULTI_HOP_AUTO_MIN_SUBQUERIES:
        return resolved or None
    if search_mode == "semantic" and not _has_semantic_multi_hop_composition_signal(query):
        resolved["multi_hop"] = {
            "enabled": False,
            "auto_enabled": False,
            "auto_evaluated": True,
            "suppression_reason": "semantic-query-lacks-composition-signal",
            "max_subqueries": MULTI_HOP_MAX_SUBQUERIES,
            "per_subquery_limit": MULTI_HOP_PER_SUBQUERY_LIMIT,
        }
        return resolved
    if search_mode == "semantic":
        activation_reason = "semantic-compound-query"
    elif search_mode == "none":
        activation_reason = "no-lexical-match-compound-query"
    elif search_mode == "fts":
        if selected_search_basis == "direct-deploy-target-core" and _has_direct_deploy_target_multi_hop_signal(subqueries):
            activation_reason = "fts-direct-deploy-target-compound-query"
        elif selected_search_basis in {
            "direct-subject",
            "direct-subject-alias",
            "direct-subject-phrase-alias",
        } and _has_direct_deploy_target_multi_hop_signal(subqueries):
            activation_reason = "fts-direct-subject-compound-query"
        elif owner_relation_multi_hop_basis and _has_direct_deploy_target_multi_hop_signal(subqueries):
            activation_reason = "fts-direct-subject-compound-query"
        elif any(str(subquery.get("source") or "") == "identifier" for subquery in subqueries):
            activation_reason = "fts-identifier-compound-query"
        elif _has_multi_hop_entity_intent_signal(subqueries):
            activation_reason = "fts-entity-intent-compound-query"
        else:
            return resolved or None
    else:
        activation_reason = "fallback-compound-query"
    resolved["multi_hop"] = {
        "enabled": True,
        "auto_enabled": True,
        "activation_reason": activation_reason,
        "max_subqueries": MULTI_HOP_MAX_SUBQUERIES,
        "per_subquery_limit": MULTI_HOP_PER_SUBQUERY_LIMIT,
    }
    return resolved


def apply_embedding_overlay(
    query: str,
    memories: list[MemoryRecord],
    retrieval: dict[str, Any],
    config: dict[str, Any] | None,
    *,
    retrieval_provider_config: dict[str, Any] | None = None,
    allow_network_providers: bool = False,
) -> tuple[list[MemoryRecord], dict[str, Any]]:
    overlay_config = _candidate_config(config, "embedding")
    enabled = bool(overlay_config.get("enabled", False))
    dims = int(overlay_config.get("dims", 64))
    model_id = str(overlay_config.get("model_id", PSEUDO_EMBEDDING_MODEL_ID))
    provider_id = overlay_config.get("provider_id")
    query_hash = sha256_text(query)
    query_vector_id = embedding_vector_id(model_id, query_hash)
    index_hash = _embedding_index_hash(memories, model_id, dims)
    provider_config_hash = retrieval_provider_config_hash(retrieval_provider_config) if retrieval_provider_config else None
    metadata = {
        "schema": EMBEDDING_RETRIEVAL_SCHEMA,
        "enabled": enabled,
        "provider": "local-pseudo" if enabled else "none",
        "provider_id": None,
        "auto_enabled": bool(overlay_config.get("auto_enabled", False)),
        "activation_reason": overlay_config.get("activation_reason"),
        "provider_config_hash": provider_config_hash,
        "model_id": model_id,
        "dims": dims,
        "query_vector_id": query_vector_id,
        "query_vector_hash": None,
        "index_id": "local-candidates-v1",
        "index_hash": index_hash,
        "network_calls_enabled": False,
        "retrieval_reproducibility": "deterministic-local",
        "fallback": not enabled,
        "disabled_reason": None if enabled else "disabled-by-config",
    }
    candidates = _candidate_by_id(retrieval)
    query_vector: list[float] | None = None
    local_query_vector: list[float] | None = None
    memory_vectors: dict[str, list[float]] = {}
    memory_vector_hashes: dict[str, str] = {}
    provider_result = None
    provider_rank_by_id: dict[str, int] = {}
    provider_excluded_reason_by_id: dict[str, str] = {}
    provider_memories = memories
    if enabled and memories:
        if provider_id:
            metadata["provider_id"] = str(provider_id)
            metadata["provider"] = str(provider_id)
            if retrieval_provider_config is None:
                metadata["fallback"] = True
                metadata["disabled_reason"] = "missing-provider-config"
            else:
                provider_memories, provider_excluded, provider_excluded_reason_by_id = _provider_active_candidate_scope(memories)
                metadata["provider_candidate_ids"] = [memory.id for memory in provider_memories]
                metadata["provider_excluded"] = provider_excluded
                metadata["provider_scope"] = "active-only"
                if not provider_memories:
                    metadata["fallback"] = True
                    metadata["disabled_reason"] = "no-active-candidates"
                else:
                    try:
                        provider_entry = resolve_embedding_provider(
                            retrieval_provider_config,
                            str(provider_id),
                            allow_network_providers=allow_network_providers,
                        )
                        provider_result = embed_texts(provider_entry, [query] + [memory.content for memory in provider_memories])
                        query_vector = provider_result.vectors[0]
                        memory_vectors = {
                            memory.id: provider_result.vectors[index + 1] for index, memory in enumerate(provider_memories)
                        }
                        memory_vector_hashes = {
                            memory.id: provider_result.vector_hashes[index + 1]
                            for index, memory in enumerate(provider_memories)
                        }
                        model_id = provider_result.model_id
                        dims = provider_result.dims
                        query_vector_id = embedding_vector_id(model_id, query_hash)
                        metadata.update(
                            {
                                "model_id": model_id,
                                "dims": dims,
                                "query_vector_id": query_vector_id,
                                "query_vector_hash": provider_result.vector_hashes[0],
                                "network_calls_enabled": bool(provider_result.network_call),
                                "retrieval_reproducibility": "provider-observed"
                                if provider_result.network_call
                                else "deterministic-local",
                                "fallback": False,
                                "disabled_reason": None,
                                "latency_ms": provider_result.latency_ms,
                                "merge_strategy": "active_slots_preserved_v1",
                            }
                        )
                    except ValueError as exc:
                        metadata["fallback"] = True
                        metadata["disabled_reason"] = _provider_disabled_reason(str(exc))
        local_query_vector = pseudo_embedding(query, dims=dims)
        if query_vector is None:
            query_vector = local_query_vector
            metadata["query_vector_hash"] = embedding_vector_hash(query_vector)
        if not metadata["disabled_reason"]:
            metadata["fallback"] = False
    elif enabled:
        metadata["fallback"] = True
        metadata["disabled_reason"] = "no-candidates"

    scored: list[tuple[MemoryRecord, float, int]] = []
    for memory in memories:
        candidate = candidates[memory.id]
        pre_rank = int(candidate.get("rank", len(scored) + 1))
        _set_candidate_rank(candidate, "pre_embedding_rank", pre_rank)
        memory_vector_id = embedding_vector_id(model_id, memory.content_hash)
        similarity = 0.0
        if memory.id in memory_vectors and query_vector is not None:
            similarity = cosine_similarity(query_vector, memory_vectors[memory.id])
        elif local_query_vector is not None:
            similarity = cosine_similarity(local_query_vector, pseudo_embedding(memory.content, dims=dims))
        _record_candidate_score_component(candidate, "embedding", similarity if enabled else 0.0)
        candidate["embedding"] = {
            "model_id": model_id,
            "provider_id": metadata.get("provider_id"),
            "memory_vector_id": memory_vector_id,
            "memory_vector_hash": memory_vector_hashes.get(memory.id)
            or (embedding_vector_hash(memory_vectors[memory.id]) if memory.id in memory_vectors else None),
            "content_hash": memory.content_hash,
            "score": round(similarity, 6) if enabled else None,
            "provider_eligible": bool(enabled and provider_id and memory.id not in provider_excluded_reason_by_id),
            "provider_excluded_reason": provider_excluded_reason_by_id.get(memory.id),
        }
        candidate.setdefault("features", {})["embedding"] = candidate["embedding"]
        candidate["provider_embedding_rank"] = None
        candidate.setdefault("features", {})["provider_embedding_rank"] = None
        scored.append((memory, similarity, pre_rank))

    if provider_result is not None:
        ranked_provider_memories = [
            item[0]
            for item in sorted(
                (
                    (memory, candidates[memory.id]["embedding"]["score"], int(candidates[memory.id].get("rank", len(memories) + 1)))
                    for memory in provider_memories
                ),
                key=lambda item: (-float(item[1]), item[2], item[0].id),
            )
        ]
        ordered, provider_rank_by_id = _merge_ranked_subset(memories, ranked_provider_memories)
        metadata["provider_ranked_ids"] = [memory.id for memory in ranked_provider_memories]
    elif enabled and memories and not metadata["fallback"]:
        ordered = [item[0] for item in sorted(scored, key=lambda item: (-item[1], item[2], item[0].id))]
    else:
        ordered = memories

    ordered_candidates = []
    for rank, memory in enumerate(ordered, start=1):
        candidate = candidates[memory.id]
        candidate["rank"] = rank
        _set_candidate_rank(candidate, "embedding_rank", rank)
        if memory.id in provider_rank_by_id:
            _set_candidate_rank(candidate, "provider_embedding_rank", provider_rank_by_id[memory.id])
        ordered_candidates.append(candidate)
    retrieval["candidates"] = ordered_candidates
    retrieval["embedding"] = metadata
    _annotate_overlay_ranking(
        retrieval,
        overlay_key="embedding",
        pre_rank_key="pre_embedding_rank",
        post_rank_key="embedding_rank",
        rank_key="embedding_rank",
        promoted_key="embedding_promoted",
        outranked_key="embedding_outranked",
        reason_key="embedding_outranked_reason",
    )
    return ordered, metadata


def _provider_active_candidate_scope(
    memories: list[MemoryRecord],
) -> tuple[list[MemoryRecord], list[dict[str, str]], dict[str, str]]:
    eligible = []
    excluded = []
    excluded_by_id = {}
    for memory in memories:
        if memory.status == "active":
            eligible.append(memory)
            continue
        reason = f"status={memory.status}"
        excluded.append({"memory_id": memory.id, "reason": reason})
        excluded_by_id[memory.id] = reason
    return eligible, excluded, excluded_by_id


def _provider_disabled_reason(error: str) -> str:
    if "network provider not allowed" in error:
        return "network-not-allowed"
    if "disabled" in error:
        return "provider-disabled"
    if "missing API key" in error:
        return "missing-api-key"
    if "missing-provider-config" in error:
        return "missing-provider-config"
    return "provider-error"


def _provider_reranker_candidate_scope(
    memories: list[MemoryRecord],
) -> tuple[list[MemoryRecord], list[dict[str, str]], dict[str, str]]:
    return _provider_active_candidate_scope(memories)


def _merge_ranked_subset(
    memories: list[MemoryRecord],
    ranked_subset: list[MemoryRecord],
) -> tuple[list[MemoryRecord], dict[str, int]]:
    reranked_ids = {memory.id for memory in ranked_subset}
    subset_iter = iter(ranked_subset)
    merged = []
    subset_rank_by_id = {
        memory.id: rank
        for rank, memory in enumerate(ranked_subset, start=1)
    }
    for memory in memories:
        if memory.id in reranked_ids:
            merged.append(next(subset_iter))
        else:
            merged.append(memory)
    return merged, subset_rank_by_id


def apply_reranker(
    query: str,
    memories: list[MemoryRecord],
    retrieval: dict[str, Any],
    config: dict[str, Any] | None,
    *,
    retrieval_provider_config: dict[str, Any] | None = None,
    allow_network_providers: bool = False,
) -> tuple[list[MemoryRecord], dict[str, Any]]:
    reranker_config = _candidate_config(config, "reranker")
    enabled = bool(reranker_config.get("enabled", False))
    hybrid = retrieval.get("hybrid") if isinstance(retrieval.get("hybrid"), dict) else {}
    hybrid_applied = bool(hybrid.get("applied"))
    provider_id = reranker_config.get("provider_id")
    requested_reranker_id = str(reranker_config.get("reranker_id", reranker_config.get("model_id", "none")))
    if enabled and requested_reranker_id == "none":
        requested_reranker_id = DETERMINISTIC_RERANKER_ID
    reranker_id = DETERMINISTIC_RERANKER_ID if enabled and provider_id else requested_reranker_id
    provider_config_hash = retrieval_provider_config_hash(retrieval_provider_config) if retrieval_provider_config else None
    metadata = {
        "schema": RERANKER_SCHEMA,
        "enabled": enabled,
        "model_id": reranker_id,
        "reranker_id": reranker_id,
        "requested_reranker_id": requested_reranker_id if enabled else None,
        "provider": str(provider_id) if provider_id else ("local:deterministic" if enabled else "none"),
        "provider_id": str(provider_id) if provider_id else None,
        "auto_enabled": bool(reranker_config.get("auto_enabled", False)),
        "activation_reason": reranker_config.get("activation_reason"),
        "provider_config_hash": provider_config_hash,
        "network_calls_enabled": False,
        "retrieval_reproducibility": "deterministic-local",
        "config_hash": sha256_text(stable_json(reranker_config)),
        "fallback": not enabled,
        "disabled_reason": None if enabled else "disabled-by-config",
    }
    candidates = _candidate_by_id(retrieval)
    terms = query_terms(query)
    provider_result = None
    provider_scores: dict[str, float] = {}
    provider_score_hashes: dict[str, str] = {}
    provider_rank_by_id: dict[str, int] = {}
    provider_excluded_reason_by_id: dict[str, str] = {}
    provider_memories = memories
    if enabled and provider_id and len(memories) >= 2:
        provider_memories, provider_excluded, provider_excluded_reason_by_id = _provider_reranker_candidate_scope(memories)
        metadata["provider_candidate_ids"] = [memory.id for memory in provider_memories]
        metadata["provider_excluded"] = provider_excluded
        metadata["provider_scope"] = "active-only"
        if retrieval_provider_config is None:
            metadata["fallback"] = True
            metadata["disabled_reason"] = "missing-provider-config"
        elif len(provider_memories) < 2:
            metadata["fallback"] = True
            metadata["disabled_reason"] = "not-enough-active-candidates"
        else:
            try:
                provider_entry = resolve_reranker_provider(
                    retrieval_provider_config,
                    str(provider_id),
                    allow_network_providers=allow_network_providers,
                )
                provider_result = rerank_texts(
                    provider_entry,
                    query,
                    [f"{memory.content} {' '.join(memory.labels)}".strip() for memory in provider_memories],
                )
                provider_scores = {
                    memory.id: provider_result.scores[index]
                    for index, memory in enumerate(provider_memories)
                }
                provider_score_hashes = {
                    memory.id: provider_result.score_hashes[index]
                    for index, memory in enumerate(provider_memories)
                }
                metadata.update(
                    {
                        "model_id": provider_result.model_id,
                        "reranker_id": provider_result.reranker_id,
                        "network_calls_enabled": bool(provider_result.network_call),
                        "retrieval_reproducibility": "provider-observed"
                        if provider_result.network_call
                        else "deterministic-local",
                        "fallback": False,
                        "disabled_reason": None,
                        "latency_ms": provider_result.latency_ms,
                        "merge_strategy": "active_slots_preserved_v1",
                    }
                )
            except ValueError as exc:
                metadata["fallback"] = True
                metadata["disabled_reason"] = _provider_disabled_reason(str(exc))

    scored: list[tuple[MemoryRecord, float, int]] = []
    for memory in memories:
        candidate = candidates[memory.id]
        pre_rank = int(candidate.get("rank", len(scored) + 1))
        _set_candidate_rank(candidate, "pre_rerank_rank", pre_rank)
        haystack = f"{memory.content} {' '.join(memory.labels)}"
        lexical_score = 0.0
        if enabled and terms:
            lexical_score = _term_match_count(haystack, terms) / len(terms)
        hybrid_semantic_score = candidate.get("semantic_backfill_score") if hybrid_applied else None
        local_score = lexical_score
        if enabled and isinstance(hybrid_semantic_score, (int, float)):
            local_score = float(hybrid_semantic_score)
        reranker_score = provider_scores.get(memory.id, local_score) if enabled else 0.0
        _record_candidate_score_component(candidate, "reranker", reranker_score if enabled else 0.0)
        candidate["reranker_score"] = round(reranker_score, 6) if enabled else None
        candidate.setdefault("features", {})["reranker_score"] = candidate["reranker_score"]
        candidate["reranker"] = {
            "provider_id": metadata.get("provider_id"),
            "model_id": metadata["model_id"],
            "reranker_id": metadata["reranker_id"],
            "score": candidate["reranker_score"],
            "score_hash": provider_score_hashes.get(memory.id),
            "local_score": round(local_score, 6) if enabled else None,
            "local_lexical_score": round(lexical_score, 6) if enabled else None,
            "hybrid_semantic_score": (
                round(float(hybrid_semantic_score), 6)
                if isinstance(hybrid_semantic_score, (int, float))
                else None
            ),
            "local_strategy": (
                "hybrid_semantic_backfill_score_v1"
                if enabled and isinstance(hybrid_semantic_score, (int, float))
                else ("lexical_term_match_v1" if enabled else None)
            ),
            "provider_eligible": bool(enabled and provider_id and memory.id not in provider_excluded_reason_by_id),
            "provider_excluded_reason": provider_excluded_reason_by_id.get(memory.id),
        }
        candidate.setdefault("features", {})["reranker"] = candidate["reranker"]
        candidate["provider_rerank_rank"] = None
        candidate.setdefault("features", {})["provider_rerank_rank"] = None
        scored.append((memory, reranker_score, pre_rank))

    if enabled and len(memories) < 2:
        metadata["fallback"] = True
        metadata["disabled_reason"] = "not-enough-candidates"
        ordered = memories
    elif provider_result is not None:
        reranked_provider_memories = [
            item[0]
            for item in sorted(
                (
                    (memory, provider_scores[memory.id], int(candidates[memory.id].get("rank", len(memories) + 1)))
                    for memory in provider_memories
                ),
                key=lambda item: (-item[1], item[2], item[0].id),
            )
        ]
        ordered, provider_rank_by_id = _merge_ranked_subset(memories, reranked_provider_memories)
        metadata["provider_ranked_ids"] = [memory.id for memory in reranked_provider_memories]
    elif enabled:
        if not provider_id or provider_result is not None:
            metadata["fallback"] = False
        ordered = [item[0] for item in sorted(scored, key=lambda item: (-item[1], item[2], item[0].id))]
    else:
        ordered = memories

    ordered_candidates = []
    for rank, memory in enumerate(ordered, start=1):
        candidate = candidates[memory.id]
        candidate["rank"] = rank
        _set_candidate_rank(candidate, "post_rerank_rank", rank)
        if memory.id in provider_rank_by_id:
            _set_candidate_rank(candidate, "provider_rerank_rank", provider_rank_by_id[memory.id])
        ordered_candidates.append(candidate)
    retrieval["candidates"] = ordered_candidates
    retrieval["reranker"] = metadata
    _annotate_overlay_ranking(
        retrieval,
        overlay_key="reranker",
        pre_rank_key="pre_rerank_rank",
        post_rank_key="post_rerank_rank",
        rank_key="reranker_rank",
        promoted_key="reranker_promoted",
        outranked_key="reranker_outranked",
        reason_key="reranker_outranked_reason",
    )
    return ordered, metadata


def _effective_retrieval_config(
    config: dict[str, Any] | None,
    *,
    semantic_rescue_applied: bool,
    hybrid_backfill_applied: bool,
    candidate_count: int,
) -> dict[str, Any] | None:
    resolved = dict(config or {})
    auto_fusion_reason = None
    if semantic_rescue_applied:
        auto_fusion_reason = "semantic-rescue"
    elif hybrid_backfill_applied:
        auto_fusion_reason = "hybrid-semantic-backfill"
    if auto_fusion_reason is None:
        return resolved or None
    if "embedding" not in resolved:
        resolved["embedding"] = {
            "enabled": True,
            "model_id": PSEUDO_EMBEDDING_MODEL_ID,
            "auto_enabled": True,
            "activation_reason": auto_fusion_reason,
        }
    if candidate_count > 1 and "reranker" not in resolved:
        resolved["reranker"] = {
            "enabled": True,
            "reranker_id": DETERMINISTIC_RERANKER_ID,
            "auto_enabled": True,
            "activation_reason": auto_fusion_reason,
        }
    return resolved or None


def _ranking_payload(
    memories: list[MemoryRecord],
    *,
    query: str,
    query_terms: list[str],
    search_query: str,
    search_terms: list[str],
    fts_query: str,
    search_mode: str,
    bm25_scores: dict[str, float | None],
    query_lookup: dict[str, Any],
    candidate_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    candidates = []
    candidate_metadata = candidate_metadata or {}
    for rank, memory in enumerate(memories, start=1):
        bm25_score = bm25_scores.get(memory.id)
        features = _rank_features(
            memory,
            terms=search_terms,
            search_query=search_query,
            bm25_score=bm25_score,
            search_mode=search_mode,
            query_lookup=query_lookup,
        )
        metadata = candidate_metadata.get(memory.id, {})
        candidate = {
            "memory_id": memory.id,
            "rank": rank,
            "search_mode": search_mode,
            "mode": search_mode,
            "bm25": bm25_score,
            "score": _rank_score(features),
            "score_components": features["score_components"],
            "matched_fields": features["matched_fields"],
            "features": features,
        }
        for key in (
            "fts_window_rank",
            "fts_preselection_rank",
            "pre_hybrid_rank",
            "hybrid_candidate_source",
            "structured_fact_candidate",
            "semantic_backfill_score",
            "semantic_backfill_term_overlap",
            "fusion_rank",
            "fusion_score",
            "fusion_sources",
            "pre_multi_hop_rank",
            "multi_hop_rank",
            "introduced_by_subquery_id",
            "multi_hop_subquery_ids",
            "multi_hop_duplicate_count",
            "multi_hop_fusion_rank",
            "multi_hop_fusion_score",
            "multi_hop_fusion_sources",
            "multi_hop_fusion_source_count",
            "multi_hop_rank_delta",
            "multi_hop_promoted_by_fusion",
            "multi_hop_outranked_by_fusion",
            "multi_hop_outranked_reason",
            "observation_seq",
            "temporal_support_candidate",
            "temporal_support_kind",
            "support_expansion_candidate",
            "support_expansion_kind",
            "support_expansion_rank",
            "support_expansion_nucleus_ids",
        ):
            candidate[key] = metadata.get(key)
            features[key] = metadata.get(key)
        candidates.append(candidate)
    return {
        "schema": RETRIEVAL_SCHEMA,
        "query": query,
        "query_terms": query_terms,
        "search_query": search_query,
        "search_terms": search_terms,
        "fts_query": fts_query,
        "search_mode": search_mode,
        "mode": search_mode,
        "candidate_limit": RETRIEVAL_CANDIDATE_LIMIT,
        "limit": RETRIEVAL_CANDIDATE_LIMIT,
        "rank_config": RETRIEVAL_RANK_CONFIG,
        "query_lookup": query_lookup,
        "candidates": candidates,
    }


def _rank_lookup(retrieval: dict[str, Any]) -> dict[str, int]:
    return {
        str(candidate["memory_id"]): int(candidate["rank"])
        for candidate in retrieval.get("candidates", [])
        if "memory_id" in candidate and "rank" in candidate
    }


def _reciprocal_rank_fusion(
    source_rankings: dict[str, list[str]],
    *,
    selected_candidate_ids: list[str] | None = None,
    k: int = RRF_K,
) -> dict[str, Any]:
    selected_set = set(selected_candidate_ids or [])
    candidate_scores: dict[str, dict[str, Any]] = {}
    normalized_sources: dict[str, list[str]] = {}
    for source, memory_ids in source_rankings.items():
        ordered_ids = []
        seen_ids: set[str] = set()
        for memory_id in memory_ids:
            memory_id = str(memory_id)
            if not memory_id or memory_id in seen_ids:
                continue
            seen_ids.add(memory_id)
            ordered_ids.append(memory_id)
        if not ordered_ids:
            continue
        normalized_sources[source] = ordered_ids
        for rank, memory_id in enumerate(ordered_ids, start=1):
            contribution = round(1.0 / (float(k) + rank), 9)
            entry = candidate_scores.setdefault(
                memory_id,
                {
                    "memory_id": memory_id,
                    "score": 0.0,
                    "best_source_rank": rank,
                    "source_contributions": [],
                    "selected": memory_id in selected_set,
                },
            )
            entry["score"] = round(float(entry["score"]) + contribution, 9)
            entry["best_source_rank"] = min(int(entry["best_source_rank"]), rank)
            entry["source_contributions"].append(
                {
                    "source": source,
                    "rank": rank,
                    "score": contribution,
                }
            )

    ranked_candidates = sorted(
        candidate_scores.values(),
        key=lambda item: (-float(item["score"]), int(item["best_source_rank"]), str(item["memory_id"])),
    )
    rank_by_id = {
        str(item["memory_id"]): rank
        for rank, item in enumerate(ranked_candidates, start=1)
    }
    for item in ranked_candidates:
        item["fusion_rank"] = rank_by_id[str(item["memory_id"])]
    return {
        "schema": RANK_FUSION_SCHEMA,
        "strategy": "reciprocal_rank_fusion_v1",
        "k": int(k),
        "source_rankings": normalized_sources,
        "selected_candidate_ids": list(selected_candidate_ids or []),
        "ranked_candidate_ids": [str(item["memory_id"]) for item in ranked_candidates],
        "candidate_scores": ranked_candidates,
    }


def _temporal_support_fusion_source_rankings(
    *,
    candidate_ids_in_rank_order: list[str],
    selection: dict[str, Any],
) -> dict[str, list[str]]:
    selection_reason = str(selection.get("selection_reason") or "")
    support_ids = [
        str(memory_id)
        for memory_id in (
            list(selection.get("selected_target_support_ids", []))
            + list(selection.get("selected_relation_support_ids", []))
            + list(selection.get("selected_current_support_ids", []))
        )
        if str(memory_id)
    ]
    mutation_anchor_ids = [
        str(memory_id)
        for memory_id in selection.get("selected_mutation_anchor_ids", [])
        if str(memory_id)
    ]
    update_pair_ids = [
        str(memory_id)
        for memory_id in (
            list(selection.get("selected_superseded_ids", []))
            + ([selection.get("selected_update_current_id")] if selection.get("selected_update_current_id") else [])
        )
        if str(memory_id)
    ]
    current_support_ids = [
        str(memory_id)
        for memory_id in selection.get("selected_current_support_ids", [])
        if str(memory_id)
    ]
    relation_update_pair_ids = [
        str(memory_id)
        for memory_id in (
            list(selection.get("selected_superseded_ids", []))
            + ([selection.get("selected_relation_current_id")] if selection.get("selected_relation_current_id") else [])
        )
        if str(memory_id)
    ]
    if not selection.get("selection_exclusions") and not support_ids and not mutation_anchor_ids:
        return {}
    source_rankings: dict[str, list[str]] = {
        "baseline": [str(memory_id) for memory_id in candidate_ids_in_rank_order if str(memory_id)]
    }
    selected_ids = [str(memory_id) for memory_id in selection.get("selected_ids", []) if str(memory_id)]
    if len(selected_ids) > 1:
        source_rankings["temporal_selection"] = selected_ids
    injection_ids = [str(memory_id) for memory_id in selection.get("injection_preferred_ids", []) if str(memory_id)]
    if len(injection_ids) > 1:
        source_rankings["temporal_injection"] = injection_ids
    if mutation_anchor_ids:
        source_rankings["temporal_mutation_anchor"] = mutation_anchor_ids
    if len(update_pair_ids) > 1 and current_support_ids:
        source_rankings["temporal_update_pair"] = update_pair_ids
    if selection_reason == "history-query-terms" and len(relation_update_pair_ids) > 1 and current_support_ids:
        source_rankings["temporal_history_relation_pair"] = relation_update_pair_ids
    if selection_reason == "update-history-query-terms" and len(relation_update_pair_ids) > 1 and current_support_ids:
        source_rankings["temporal_update_relation_pair"] = relation_update_pair_ids
    if selection_reason == "earliest-history-query-terms" and len(relation_update_pair_ids) > 1 and current_support_ids:
        source_rankings["temporal_earliest_relation_pair"] = relation_update_pair_ids
    if len(source_rankings) <= 1:
        return {}
    return source_rankings


def _temporal_fusion_signal(selection: dict[str, Any]) -> str | None:
    selection_reason = str(selection.get("selection_reason") or "")
    if any(str(memory_id) for memory_id in selection.get("selected_mutation_anchor_ids", [])):
        return "temporal_mutation_rrf_score_v1"
    update_pair_ids = [
        str(memory_id)
        for memory_id in (
            list(selection.get("selected_superseded_ids", []))
            + ([selection.get("selected_update_current_id")] if selection.get("selected_update_current_id") else [])
        )
        if str(memory_id)
    ]
    current_support_ids = [
        str(memory_id)
        for memory_id in selection.get("selected_current_support_ids", [])
        if str(memory_id)
    ]
    if len(update_pair_ids) > 1 and current_support_ids:
        return "temporal_update_pair_rrf_score_v1"
    relation_update_pair_ids = [
        str(memory_id)
        for memory_id in (
            list(selection.get("selected_superseded_ids", []))
            + ([selection.get("selected_relation_current_id")] if selection.get("selected_relation_current_id") else [])
        )
        if str(memory_id)
    ]
    if selection_reason == "history-query-terms" and len(relation_update_pair_ids) > 1 and current_support_ids:
        return "temporal_history_relation_pair_rrf_score_v1"
    if selection_reason == "update-history-query-terms" and len(relation_update_pair_ids) > 1 and current_support_ids:
        return "temporal_update_relation_pair_rrf_score_v1"
    if selection_reason == "earliest-history-query-terms" and len(relation_update_pair_ids) > 1 and current_support_ids:
        return "temporal_earliest_relation_pair_rrf_score_v1"
    support_ids = (
        list(selection.get("selected_target_support_ids", []))
        + list(selection.get("selected_relation_support_ids", []))
        + list(selection.get("selected_current_support_ids", []))
    )
    if selection.get("selection_exclusions") or any(str(memory_id) for memory_id in support_ids):
        return "temporal_support_rrf_score_v1"
    return None


def _temporal_fusion_basis(signal: str | None) -> str | None:
    if signal == "temporal_mutation_rrf_score_v1":
        return "mutation_anchor"
    if signal == "temporal_update_pair_rrf_score_v1":
        return "update_pair"
    if signal == "temporal_history_relation_pair_rrf_score_v1":
        return "history_relation_pair"
    if signal == "temporal_update_relation_pair_rrf_score_v1":
        return "update_relation_pair"
    if signal == "temporal_earliest_relation_pair_rrf_score_v1":
        return "earliest_relation_pair"
    if signal == "temporal_support_rrf_score_v1":
        return "support_chain"
    return None


def _packing_priority(
    memory: MemoryRecord,
    *,
    candidate: dict[str, Any] | None,
    candidate_count: int,
    prefer_temporal_fusion_rank: bool = False,
    prefer_multi_hop_fusion_rank: bool = False,
    prefer_reranker_rank: bool = False,
    prefer_embedding_rank: bool = False,
    prefer_hybrid_semantic_rank: bool = False,
    allow_default_current_selection_override: bool = False,
) -> int:
    candidate = candidate or {}
    features = candidate.get("features", {})
    selected_by_temporal_strategy = bool(
        candidate.get("selected_by_temporal_strategy", features.get("selected_by_temporal_strategy", False))
    )
    multi_hop_fusion_rank = candidate.get("multi_hop_fusion_rank", features.get("multi_hop_fusion_rank"))
    temporal_fusion_rank = candidate.get("temporal_fusion_rank", features.get("temporal_fusion_rank"))
    reranker_rank = candidate.get("reranker_rank", features.get("reranker_rank"))
    embedding_rank = candidate.get("embedding_rank", features.get("embedding_rank"))
    hybrid_semantic_rank = candidate.get("hybrid_semantic_rank", features.get("hybrid_semantic_rank"))
    temporal_injection_rank = candidate.get("temporal_injection_rank", features.get("temporal_injection_rank"))
    temporal_selection_rank = candidate.get("temporal_selection_rank", features.get("temporal_selection_rank"))
    if (
        prefer_temporal_fusion_rank
        and selected_by_temporal_strategy
        and isinstance(temporal_fusion_rank, int)
        and temporal_fusion_rank > 0
    ):
        rank = temporal_fusion_rank
    elif isinstance(multi_hop_fusion_rank, int) and multi_hop_fusion_rank > 0 and prefer_multi_hop_fusion_rank:
        rank = multi_hop_fusion_rank
    elif (
        prefer_reranker_rank
        and (not selected_by_temporal_strategy or allow_default_current_selection_override)
        and isinstance(reranker_rank, int)
        and reranker_rank > 0
    ):
        rank = reranker_rank
    elif (
        prefer_embedding_rank
        and (not selected_by_temporal_strategy or allow_default_current_selection_override)
        and isinstance(embedding_rank, int)
        and embedding_rank > 0
    ):
        rank = embedding_rank
    elif (
        prefer_hybrid_semantic_rank
        and (not selected_by_temporal_strategy or allow_default_current_selection_override)
        and isinstance(hybrid_semantic_rank, int)
        and hybrid_semantic_rank > 0
    ):
        rank = hybrid_semantic_rank
    elif (
        selected_by_temporal_strategy
        and isinstance(temporal_injection_rank, int)
        and temporal_injection_rank > 0
    ):
        rank = temporal_injection_rank
    elif (
        selected_by_temporal_strategy
        and isinstance(temporal_selection_rank, int)
        and temporal_selection_rank > 0
    ):
        rank = temporal_selection_rank
    else:
        rank = int(candidate.get("rank", candidate_count + 1))
    score = int(round(float(candidate.get("score", 0.0)) * 100))
    authority = int(features.get("authority_rank", authority_rank(memory.authority)))
    trust = int(round(float(features.get("trust", memory.trust)) * 100))
    matched_fields = len(candidate.get("matched_fields", features.get("matched_fields", [])))
    temporal_state = str(candidate.get("temporal_state", features.get("temporal_state", "current")))
    return (
        max(candidate_count - rank + 1, 0) * 10_000
        + score * 10
        + authority * 250
        + trust * 2
        + matched_fields * 100
        + (500 if temporal_state == "current" else 0)
        + (750 if memory.type == "policy" else 0)
    )


def _packing_state_is_better(
    candidate_state: tuple[int, int, int, tuple[int, ...]],
    existing_state: tuple[int, int, int, tuple[int, ...]] | None,
) -> bool:
    if existing_state is None:
        return True
    candidate_key = (
        candidate_state[0],
        candidate_state[1],
        -candidate_state[2],
        tuple(-rank for rank in candidate_state[3]),
    )
    existing_key = (
        existing_state[0],
        existing_state[1],
        -existing_state[2],
        tuple(-rank for rank in existing_state[3]),
    )
    return candidate_key > existing_key


def _mixed_owner_contact_role_reservation(
    authorized_entries: list[dict[str, Any]],
    retrieval: dict[str, Any],
) -> dict[str, Any] | None:
    query_lookup = retrieval.get("query_lookup") if isinstance(retrieval.get("query_lookup"), dict) else {}
    if str(query_lookup.get("selected_search_basis") or "") != "direct-subject":
        return None

    multi_hop = retrieval.get("multi_hop") if isinstance(retrieval.get("multi_hop"), dict) else {}
    subqueries = multi_hop.get("subqueries")
    if not isinstance(subqueries, list) or not subqueries:
        return None

    owner_subquery_ids: set[str] = set()
    contact_subquery_ids: set[str] = set()
    rollback_subquery_ids: set[str] = set()
    for subquery in subqueries:
        if not isinstance(subquery, dict):
            continue
        subquery_id = str(subquery.get("id") or "")
        if not subquery_id:
            continue
        terms = {str(term).lower() for term in subquery.get("terms", []) if str(term)}
        if not terms:
            continue
        if {"rollback", "policy"}.issubset(terms):
            rollback_subquery_ids.add(subquery_id)
        if "contact" in terms:
            contact_subquery_ids.add(subquery_id)
        elif terms.intersection({"owner", "maintainer"}):
            owner_subquery_ids.add(subquery_id)

    if not owner_subquery_ids or not contact_subquery_ids or not rollback_subquery_ids:
        return None

    candidate_by_id = {
        str(candidate.get("memory_id")): candidate
        for candidate in retrieval.get("candidates", [])
        if isinstance(candidate, dict) and str(candidate.get("memory_id") or "")
    }
    ordered_entries = sorted(
        authorized_entries,
        key=lambda entry: (
            int(entry["rank"]),
            int(entry["packing_rank"]),
            str(entry["memory"].id),
        ),
    )
    owner_entry = next(
        (
            entry
            for entry in ordered_entries
            if str((candidate_by_id.get(entry["memory"].id) or {}).get("introduced_by_subquery_id") or "")
            in owner_subquery_ids
        ),
        None,
    )
    contact_entry = next(
        (
            entry
            for entry in ordered_entries
            if str((candidate_by_id.get(entry["memory"].id) or {}).get("introduced_by_subquery_id") or "")
            in contact_subquery_ids
        ),
        None,
    )
    if owner_entry is None or contact_entry is None:
        return None

    requested_ids = [owner_entry["memory"].id]
    if contact_entry["memory"].id not in requested_ids:
        requested_ids.append(contact_entry["memory"].id)
    return {
        "strategy": "mixed_owner_contact_role_pair_v1",
        "reason": "mixed-owner-contact-keep-role-facts-before-rollback",
        "requested_ids": requested_ids,
        "applied_ids": [],
        "applied": False,
        "blocked_reason": None,
    }


def _chronology_sort_key(memory: MemoryRecord, *, temporal_rank: int) -> tuple[str, str, int, str]:
    return (
        memory.created_at,
        memory.updated_at,
        temporal_rank,
        memory.id,
    )


def _chronology_ordered_ids(
    memory_ids: list[str],
    *,
    candidate_by_id: dict[str, MemoryRecord],
    rank_by_id: dict[str, int],
    reverse: bool = False,
) -> list[str]:
    return [
        memory.id
        for memory in sorted(
            (candidate_by_id[memory_id] for memory_id in memory_ids if memory_id in candidate_by_id),
            key=lambda memory: _chronology_sort_key(memory, temporal_rank=rank_by_id.get(memory.id, len(rank_by_id) + 1)),
            reverse=reverse,
        )
    ]


def _target_history_support_ordered_ids(
    *,
    query_lookup: dict[str, Any],
    current_ids: list[str],
    candidate_by_id: dict[str, MemoryRecord],
    rank_by_id: dict[str, int],
) -> list[str]:
    target_history = dict((query_lookup or {}).get("target_history", {}))
    if not target_history.get("applied") or len(current_ids) < 2:
        return []
    target_terms = [str(term) for term in query_terms(str(target_history.get("target_query") or "")) if str(term)]
    if not target_terms:
        return []
    history_terms = {
        str(term)
        for term in target_history.get("history_terms", [])
        if str(term)
    }
    target_current_ids: list[str] = []
    support_ids: list[str] = []
    for memory_id in current_ids:
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        haystack_terms = set(_query_tokens(f"{memory.content} {' '.join(memory.labels)}"))
        if all(term in haystack_terms for term in target_terms):
            target_current_ids.append(memory_id)
        else:
            support_ids.append(memory_id)
    if len(target_current_ids) != 1 or not support_ids:
        return []
    ordered_support_ids = _chronology_ordered_ids(
        support_ids,
        candidate_by_id=candidate_by_id,
        rank_by_id=rank_by_id,
    )
    ordered_target_ids = _chronology_ordered_ids(
        target_current_ids,
        candidate_by_id=candidate_by_id,
        rank_by_id=rank_by_id,
    )
    if not ordered_support_ids or not ordered_target_ids:
        return []
    history_support_ids = []
    for memory_id in ordered_support_ids:
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        haystack_terms = set(_query_tokens(f"{memory.content} {' '.join(memory.labels)}"))
        if history_terms.intersection(haystack_terms):
            history_support_ids.append(memory_id)
    selected_support_id = (history_support_ids or ordered_support_ids)[0]
    return [selected_support_id] + ordered_target_ids


def _current_update_preferred_ids(
    *,
    query_lookup: dict[str, Any],
    current_ids: list[str],
    candidate_by_id: dict[str, MemoryRecord],
) -> list[str]:
    current_lookup = dict((query_lookup or {}).get("current", {}))
    matched_current_terms = [str(term) for term in current_lookup.get("matched_terms", []) if str(term)]
    anchor_terms = [str(term) for term in current_lookup.get("update_anchor_terms", []) if str(term)]
    if not matched_current_terms or len(current_ids) < 2 or not anchor_terms:
        return []

    anchor_term_set = set(anchor_terms)
    update_candidate_ids: list[str] = []
    sibling_ids: list[str] = []
    for memory_id in current_ids:
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        update_signature = _lexical_update_signature(memory)
        if update_signature is None:
            sibling_ids.append(memory_id)
            continue
        subject_terms = {
            str(term)
            for term in query_terms(str(update_signature.get("subject_key") or ""))
            if str(term)
        }
        if len(anchor_term_set.intersection(subject_terms)) < 2:
            sibling_ids.append(memory_id)
            continue
        update_candidate_ids.append(memory_id)

    if len(update_candidate_ids) != 1 or not sibling_ids:
        return []
    return update_candidate_ids


def _chronology_mutation_injection_preference(
    *,
    selection: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
    temporal_state_by_id: dict[str, str],
) -> dict[str, Any]:
    selected_ids = [str(memory_id) for memory_id in selection.get("selected_ids", []) if str(memory_id)]
    default_preference = {
        "applied": False,
        "strategy": None,
        "reason": None,
        "order": selection.get("selection_order"),
        "preferred_ids": selected_ids,
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
    }
    if selection.get("selection_reason") != "chronology-query-terms" or len(selected_ids) < 2:
        return default_preference

    selected_temporal_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) in {"current", "superseded"}
    ]
    if len(selected_temporal_ids) < 2:
        return default_preference

    explicit_update_ids = [
        memory_id
        for memory_id in selected_ids
        if memory_id in candidate_by_id and _lexical_update_signature(candidate_by_id[memory_id]) is not None
    ]
    if not explicit_update_ids:
        return default_preference

    ordered_explicit_update_ids = list(reversed(explicit_update_ids))
    mutation_anchor_id = ordered_explicit_update_ids[0]
    return {
        "applied": True,
        "strategy": "chronology_mutation_anchor_first_v1",
        "reason": "chronology-explicit-update-anchor",
        "order": (
            "explicit_updates_then_timeline_support"
            if len(ordered_explicit_update_ids) > 1
            else "explicit_update_then_timeline_support"
        ),
        "preferred_ids": ordered_explicit_update_ids + [
            memory_id for memory_id in selected_ids if memory_id not in ordered_explicit_update_ids
        ],
        "selected_mutation_anchor_id": mutation_anchor_id,
        "selected_mutation_anchor_ids": ordered_explicit_update_ids,
    }


def _chronology_relation_current_anchor_injection_preference(
    *,
    selection: dict[str, Any],
    query_lookup: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
    temporal_state_by_id: dict[str, str],
) -> dict[str, Any]:
    selected_ids = [str(memory_id) for memory_id in selection.get("selected_ids", []) if str(memory_id)]
    default_preference = {
        "applied": False,
        "strategy": None,
        "reason": None,
        "order": selection.get("selection_order"),
        "preferred_ids": selected_ids,
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_relation_current_id": None,
        "selected_relation_support_ids": [],
        "selected_update_current_id": None,
        "selected_current_support_ids": [],
        "current_anchor_id": None,
    }
    if str(selection.get("selection_reason") or "") != "chronology-query-terms":
        return default_preference

    selected_search_terms = [
        str(term)
        for term in (query_lookup or {}).get("selected_search_terms", [])
        if str(term)
    ]
    selected_search_basis = str((query_lookup or {}).get("selected_search_basis") or "")
    lookup_relation = str((query_lookup or {}).get("lookup_relation") or "")
    basis_supports_relation_anchor = selected_search_basis.startswith("chronology-subject-core")
    if len(selected_search_terms) < 2 or (not basis_supports_relation_anchor and not lookup_relation):
        return default_preference

    selected_superseded_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) == "superseded"
    ]
    selected_current_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) == "current"
    ]
    if not selected_superseded_ids or len(selected_current_ids) < 2:
        return default_preference

    search_term_set = set(selected_search_terms)
    relation_current_ids: list[str] = []
    support_current_ids: list[str] = []
    for memory_id in selected_current_ids:
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        relation_signature = _lexical_conflict_signature(memory)
        if relation_signature is None:
            support_current_ids.append(memory_id)
            continue
        if lookup_relation and str(relation_signature.get("relation") or "") != lookup_relation:
            support_current_ids.append(memory_id)
            continue
        subject_terms = {
            str(term)
            for term in query_terms(str(relation_signature.get("subject_key") or ""))
            if str(term)
        }
        if len(search_term_set.intersection(subject_terms)) >= min(2, len(subject_terms)):
            relation_current_ids.append(memory_id)
        else:
            support_current_ids.append(memory_id)
    if len(relation_current_ids) != 1 or not support_current_ids:
        return default_preference

    relation_current_id = relation_current_ids[0]
    prioritized_ids = selected_superseded_ids + [relation_current_id] + support_current_ids
    return {
        "applied": True,
        "strategy": "chronology_relation_current_anchor_first_v1",
        "reason": "chronology-keep-explicit-current-relation",
        "order": "selected_stale_then_relation_current_then_current_support",
        "preferred_ids": prioritized_ids + [
            memory_id
            for memory_id in selected_ids
            if memory_id not in set(prioritized_ids)
        ],
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_relation_current_id": relation_current_id,
        "selected_relation_support_ids": support_current_ids,
        "selected_update_current_id": None,
        "selected_current_support_ids": support_current_ids,
        "current_anchor_id": relation_current_id,
    }


def _history_target_current_anchor_injection_preference(
    *,
    selection: dict[str, Any],
    query_lookup: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
    temporal_state_by_id: dict[str, str],
) -> dict[str, Any]:
    selected_ids = [str(memory_id) for memory_id in selection.get("selected_ids", []) if str(memory_id)]
    default_preference = {
        "applied": False,
        "strategy": None,
        "reason": None,
        "order": selection.get("selection_order"),
        "preferred_ids": selected_ids,
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_update_current_id": None,
        "selected_current_support_ids": [],
        "current_anchor_id": None,
    }
    target_history = dict((query_lookup or {}).get("target_history", {}))
    if not target_history.get("applied"):
        return default_preference

    target_terms = [str(term) for term in query_terms(str(target_history.get("target_query") or "")) if str(term)]
    if not target_terms:
        return default_preference

    selected_superseded_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) == "superseded"
    ]
    selected_current_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) == "current"
    ]
    if not selected_superseded_ids or len(selected_current_ids) < 2:
        return default_preference

    target_current_ids: list[str] = []
    support_current_ids: list[str] = []
    for memory_id in selected_current_ids:
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        haystack_terms = set(_query_tokens(f"{memory.content} {' '.join(memory.labels)}"))
        if all(term in haystack_terms for term in target_terms):
            target_current_ids.append(memory_id)
        else:
            support_current_ids.append(memory_id)
    if len(target_current_ids) != 1 or not support_current_ids:
        return default_preference

    target_current_id = target_current_ids[0]
    prioritized_ids = selected_superseded_ids + [target_current_id] + support_current_ids
    return {
        "applied": True,
        "strategy": "history_target_current_anchor_first_v1",
        "reason": "history-target-keep-explicit-current-anchor",
        "order": "selected_stale_then_target_current_then_current_support",
        "preferred_ids": prioritized_ids + [
            memory_id
            for memory_id in selected_ids
            if memory_id not in set(prioritized_ids)
        ],
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": target_current_id,
        "selected_target_support_ids": support_current_ids,
        "selected_update_current_id": None,
        "selected_current_support_ids": [],
        "current_anchor_id": target_current_id,
    }


def _history_current_anchor_injection_preference(
    *,
    selection: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
    temporal_state_by_id: dict[str, str],
) -> dict[str, Any]:
    selected_ids = [str(memory_id) for memory_id in selection.get("selected_ids", []) if str(memory_id)]
    default_preference = {
        "applied": False,
        "strategy": None,
        "reason": None,
        "order": selection.get("selection_order"),
        "preferred_ids": selected_ids,
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_relation_current_id": None,
        "selected_relation_support_ids": [],
        "selected_update_current_id": None,
        "selected_current_support_ids": [],
        "current_anchor_id": None,
    }
    selection_reason = str(selection.get("selection_reason") or "")
    if selection_reason not in {
        "history-query-terms",
        "update-history-query-terms",
        "earliest-history-query-terms",
    }:
        return default_preference

    selected_superseded_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) == "superseded"
    ]
    selected_current_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) == "current"
    ]
    if not selected_superseded_ids or len(selected_current_ids) < 2:
        return default_preference

    update_current_ids: list[str] = []
    support_current_ids: list[str] = []
    for memory_id in selected_current_ids:
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        if _lexical_update_signature(memory) is not None:
            update_current_ids.append(memory_id)
        else:
            support_current_ids.append(memory_id)
    if len(update_current_ids) != 1 or not support_current_ids:
        return default_preference

    update_current_id = update_current_ids[0]
    prioritized_ids = selected_superseded_ids + [update_current_id] + support_current_ids
    is_earliest_history = selection_reason == "earliest-history-query-terms"
    is_update_history = selection_reason == "update-history-query-terms"
    return {
        "applied": True,
        "strategy": (
            "earliest_history_current_anchor_first_v1"
            if is_earliest_history
            else "update_history_current_anchor_first_v1"
            if is_update_history
            else "history_current_anchor_first_v1"
        ),
        "reason": (
            "earliest-history-keep-explicit-current-anchor"
            if is_earliest_history
            else "update-history-keep-explicit-current-anchor"
            if is_update_history
            else "history-keep-explicit-current-anchor"
        ),
        "order": "selected_stale_then_update_current_then_current_support",
        "preferred_ids": prioritized_ids + [
            memory_id
            for memory_id in selected_ids
            if memory_id not in set(prioritized_ids)
        ],
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_relation_current_id": None,
        "selected_relation_support_ids": [],
        "selected_update_current_id": update_current_id,
        "selected_current_support_ids": support_current_ids,
        "current_anchor_id": update_current_id,
    }


def _history_relation_current_anchor_injection_preference(
    *,
    selection: dict[str, Any],
    query_lookup: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
    temporal_state_by_id: dict[str, str],
) -> dict[str, Any]:
    selected_ids = [str(memory_id) for memory_id in selection.get("selected_ids", []) if str(memory_id)]
    default_preference = {
        "applied": False,
        "strategy": None,
        "reason": None,
        "order": selection.get("selection_order"),
        "preferred_ids": selected_ids,
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_relation_current_id": None,
        "selected_relation_support_ids": [],
        "selected_update_current_id": None,
        "selected_current_support_ids": [],
        "current_anchor_id": None,
    }
    selection_reason = str(selection.get("selection_reason") or "")
    if selection_reason not in {
        "history-query-terms",
        "update-history-query-terms",
        "earliest-history-query-terms",
    }:
        return default_preference

    selected_search_terms = [
        str(term)
        for term in (query_lookup or {}).get("selected_search_terms", [])
        if str(term)
    ]
    selected_search_basis = str((query_lookup or {}).get("selected_search_basis") or "")
    lookup_relation = str((query_lookup or {}).get("lookup_relation") or "")
    basis_supports_relation_anchor = selected_search_basis.startswith("history-subject-core") or selected_search_basis.startswith(
        "update-history-subject-core"
    )
    if len(selected_search_terms) < 2 or (not basis_supports_relation_anchor and not lookup_relation):
        return default_preference

    selected_superseded_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) == "superseded"
    ]
    selected_current_ids = [
        memory_id
        for memory_id in selected_ids
        if temporal_state_by_id.get(memory_id) == "current"
    ]
    if not selected_superseded_ids or len(selected_current_ids) < 2:
        return default_preference

    search_term_set = set(selected_search_terms)
    relation_current_ids: list[str] = []
    support_current_ids: list[str] = []
    for memory_id in selected_current_ids:
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        relation_signature = _lexical_conflict_signature(memory)
        if relation_signature is None:
            support_current_ids.append(memory_id)
            continue
        if lookup_relation and str(relation_signature.get("relation") or "") != lookup_relation:
            support_current_ids.append(memory_id)
            continue
        subject_terms = {
            str(term)
            for term in query_terms(str(relation_signature.get("subject_key") or ""))
            if str(term)
        }
        if len(search_term_set.intersection(subject_terms)) >= min(2, len(subject_terms)):
            relation_current_ids.append(memory_id)
        else:
            support_current_ids.append(memory_id)
    if len(relation_current_ids) != 1 or not support_current_ids:
        return default_preference

    relation_current_id = relation_current_ids[0]
    prioritized_ids = selected_superseded_ids + [relation_current_id] + support_current_ids
    is_earliest_history = selection_reason == "earliest-history-query-terms"
    is_update_history = selection_reason == "update-history-query-terms"
    return {
        "applied": True,
        "strategy": (
            "earliest_history_relation_current_anchor_first_v1"
            if is_earliest_history
            else "update_history_relation_current_anchor_first_v1"
            if is_update_history
            else "history_relation_current_anchor_first_v1"
        ),
        "reason": (
            "earliest-history-keep-explicit-current-relation"
            if is_earliest_history
            else "update-history-keep-explicit-current-relation"
            if is_update_history
            else "history-keep-explicit-current-relation"
        ),
        "order": "selected_stale_then_relation_current_then_current_support",
        "preferred_ids": prioritized_ids + [
            memory_id
            for memory_id in selected_ids
            if memory_id not in set(prioritized_ids)
        ],
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_relation_current_id": relation_current_id,
        "selected_relation_support_ids": support_current_ids,
        "selected_update_current_id": None,
        "selected_current_support_ids": support_current_ids,
        "current_anchor_id": relation_current_id,
    }


def _update_current_relation_support_injection_preference(
    *,
    selection: dict[str, Any],
    query_lookup: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
) -> dict[str, Any]:
    selected_ids = [str(memory_id) for memory_id in selection.get("selected_ids", []) if str(memory_id)]
    default_preference = {
        "applied": False,
        "strategy": None,
        "reason": None,
        "order": selection.get("selection_order"),
        "preferred_ids": selected_ids,
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_relation_current_id": None,
        "selected_relation_support_ids": [],
        "selected_update_current_id": None,
        "selected_current_support_ids": [],
        "current_anchor_id": None,
    }
    if str(selection.get("selection_strategy") or "") != "current_only_v1":
        return default_preference

    update_lookup = dict((query_lookup or {}).get("update", {}))
    if str(update_lookup.get("direction") or "") != "current":
        return default_preference

    selected_search_terms = [
        str(term)
        for term in (query_lookup or {}).get("selected_search_terms", [])
        if str(term)
    ]
    selected_search_basis = str((query_lookup or {}).get("selected_search_basis") or "")
    lookup_relation = str((query_lookup or {}).get("lookup_relation") or "")
    if len(selected_search_terms) < 2 or not selected_search_basis.startswith("update-subject-core"):
        return default_preference

    selected_current_ids = [
        str(memory_id)
        for memory_id in selection.get("selected_current_ids", [])
        if str(memory_id)
    ]
    support_ids = [
        str(memory_id)
        for memory_id in update_lookup.get("support_candidate_ids", [])
        if str(memory_id) in selected_current_ids
    ]
    if not support_ids:
        return default_preference
    support_id_set = set(support_ids)

    search_term_set = set(selected_search_terms)
    relation_current_ids: list[str] = []
    trailing_ids: list[str] = []
    for memory_id in selected_current_ids:
        if memory_id in support_id_set:
            continue
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        relation_signature = _lexical_conflict_signature(memory)
        if relation_signature is None:
            trailing_ids.append(memory_id)
            continue
        if lookup_relation and str(relation_signature.get("relation") or "") != lookup_relation:
            trailing_ids.append(memory_id)
            continue
        subject_terms = {
            str(term)
            for term in query_terms(str(relation_signature.get("subject_key") or ""))
            if str(term)
        }
        if len(search_term_set.intersection(subject_terms)) >= min(2, len(subject_terms)):
            relation_current_ids.append(memory_id)
        else:
            trailing_ids.append(memory_id)
    if len(relation_current_ids) != 1:
        return default_preference

    relation_current_id = relation_current_ids[0]
    prioritized_ids = [relation_current_id, *support_ids]
    prioritized_id_set = set(prioritized_ids)
    prioritized_ids.extend(memory_id for memory_id in selected_ids if memory_id not in prioritized_id_set)
    return {
        "applied": True,
        "strategy": "update_current_relation_support_anchor_first_v1",
        "reason": "update-current-keep-explicit-current-support-pair",
        "order": "relation_current_then_current_support",
        "preferred_ids": prioritized_ids,
        "selected_mutation_anchor_id": None,
        "selected_mutation_anchor_ids": [],
        "selected_target_current_id": None,
        "selected_target_support_ids": [],
        "selected_relation_current_id": relation_current_id,
        "selected_relation_support_ids": support_ids,
        "selected_update_current_id": None,
        "selected_current_support_ids": support_ids,
        "current_anchor_id": relation_current_id,
    }


def _packing_reservation(authorized_entries: list[dict[str, Any]], retrieval: dict[str, Any]) -> dict[str, Any]:
    temporal = dict(retrieval.get("temporal", {}))
    selection_strategy = temporal.get("selection_strategy")
    selection_reason = temporal.get("selection_reason")
    injection_strategy = str(temporal.get("injection_strategy") or "")
    support_id_set = {
        str(memory_id)
        for key in (
            "selected_target_support_ids",
            "selected_relation_support_ids",
            "selected_current_support_ids",
        )
        for memory_id in temporal.get(key, [])
        if str(memory_id)
    }
    reservation_strategy = None
    reservation_reason = None
    explicit_change_ids = [
        str(memory_id)
        for memory_id in temporal.get("selected_mutation_anchor_ids", [])
        if str(memory_id)
    ]
    if selection_strategy == "earliest_history_preferred_v1":
        reservation_strategy = "earliest_history_anchor_pair_v1"
        reservation_reason = "earliest-history-keep-earliest-and-latest-current"
    elif selection_strategy == "historical_preferred_v1":
        reservation_strategy = (
            "update_history_anchor_pair_v1"
            if selection_reason == "update-history-query-terms"
            else "history_anchor_pair_v1"
        )
        reservation_reason = (
            "update-history-keep-selected-stale-and-latest-current"
            if selection_reason == "update-history-query-terms"
            else "history-keep-selected-stale-and-latest-current"
        )
    elif selection_strategy == "chronological_timeline_v1" and explicit_change_ids:
        reservation_strategy = "chronology_mutation_anchor_set_v1"
        reservation_reason = "chronology-keep-explicit-change-events"
    elif selection_strategy == "chronological_timeline_v1" and support_id_set:
        reservation_strategy = "chronology_relation_support_chain_v1"
        reservation_reason = "chronology-keep-selected-stale-current-support-chain"
    elif selection_strategy == "current_only_v1" and injection_strategy == "update_current_relation_support_anchor_first_v1" and support_id_set:
        reservation_strategy = "update_current_support_pair_v1"
        reservation_reason = "update-current-keep-explicit-current-support-pair"
    elif selection_strategy == "target_history_support_preferred_v1" and support_id_set:
        reservation_strategy = "target_history_support_chain_v1"
        reservation_reason = "history-target-keep-selected-support-current-pair"
    if reservation_strategy is None:
        multi_hop_reservation = _mixed_owner_contact_role_reservation(authorized_entries, retrieval)
        if multi_hop_reservation is not None:
            return multi_hop_reservation
        return {
            "strategy": None,
            "reason": None,
            "requested_ids": [],
            "fallback_requested_ids": [],
            "applied_ids": [],
            "applied": False,
            "fallback_applied": False,
            "fallback_reason": None,
            "blocked_reason": None,
        }

    authorized_ids = {entry["memory"].id for entry in authorized_entries}
    if selection_strategy == "chronological_timeline_v1" and explicit_change_ids:
        requested_ids = [memory_id for memory_id in explicit_change_ids if memory_id in authorized_ids]
        return {
            "strategy": reservation_strategy,
            "reason": reservation_reason,
            "requested_ids": requested_ids,
            "fallback_requested_ids": [],
            "applied_ids": [],
            "applied": False,
            "fallback_applied": False,
            "fallback_reason": None,
            "blocked_reason": None,
        }
    if reservation_strategy == "update_current_support_pair_v1":
        current_anchor_id = str(
            temporal.get("selected_relation_current_id")
            or temporal.get("selected_current_anchor_id")
            or ""
        )
        requested_ids = [current_anchor_id] if current_anchor_id in authorized_ids else []
        fallback_requested_ids = list(requested_ids)
        ordered_support_ids = []
        for memory_id in [
            str(memory_id)
            for memory_id in temporal.get("injection_preferred_ids", [])
            if str(memory_id)
        ] + [
            str(memory_id)
            for memory_id in temporal.get("selected_ids", [])
            if str(memory_id)
        ]:
            if (
                memory_id in support_id_set
                and memory_id in authorized_ids
                and memory_id not in requested_ids
                and memory_id not in ordered_support_ids
            ):
                ordered_support_ids.append(memory_id)
        if ordered_support_ids:
            requested_ids.extend(ordered_support_ids)
        return {
            "strategy": reservation_strategy,
            "reason": reservation_reason,
            "requested_ids": requested_ids,
            "fallback_requested_ids": fallback_requested_ids,
            "applied_ids": [],
            "applied": False,
            "fallback_applied": False,
            "fallback_reason": None,
            "blocked_reason": None,
        }

    selected_ids = [str(memory_id) for memory_id in temporal.get("selected_ids", []) if str(memory_id) in authorized_ids]
    current_ids = {str(memory_id) for memory_id in temporal.get("current_ids", []) if str(memory_id) in authorized_ids}
    requested_ids: list[str] = []
    if selected_ids:
        requested_ids.append(selected_ids[0])
    current_anchor_id = str(temporal.get("selected_current_anchor_id") or "")
    if current_anchor_id not in current_ids:
        current_anchor_id = next((memory_id for memory_id in reversed(selected_ids) if memory_id in current_ids), "")
    if current_anchor_id and current_anchor_id not in requested_ids:
        requested_ids.append(current_anchor_id)
    fallback_requested_ids = list(requested_ids)
    ordered_support_ids: list[str] = []
    preferred_support_order = [
        str(memory_id)
        for memory_id in temporal.get("injection_preferred_ids", [])
        if str(memory_id)
    ]
    for memory_id in preferred_support_order + selected_ids:
        if (
            memory_id in support_id_set
            and memory_id in authorized_ids
            and memory_id not in requested_ids
            and memory_id not in ordered_support_ids
        ):
            ordered_support_ids.append(memory_id)
    if ordered_support_ids:
        requested_ids.extend(ordered_support_ids)
        if reservation_strategy == "earliest_history_anchor_pair_v1":
            reservation_reason = "earliest-history-keep-earliest-current-support-chain"
        elif reservation_strategy == "history_anchor_pair_v1":
            reservation_reason = "history-keep-selected-stale-current-support-chain"
        elif reservation_strategy == "update_history_anchor_pair_v1":
            reservation_reason = "update-history-keep-selected-stale-current-support-chain"
        elif reservation_strategy != "chronology_relation_support_chain_v1":
            fallback_requested_ids = []
    return {
        "strategy": reservation_strategy,
        "reason": reservation_reason,
        "requested_ids": requested_ids,
        "fallback_requested_ids": fallback_requested_ids,
        "applied_ids": [],
        "applied": False,
        "fallback_applied": False,
        "fallback_reason": None,
        "blocked_reason": None,
    }


def _target_history_selected_pair(
    temporal: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    selected_current_id = str(
        temporal.get("selected_target_current_id")
        or temporal.get("selected_relation_current_id")
        or temporal.get("selected_current_anchor_id")
        or ""
    )
    selected_support_ids: list[str] = []
    for memory_id in [
        str(memory_id)
        for memory_id in temporal.get("selected_target_support_ids", [])
        if str(memory_id)
    ] + [
        str(memory_id)
        for memory_id in temporal.get("selected_relation_support_ids", [])
        if str(memory_id)
    ] + [
        str(memory_id)
        for memory_id in temporal.get("selected_current_support_ids", [])
        if str(memory_id)
    ]:
        if memory_id and memory_id not in selected_support_ids:
            selected_support_ids.append(memory_id)

    selected_pair_ids = list(selected_support_ids)
    if selected_current_id and selected_current_id not in selected_pair_ids:
        selected_pair_ids.append(selected_current_id)
    return selected_current_id, selected_support_ids, selected_pair_ids


def _packing_blocked_target_history_pair_metadata(
    *,
    entry: dict[str, Any],
    reservation: dict[str, Any],
    temporal: dict[str, Any],
) -> dict[str, Any] | None:
    if (
        reservation.get("strategy") != "target_history_support_chain_v1"
        or reservation.get("blocked_reason") != "reservation-exceeds-budget"
        or not entry.get("selected_by_temporal_strategy")
        or not entry.get("reserved_by_strategy")
    ):
        return None

    selected_current_id, selected_support_ids, selected_pair_ids = _target_history_selected_pair(temporal)
    if not selected_current_id or not selected_support_ids or entry["memory"].id not in selected_pair_ids:
        return None

    blocked_pair_member_role = (
        "target-current"
        if entry["memory"].id == selected_current_id
        else "history-support"
    )
    return {
        "reason": "target-history-support-pair-blocked",
        "detail": "selected-target-support-current-pair-exceeds-budget",
        "blocked_reason": "reservation-exceeds-budget",
        "blocked_pair_member_role": blocked_pair_member_role,
        "selected_target_current_id": selected_current_id,
        "selected_target_support_ids": selected_support_ids,
        "selected_pair_ids": selected_pair_ids,
    }


def _packing_reservation_exclusion(
    *,
    entry: dict[str, Any],
    selected_ids: set[str],
    reservation: dict[str, Any],
    temporal: dict[str, Any],
) -> dict[str, Any] | None:
    if (
        not reservation.get("applied")
        or entry["memory"].id in selected_ids
        or entry.get("reserved_by_strategy")
        or not entry.get("selected_by_temporal_strategy")
    ):
        return None

    strategy = reservation.get("strategy")
    if strategy == "update_current_support_pair_v1":
        if entry.get("temporal_state") != "current":
            return None
        selected_current_id = str(
            temporal.get("selected_relation_current_id")
            or temporal.get("selected_current_anchor_id")
            or ""
        )
        selected_support_ids = [
            str(memory_id)
            for memory_id in temporal.get("selected_relation_support_ids", [])
            if str(memory_id)
        ]
        if not selected_current_id or not selected_support_ids:
            return None

        selected_pair_ids = [selected_current_id, *selected_support_ids]
        if reservation.get("applied_ids") != selected_pair_ids:
            return None

        return {
            "reason": "update-current-support-pair-reserved",
            "detail": "explicit-current-relation-plus-support-anchor-kept",
            "selected_current_id": selected_current_id,
            "selected_support_ids": selected_support_ids,
            "selected_pair_ids": selected_pair_ids,
        }

    if strategy == "history_anchor_pair_v1":
        if entry.get("temporal_state") != "superseded":
            return None
        selected_ids_ordered = [
            str(memory_id)
            for memory_id in temporal.get("selected_ids", [])
            if str(memory_id)
        ]
        selected_stale_id = selected_ids_ordered[0] if selected_ids_ordered else ""
        selected_current_id = str(
            temporal.get("selected_relation_current_id")
            or temporal.get("selected_current_anchor_id")
            or ""
        )
        selected_support_ids = []
        for memory_id in [
            str(memory_id)
            for memory_id in temporal.get("selected_relation_support_ids", [])
            if str(memory_id)
        ] + [
            str(memory_id)
            for memory_id in temporal.get("selected_current_support_ids", [])
            if str(memory_id)
        ]:
            if memory_id and memory_id not in selected_support_ids:
                selected_support_ids.append(memory_id)
        if not selected_stale_id or not selected_current_id or not selected_support_ids:
            return None

        selected_chain_ids = [selected_stale_id, selected_current_id, *selected_support_ids]
        if reservation.get("applied_ids") != selected_chain_ids:
            return None

        return {
            "reason": "history-support-chain-reserved",
            "detail": "selected-stale-current-support-chain-kept",
            "selected_stale_id": selected_stale_id,
            "selected_current_id": selected_current_id,
            "selected_support_ids": selected_support_ids,
            "selected_chain_ids": selected_chain_ids,
        }

    if strategy == "earliest_history_anchor_pair_v1":
        if entry.get("temporal_state") != "superseded":
            return None
        selected_ids_ordered = [
            str(memory_id)
            for memory_id in temporal.get("selected_ids", [])
            if str(memory_id)
        ]
        selected_stale_id = selected_ids_ordered[0] if selected_ids_ordered else ""
        selected_current_id = str(
            temporal.get("selected_relation_current_id")
            or temporal.get("selected_current_anchor_id")
            or ""
        )
        if not selected_stale_id or not selected_current_id:
            return None

        selected_support_ids = []
        for memory_id in [
            str(memory_id)
            for memory_id in temporal.get("selected_relation_support_ids", [])
            if str(memory_id)
        ] + [
            str(memory_id)
            for memory_id in temporal.get("selected_current_support_ids", [])
            if str(memory_id)
        ]:
            if memory_id and memory_id not in selected_support_ids:
                selected_support_ids.append(memory_id)

        selected_pair_ids = [selected_stale_id, selected_current_id]
        if reservation.get("applied_ids") == selected_pair_ids:
            return {
                "reason": "earliest-history-anchor-pair-reserved",
                "detail": "selected-earliest-current-anchor-pair-kept",
                "selected_stale_id": selected_stale_id,
                "selected_current_id": selected_current_id,
                "selected_pair_ids": selected_pair_ids,
            }

        if not selected_support_ids:
            return None

        selected_chain_ids = [selected_stale_id, selected_current_id, *selected_support_ids]
        if reservation.get("applied_ids") != selected_chain_ids:
            return None

        return {
            "reason": "earliest-history-support-chain-reserved",
            "detail": "selected-earliest-current-support-chain-kept",
            "selected_stale_id": selected_stale_id,
            "selected_current_id": selected_current_id,
            "selected_support_ids": selected_support_ids,
            "selected_chain_ids": selected_chain_ids,
        }

    if strategy == "chronology_relation_support_chain_v1":
        if entry.get("temporal_state") != "superseded":
            return None
        selected_ids_ordered = [
            str(memory_id)
            for memory_id in temporal.get("selected_ids", [])
            if str(memory_id)
        ]
        selected_stale_id = selected_ids_ordered[0] if selected_ids_ordered else ""
        selected_current_id = str(
            temporal.get("selected_relation_current_id")
            or temporal.get("selected_current_anchor_id")
            or ""
        )
        selected_support_ids = []
        for memory_id in [
            str(memory_id)
            for memory_id in temporal.get("selected_relation_support_ids", [])
            if str(memory_id)
        ] + [
            str(memory_id)
            for memory_id in temporal.get("selected_current_support_ids", [])
            if str(memory_id)
        ]:
            if memory_id and memory_id not in selected_support_ids:
                selected_support_ids.append(memory_id)
        if not selected_stale_id or not selected_current_id or not selected_support_ids:
            return None

        selected_chain_ids = [selected_stale_id, selected_current_id, *selected_support_ids]
        if reservation.get("applied_ids") != selected_chain_ids:
            return None

        return {
            "reason": "chronology-support-chain-reserved",
            "detail": "selected-stale-current-support-chain-kept",
            "selected_stale_id": selected_stale_id,
            "selected_current_id": selected_current_id,
            "selected_support_ids": selected_support_ids,
            "selected_chain_ids": selected_chain_ids,
        }

    if strategy == "update_history_anchor_pair_v1":
        if entry.get("temporal_state") != "superseded":
            return None
        selected_ids_ordered = [
            str(memory_id)
            for memory_id in temporal.get("selected_ids", [])
            if str(memory_id)
        ]
        selected_stale_id = selected_ids_ordered[0] if selected_ids_ordered else ""
        selected_current_id = str(
            temporal.get("selected_relation_current_id")
            or temporal.get("selected_current_anchor_id")
            or ""
        )
        if not selected_stale_id or not selected_current_id:
            return None

        selected_support_ids = []
        for memory_id in [
            str(memory_id)
            for memory_id in temporal.get("selected_relation_support_ids", [])
            if str(memory_id)
        ] + [
            str(memory_id)
            for memory_id in temporal.get("selected_current_support_ids", [])
            if str(memory_id)
        ]:
            if memory_id and memory_id not in selected_support_ids:
                selected_support_ids.append(memory_id)

        selected_pair_ids = [selected_stale_id, selected_current_id]
        if reservation.get("applied_ids") == selected_pair_ids:
            return {
                "reason": "update-history-anchor-pair-reserved",
                "detail": "selected-stale-current-anchor-pair-kept",
                "selected_stale_id": selected_stale_id,
                "selected_current_id": selected_current_id,
                "selected_pair_ids": selected_pair_ids,
            }

        if not selected_support_ids:
            return None

        selected_chain_ids = [selected_stale_id, selected_current_id, *selected_support_ids]
        if reservation.get("applied_ids") != selected_chain_ids:
            return None

        return {
            "reason": "update-history-support-chain-reserved",
            "detail": "selected-stale-current-support-chain-kept",
            "selected_stale_id": selected_stale_id,
            "selected_current_id": selected_current_id,
            "selected_support_ids": selected_support_ids,
            "selected_chain_ids": selected_chain_ids,
        }

    return None


def _candidate_has_positive_rank(candidate: dict[str, Any] | None, rank_key: str) -> bool:
    if not isinstance(candidate, dict):
        return False
    rank = candidate.get(rank_key)
    return isinstance(rank, int) and not isinstance(rank, bool) and rank > 0


def _current_ordering_rank(
    *,
    memory_id: str,
    candidate_meta: dict[str, dict[str, Any]],
    basis: str,
    pass_through: bool,
    fallback_rank: int,
) -> int | None:
    candidate = candidate_meta.get(memory_id, {})
    if pass_through:
        rank = candidate.get(basis)
    elif basis == "retrieval_rank":
        rank = candidate.get("rank")
    else:
        rank = fallback_rank
    return rank if isinstance(rank, int) and not isinstance(rank, bool) else None


def _current_only_ordering_metadata(
    *,
    retrieval: dict[str, Any],
    selection: dict[str, Any],
    candidate_meta: dict[str, dict[str, Any]],
    current_ids: list[str],
    conflict_sets: list[dict[str, Any]],
) -> dict[str, Any]:
    selection_strategy = str(selection.get("selection_strategy") or "")
    current_ids = [str(memory_id) for memory_id in current_ids if str(memory_id)]
    selected_current_ids = [
        str(memory_id)
        for memory_id in selection.get("selected_current_ids", [])
        if str(memory_id)
    ]
    considered_current_ids = list(selected_current_ids)
    basis = "retrieval_rank"
    source = "baseline"
    pass_through = False
    reason = "current-only-retrieval-rank"

    reranker = retrieval.get("reranker") if isinstance(retrieval.get("reranker"), dict) else {}
    embedding = retrieval.get("embedding") if isinstance(retrieval.get("embedding"), dict) else {}
    hybrid = retrieval.get("hybrid") if isinstance(retrieval.get("hybrid"), dict) else {}

    if selection_strategy == "current_only_v1" and selected_current_ids:
        if bool(reranker.get("enabled")) and all(
            _candidate_has_positive_rank(candidate_meta.get(memory_id), "reranker_rank")
            for memory_id in selected_current_ids
        ):
            basis = "reranker_rank"
            source = "reranker"
            pass_through = True
            reason = "current-only-reranker-pass-through"
        elif bool(embedding.get("enabled")) and all(
            _candidate_has_positive_rank(candidate_meta.get(memory_id), "embedding_rank")
            for memory_id in selected_current_ids
        ):
            basis = "embedding_rank"
            source = "embedding"
            pass_through = True
            reason = "current-only-embedding-pass-through"
        elif bool(hybrid.get("applied")) and all(
            _candidate_has_positive_rank(candidate_meta.get(memory_id), "hybrid_semantic_rank")
            for memory_id in selected_current_ids
        ):
            basis = "hybrid_semantic_rank"
            source = "hybrid_semantic_backfill"
            pass_through = True
            reason = "current-only-hybrid-semantic-pass-through"
    elif selection_strategy == "current_update_preferred_v1" and selected_current_ids:
        basis = "current_update_preference_rank"
        source = "temporal_current_update_preference"
        reason = "current-update-explicit-anchor-selection"
        considered_current_ids = selected_current_ids + [
            memory_id for memory_id in current_ids if memory_id not in selected_current_ids
        ]
    elif selection_strategy == "current_conflict_resolved_v1" and selected_current_ids:
        basis = "current_conflict_resolution_rank"
        source = "temporal_current_conflict_resolution"
        reason = "lexical-current-conflict-deterministic-resolution"
        conflict_current_ids: list[str] = []
        selected_current_id_set = set(selected_current_ids)
        for conflict_set in conflict_sets:
            if (
                str(conflict_set.get("reason") or "") != "lexical-current-conflict"
                or str(conflict_set.get("resolution_outcome") or "") != "resolved"
            ):
                continue
            ordered_current_ids = [
                str(memory_id)
                for memory_id in conflict_set.get("current_ids", [])
                if str(memory_id)
            ]
            if not selected_current_id_set.intersection(ordered_current_ids):
                continue
            conflict_current_ids.extend(ordered_current_ids)
        if conflict_current_ids:
            deduped_conflict_current_ids: list[str] = []
            seen_conflict_ids: set[str] = set()
            for memory_id in conflict_current_ids:
                if memory_id in seen_conflict_ids:
                    continue
                seen_conflict_ids.add(memory_id)
                deduped_conflict_current_ids.append(memory_id)
            considered_current_ids = deduped_conflict_current_ids + [
                memory_id for memory_id in current_ids if memory_id not in seen_conflict_ids
            ]
        else:
            considered_current_ids = selected_current_ids + [
                memory_id for memory_id in current_ids if memory_id not in selected_current_ids
            ]
    elif selection_strategy == "current_conflict_abstained_v1":
        basis = "current_conflict_abstention_rank"
        source = "temporal_current_conflict_abstention"
        reason = "lexical-current-conflict-abstained"
        conflict_current_ids: list[str] = []
        for conflict_set in conflict_sets:
            if (
                str(conflict_set.get("reason") or "") != "lexical-current-conflict"
                or str(conflict_set.get("resolution_outcome") or "") != "abstained"
            ):
                continue
            conflict_current_ids.extend(
                [
                    str(memory_id)
                    for memory_id in conflict_set.get("current_ids", [])
                    if str(memory_id)
                ]
            )
        if conflict_current_ids:
            deduped_conflict_current_ids: list[str] = []
            seen_conflict_ids: set[str] = set()
            for memory_id in conflict_current_ids:
                if memory_id in seen_conflict_ids:
                    continue
                seen_conflict_ids.add(memory_id)
                deduped_conflict_current_ids.append(memory_id)
            considered_current_ids = deduped_conflict_current_ids + [
                memory_id for memory_id in current_ids if memory_id not in seen_conflict_ids
            ]
        else:
            considered_current_ids = list(current_ids)
    elif selection_strategy == "abstained_only_v1":
        basis = "current_conflict_abstention_rank"
        source = "temporal_current_conflict_abstention"
        reason = "explicit-abstained-current-filter"
        considered_current_ids = selected_current_ids + [
            memory_id for memory_id in current_ids if memory_id not in selected_current_ids
        ]
    elif selection_strategy == "dropped_only_v1":
        basis = "current_conflict_resolution_rank"
        source = "temporal_current_conflict_resolution"
        reason = "explicit-dropped-current-filter"
        considered_current_ids = selected_current_ids + [
            memory_id for memory_id in current_ids if memory_id not in selected_current_ids
        ]

    selected_current_rankings = []
    for index, memory_id in enumerate(selected_current_ids, start=1):
        selected_current_rankings.append(
            {
                "memory_id": memory_id,
                "rank": _current_ordering_rank(
                    memory_id=memory_id,
                    candidate_meta=candidate_meta,
                    basis=basis,
                    pass_through=pass_through,
                    fallback_rank=index,
                ),
            }
        )
    selected_current_id_set = set(selected_current_ids)
    considered_current_rankings = []
    for index, memory_id in enumerate(considered_current_ids, start=1):
        considered_current_rankings.append(
            {
                "memory_id": memory_id,
                "rank": _current_ordering_rank(
                    memory_id=memory_id,
                    candidate_meta=candidate_meta,
                    basis=basis,
                    pass_through=pass_through,
                    fallback_rank=index,
                ),
                "selected": memory_id in selected_current_id_set,
            }
        )

    return {
        "applied": selection_strategy in {
            "abstained_only_v1",
            "dropped_only_v1",
            "current_only_v1",
            "current_update_preferred_v1",
            "current_conflict_resolved_v1",
            "current_conflict_abstained_v1",
        },
        "pass_through": pass_through,
        "basis": basis,
        "source": source,
        "reason": reason,
        "selected_current_rankings": selected_current_rankings,
        "considered_current_rankings": considered_current_rankings,
    }


def _history_ordering_metadata(
    *,
    selection: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
    candidate_ids_in_rank_order: list[str],
    current_ids: list[str],
    conflict_sets: list[dict[str, Any]],
    query_lookup: dict[str, Any] | None,
) -> dict[str, Any]:
    selection_strategy = str(selection.get("selection_strategy") or "")
    selection_reason = str(selection.get("selection_reason") or "")
    selected_history_strategy_metadata = {
        "earliest_history_preferred_v1": (
            "earliest_history_selection_rank",
            "temporal_earliest_history_selection",
        ),
        "historical_preferred_v1": (
            "historical_selection_rank",
            "temporal_history_selection",
        ),
    }
    if selection_strategy in selected_history_strategy_metadata:
        basis, source = selected_history_strategy_metadata[selection_strategy]
        selected_history_ids = [
            str(memory_id)
            for memory_id in selection.get("selected_ids", [])
            if str(memory_id)
        ]
        selected_history_rankings = [
            {"memory_id": memory_id, "rank": index}
            for index, memory_id in enumerate(selected_history_ids, start=1)
        ]
        return {
            "applied": True,
            "pass_through": False,
            "basis": basis,
            "source": source,
            "reason": selection_reason,
            "selected_history_rankings": selected_history_rankings,
            "considered_history_rankings": [
                {**item, "selected": True}
                for item in selected_history_rankings
            ],
        }
    if selection_strategy == "chronological_timeline_v1":
        selected_history_ids = [
            str(memory_id)
            for memory_id in selection.get("selected_ids", [])
            if str(memory_id)
        ]
        considered_history_candidates = list(selected_history_ids)
        considered_history_candidates.extend(
            memory_id
            for memory_id in current_ids
            if str(memory_id) and str(memory_id) not in considered_history_candidates
        )
        rank_by_id = {
            memory_id: rank
            for rank, memory_id in enumerate(candidate_ids_in_rank_order, start=1)
        }
        considered_history_ids = _chronology_ordered_ids(
            considered_history_candidates,
            candidate_by_id=candidate_by_id,
            rank_by_id=rank_by_id,
        )
        selected_history_id_set = set(selected_history_ids)
        return {
            "applied": True,
            "pass_through": False,
            "basis": "chronological_timeline_selection_rank",
            "source": "temporal_chronological_timeline_selection",
            "reason": selection_reason,
            "selected_history_rankings": [
                {"memory_id": memory_id, "rank": index}
                for index, memory_id in enumerate(selected_history_ids, start=1)
            ],
            "considered_history_rankings": [
                {
                    "memory_id": memory_id,
                    "rank": index,
                    "selected": memory_id in selected_history_id_set,
                }
                for index, memory_id in enumerate(considered_history_ids, start=1)
            ],
        }
    support_pair_history_strategy_metadata = {
        "target_history_support_preferred_v1": (
            "target_history_support_selection_rank",
            "temporal_target_history_support_selection",
        ),
        "history_observation_support_v1": (
            "history_observation_support_selection_rank",
            "temporal_history_observation_support_selection",
        ),
    }
    if selection_strategy in support_pair_history_strategy_metadata:
        basis, source = support_pair_history_strategy_metadata[selection_strategy]
        selected_history_ids = [
            str(memory_id)
            for memory_id in selection.get("selected_ids", [])
            if str(memory_id)
        ]
        considered_history_ids = list(selected_history_ids)
        if selection_strategy == "target_history_support_preferred_v1":
            considered_history_ids.extend(
                str(item.get("memory_id"))
                for item in selection.get("selection_exclusions", [])
                if str(item.get("memory_id"))
                and str(item.get("memory_id")) not in considered_history_ids
            )
        else:
            observation_support = dict(((query_lookup or {}).get("history") or {}).get("observation_support", {}))
            ordered_anchor_candidate_ids = [
                str(memory_id)
                for memory_id in observation_support.get("ordered_anchor_candidate_ids", [])
                if str(memory_id)
            ]
            if not ordered_anchor_candidate_ids:
                ordered_anchor_candidate_ids = [
                    str(memory_id)
                    for memory_id in observation_support.get("anchor_candidate_ids", [])
                    if str(memory_id)
                ]
            ordered_support_candidate_ids = [
                str(memory_id)
                for memory_id in observation_support.get("ordered_support_candidate_ids", [])
                if str(memory_id)
            ]
            if not ordered_support_candidate_ids:
                ordered_support_candidate_ids = [
                    str(memory_id)
                    for memory_id in observation_support.get("considered_candidate_ids", [])
                    if str(memory_id)
                ]
            considered_history_ids.extend(
                memory_id
                for memory_id in ordered_anchor_candidate_ids
                if memory_id not in considered_history_ids
            )
            considered_history_ids.extend(
                memory_id
                for memory_id in ordered_support_candidate_ids
                if memory_id not in considered_history_ids
            )
        selected_history_rankings = [
            {"memory_id": memory_id, "rank": index}
            for index, memory_id in enumerate(selected_history_ids, start=1)
        ]
        selected_history_id_set = set(selected_history_ids)
        return {
            "applied": True,
            "pass_through": False,
            "basis": basis,
            "source": source,
            "reason": selection_reason,
            "selected_history_rankings": selected_history_rankings,
            "considered_history_rankings": [
                {
                    "memory_id": memory_id,
                    "rank": index,
                    "selected": memory_id in selected_history_id_set,
                }
                for index, memory_id in enumerate(considered_history_ids, start=1)
            ],
        }
    if selection_strategy != "history_conflict_abstained_v1":
        return {
            "applied": False,
            "pass_through": False,
            "basis": "history_conflict_abstention_rank",
            "source": "temporal_history_conflict_abstention",
            "reason": selection_reason,
            "selected_history_rankings": [],
            "considered_history_rankings": [],
        }

    abstained_history_ids = [
        str(memory_id)
        for memory_id in selection.get("abstention", {}).get("abstained_ids", [])
        if str(memory_id)
    ]
    if not abstained_history_ids:
        for conflict_set in conflict_sets:
            if str(conflict_set.get("reason") or "") != "subject-lookup-cross-provenance-conflict":
                continue
            if str(conflict_set.get("resolution_outcome") or "") != "abstained":
                continue
            abstained_history_ids.extend(
                str(memory_id)
                for memory_id in conflict_set.get("abstained_current_ids", [])
                if str(memory_id)
            )

    deduped_abstained_history_ids: list[str] = []
    seen_history_ids: set[str] = set()
    for memory_id in abstained_history_ids:
        if memory_id in seen_history_ids:
            continue
        seen_history_ids.add(memory_id)
        deduped_abstained_history_ids.append(memory_id)

    selection_order = str(selection.get("selection_order") or "")
    if selection_order in {
        "chronological_asc_abstained",
        "chronological_asc_prefer_earliest_abstained",
    }:
        rank_by_id = {
            memory_id: rank
            for rank, memory_id in enumerate(candidate_ids_in_rank_order, start=1)
        }
        considered_history_ids = _chronology_ordered_ids(
            deduped_abstained_history_ids,
            candidate_by_id=candidate_by_id,
            rank_by_id=rank_by_id,
        )
    else:
        considered_history_ids = [
            memory_id
            for memory_id in candidate_ids_in_rank_order
            if memory_id in seen_history_ids
        ]

    return {
        "applied": True,
        "pass_through": False,
        "basis": "history_conflict_abstention_rank",
        "source": "temporal_history_conflict_abstention",
        "reason": selection_reason,
        "selected_history_rankings": [],
        "considered_history_rankings": [
            {"memory_id": memory_id, "rank": index, "selected": False}
            for index, memory_id in enumerate(considered_history_ids, start=1)
        ],
    }


def _normalize_conflict_fragment(value: str) -> str:
    terms = [term for term in query_terms(value) if term not in {"a", "an", "the"}]
    return " ".join(terms)


def _normalize_lookup_subject_fragment(value: str) -> str:
    tokens = [
        token
        for token in _query_tokens(value)
        if token not in RELATION_SEARCH_ARTICLES and token not in GENERIC_SUBJECT_NOISE_TERMS
    ]
    return " ".join(tokens)


def _normalize_relation_value_fragment(value: str) -> str:
    tokens = [token for token in _query_tokens(value) if token not in RELATION_SEARCH_ARTICLES]
    return " ".join(tokens)


def _normalize_relation_search_fragment(value: str) -> str:
    tokens = [
        token
        for token in _query_tokens(value)
        if token not in RELATION_SEARCH_ARTICLES
    ]
    return " ".join(tokens)


def _relation_search_terms(value: str) -> list[str]:
    return [
        token
        for token in _query_tokens(value)
        if token not in RELATION_SEARCH_ARTICLES
    ]


def _query_tokens(value: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-z0-9_]+", value)]


def _canonical_subject_core_terms(
    terms: list[str],
    *,
    excluded_terms: set[str],
) -> dict[str, Any]:
    matched_aliases = []
    raw_core_terms = []
    core_terms = []
    seen_aliases: set[tuple[str, str]] = set()
    for term in terms:
        if term in excluded_terms or term in RELATION_SEARCH_ARTICLES:
            continue
        raw_core_terms.append(term)
        canonical = SEMANTIC_ALIAS_CANONICAL_BY_TOKEN.get(term, term)
        if canonical != term and (term, canonical) not in seen_aliases:
            seen_aliases.add((term, canonical))
            matched_aliases.append({"token": term, "canonical": canonical})
        core_terms.append(canonical)
    raw_core_terms = _ordered_unique(raw_core_terms)
    core_terms = _ordered_unique(core_terms)
    return {
        "raw_core_terms": raw_core_terms,
        "core_terms": core_terms,
        "matched_aliases": matched_aliases,
        "alias_expanded": core_terms != raw_core_terms,
    }


def _subject_core_search_variants(
    core_terms: list[str],
    *,
    basis: str,
    include_phrase_aliases: bool = True,
) -> dict[str, Any]:
    variants = []
    search_alias_variants = []
    preferred_variants = []
    if len(core_terms) < 2:
        return {
            "variants": variants,
            "search_alias_variants": search_alias_variants,
            "search_alias_expanded": False,
        }
    variants.append(
        {
            "query": " ".join(core_terms),
            "terms": list(core_terms),
            "basis": basis,
        }
    )
    seen_term_sets = {tuple(core_terms)}
    for index, term in enumerate(core_terms):
        for alias_term in TEMPORAL_SEARCH_ALIAS_TERMS_BY_CANONICAL.get(term, []):
            alias_terms = list(core_terms)
            alias_terms[index] = alias_term
            alias_key = tuple(alias_terms)
            if alias_key in seen_term_sets:
                continue
            seen_term_sets.add(alias_key)
            alias_query = " ".join(alias_terms)
            variants.append(
                {
                    "query": alias_query,
                    "terms": alias_terms,
                    "basis": f"{basis}-alias",
                }
            )
            search_alias_variants.append(
                {
                    "canonical": term,
                    "search_term": alias_term,
                    "query": alias_query,
                }
            )
    if include_phrase_aliases:
        normalized_core_query = _normalize_conflict_fragment(" ".join(core_terms))
        core_term_set = {str(term) for term in core_terms if str(term)}
        for alias_variant in SUBJECT_CORE_PHRASE_ALIAS_VARIANTS:
            if not set(alias_variant["required_terms"]).issubset(core_term_set):
                continue
            alias_query = str(alias_variant["search_query"])
            alias_terms = query_terms(alias_query)
            alias_key = tuple(alias_terms)
            if not alias_terms or alias_key in seen_term_sets:
                continue
            seen_term_sets.add(alias_key)
            alias_variant_entry = {
                "query": alias_query,
                "terms": alias_terms,
                "basis": f"{basis}-phrase-alias",
            }
            if alias_variant.get("prefer_before_core"):
                preferred_variants.append(alias_variant_entry)
            else:
                variants.append(alias_variant_entry)
            search_alias_variants.append(
                {
                    "canonical_query": normalized_core_query,
                    "search_term": alias_query,
                    "query": alias_query,
                    "match_strategy": "phrase",
                }
            )
    if preferred_variants:
        variants = preferred_variants + variants
    return {
        "variants": variants,
        "search_alias_variants": search_alias_variants,
        "search_alias_expanded": bool(search_alias_variants),
    }


def _implicit_owner_core_terms_for_person_query(
    raw_tokens: list[str],
    raw_core_terms: list[str],
    core_terms: list[str],
) -> dict[str, Any] | None:
    if not raw_tokens or raw_tokens[0] != "who":
        return None
    core_term_set = {str(term) for term in core_terms if str(term)}
    if core_term_set.intersection({"approver", "contact", "maintainer", "owner"}):
        return None
    raw_core_term_set = {str(term) for term in raw_core_terms if str(term)}
    if "deployment" not in raw_core_term_set:
        return None
    if not (
        raw_core_term_set.intersection({"approval", "approvals", "signoff"})
        or {"sign", "off"}.issubset(raw_core_term_set)
    ):
        return None
    return {
        "role": "owner",
        "reason": "who-wrapper-person-role",
        "core_terms": _ordered_unique([*core_terms, "owner"]),
    }


def _temporal_wrapped_relation_candidate_queries(stripped_query: str, stripped_tokens: list[str]) -> list[str]:
    if not stripped_query:
        return []

    candidates: list[str] = []
    relation_rewrites = (
        (
            re.compile(r"^(?P<subject>.+?)\s+point(?:\s+(?P<particle>at|to))?$", re.IGNORECASE),
            lambda match: [
                f"where does {match.group('subject')} point {match.group('particle') or 'to'}",
                f"what does {match.group('subject')} point {match.group('particle') or 'to'}",
            ],
        ),
        (
            re.compile(r"^(?P<subject>.+?)\s+deploy(?:\s+to)?$", re.IGNORECASE),
            lambda match: [
                f"where does {match.group('subject')} deploy to",
                f"what does {match.group('subject')} deploy to",
            ],
        ),
        (
            re.compile(r"^(?P<subject>.+?)\s+run(?:\s+on)?$", re.IGNORECASE),
            lambda match: [
                f"what does {match.group('subject')} run on",
                f"where does {match.group('subject')} run on",
            ],
        ),
        (
            re.compile(r"^(?P<subject>.+?)\s+belong(?:\s+to)?$", re.IGNORECASE),
            lambda match: [
                f"what does {match.group('subject')} belong to",
                f"which does {match.group('subject')} belong to",
            ],
        ),
    )
    for pattern, builder in relation_rewrites:
        match = pattern.match(stripped_query)
        if match:
            candidates.extend(builder(match))
    if stripped_tokens and stripped_tokens[0] not in SUBJECT_LOOKUP_QUERY_WRAPPERS:
        candidates.extend(
            [
                f"who is {stripped_query}",
                f"what is {stripped_query}",
                f"which is {stripped_query}",
                stripped_query,
            ]
        )
    else:
        candidates.append(stripped_query)
    return _ordered_unique(candidates)


def _temporal_wrapped_relation_query_plan(
    query: str,
    raw_tokens: list[str],
    *,
    excluded_terms: set[str],
) -> dict[str, Any] | None:
    has_wrapper_terms = any(token in excluded_terms for token in raw_tokens)
    if not has_wrapper_terms:
        relation_plan = _relation_query_plan(query)
        if relation_plan is not None:
            return relation_plan
    stripped_tokens = [token for token in raw_tokens if token not in excluded_terms]
    if not stripped_tokens:
        return None
    stripped_query = _normalize_relation_search_fragment(" ".join(stripped_tokens))
    if not stripped_query:
        return None
    if any(
        token in TEMPORAL_CHRONOLOGY_TERMS
        or token in TEMPORAL_CURRENT_TERMS
        or token in TEMPORAL_HISTORY_TERMS
        or token in CHRONOLOGY_QUERY_MUTATION_TERMS
        or token in UPDATE_QUERY_CURRENT_DIRECTION_TERMS
        or token in UPDATE_QUERY_HISTORY_DIRECTION_TERMS
        for token in raw_tokens
    ):
        direct_short_relation_rewrites = (
            ("role-relation-uses", "uses", re.compile(r"^(?P<subject>.+?)\s+use$", re.IGNORECASE)),
            ("role-relation-requires", "requires", re.compile(r"^(?P<subject>.+?)\s+require$", re.IGNORECASE)),
        )
        for lookup_basis, lookup_relation, pattern in direct_short_relation_rewrites:
            match = pattern.match(stripped_query)
            if not match:
                continue
            lookup_key = _normalize_lookup_subject_fragment(match.group("subject"))
            if not lookup_key:
                continue
            search_query = f"{lookup_key} {lookup_relation}"
            return {
                "lookup_key": lookup_key,
                "lookup_basis": lookup_basis,
                "lookup_relation": lookup_relation,
                "search_query": search_query,
                "search_terms": _relation_search_terms(search_query),
                "temporal_wrapper_query": stripped_query,
                "temporal_wrapper_applied": True,
            }
    candidate_queries = _temporal_wrapped_relation_candidate_queries(stripped_query, stripped_tokens)
    for candidate_query in candidate_queries:
        relation_plan = _relation_query_plan(candidate_query)
        if relation_plan is None:
            continue
        wrapped_plan = dict(relation_plan)
        wrapped_plan["temporal_wrapper_query"] = stripped_query
        wrapped_plan["temporal_wrapper_applied"] = candidate_query != stripped_query
        return wrapped_plan
    return None


def _chronology_query_variants(query: str, raw_tokens: list[str], raw_terms: list[str]) -> dict[str, Any] | None:
    matched_terms = [term for term in raw_terms if term in TEMPORAL_CHRONOLOGY_TERMS]
    if not matched_terms:
        return None
    relation_plan = _temporal_wrapped_relation_query_plan(
        query,
        raw_tokens,
        excluded_terms=(
            SUBJECT_LOOKUP_QUERY_WRAPPERS
            | CHRONOLOGY_QUERY_NOISE_TERMS
            | CHRONOLOGY_QUERY_MUTATION_TERMS
        ),
    )
    core_info = _canonical_subject_core_terms(
        raw_terms,
        excluded_terms=(
            SUBJECT_LOOKUP_QUERY_WRAPPERS
            | CHRONOLOGY_QUERY_NOISE_TERMS
            | CHRONOLOGY_QUERY_MUTATION_TERMS
        ),
    )
    relation_terms = [str(term) for term in (relation_plan or {}).get("search_terms", []) if str(term)]
    core_terms = relation_terms or core_info["core_terms"]
    variant_info = _subject_core_search_variants(core_terms, basis="chronology-subject-core")
    return {
        "matched_terms": sorted(set(matched_terms)),
        "raw_core_terms": core_info["raw_core_terms"],
        "core_terms": core_terms,
        "matched_aliases": core_info["matched_aliases"],
        "alias_expanded": core_info["alias_expanded"],
        "search_alias_variants": variant_info["search_alias_variants"],
        "search_alias_expanded": variant_info["search_alias_expanded"],
        "variants": variant_info["variants"],
    }


def _history_query_variants(query: str, raw_terms: list[str]) -> dict[str, Any] | None:
    raw_tokens = _query_tokens(query)
    history_before_update = "before" in raw_terms and "update" in raw_terms
    history_excluded_terms = HISTORY_QUERY_NOISE_TERMS | ({"update"} if history_before_update else set())
    relation_plan = _temporal_wrapped_relation_query_plan(
        query,
        _query_tokens(query),
        excluded_terms=history_excluded_terms,
    )
    relation_basis = str((relation_plan or {}).get("lookup_basis") or "")
    passive_history_wrapper = relation_basis.startswith("inverse-relation-") or relation_basis.startswith(
        "passive-relation-"
    )
    matched_terms = _ordered_unique([term for term in raw_terms if term in GENERIC_HISTORY_QUERY_TERMS])
    if history_before_update or ("before" in raw_terms and passive_history_wrapper):
        matched_terms = _ordered_unique(matched_terms + ["before"])
    if not matched_terms:
        return None
    core_info = _canonical_subject_core_terms(
        raw_terms,
        excluded_terms=history_excluded_terms,
    )
    relation_terms = [str(term) for term in (relation_plan or {}).get("search_terms", []) if str(term)]
    core_terms = relation_terms or core_info["core_terms"]
    inferred_role = None
    if not relation_terms:
        inferred_role = _implicit_owner_core_terms_for_person_query(
            raw_tokens,
            core_info["raw_core_terms"],
            core_terms,
        )
        if inferred_role is not None:
            core_terms = [str(term) for term in inferred_role["core_terms"] if str(term)]
    variant_info = _subject_core_search_variants(core_terms, basis="history-subject-core")
    return {
        "matched_terms": matched_terms,
        "raw_core_terms": core_info["raw_core_terms"],
        "core_terms": core_terms,
        "matched_aliases": core_info["matched_aliases"],
        "alias_expanded": core_terms != core_info["raw_core_terms"],
        "search_alias_variants": variant_info["search_alias_variants"],
        "search_alias_expanded": variant_info["search_alias_expanded"],
        "role_inferred": (inferred_role or {}).get("role"),
        "role_inference_reason": (inferred_role or {}).get("reason"),
        "expanded": bool(variant_info["variants"]),
        "variants": variant_info["variants"],
    }


def _current_query_variants(query: str, raw_terms: list[str]) -> dict[str, Any] | None:
    matched_terms = _ordered_unique([term for term in raw_terms if term in TEMPORAL_CURRENT_TERMS])
    if not matched_terms:
        return None
    current_excluded_terms = TEMPORAL_CURRENT_TERMS | SUBJECT_LOOKUP_QUERY_WRAPPERS | {"are", "be", "did", "do", "does", "is", "was", "were"}
    relation_plan = _temporal_wrapped_relation_query_plan(
        query,
        _query_tokens(query),
        excluded_terms=current_excluded_terms,
    )
    core_info = _canonical_subject_core_terms(
        raw_terms,
        excluded_terms=current_excluded_terms,
    )
    relation_terms = [str(term) for term in (relation_plan or {}).get("search_terms", []) if str(term)]
    core_terms = relation_terms or core_info["core_terms"]
    inferred_role = None
    if not relation_terms:
        inferred_role = _implicit_owner_core_terms_for_person_query(
            raw_terms,
            core_info["raw_core_terms"],
            core_terms,
        )
        if inferred_role is not None:
            core_terms = [str(term) for term in inferred_role["core_terms"] if str(term)]
    variant_info = _subject_core_search_variants(core_terms, basis="current-subject-core")
    return {
        "matched_terms": matched_terms,
        "raw_core_terms": core_info["raw_core_terms"],
        "core_terms": core_terms,
        "matched_aliases": core_info["matched_aliases"],
        "alias_expanded": core_terms != core_info["raw_core_terms"],
        "search_alias_variants": variant_info["search_alias_variants"],
        "search_alias_expanded": variant_info["search_alias_expanded"],
        "role_inferred": (inferred_role or {}).get("role"),
        "role_inference_reason": (inferred_role or {}).get("reason"),
        "expanded": bool(variant_info["variants"]),
        "variants": variant_info["variants"],
    }


def _update_query_variants(query: str) -> dict[str, Any] | None:
    raw_tokens = _query_tokens(query)
    matched_terms = _ordered_unique([term for term in raw_tokens if term in CHRONOLOGY_QUERY_MUTATION_TERMS])
    if not matched_terms:
        return None
    history_direction_terms = _ordered_unique(
        [term for term in raw_tokens if term in UPDATE_QUERY_HISTORY_DIRECTION_TERMS]
    )
    current_direction_terms = _ordered_unique(
        [term for term in raw_tokens if term in UPDATE_QUERY_CURRENT_DIRECTION_TERMS]
    )
    if history_direction_terms:
        direction = "history"
        direction_terms = history_direction_terms
        search_basis = "update-history-subject-core"
    elif current_direction_terms:
        direction = "current"
        direction_terms = current_direction_terms
        search_basis = "update-subject-core"
    else:
        return None
    core_info = _canonical_subject_core_terms(
        raw_tokens,
        excluded_terms=(
            UPDATE_QUERY_NOISE_TERMS
            | CHRONOLOGY_QUERY_MUTATION_TERMS
            | UPDATE_QUERY_CURRENT_DIRECTION_TERMS
            | UPDATE_QUERY_HISTORY_DIRECTION_TERMS
        ),
    )
    relation_plan = _temporal_wrapped_relation_query_plan(
        query,
        raw_tokens,
        excluded_terms=(
            UPDATE_QUERY_NOISE_TERMS
            | CHRONOLOGY_QUERY_MUTATION_TERMS
            | UPDATE_QUERY_CURRENT_DIRECTION_TERMS
            | UPDATE_QUERY_HISTORY_DIRECTION_TERMS
        ),
    )
    relation_terms = [str(term) for term in (relation_plan or {}).get("search_terms", []) if str(term)]
    core_terms = relation_terms or core_info["core_terms"]
    inferred_role = None
    if not relation_terms:
        inferred_role = _implicit_owner_core_terms_for_person_query(
            raw_tokens,
            core_info["raw_core_terms"],
            core_terms,
        )
        if inferred_role is not None:
            core_terms = [str(term) for term in inferred_role["core_terms"] if str(term)]
    variant_info = _subject_core_search_variants(core_terms, basis=search_basis)
    return {
        "matched_terms": matched_terms,
        "raw_core_terms": core_info["raw_core_terms"],
        "core_terms": core_terms,
        "matched_aliases": core_info["matched_aliases"],
        "alias_expanded": core_terms != core_info["raw_core_terms"],
        "search_alias_variants": variant_info["search_alias_variants"],
        "search_alias_expanded": variant_info["search_alias_expanded"],
        "direction": direction,
        "direction_terms": direction_terms,
        "role_inferred": (inferred_role or {}).get("role"),
        "role_inference_reason": (inferred_role or {}).get("reason"),
        "expanded": bool(variant_info["variants"]),
        "variants": variant_info["variants"],
    }


def _target_qualified_history_variants(query: str) -> dict[str, Any] | None:
    normalized_query = " ".join(_query_tokens(query))
    if not normalized_query:
        return None
    match = re.match(
        r"^(?:where|what|which)\s+did\s+(?P<subject>.+?)\s+deploy(?:\s+to)?\s+before\s+it\s+"
        r"(?P<mutation>change|changed|move|moved|shift|shifted|switch|switched|update|updated)"
        r"(?:\s+(?:to|into))\s+(?P<target>.+)$",
        normalized_query,
        re.IGNORECASE,
    )
    if not match:
        return None
    subject_query = _normalize_conflict_fragment(match.group("subject"))
    target_query = _normalize_conflict_fragment(match.group("target"))
    if not subject_query or not target_query:
        return None
    return {
        "applied": True,
        "relation": "deploys_to",
        "history_terms": ["before"],
        "mutation_terms": [str(match.group("mutation")).lower()],
        "target_query": target_query,
        "variants": [
            {
                "query": subject_query,
                "terms": query_terms(subject_query),
                "basis": "history-target-subject-entity",
            },
            {
                "query": f"{subject_query} deploy",
                "terms": query_terms(f"{subject_query} deploy"),
                "basis": "history-target-subject-action",
            },
        ],
    }


def _relation_query_plan(query: str) -> dict[str, Any] | None:
    tokens = [token for token in _query_tokens(query) if token not in TEMPORAL_CURRENT_TERMS]
    normalized_query = " ".join(tokens)
    if not normalized_query:
        return None
    for basis, relation, pattern, canonical_builder in RELATION_QUERY_PATTERNS:
        match = pattern.match(normalized_query)
        if not match:
            continue
        inverse_relation_basis = basis.startswith("inverse-relation-")
        if "object" in pattern.groupindex:
            canonical_query = _normalize_relation_search_fragment(canonical_builder(match))
            search_terms = _relation_search_terms(canonical_query)
            if "subject" in pattern.groupindex:
                lookup_key = _normalize_lookup_subject_fragment(match.group("subject"))
            else:
                lookup_key = _normalize_relation_value_fragment(match.group("object"))
        else:
            if inverse_relation_basis:
                subject_query = (
                    _normalize_lookup_subject_fragment(match.group("subject"))
                    if "subject" in pattern.groupindex
                    else ""
                )
                relation_phrase = _normalize_conflict_fragment(relation.replace("_", " "))
                canonical_query = " ".join(part for part in (subject_query, relation_phrase) if part)
                search_terms = _relation_search_terms(canonical_query)
            else:
                canonical_query = _normalize_conflict_fragment(canonical_builder(match))
                search_terms = query_terms(canonical_query)
            if relation == "is":
                lookup_key = canonical_query
            elif "subject" in pattern.groupindex:
                lookup_key = _normalize_lookup_subject_fragment(match.group("subject"))
            else:
                relation_suffix = _normalize_conflict_fragment(relation.replace("_", " "))
                lookup_key = canonical_query.removesuffix(f" {relation_suffix}") or canonical_query
        if basis in OWNER_RELATION_MULTI_HOP_LOOKUP_BASES and relation == "is":
            canonical_terms = query_terms(canonical_query)
            if canonical_terms and canonical_terms[-1] == "owner":
                trimmed_subject_terms = _trim_owner_relation_phrase_alias_terms(canonical_terms[:-1])
                canonical_terms = [*trimmed_subject_terms, "owner"]
                canonical_query = " ".join(canonical_terms)
                lookup_key = canonical_query
                search_terms = query_terms(canonical_query)
        if not canonical_query:
            return None
        return {
            "lookup_key": lookup_key,
            "lookup_basis": basis,
            "lookup_relation": relation,
            "search_query": canonical_query,
            "search_terms": search_terms,
        }
    return None


def _subject_lookup_query_plan(query: str, query_terms: list[str]) -> dict[str, Any]:
    temporal_signal_terms = (
        TEMPORAL_CHRONOLOGY_TERMS
        | TEMPORAL_CURRENT_TERMS
        | TEMPORAL_HISTORY_TERMS
        | CHRONOLOGY_QUERY_MUTATION_TERMS
        | UPDATE_QUERY_CURRENT_DIRECTION_TERMS
        | UPDATE_QUERY_HISTORY_DIRECTION_TERMS
    )
    temporal_wrapper_terms = (
        SUBJECT_LOOKUP_QUERY_WRAPPERS
        | TEMPORAL_CHRONOLOGY_TERMS
        | TEMPORAL_CURRENT_TERMS
        | TEMPORAL_HISTORY_TERMS
        | CHRONOLOGY_QUERY_MUTATION_TERMS
        | UPDATE_QUERY_CURRENT_DIRECTION_TERMS
        | UPDATE_QUERY_HISTORY_DIRECTION_TERMS
        | {"did", "do", "does", "is", "are", "was", "were"}
    )
    raw_tokens = _query_tokens(query)
    temporal_relation_plan = _temporal_wrapped_relation_query_plan(
        query,
        raw_tokens,
        excluded_terms=temporal_wrapper_terms,
    )
    if temporal_relation_plan is not None and any(token in temporal_signal_terms for token in raw_tokens):
        return temporal_relation_plan
    relation_plan = _relation_query_plan(query)
    if relation_plan is not None:
        return relation_plan
    if temporal_relation_plan is not None:
        return temporal_relation_plan
    if any(term in TEMPORAL_CURRENT_TERMS for term in query_terms):
        return {
            "lookup_key": _normalize_conflict_fragment(
                " ".join(
                    term
                    for term in query_terms
                    if term not in TEMPORAL_CURRENT_TERMS and term not in SUBJECT_LOOKUP_QUERY_WRAPPERS
                )
            ),
            "lookup_basis": "current-term",
            "lookup_relation": None,
            "search_query": _normalize_conflict_fragment(query),
        }
    if query_terms and query_terms[0] in SUBJECT_LOOKUP_QUERY_WRAPPERS:
        return {
            "lookup_key": _normalize_conflict_fragment(
                " ".join(
                    term
                    for term in query_terms
                    if term not in SUBJECT_LOOKUP_QUERY_WRAPPERS
                )
            ),
            "lookup_basis": "question-wrapper",
            "lookup_relation": None,
            "search_query": _normalize_conflict_fragment(
                " ".join(
                    term
                    for term in query_terms
                    if term not in SUBJECT_LOOKUP_QUERY_WRAPPERS
                )
            ),
        }
    normalized_query = _normalize_conflict_fragment(" ".join(query_terms))
    return {
        "lookup_key": normalized_query,
        "lookup_basis": "direct-subject",
        "lookup_relation": None,
        "search_query": normalized_query,
    }


def _generic_subject_alias_variant(raw_tokens: list[str]) -> dict[str, Any] | None:
    informative_tokens = [
        token
        for token in raw_tokens
        if token not in GENERIC_SUBJECT_NOISE_TERMS
    ]
    if not informative_tokens:
        return None
    matched_aliases = []
    core_terms = []
    for token in informative_tokens:
        canonical = SEMANTIC_ALIAS_CANONICAL_BY_TOKEN.get(token)
        if canonical is not None:
            matched_aliases.append({"token": token, "canonical": canonical})
            core_terms.append(canonical)
            continue
        if len(token) > 2 and token not in GENERIC_SUBJECT_HELPER_TERMS:
            core_terms.append(token)
    core_terms = _ordered_unique(core_terms)
    if not matched_aliases or not core_terms:
        return None
    return {
        "lookup_basis": "semantic-alias-core",
        "search_query": " ".join(core_terms),
        "search_terms": core_terms,
        "matched_aliases": matched_aliases,
        "core_terms": core_terms,
    }


def _direct_deploy_target_alias_variant(raw_tokens: list[str]) -> dict[str, Any] | None:
    core_info = _canonical_subject_core_terms(
        raw_tokens,
        excluded_terms=GENERIC_SUBJECT_NOISE_TERMS,
    )
    raw_core_terms = [str(term) for term in core_info.get("raw_core_terms", []) if str(term)]
    core_terms = [str(term) for term in core_info.get("core_terms", []) if str(term)]
    if "deploy" not in raw_core_terms or "target" not in core_terms:
        return None
    variant_info = _subject_core_search_variants(core_terms, basis="direct-deploy-target-core")
    if not variant_info.get("variants"):
        return None
    first_variant = variant_info["variants"][0]
    return {
        "lookup_basis": "direct-deploy-target-core",
        "search_query": str(first_variant["query"]),
        "search_terms": [str(term) for term in first_variant.get("terms", []) if str(term)],
        "matched_aliases": core_info.get("matched_aliases", []),
        "raw_core_terms": raw_core_terms,
        "core_terms": core_terms,
        "alias_expanded": bool(core_info.get("alias_expanded")),
        "variants": variant_info.get("variants", []),
        "search_alias_variants": variant_info.get("search_alias_variants", []),
        "search_alias_expanded": bool(variant_info.get("search_alias_expanded")),
    }


def _direct_subject_core_alias_variant(
    query_lookup: dict[str, Any],
    raw_tokens: list[str],
) -> dict[str, Any] | None:
    lookup_basis = str(query_lookup.get("lookup_basis") or "")
    if lookup_basis not in {
        "direct-subject",
        "question-wrapper",
        "role-relation-owner",
        "role-relation-on-point",
        "role-relation-responsible",
        "role-relation-in-charge",
    }:
        return None
    search_query = str(query_lookup.get("search_query") or "").strip()
    search_terms = [str(term) for term in query_lookup.get("search_terms", []) if str(term)] or query_terms(search_query)
    if not {"owner", "contact"}.intersection(search_terms):
        return None
    variant_info = _subject_core_search_variants(
        search_terms,
        basis=lookup_basis,
        include_phrase_aliases=False,
    )
    if "deployment" in search_terms and {"owner", "contact"}.intersection(search_terms):
        number_alias_query = None
        number_alias_terms = list(search_terms)
        if "approvals" in search_terms:
            number_alias_terms[number_alias_terms.index("approvals")] = "approval"
            number_alias_query = " ".join(number_alias_terms)
            number_alias_canonical = "approvals"
            number_alias_search_term = "approval"
        elif "approval" in search_terms:
            number_alias_terms[number_alias_terms.index("approval")] = "approvals"
            number_alias_query = " ".join(number_alias_terms)
            number_alias_canonical = "approval"
            number_alias_search_term = "approvals"
        else:
            number_alias_canonical = None
            number_alias_search_term = None
        if (
            number_alias_query
            and number_alias_canonical
            and number_alias_search_term
            and number_alias_query not in {str(variant.get("query") or "") for variant in variant_info.get("variants", [])}
        ):
            variant_info.setdefault("variants", []).insert(
                1 if variant_info.get("variants") else 0,
                {
                    "query": number_alias_query,
                    "terms": number_alias_terms,
                    "basis": f"{lookup_basis}-alias",
                }
            )
            variant_info.setdefault("search_alias_variants", []).append(
                {
                    "canonical": number_alias_canonical,
                    "search_term": number_alias_search_term,
                    "query": number_alias_query,
                }
            )
            variant_info["search_alias_expanded"] = True
        normalized_search_query = _normalize_conflict_fragment(" ".join(search_terms))
        search_term_set = {str(term) for term in search_terms if str(term)}
        for alias_variant in SUBJECT_CORE_PHRASE_ALIAS_VARIANTS:
            allow_late_phrase_alias_lookup = bool(alias_variant.get("allow_empty_subject_anchor"))
            if (
                not allow_late_phrase_alias_lookup
                and alias_variant.get("prefer_before_core")
                and "owner" in search_term_set
            ):
                allow_late_phrase_alias_lookup = True
            if not allow_late_phrase_alias_lookup:
                continue
            required_terms = {str(term) for term in alias_variant["required_terms"] if str(term)}
            if not required_terms or not required_terms.issubset(search_term_set):
                continue
            alias_query = str(alias_variant["search_query"]).strip()
            alias_terms = query_terms(alias_query)
            if (
                not alias_query
                or not alias_terms
                or alias_query in {str(variant.get("query") or "") for variant in variant_info.get("variants", [])}
            ):
                continue
            variant_info.setdefault("variants", []).append(
                {
                    "query": alias_query,
                    "terms": alias_terms,
                    "basis": f"{lookup_basis}-phrase-alias",
                }
            )
            variant_info.setdefault("search_alias_variants", []).append(
                {
                    "canonical_query": normalized_search_query,
                    "search_term": alias_query,
                    "query": alias_query,
                    "match_strategy": "phrase",
                }
            )
            variant_info["search_alias_expanded"] = True
    if not variant_info.get("search_alias_variants"):
        return None
    matched_aliases = _canonical_subject_core_terms(
        raw_tokens,
        excluded_terms=GENERIC_SUBJECT_NOISE_TERMS,
    ).get("matched_aliases", [])
    return {
        "lookup_basis": lookup_basis,
        "search_query": search_query,
        "search_terms": search_terms,
        "matched_aliases": matched_aliases,
        "raw_core_terms": search_terms,
        "core_terms": search_terms,
        "alias_expanded": bool(variant_info.get("search_alias_expanded")),
        "variants": variant_info.get("variants", []),
        "search_alias_variants": variant_info.get("search_alias_variants", []),
        "search_alias_expanded": bool(variant_info.get("search_alias_expanded")),
    }


def _row_term_overlap(row: sqlite3.Row, terms: list[str]) -> int:
    memory = MemoryRecord.from_row(row)
    haystack = f"{memory.content} {' '.join(memory.labels)}".strip().lower()
    return sum(1 for term in terms if term and term in haystack)


def _has_full_lexical_match(rows: list[sqlite3.Row], terms: list[str]) -> bool:
    normalized_terms = [str(term).lower() for term in terms if str(term)]
    if not normalized_terms:
        return False
    return any(_row_term_overlap(row, normalized_terms) >= len(normalized_terms) for row in rows)


def _row_has_structured_fact(row: sqlite3.Row) -> bool:
    memory = MemoryRecord.from_row(row)
    return _lexical_conflict_signature(memory) is not None or _lexical_update_signature(memory) is not None


def _current_update_anchor_terms(current_lookup: dict[str, Any] | None) -> list[str]:
    if not current_lookup or not current_lookup.get("matched_terms"):
        return []
    return _ordered_unique(
        [
            str(term)
            for term in current_lookup.get("core_terms", [])
            if str(term)
            and str(term) not in GENERIC_SUBJECT_NOISE_TERMS
            and str(term) not in GENERIC_SUBJECT_HELPER_TERMS
            and len(str(term)) > 2
        ]
    )


def _relation_support_anchor_profile(
    *,
    query_lookup: dict[str, Any],
    matched_terms: list[str],
    selected_variant: dict[str, Any],
    basis_prefixes: tuple[str, ...],
    support_kind: str,
) -> dict[str, Any] | None:
    if not matched_terms:
        return None
    lookup_key = _normalize_lookup_subject_fragment(str(query_lookup.get("lookup_key") or ""))
    if not lookup_key:
        return None
    lookup_relation = str(query_lookup.get("lookup_relation") or "")
    relation_terms = list(CHRONOLOGY_RELATION_SUPPORT_TERMS.get(lookup_relation, []))
    if not relation_terms:
        return None
    selected_search_basis = str(selected_variant.get("basis") or "")
    if not any(selected_search_basis.startswith(prefix) for prefix in basis_prefixes):
        return None
    return {
        "applied": False,
        "reason": "no-support-anchor-match",
        "subject_term": lookup_key,
        "relation": lookup_relation,
        "relation_terms": relation_terms,
        "mutation_terms": sorted(CHRONOLOGY_QUERY_MUTATION_TERMS),
        "selected_search_basis": selected_search_basis,
        "selected_candidate_ids": [],
        "support_kind": support_kind,
    }


def _chronology_support_anchor_profile(
    *,
    query_lookup: dict[str, Any],
    chronology: dict[str, Any] | None,
    selected_variant: dict[str, Any],
) -> dict[str, Any] | None:
    return _relation_support_anchor_profile(
        query_lookup=query_lookup,
        matched_terms=[str(term) for term in (chronology or {}).get("matched_terms", []) if str(term)],
        selected_variant=selected_variant,
        basis_prefixes=("chronology-subject-core",),
        support_kind="chronology",
    )


def _history_support_anchor_profile(
    *,
    query_lookup: dict[str, Any],
    history_lookup: dict[str, Any] | None,
    selected_variant: dict[str, Any],
) -> dict[str, Any] | None:
    return _relation_support_anchor_profile(
        query_lookup=query_lookup,
        matched_terms=[str(term) for term in (history_lookup or {}).get("matched_terms", []) if str(term)],
        selected_variant=selected_variant,
        basis_prefixes=("history-subject-core",),
        support_kind="history",
    )


def _update_history_support_anchor_profile(
    *,
    query_lookup: dict[str, Any],
    update_lookup: dict[str, Any] | None,
    selected_variant: dict[str, Any],
) -> dict[str, Any] | None:
    if str((update_lookup or {}).get("direction") or "") != "history":
        return None
    matched_terms = _ordered_unique(
        [str(term) for term in (update_lookup or {}).get("matched_terms", []) if str(term)]
        + [str(term) for term in (update_lookup or {}).get("direction_terms", []) if str(term)]
    )
    return _relation_support_anchor_profile(
        query_lookup=query_lookup,
        matched_terms=matched_terms,
        selected_variant=selected_variant,
        basis_prefixes=("update-history-subject-core",),
        support_kind="update-history",
    )


def _update_current_support_anchor_profile(
    *,
    query_lookup: dict[str, Any],
    update_lookup: dict[str, Any] | None,
    selected_variant: dict[str, Any],
) -> dict[str, Any] | None:
    if str((update_lookup or {}).get("direction") or "") != "current":
        return None
    matched_terms = _ordered_unique(
        [str(term) for term in (update_lookup or {}).get("matched_terms", []) if str(term)]
        + [str(term) for term in (update_lookup or {}).get("direction_terms", []) if str(term)]
    )
    return _relation_support_anchor_profile(
        query_lookup=query_lookup,
        matched_terms=matched_terms,
        selected_variant=selected_variant,
        basis_prefixes=("update-subject-core",),
        support_kind="update-current",
    )


def _append_relation_support_rows(
    conn: sqlite3.Connection,
    *,
    support: dict[str, Any],
    rows: list[sqlite3.Row],
    candidate_metadata: dict[str, dict[str, Any]],
    status_sql: str,
    scope_sql: str,
    authority_order_sql: str,
    scope: str | None,
    limit: int,
) -> None:
    if not support or not rows or len(rows) >= limit:
        return
    relation_terms = [str(term) for term in support.get("relation_terms", []) if str(term)]
    mutation_terms = [str(term) for term in support.get("mutation_terms", []) if str(term)]
    subject_term = str(support.get("subject_term") or "")
    if not subject_term or not relation_terms or not mutation_terms:
        return
    relation_sql = " OR ".join(["lower(m.content) LIKE ?" for _ in relation_terms])
    mutation_sql = " OR ".join(["lower(m.content) LIKE ?" for _ in mutation_terms])
    support_params: list[Any] = [f"%{subject_term}%"]
    support_params.extend(f"%{term}%" for term in relation_terms)
    support_params.extend(f"%{term}%" for term in mutation_terms)
    if scope:
        support_params.append(scope)
    support_rows = conn.execute(
        f"""
        SELECT m.*,
               COALESCE((SELECT MAX(e.seq) FROM events e WHERE e.memory_id = m.id), 0) AS observation_seq
        FROM memories m
        WHERE lower(m.content) LIKE ?
          AND ({relation_sql})
          AND ({mutation_sql})
          AND {status_sql}
          {scope_sql}
        ORDER BY {authority_order_sql} DESC, m.trust DESC, observation_seq DESC, m.id ASC
        LIMIT {limit}
        """,
        support_params,
    ).fetchall()
    existing_ids = {row["id"] for row in rows}
    for support_row in support_rows:
        if support_row["id"] in existing_ids:
            continue
        rows.append(support_row)
        existing_ids.add(support_row["id"])
        support["selected_candidate_ids"].append(str(support_row["id"]))
        candidate_metadata[str(support_row["id"])] = {
            "pre_hybrid_rank": None,
            "hybrid_candidate_source": f"{support['support_kind']}-support",
            "structured_fact_candidate": _row_has_structured_fact(support_row),
            "semantic_backfill_score": None,
            "semantic_backfill_term_overlap": None,
            "observation_seq": int(support_row["observation_seq"]) if "observation_seq" in support_row.keys() else 0,
            "temporal_support_candidate": True,
            "temporal_support_kind": support["support_kind"],
        }
        if len(rows) >= limit:
            break
    if support["selected_candidate_ids"]:
        support["applied"] = True
        support["reason"] = "subject_relation_mutation_anchor"


def _transcript_memory_locator(content: str) -> dict[str, Any] | None:
    match = TRANSCRIPT_MEMORY_PREFIX_PATTERN.match(content)
    if match is None:
        return None
    return {
        "session_id": str(match.group("session")),
        "turn": int(match.group("turn")),
        "timestamp": " ".join(str(match.group("timestamp")).split()),
        "speaker": " ".join(str(match.group("speaker")).lower().split()),
    }


def _transcript_neighbor_support_expansion(
    conn: sqlite3.Connection,
    *,
    query: str,
    search_mode: str,
    rows: list[sqlite3.Row],
    candidate_metadata: dict[str, dict[str, Any]],
    status_sql: str,
    scope_sql: str,
    authority_order_sql: str,
    scope: str | None,
    limit: int,
) -> tuple[list[sqlite3.Row], dict[str, Any]]:
    metadata = {
        "schema": SUPPORT_EXPANSION_SCHEMA,
        "strategy": "transcript_neighbor_support_v1",
        "applied": False,
        "reason": "query-not-when-did-onset-shaped",
        "subject_term": None,
        "event_terms": [],
        "event_head_term": None,
        "nucleus_candidate_ids": [],
        "selected_candidate_ids": [],
        "selected_candidates": [],
        "replaced_candidate_ids": [],
        "candidate_limit": 1,
        "max_turn_distance": TRANSCRIPT_NEIGHBOR_SUPPORT_MAX_TURN_DISTANCE,
        "max_nuclei": TRANSCRIPT_NEIGHBOR_SUPPORT_MAX_NUCLEI,
        "direction": "earlier",
        "same_timestamp_required": True,
        "search_mode": search_mode,
    }
    match = WHEN_DID_ONSET_SUPPORT_QUERY_PATTERN.fullmatch(" ".join(query.strip().split()))
    if match is None or limit <= 0 or not rows:
        return rows, metadata
    if search_mode not in {"fallback", "semantic"}:
        metadata["reason"] = "search-mode-not-eligible"
        return rows, metadata

    subject_term = str(match.group("subject")).lower()
    event_text = str(match.group("event"))
    event_terms = _ordered_unique(
        [
            term
            for term in query_terms(event_text)
            if term != subject_term
            and term not in TRANSCRIPT_NEIGHBOR_SUPPORT_NOISE_TERMS
            and term not in MULTI_HOP_STOPWORDS
            and not term.isdigit()
        ]
    )
    event_head_text = re.split(
        r"\b(?:after|before|during|for|from|in|on|with)\b",
        event_text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    event_head_terms = [
        term
        for term in query_terms(event_head_text)
        if term != subject_term
        and term not in TRANSCRIPT_NEIGHBOR_SUPPORT_NOISE_TERMS
        and term not in MULTI_HOP_STOPWORDS
        and not term.isdigit()
    ]
    event_head_term = event_head_terms[-1] if event_head_terms else None
    metadata.update(
        {
            "reason": "no-event-anchor",
            "subject_term": subject_term,
            "event_terms": event_terms,
            "event_head_term": event_head_term,
        }
    )
    if not event_terms:
        return rows, metadata
    if len(event_terms) < 2:
        metadata["reason"] = "insufficient-event-anchors"
        return rows, metadata
    if event_head_term is None:
        metadata["reason"] = "no-event-head-anchor"
        return rows, metadata

    nucleus_profiles = []
    for row in rows:
        locator = _transcript_memory_locator(str(row["content"]))
        if locator is None or locator["speaker"] != subject_term:
            continue
        content_terms = set(query_terms(str(row["content"])))
        if event_head_term not in content_terms:
            continue
        matched_event_terms = sorted(set(event_terms).intersection(content_terms))
        if not matched_event_terms:
            continue
        observation_seq = int(row["observation_seq"]) if "observation_seq" in row.keys() else 0
        if observation_seq <= 0:
            continue
        nucleus_profiles.append(
            {
                "memory_id": str(row["id"]),
                "locator": locator,
                "event_terms": matched_event_terms,
                "observation_seq": observation_seq,
            }
        )
    nucleus_profiles = nucleus_profiles[:TRANSCRIPT_NEIGHBOR_SUPPORT_MAX_NUCLEI]
    metadata["nucleus_candidate_ids"] = [item["memory_id"] for item in nucleus_profiles]
    if not nucleus_profiles:
        metadata["reason"] = "no-retrieved-transcript-nucleus"
        return rows, metadata

    candidate_event_seqs = sorted(
        {
            int(nucleus["observation_seq"]) + offset
            for nucleus in nucleus_profiles
            for offset in range(
                -TRANSCRIPT_NEIGHBOR_SUPPORT_MAX_TURN_DISTANCE,
                TRANSCRIPT_NEIGHBOR_SUPPORT_MAX_TURN_DISTANCE + 1,
            )
            if offset != 0 and int(nucleus["observation_seq"]) + offset > 0
        }
    )
    if not candidate_event_seqs:
        metadata["reason"] = "no-transcript-neighbor-event-window"
        return rows, metadata
    event_seq_sql = ",".join(["?" for _ in candidate_event_seqs])
    params: list[Any] = list(candidate_event_seqs)
    if scope:
        params.append(scope)
    support_rows = conn.execute(
        f"""
        SELECT m.*,
               e.seq AS observation_seq
        FROM events e
        JOIN memories m ON m.id = e.memory_id
        WHERE e.seq IN ({event_seq_sql})
          AND e.event_type IN ('OBSERVED', 'PROPOSED')
          AND {status_sql}
          {scope_sql}
        ORDER BY {authority_order_sql} DESC, m.trust DESC, observation_seq DESC, m.id ASC
        """,
        params,
    ).fetchall()
    existing_ids = {str(row["id"]) for row in rows}
    candidates = []
    for row in support_rows:
        memory_id = str(row["id"])
        if memory_id in existing_ids:
            continue
        locator = _transcript_memory_locator(str(row["content"]))
        if locator is None or locator["speaker"] != subject_term:
            continue
        content_terms = set(query_terms(str(row["content"])))
        if event_head_term not in content_terms:
            continue
        relations = []
        for nucleus in nucleus_profiles:
            nucleus_locator = nucleus["locator"]
            if locator["session_id"] != nucleus_locator["session_id"]:
                continue
            if locator["timestamp"] != nucleus_locator["timestamp"]:
                continue
            candidate_turn = int(locator["turn"])
            nucleus_turn = int(nucleus_locator["turn"])
            if candidate_turn >= nucleus_turn:
                continue
            turn_distance = nucleus_turn - candidate_turn
            if turn_distance > TRANSCRIPT_NEIGHBOR_SUPPORT_MAX_TURN_DISTANCE:
                continue
            shared_event_terms = sorted(set(nucleus["event_terms"]).intersection(content_terms))
            if not shared_event_terms:
                continue
            relations.append(
                {
                    "nucleus_memory_id": nucleus["memory_id"],
                    "nucleus_turn": nucleus_turn,
                    "turn_distance": turn_distance,
                    "direction": "earlier",
                    "same_timestamp": True,
                    "shared_event_terms": shared_event_terms,
                }
            )
        if not relations:
            continue
        relations.sort(
            key=lambda item: (
                int(item["turn_distance"]),
                -len(item["shared_event_terms"]),
                int(item["nucleus_turn"]),
                str(item["nucleus_memory_id"]),
            )
        )
        relation = relations[0]
        observation_seq = int(row["observation_seq"]) if "observation_seq" in row.keys() else 0
        candidates.append(
            {
                "row": row,
                "locator": locator,
                "observation_seq": observation_seq,
                **relation,
            }
        )
    if not candidates:
        metadata["reason"] = "no-transcript-neighbor-candidate"
        return rows, metadata

    candidates.sort(
        key=lambda item: (
            int(item["turn_distance"]),
            -len(item["shared_event_terms"]),
            -authority_rank(str(item["row"]["authority"])),
            -float(item["row"]["trust"]),
            int(item["locator"]["turn"]),
            str(item["row"]["id"]),
        )
    )
    selected = candidates[0]
    selected_row = selected["row"]
    selected_id = str(selected_row["id"])
    selected_detail = {
        "memory_id": selected_id,
        "transcript_session_id": selected["locator"]["session_id"],
        "transcript_turn": int(selected["locator"]["turn"]),
        "speaker": selected["locator"]["speaker"],
        "nucleus_memory_id": selected["nucleus_memory_id"],
        "nucleus_turn": int(selected["nucleus_turn"]),
        "turn_distance": int(selected["turn_distance"]),
        "direction": selected["direction"],
        "same_timestamp": bool(selected["same_timestamp"]),
        "event_head_term": event_head_term,
        "shared_event_terms": selected["shared_event_terms"],
        "observation_seq": int(selected["observation_seq"]),
    }
    expanded_rows = [selected_row, *rows]
    replaced_rows = expanded_rows[limit:]
    rows = expanded_rows[:limit]
    metadata.update(
        {
            "applied": True,
            "reason": "same-session-speaker-topic-earlier-neighbor",
            "selected_candidate_ids": [selected_id],
            "selected_candidates": [selected_detail],
            "replaced_candidate_ids": [str(row["id"]) for row in replaced_rows],
        }
    )
    candidate_metadata[selected_id] = {
        **candidate_metadata.get(selected_id, {}),
        "pre_hybrid_rank": None,
        "hybrid_candidate_source": "transcript-neighbor-support-expansion",
        "structured_fact_candidate": _row_has_structured_fact(selected_row),
        "semantic_backfill_score": None,
        "semantic_backfill_term_overlap": len(selected["shared_event_terms"]),
        "observation_seq": int(selected["observation_seq"]),
        "support_expansion_candidate": True,
        "support_expansion_kind": "transcript-neighbor",
        "support_expansion_rank": 1,
        "support_expansion_nucleus_ids": metadata["nucleus_candidate_ids"],
        "support_expansion_event_head_term": event_head_term,
    }
    return rows, metadata


def _completion_support_expansion(
    conn: sqlite3.Connection,
    *,
    query: str,
    search_mode: str,
    rows: list[sqlite3.Row],
    candidate_metadata: dict[str, dict[str, Any]],
    status_sql: str,
    scope_sql: str,
    authority_order_sql: str,
    scope: str | None,
    limit: int,
) -> tuple[list[sqlite3.Row], dict[str, Any]]:
    metadata = {
        "schema": SUPPORT_EXPANSION_SCHEMA,
        "strategy": "nucleus_completion_support_v1",
        "applied": False,
        "reason": "query-not-completion-shaped",
        "subject_term": None,
        "object_terms": [],
        "nucleus_bridge_terms": [],
        "matched_query_terms": [],
        "nucleus_candidate_ids": [],
        "selected_candidate_ids": [],
        "selected_candidates": [],
        "replaced_candidate_ids": [],
        "candidate_limit": 1,
    }
    normalized_query = " ".join(query.strip().split())
    match = COMPLETION_SUPPORT_QUERY_PATTERN.fullmatch(normalized_query)
    if match is None and WHEN_DID_ONSET_SUPPORT_QUERY_PATTERN.fullmatch(normalized_query) is not None:
        return _transcript_neighbor_support_expansion(
            conn,
            query=query,
            search_mode=search_mode,
            rows=rows,
            candidate_metadata=candidate_metadata,
            status_sql=status_sql,
            scope_sql=scope_sql,
            authority_order_sql=authority_order_sql,
            scope=scope,
            limit=limit,
        )
    if match is None or limit <= 0 or not rows:
        return rows, metadata

    subject_term = str(match.group("subject")).lower()
    object_terms = [
        term
        for term in query_terms(str(match.group("object")))
        if term not in COMPLETION_SUPPORT_OBJECT_NOISE_TERMS
        and term not in COMPLETION_SUPPORT_TERMS
        and term != subject_term
    ]
    matched_query_terms = sorted(
        set(query_terms(str(match.group("intent")))).intersection(COMPLETION_SUPPORT_TERMS)
    )
    metadata.update(
        {
            "reason": "no-object-anchor",
            "subject_term": subject_term,
            "object_terms": object_terms,
            "matched_query_terms": matched_query_terms,
        }
    )
    if not object_terms:
        return rows, metadata

    object_term_set = set(object_terms)

    query_term_set = set(query_terms(query))

    def support_profile(row: sqlite3.Row) -> tuple[set[str], list[str], list[str]]:
        content_terms = set(query_terms(str(row["content"])))
        if subject_term not in content_terms:
            return set(), [], []
        object_overlap = sorted(object_term_set.intersection(content_terms))
        completion_overlap = sorted(COMPLETION_SUPPORT_TERMS.intersection(content_terms))
        return content_terms, object_overlap, completion_overlap

    def nucleus_bridge_profile(row: sqlite3.Row) -> set[str]:
        content = re.sub(
            r"^\s*\[[^\]]+\]\s*\([^)]*\)\s*[^:]+:\s*",
            "",
            str(row["content"]),
        )
        content_terms = query_terms(content)
        object_indexes = [
            index for index, term in enumerate(content_terms) if term in object_term_set
        ]
        local_terms: set[str] = set()
        for index in object_indexes:
            local_terms.update(content_terms[max(0, index - 8) : index + 9])
        return (
            local_terms
            - query_term_set
            - COMPLETION_SUPPORT_TERMS
            - COMPLETION_SUPPORT_OBJECT_NOISE_TERMS
            - COMPLETION_SUPPORT_BRIDGE_NOISE_TERMS
            - MULTI_HOP_STOPWORDS
            - {subject_term}
        )

    nucleus_candidate_ids = []
    existing_support_candidates = []
    nucleus_bridge_terms: set[str] = set()
    for row in rows:
        content_terms, object_overlap, completion_overlap = support_profile(row)
        if not object_overlap:
            continue
        if completion_overlap:
            existing_support_candidates.append(
                {
                    "row": row,
                    "object_overlap_terms": object_overlap,
                    "completion_terms": completion_overlap,
                    "content_terms": content_terms,
                    "already_retrieved": True,
                }
            )
            continue
        nucleus_candidate_ids.append(str(row["id"]))
        nucleus_bridge_terms.update(nucleus_bridge_profile(row))
    metadata["nucleus_candidate_ids"] = nucleus_candidate_ids
    metadata["nucleus_bridge_terms"] = sorted(nucleus_bridge_terms)
    if not nucleus_candidate_ids:
        metadata["reason"] = "no-retrieved-nucleus"
        return rows, metadata
    if not nucleus_bridge_terms:
        metadata["reason"] = "no-nucleus-bridge-term"
        return rows, metadata

    object_sql = " OR ".join(["lower(m.content) LIKE ?" for _ in object_terms])
    completion_sql = " OR ".join(["lower(m.content) LIKE ?" for _ in sorted(COMPLETION_SUPPORT_TERMS)])
    params: list[Any] = [f"%{subject_term}%"]
    params.extend(f"%{term}%" for term in object_terms)
    params.extend(f"%{term}%" for term in sorted(COMPLETION_SUPPORT_TERMS))
    if scope:
        params.append(scope)
    support_rows = conn.execute(
        f"""
        SELECT m.*,
               COALESCE((SELECT MAX(e.seq) FROM events e WHERE e.memory_id = m.id), 0) AS observation_seq
        FROM memories m
        WHERE lower(m.content) LIKE ?
          AND ({object_sql})
          AND ({completion_sql})
          AND {status_sql}
          {scope_sql}
        ORDER BY {authority_order_sql} DESC, m.trust DESC, observation_seq DESC, m.id ASC
        LIMIT {max(limit * 2, RETRIEVAL_CANDIDATE_LIMIT)}
        """,
        params,
    ).fetchall()
    existing_ids = {str(row["id"]) for row in rows}
    candidates = []
    for item in existing_support_candidates:
        bridge_overlap = sorted(nucleus_bridge_terms.intersection(item.pop("content_terms")))
        if not bridge_overlap:
            continue
        row = item["row"]
        item["nucleus_bridge_terms"] = bridge_overlap
        item["observation_seq"] = (
            int(row["observation_seq"])
            if "observation_seq" in row.keys()
            else int(candidate_metadata.get(str(row["id"]), {}).get("observation_seq") or 0)
        )
        candidates.append(item)
    for row in support_rows:
        if str(row["id"]) in existing_ids:
            continue
        content_terms, object_overlap, completion_overlap = support_profile(row)
        bridge_overlap = sorted(nucleus_bridge_terms.intersection(content_terms))
        if not object_overlap or not completion_overlap or not bridge_overlap:
            continue
        observation_seq = int(row["observation_seq"]) if "observation_seq" in row.keys() else 0
        candidates.append(
            {
                "row": row,
                "object_overlap_terms": object_overlap,
                "completion_terms": completion_overlap,
                "nucleus_bridge_terms": bridge_overlap,
                "observation_seq": observation_seq,
                "already_retrieved": False,
            }
        )
    if not candidates:
        metadata["reason"] = "no-completion-support-candidate"
        return rows, metadata

    candidates.sort(
        key=lambda item: (
            -len(item["nucleus_bridge_terms"]),
            -len(item["object_overlap_terms"]),
            -authority_rank(str(item["row"]["authority"])),
            -float(item["row"]["trust"]),
            -int(item["observation_seq"]),
            str(item["row"]["id"]),
        )
    )
    selected = candidates[0]
    selected_row = selected["row"]
    selected_id = str(selected_row["id"])
    selected_detail = {
        "memory_id": selected_id,
        "object_overlap_terms": selected["object_overlap_terms"],
        "completion_terms": selected["completion_terms"],
        "nucleus_bridge_terms": selected["nucleus_bridge_terms"],
        "observation_seq": selected["observation_seq"],
    }
    if selected["already_retrieved"]:
        metadata.update(
            {
                "reason": "completion-support-already-retrieved",
                "selected_candidate_ids": [selected_id],
                "selected_candidates": [selected_detail],
            }
        )
        return rows, metadata
    expanded_rows = [selected_row, *rows]
    replaced_rows = expanded_rows[limit:]
    rows = expanded_rows[:limit]
    metadata.update(
        {
            "applied": True,
            "reason": "nucleus-completion-paraphrase",
            "selected_candidate_ids": [selected_id],
            "selected_candidates": [selected_detail],
            "replaced_candidate_ids": [str(row["id"]) for row in replaced_rows],
        }
    )
    candidate_metadata[selected_id] = {
        **candidate_metadata.get(selected_id, {}),
        "pre_hybrid_rank": None,
        "hybrid_candidate_source": "completion-support-expansion",
        "structured_fact_candidate": _row_has_structured_fact(selected_row),
        "semantic_backfill_score": None,
        "semantic_backfill_term_overlap": len(selected["object_overlap_terms"]),
        "observation_seq": selected["observation_seq"],
        "support_expansion_candidate": True,
        "support_expansion_kind": "completion",
        "support_expansion_rank": 1,
        "support_expansion_nucleus_ids": nucleus_candidate_ids,
    }
    return rows, metadata

def _current_direct_deploy_target_hybrid_override(
    *,
    query_lookup: dict[str, Any],
    current_lookup: dict[str, Any] | None,
    semantic_alias_variant: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if query_lookup.get("lookup_relation") is not None:
        return None
    if str(query_lookup.get("lookup_basis") or "") != "current-term":
        return None
    if not current_lookup or not semantic_alias_variant:
        return None
    if not current_lookup.get("matched_terms"):
        return None
    if str(semantic_alias_variant.get("lookup_basis") or "") != "direct-deploy-target-core":
        return None
    core_terms = [str(term) for term in current_lookup.get("core_terms", []) if str(term)]
    if "deploy" not in core_terms or "target" not in core_terms:
        return None
    variants = list(current_lookup.get("variants", []))
    if not variants:
        return None
    canonical_variant = next(
        (variant for variant in variants if str(variant.get("basis") or "") == "current-subject-core"),
        variants[0],
    )
    effective_query = str(canonical_variant.get("query") or "")
    effective_query_terms = [str(term) for term in canonical_variant.get("terms", []) if str(term)]
    if not effective_query or not effective_query_terms:
        return None
    return {
        "effective_query": effective_query,
        "effective_query_terms": effective_query_terms,
        "required_terms": effective_query_terms,
        "ignored_query_terms": [str(term) for term in current_lookup.get("matched_terms", []) if str(term)],
    }


def _history_direct_deploy_target_hybrid_override(
    *,
    query_lookup: dict[str, Any],
    history_lookup: dict[str, Any] | None,
    semantic_alias_variant: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if query_lookup.get("lookup_relation") is not None:
        return None
    if not history_lookup or not semantic_alias_variant:
        return None
    if not history_lookup.get("matched_terms"):
        return None
    if str(semantic_alias_variant.get("lookup_basis") or "") != "direct-deploy-target-core":
        return None
    core_terms = [str(term) for term in history_lookup.get("core_terms", []) if str(term)]
    if "deploy" not in core_terms or "target" not in core_terms:
        return None
    variants = list(history_lookup.get("variants", []))
    if not variants:
        return None
    canonical_variant = next(
        (variant for variant in variants if str(variant.get("basis") or "") == "history-subject-core"),
        variants[0],
    )
    effective_query = str(canonical_variant.get("query") or "")
    effective_query_terms = [str(term) for term in canonical_variant.get("terms", []) if str(term)]
    if not effective_query or not effective_query_terms:
        return None
    return {
        "effective_query": effective_query,
        "effective_query_terms": effective_query_terms,
        "required_terms": effective_query_terms,
        "ignored_query_terms": [str(term) for term in history_lookup.get("matched_terms", []) if str(term)],
    }


def _update_history_direct_deploy_target_hybrid_override(
    *,
    query_lookup: dict[str, Any],
    update_lookup: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if query_lookup.get("lookup_relation") is not None:
        return None
    if not update_lookup:
        return None
    if str(update_lookup.get("direction") or "") != "history":
        return None
    core_terms = [str(term) for term in update_lookup.get("core_terms", []) if str(term)]
    if "deploy" not in core_terms or "target" not in core_terms:
        return None
    variants = list(update_lookup.get("variants", []))
    if not variants:
        return None
    canonical_variant = next(
        (variant for variant in variants if str(variant.get("basis") or "") == "update-history-subject-core"),
        variants[0],
    )
    effective_query = str(canonical_variant.get("query") or "")
    effective_query_terms = [str(term) for term in canonical_variant.get("terms", []) if str(term)]
    if not effective_query or not effective_query_terms:
        return None
    return {
        "effective_query": effective_query,
        "effective_query_terms": effective_query_terms,
        "required_terms": effective_query_terms,
        "ignored_query_terms": _ordered_unique(
            [str(term) for term in update_lookup.get("matched_terms", []) if str(term)]
            + [str(term) for term in update_lookup.get("direction_terms", []) if str(term)]
        ),
    }


def _update_direct_deploy_target_hybrid_override(
    *,
    query_lookup: dict[str, Any],
    update_lookup: dict[str, Any] | None,
    semantic_alias_variant: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if query_lookup.get("lookup_relation") is not None:
        return None
    if not update_lookup or not semantic_alias_variant:
        return None
    if str(update_lookup.get("direction") or "") != "current":
        return None
    if str(semantic_alias_variant.get("lookup_basis") or "") != "direct-deploy-target-core":
        return None
    core_terms = [str(term) for term in update_lookup.get("core_terms", []) if str(term)]
    if "deploy" not in core_terms or "target" not in core_terms:
        return None
    variants = list(update_lookup.get("variants", []))
    if not variants:
        return None
    canonical_variant = next(
        (variant for variant in variants if str(variant.get("basis") or "") == "update-subject-core"),
        variants[0],
    )
    effective_query = str(canonical_variant.get("query") or "")
    effective_query_terms = [str(term) for term in canonical_variant.get("terms", []) if str(term)]
    if not effective_query or not effective_query_terms:
        return None
    return {
        "effective_query": effective_query,
        "effective_query_terms": effective_query_terms,
        "required_terms": effective_query_terms,
        "ignored_query_terms": _ordered_unique(
            [str(term) for term in update_lookup.get("matched_terms", []) if str(term)]
            + [str(term) for term in update_lookup.get("direction_terms", []) if str(term)]
        ),
    }


def _declarative_semantic_rescue_profile(
    *,
    raw_tokens: list[str],
    raw_terms: list[str],
    query_lookup: dict[str, Any],
    current_lookup: dict[str, Any] | None,
    chronology: dict[str, Any] | None,
    history_lookup: dict[str, Any] | None,
    update_lookup: dict[str, Any] | None,
    rows: list[sqlite3.Row],
    selected_terms: list[str],
    search_mode: str,
) -> dict[str, Any] | None:
    if query_lookup.get("lookup_relation") is not None:
        return None
    if not raw_tokens or raw_tokens[0] in SUBJECT_LOOKUP_QUERY_WRAPPERS:
        return None
    if raw_tokens != raw_terms:
        return None
    if chronology and chronology.get("expanded"):
        return None
    if update_lookup and update_lookup.get("expanded"):
        return None
    if search_mode not in {"none", "fallback"}:
        return None
    if search_mode == "fallback" and _has_full_lexical_match(rows, selected_terms):
        return None
    if history_lookup and history_lookup.get("expanded"):
        history_matched_terms = [str(term) for term in history_lookup.get("matched_terms", []) if str(term)]
        history_semantic_terms = [str(term) for term in history_lookup.get("core_terms", []) if str(term)]
        if history_semantic_terms:
            profile = (
                DECLARATIVE_EARLIEST_HISTORY_SEMANTIC_RESCUE_PROFILE
                if any(term in EARLIEST_HISTORY_TERMS for term in history_matched_terms)
                else DECLARATIVE_HISTORY_SEMANTIC_RESCUE_PROFILE
            )
            return {
                "enabled": True,
                "profile": profile,
                "minimum_score": DECLARATIVE_SEMANTIC_RESCUE_MIN_SCORE,
                "require_full_query_overlap": True,
                "effective_query": str(history_lookup["variants"][0]["query"]),
                "effective_query_terms": history_semantic_terms,
                "search_basis": str(history_lookup["variants"][0]["basis"]),
                "ignored_query_terms": history_matched_terms,
            }
    if current_lookup and current_lookup.get("expanded"):
        semantic_query = str(current_lookup["variants"][0]["query"])
        semantic_terms = [str(term) for term in current_lookup.get("core_terms", []) if str(term)]
        if semantic_query and semantic_terms:
            return {
                "enabled": True,
                "profile": DECLARATIVE_CURRENT_SEMANTIC_RESCUE_PROFILE,
                "minimum_score": DECLARATIVE_SEMANTIC_RESCUE_MIN_SCORE,
                "require_full_query_overlap": True,
                "effective_query": semantic_query,
                "effective_query_terms": semantic_terms,
                "search_basis": str(current_lookup["variants"][0]["basis"]),
                "ignored_query_terms": [str(term) for term in current_lookup.get("matched_terms", []) if str(term)],
            }
    return {
        "enabled": True,
        "profile": DECLARATIVE_SEMANTIC_RESCUE_PROFILE,
        "minimum_score": DECLARATIVE_SEMANTIC_RESCUE_MIN_SCORE,
        "require_full_query_overlap": True,
    }


def _normalize_temporal_subject_key(subject_key: str) -> str:
    tokens = _query_tokens(subject_key)
    while len(tokens) > 1 and tokens[0] in TEMPORAL_HISTORY_TERMS:
        tokens = tokens[1:]
    return _normalize_lookup_subject_fragment(" ".join(tokens))


def _lexical_conflict_signature(memory: MemoryRecord) -> dict[str, str] | None:
    content = " ".join(memory.content.split())
    if not content:
        return None
    for relation, pattern in LEXICAL_CONFLICT_PATTERNS:
        match = pattern.match(content)
        if not match:
            continue
        subject_key = _normalize_temporal_subject_key(match.group("subject"))
        value_key = _normalize_relation_value_fragment(match.group("object"))
        if not subject_key or not value_key:
            return None
        return {
            "group_key": f"{subject_key}|{relation}",
            "subject_key": subject_key,
            "relation": relation,
            "value_key": value_key,
        }
    return None


def _lexical_update_signature(memory: MemoryRecord) -> dict[str, str | None] | None:
    content = " ".join(memory.content.split())
    if not content:
        return None
    for pattern_name, pattern in EXPLICIT_UPDATE_PATTERNS:
        match = pattern.match(content)
        if not match:
            continue
        subject_key = _normalize_temporal_subject_key(match.group("subject"))
        next_value_key = _normalize_relation_value_fragment(match.group("to"))
        previous_value = match.groupdict().get("from")
        previous_value_key = _normalize_relation_value_fragment(previous_value) if previous_value else None
        if not subject_key or not next_value_key:
            return None
        return {
            "group_key": f"{subject_key}|is",
            "subject_key": subject_key,
            "relation": "is",
            "previous_value_key": previous_value_key or None,
            "next_value_key": next_value_key,
            "pattern": pattern_name,
        }
    return None


def _current_conflict_sort_key(memory: MemoryRecord, *, rank: int) -> tuple[int, float, str, str, int, str]:
    return (
        authority_rank(memory.authority),
        float(memory.trust),
        memory.updated_at,
        memory.created_at,
        -rank,
        memory.id,
    )


def _current_conflict_resolution_key(memory: MemoryRecord) -> tuple[int, float, str, str]:
    return (
        authority_rank(memory.authority),
        float(memory.trust),
        memory.updated_at,
        memory.created_at,
    )


def _set_temporal_decision(decisions: list[dict[str, Any]], memory_id: str, payload: dict[str, Any]) -> None:
    decisions[:] = [item for item in decisions if item.get("memory_id") != memory_id]
    decisions.append(payload)


def _candidate_observation_seq(candidate_meta: dict[str, dict[str, Any]], memory_id: str) -> int:
    candidate = candidate_meta.get(memory_id, {})
    value = candidate.get("observation_seq", candidate.get("features", {}).get("observation_seq", 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _subject_lookup_restatement_order_fields(
    memory_id: str,
    *,
    candidate_by_id: dict[str, MemoryRecord],
    candidate_meta: dict[str, dict[str, Any]],
) -> tuple[str, str, int]:
    memory = candidate_by_id[memory_id]
    return (
        memory.updated_at,
        memory.created_at,
        _candidate_observation_seq(candidate_meta, memory_id),
    )


def _subject_lookup_restatement_sort_key(
    memory_id: str,
    *,
    candidate_by_id: dict[str, MemoryRecord],
    candidate_meta: dict[str, dict[str, Any]],
) -> tuple[str, str, int, str]:
    return (
        *_subject_lookup_restatement_order_fields(
            memory_id,
            candidate_by_id=candidate_by_id,
            candidate_meta=candidate_meta,
        ),
        memory_id,
    )


def _explicit_update_sort_key(
    memory_id: str,
    *,
    candidate_by_id: dict[str, MemoryRecord],
    candidate_meta: dict[str, dict[str, Any]],
) -> tuple[str, str, int, str]:
    memory = candidate_by_id[memory_id]
    return (
        memory.updated_at,
        memory.created_at,
        _candidate_observation_seq(candidate_meta, memory_id),
        memory.id,
    )


def _same_provenance_key(memory: MemoryRecord) -> tuple[str, str, str]:
    return (memory.type, memory.source_kind, memory.scope or "")


def _apply_explicit_updates(
    *,
    candidate_by_id: dict[str, MemoryRecord],
    candidate_meta: dict[str, dict[str, Any]],
    current_ids: list[str],
    stale_ids: list[str],
    temporal_state_by_id: dict[str, str],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lexical_signatures = {
        memory_id: _lexical_conflict_signature(candidate_by_id[memory_id])
        for memory_id in current_ids
        if memory_id in candidate_by_id
    }
    update_signatures = {
        memory_id: _lexical_update_signature(candidate_by_id[memory_id])
        for memory_id in current_ids
        if memory_id in candidate_by_id
    }
    update_groups: dict[str, list[dict[str, str | None]]] = {}
    for memory_id, signature in update_signatures.items():
        if signature is None:
            continue
        update_groups.setdefault(str(signature["group_key"]), []).append({"memory_id": memory_id, **signature})

    current_id_set = set(current_ids)
    conflict_sets: list[dict[str, Any]] = []
    for group_key in sorted(update_groups):
        update_items = sorted(
            update_groups[group_key],
            key=lambda item: _explicit_update_sort_key(
                str(item["memory_id"]),
                candidate_by_id=candidate_by_id,
                candidate_meta=candidate_meta,
            ),
            reverse=True,
        )
        chosen_update = update_items[0]
        chosen_current_id = str(chosen_update["memory_id"])
        related_current_ids = [
            memory_id
            for memory_id in current_ids
            if (
                lexical_signatures.get(memory_id) and lexical_signatures[memory_id]["group_key"] == group_key
            )
            or (
                update_signatures.get(memory_id) and update_signatures[memory_id]["group_key"] == group_key
            )
        ]
        direct_current_match_ids = [
            memory_id
            for memory_id in related_current_ids
            if memory_id != chosen_current_id
            and lexical_signatures.get(memory_id) is not None
            and str(lexical_signatures[memory_id]["value_key"]) == str(chosen_update["next_value_key"])
        ]
        if direct_current_match_ids:
            chosen_current_id = direct_current_match_ids[0]
        stale_candidate_ids = [memory_id for memory_id in related_current_ids if memory_id != chosen_current_id]
        if not stale_candidate_ids:
            continue
        if chosen_update.get("previous_value_key"):
            matching_previous_ids = [
                memory_id
                for memory_id in stale_candidate_ids
                if (
                    lexical_signatures.get(memory_id)
                    and lexical_signatures[memory_id]["value_key"] == chosen_update["previous_value_key"]
                )
                or (
                    update_signatures.get(memory_id)
                    and update_signatures[memory_id]["next_value_key"] == chosen_update["previous_value_key"]
                )
            ]
            if matching_previous_ids:
                stale_candidate_ids = matching_previous_ids + [
                    memory_id for memory_id in stale_candidate_ids if memory_id not in matching_previous_ids
                ]
        for stale_memory_id in stale_candidate_ids:
            current_id_set.discard(stale_memory_id)
            if stale_memory_id not in stale_ids:
                stale_ids.append(stale_memory_id)
            temporal_state_by_id[stale_memory_id] = "superseded"
            candidate = candidate_meta.get(stale_memory_id)
            if candidate is not None:
                features = candidate.setdefault("features", {})
                candidate["temporal_state"] = "superseded"
                candidate["superseded_by_candidate"] = chosen_current_id
                features["temporal_state"] = "superseded"
                features["superseded_by_candidate"] = chosen_current_id
            _set_temporal_decision(
                decisions,
                stale_memory_id,
                {
                    "memory_id": stale_memory_id,
                    "decision": "stale",
                    "reason": "explicit-update-candidate",
                    "superseded_by_candidate": chosen_current_id,
                    "update_pattern": chosen_update["pattern"],
                },
            )
        temporal_state_by_id[chosen_current_id] = "current"
        conflict_sets.append(
            {
                "reason": "explicit-update-candidate",
                "involved_candidate_ids": [chosen_current_id] + stale_candidate_ids,
                "current_ids": [chosen_current_id],
                "stale_ids": stale_candidate_ids,
                "superseded_ids": stale_candidate_ids,
                "chosen_current_id": chosen_current_id,
                "subject_key": chosen_update["subject_key"],
                "relation": chosen_update["relation"],
                "update_pattern": chosen_update["pattern"],
                "update_previous_value": chosen_update["previous_value_key"],
                "update_current_value": chosen_update["next_value_key"],
                "matching_current_value_ids": direct_current_match_ids,
                "resolution_strategy": (
                    "explicit_update_current_value_restatement_prefers_direct_fact_v1"
                    if direct_current_match_ids
                    else "explicit_update_supersedes_conflict_v1"
                ),
                "observation_seq_by_id": {
                    memory_id: _candidate_observation_seq(candidate_meta, memory_id)
                    for memory_id in [chosen_current_id] + stale_candidate_ids
                },
            }
        )
    current_ids[:] = [memory_id for memory_id in current_ids if memory_id in current_id_set]
    return conflict_sets


def _apply_query_at_explicit_updates(
    *,
    memories_by_id: dict[str, MemoryRecord],
    valid_from_by_id: dict[str, str | None],
    updated_at_query_by_id: dict[str, str | None],
    unlearned_at_by_id: dict[str, str | None],
    status_at_query_by_id: dict[str, str],
    superseded_at_by_id: dict[str, str | None],
    superseded_by_ids: dict[str, list[str]],
    supersession_reasons_by_id: dict[str, list[str]],
    serial_at_query_by_id: dict[str, int | None],
    timestamp: str,
) -> None:
    current_ids = [
        memory_id
        for memory_id, memory in memories_by_id.items()
        if (
            valid_from_by_id.get(memory_id) is not None
            and str(valid_from_by_id[memory_id]) <= timestamp
            and status_at_query_by_id.get(memory_id) == "active"
            and not (
                unlearned_at_by_id.get(memory_id) is not None
                and str(unlearned_at_by_id[memory_id]) <= timestamp
            )
            and not (
                superseded_at_by_id.get(memory_id) is not None
                and str(superseded_at_by_id[memory_id]) <= timestamp
            )
        )
    ]
    lexical_signatures = {
        memory_id: _lexical_conflict_signature(memories_by_id[memory_id])
        for memory_id in current_ids
    }
    update_signatures = {
        memory_id: _lexical_update_signature(memories_by_id[memory_id])
        for memory_id in current_ids
    }
    update_groups: dict[str, list[dict[str, str | None]]] = {}
    for memory_id, signature in update_signatures.items():
        if signature is None:
            continue
        update_groups.setdefault(str(signature["group_key"]), []).append({"memory_id": memory_id, **signature})

    current_id_set = set(current_ids)
    for group_key in sorted(update_groups):
        update_items = sorted(
            update_groups[group_key],
            key=lambda item: (
                str(valid_from_by_id.get(str(item["memory_id"])) or memories_by_id[str(item["memory_id"])].created_at),
                str(updated_at_query_by_id.get(str(item["memory_id"])) or memories_by_id[str(item["memory_id"])].created_at),
                int(serial_at_query_by_id.get(str(item["memory_id"])) or 0),
                str(item["memory_id"]),
            ),
            reverse=True,
        )
        chosen_update = update_items[0]
        chosen_current_id = str(chosen_update["memory_id"])
        chosen_valid_from = valid_from_by_id.get(chosen_current_id)
        if chosen_valid_from is None:
            continue
        related_current_ids = [
            memory_id
            for memory_id in current_ids
            if memory_id in current_id_set
            and (
                (
                    lexical_signatures.get(memory_id) is not None
                    and lexical_signatures[memory_id]["group_key"] == group_key
                )
                or (
                    update_signatures.get(memory_id) is not None
                    and update_signatures[memory_id]["group_key"] == group_key
                )
            )
        ]
        stale_candidate_ids = [memory_id for memory_id in related_current_ids if memory_id != chosen_current_id]
        if not stale_candidate_ids:
            continue
        if chosen_update.get("previous_value_key"):
            matching_previous_ids = [
                memory_id
                for memory_id in stale_candidate_ids
                if (
                    lexical_signatures.get(memory_id) is not None
                    and lexical_signatures[memory_id]["value_key"] == chosen_update["previous_value_key"]
                )
                or (
                    update_signatures.get(memory_id) is not None
                    and update_signatures[memory_id]["next_value_key"] == chosen_update["previous_value_key"]
                )
            ]
            if matching_previous_ids:
                stale_candidate_ids = matching_previous_ids + [
                    memory_id for memory_id in stale_candidate_ids if memory_id not in matching_previous_ids
                ]
        for stale_memory_id in stale_candidate_ids:
            current_id_set.discard(stale_memory_id)
            _record_query_at_supersession(
                stale_memory_id=stale_memory_id,
                chosen_current_ids=[chosen_current_id],
                superseded_at=chosen_valid_from,
                reason="explicit-update-candidate",
                superseded_at_by_id=superseded_at_by_id,
                superseded_by_ids=superseded_by_ids,
                supersession_reasons_by_id=supersession_reasons_by_id,
            )


def _record_query_at_supersession(
    *,
    stale_memory_id: str,
    chosen_current_ids: list[str],
    superseded_at: str,
    reason: str,
    superseded_at_by_id: dict[str, str | None],
    superseded_by_ids: dict[str, list[str]],
    supersession_reasons_by_id: dict[str, list[str]],
) -> None:
    existing_superseded_at = superseded_at_by_id.get(stale_memory_id)
    if existing_superseded_at is None or superseded_at < existing_superseded_at:
        superseded_at_by_id[stale_memory_id] = superseded_at
        superseded_by_ids[stale_memory_id] = sorted({memory_id for memory_id in chosen_current_ids if memory_id})
        supersession_reasons_by_id[stale_memory_id] = [reason]
        return
    if superseded_at != existing_superseded_at:
        return

    superseding_ids = superseded_by_ids.setdefault(stale_memory_id, [])
    for chosen_current_id in chosen_current_ids:
        if chosen_current_id and chosen_current_id not in superseding_ids:
            superseding_ids.append(chosen_current_id)
    superseding_ids.sort()

    reasons = supersession_reasons_by_id.setdefault(stale_memory_id, [])
    if reason not in reasons:
        reasons.append(reason)


def _select_temporal_graph_subset(
    temporal_graph: dict[str, dict[str, Any]],
    memory_ids: list[str],
) -> dict[str, dict[str, Any]]:
    return {
        memory_id: temporal_graph[memory_id]
        for memory_id in memory_ids
        if memory_id in temporal_graph
    }


def _apply_query_at_subject_lookup_restatements(
    *,
    memories_by_id: dict[str, MemoryRecord],
    valid_from_by_id: dict[str, str | None],
    updated_at_query_by_id: dict[str, str | None],
    unlearned_at_by_id: dict[str, str | None],
    status_at_query_by_id: dict[str, str],
    superseded_at_by_id: dict[str, str | None],
    superseded_by_ids: dict[str, list[str]],
    supersession_reasons_by_id: dict[str, list[str]],
    serial_at_query_by_id: dict[str, int | None],
    timestamp: str,
) -> None:
    current_ids = [
        memory_id
        for memory_id, memory in memories_by_id.items()
        if (
            valid_from_by_id.get(memory_id) is not None
            and str(valid_from_by_id[memory_id]) <= timestamp
            and status_at_query_by_id.get(memory_id) == "active"
            and not (
                unlearned_at_by_id.get(memory_id) is not None
                and str(unlearned_at_by_id[memory_id]) <= timestamp
            )
            and not (
                superseded_at_by_id.get(memory_id) is not None
                and str(superseded_at_by_id[memory_id]) <= timestamp
            )
        )
    ]
    lexical_signatures = {
        memory_id: _lexical_conflict_signature(memories_by_id[memory_id])
        for memory_id in current_ids
    }
    groups: dict[str, list[str]] = {}
    for memory_id, signature in lexical_signatures.items():
        if signature is None:
            continue
        groups.setdefault(signature["group_key"], []).append(memory_id)

    current_id_set = set(current_ids)
    for group_key in sorted(groups):
        group_ids = [memory_id for memory_id in groups[group_key] if memory_id in current_id_set]
        if len(group_ids) < 2:
            continue
        if len({_same_provenance_key(memories_by_id[memory_id]) for memory_id in group_ids}) != 1:
            continue
        distinct_values = {
            lexical_signatures[memory_id]["value_key"]
            for memory_id in group_ids
            if lexical_signatures.get(memory_id) is not None
        }
        if len(distinct_values) < 2:
            continue
        ordered = sorted(
            group_ids,
            key=lambda memory_id: (
                str(valid_from_by_id.get(memory_id) or memories_by_id[memory_id].created_at),
                str(updated_at_query_by_id.get(memory_id) or memories_by_id[memory_id].created_at),
                int(serial_at_query_by_id.get(memory_id) or 0),
                memory_id,
            ),
            reverse=True,
        )
        chosen_current_id = ordered[0]
        chosen_order_fields = (
            str(valid_from_by_id.get(chosen_current_id) or memories_by_id[chosen_current_id].created_at),
            str(updated_at_query_by_id.get(chosen_current_id) or memories_by_id[chosen_current_id].created_at),
            int(serial_at_query_by_id.get(chosen_current_id) or 0),
        )
        next_order_fields = (
            str(valid_from_by_id.get(ordered[1]) or memories_by_id[ordered[1]].created_at),
            str(updated_at_query_by_id.get(ordered[1]) or memories_by_id[ordered[1]].created_at),
            int(serial_at_query_by_id.get(ordered[1]) or 0),
        )
        if chosen_order_fields == next_order_fields:
            continue
        chosen_valid_from = valid_from_by_id.get(chosen_current_id)
        if chosen_valid_from is None:
            continue
        for stale_memory_id in ordered[1:]:
            current_id_set.discard(stale_memory_id)
            _record_query_at_supersession(
                stale_memory_id=stale_memory_id,
                chosen_current_ids=[chosen_current_id],
                superseded_at=chosen_valid_from,
                reason="subject-lookup-restatement",
                superseded_at_by_id=superseded_at_by_id,
                superseded_by_ids=superseded_by_ids,
                supersession_reasons_by_id=supersession_reasons_by_id,
            )


def _apply_subject_lookup_restatements(
    *,
    query_lookup: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
    candidate_meta: dict[str, dict[str, Any]],
    current_ids: list[str],
    stale_ids: list[str],
    temporal_state_by_id: dict[str, str],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup_query_key = str(query_lookup.get("lookup_key") or "")
    lookup_query_basis = str(query_lookup.get("lookup_basis") or "direct-subject")
    lookup_query_relation = query_lookup.get("lookup_relation")
    if not lookup_query_key:
        return []

    lexical_signatures = {
        memory_id: _lexical_conflict_signature(candidate_by_id[memory_id])
        for memory_id in current_ids
        if memory_id in candidate_by_id
    }
    groups: dict[str, list[str]] = {}
    for memory_id, signature in lexical_signatures.items():
        if signature is None or signature["subject_key"] != lookup_query_key:
            continue
        if lookup_query_relation and signature["relation"] != lookup_query_relation:
            continue
        groups.setdefault(signature["group_key"], []).append(memory_id)

    current_id_set = set(current_ids)
    conflict_sets: list[dict[str, Any]] = []
    for group_key in sorted(groups):
        group_ids = groups[group_key]
        if len(group_ids) < 2:
            continue
        if len({_same_provenance_key(candidate_by_id[memory_id]) for memory_id in group_ids}) != 1:
            continue
        distinct_values = {
            lexical_signatures[memory_id]["value_key"]
            for memory_id in group_ids
            if lexical_signatures.get(memory_id) is not None
        }
        if len(distinct_values) < 2:
            continue
        ordered = sorted(
            group_ids,
            key=lambda memory_id: _subject_lookup_restatement_sort_key(
                memory_id,
                candidate_by_id=candidate_by_id,
                candidate_meta=candidate_meta,
            ),
            reverse=True,
        )
        chosen_current_id = ordered[0]
        chosen_order_fields = _subject_lookup_restatement_order_fields(
            chosen_current_id,
            candidate_by_id=candidate_by_id,
            candidate_meta=candidate_meta,
        )
        next_order_fields = _subject_lookup_restatement_order_fields(
            ordered[1],
            candidate_by_id=candidate_by_id,
            candidate_meta=candidate_meta,
        )
        if chosen_order_fields == next_order_fields:
            continue

        stale_candidate_ids = [memory_id for memory_id in group_ids if memory_id != chosen_current_id]
        for stale_memory_id in stale_candidate_ids:
            current_id_set.discard(stale_memory_id)
            if stale_memory_id not in stale_ids:
                stale_ids.append(stale_memory_id)
            temporal_state_by_id[stale_memory_id] = "superseded"
            candidate = candidate_meta.get(stale_memory_id)
            if candidate is not None:
                features = candidate.setdefault("features", {})
                candidate["temporal_state"] = "superseded"
                candidate["superseded_by_candidate"] = chosen_current_id
                features["temporal_state"] = "superseded"
                features["superseded_by_candidate"] = chosen_current_id
            _set_temporal_decision(
                decisions,
                stale_memory_id,
                {
                    "memory_id": stale_memory_id,
                    "decision": "stale",
                    "reason": "subject-lookup-restatement",
                    "superseded_by_candidate": chosen_current_id,
                    "query_lookup_key": lookup_query_key,
                    "query_lookup_basis": lookup_query_basis,
                    "query_lookup_relation": lookup_query_relation,
                },
            )
        temporal_state_by_id[chosen_current_id] = "current"
        provenance = candidate_by_id[chosen_current_id]
        conflict_sets.append(
            {
                "reason": "subject-lookup-restatement",
                "involved_candidate_ids": ordered,
                "current_ids": [chosen_current_id],
                "stale_ids": stale_candidate_ids,
                "superseded_ids": stale_candidate_ids,
                "chosen_current_id": chosen_current_id,
                "subject_key": lexical_signatures[chosen_current_id]["subject_key"],
                "relation": lexical_signatures[chosen_current_id]["relation"],
                "value_by_id": {
                    memory_id: lexical_signatures[memory_id]["value_key"]
                    for memory_id in ordered
                    if lexical_signatures.get(memory_id) is not None
                },
                "query_lookup_key": lookup_query_key,
                "query_lookup_basis": lookup_query_basis,
                "query_lookup_relation": lookup_query_relation,
                "resolution_strategy": SUBJECT_LOOKUP_RESTATEMENT_STRATEGY,
                "same_provenance": {
                    "memory_type": provenance.type,
                    "source_kind": provenance.source_kind,
                    "scope": provenance.scope,
                },
                "resolution_fields": ["updated_at", "created_at", "observation_seq"],
                "observation_seq_by_id": {
                    memory_id: _candidate_observation_seq(candidate_meta, memory_id) for memory_id in ordered
                },
                "updated_at_by_id": {
                    memory_id: candidate_by_id[memory_id].updated_at for memory_id in ordered
                },
                "created_at_by_id": {
                    memory_id: candidate_by_id[memory_id].created_at for memory_id in ordered
                },
            }
        )
    current_ids[:] = [memory_id for memory_id in current_ids if memory_id in current_id_set]
    return conflict_sets


def _collect_subject_lookup_cross_provenance_conflicts(
    *,
    query_lookup: dict[str, Any],
    candidate_by_id: dict[str, MemoryRecord],
    candidate_meta: dict[str, dict[str, Any]],
    current_ids: list[str],
) -> list[dict[str, Any]]:
    lookup_query_key = str(query_lookup.get("lookup_key") or "")
    lookup_query_basis = str(query_lookup.get("lookup_basis") or "direct-subject")
    lookup_query_relation = str(query_lookup.get("lookup_relation") or "")
    if not lookup_query_key or lookup_query_relation not in SUBJECT_LOOKUP_HISTORY_RELATIONS:
        return []

    lexical_signatures = {
        memory_id: _lexical_conflict_signature(candidate_by_id[memory_id])
        for memory_id in current_ids
        if memory_id in candidate_by_id
    }
    groups: dict[str, list[str]] = {}
    for memory_id, signature in lexical_signatures.items():
        if signature is None or signature["subject_key"] != lookup_query_key:
            continue
        if signature["relation"] != lookup_query_relation:
            continue
        groups.setdefault(signature["group_key"], []).append(memory_id)

    conflict_sets: list[dict[str, Any]] = []
    for group_key in sorted(groups):
        group_ids = groups[group_key]
        if len(group_ids) < 2:
            continue
        distinct_values = {
            lexical_signatures[memory_id]["value_key"]
            for memory_id in group_ids
            if lexical_signatures.get(memory_id) is not None
        }
        if len(distinct_values) < 2:
            continue
        provenance_keys = {_same_provenance_key(candidate_by_id[memory_id]) for memory_id in group_ids}
        if len(provenance_keys) < 2:
            continue
        ordered = sorted(
            group_ids,
            key=lambda memory_id: _subject_lookup_restatement_sort_key(
                memory_id,
                candidate_by_id=candidate_by_id,
                candidate_meta=candidate_meta,
            ),
            reverse=True,
        )
        conflict_sets.append(
            {
                "reason": "subject-lookup-cross-provenance-conflict",
                "involved_candidate_ids": ordered,
                "current_ids": list(ordered),
                "chosen_current_id": None,
                "abstained_current_ids": list(ordered),
                "subject_key": lexical_signatures[ordered[0]]["subject_key"],
                "relation": lexical_signatures[ordered[0]]["relation"],
                "value_by_id": {
                    memory_id: lexical_signatures[memory_id]["value_key"]
                    for memory_id in ordered
                    if lexical_signatures.get(memory_id) is not None
                },
                "query_lookup_key": lookup_query_key,
                "query_lookup_basis": lookup_query_basis,
                "query_lookup_relation": lookup_query_relation,
                "resolution_strategy": SUBJECT_LOOKUP_CROSS_PROVENANCE_HISTORY_STRATEGY,
                "resolution_outcome": "abstained",
                "provenance_by_id": {
                    memory_id: {
                        "memory_type": candidate_by_id[memory_id].type,
                        "source_kind": candidate_by_id[memory_id].source_kind,
                        "scope": candidate_by_id[memory_id].scope,
                        "authority": candidate_by_id[memory_id].authority,
                        "trust": candidate_by_id[memory_id].trust,
                    }
                    for memory_id in ordered
                },
                "resolution_fields": [
                    "memory_type",
                    "source_kind",
                    "scope",
                    "authority",
                    "trust",
                    "updated_at",
                    "created_at",
                    "observation_seq",
                ],
                "observation_seq_by_id": {
                    memory_id: _candidate_observation_seq(candidate_meta, memory_id) for memory_id in ordered
                },
                "updated_at_by_id": {
                    memory_id: candidate_by_id[memory_id].updated_at for memory_id in ordered
                },
                "created_at_by_id": {
                    memory_id: candidate_by_id[memory_id].created_at for memory_id in ordered
                },
            }
        )
    return conflict_sets


def _resolve_current_conflicts(
    *,
    candidate_by_id: dict[str, MemoryRecord],
    current_ids: list[str],
    candidate_ids_in_rank_order: list[str],
) -> list[dict[str, Any]]:
    rank_by_id = {
        memory_id: rank
        for rank, memory_id in enumerate(candidate_ids_in_rank_order, start=1)
    }
    groups: dict[str, list[dict[str, Any]]] = {}
    for memory_id in current_ids:
        memory = candidate_by_id.get(memory_id)
        if memory is None:
            continue
        signature = _lexical_conflict_signature(memory)
        if signature is None:
            continue
        item = {
            "memory": memory,
            "rank": rank_by_id.get(memory_id, len(rank_by_id) + 1),
            **signature,
        }
        groups.setdefault(signature["group_key"], []).append(item)

    conflict_sets: list[dict[str, Any]] = []
    for group_key in sorted(groups):
        items = groups[group_key]
        if len(items) < 2:
            continue
        distinct_values = {item["value_key"] for item in items}
        if len(distinct_values) < 2:
            continue
        ordered = sorted(
            items,
            key=lambda item: _current_conflict_sort_key(item["memory"], rank=item["rank"]),
            reverse=True,
        )
        winning_key = _current_conflict_resolution_key(ordered[0]["memory"])
        tied_current_ids = [
            item["memory"].id
            for item in ordered
            if _current_conflict_resolution_key(item["memory"]) == winning_key
        ]
        if len(tied_current_ids) > 1:
            conflict_sets.append(
                {
                    "reason": "lexical-current-conflict",
                    "involved_candidate_ids": [item["memory"].id for item in ordered],
                    "current_ids": [item["memory"].id for item in ordered],
                    "chosen_current_id": None,
                    "dropped_current_ids": [],
                    "abstained_current_ids": [item["memory"].id for item in ordered],
                    "tied_current_ids": tied_current_ids,
                    "subject_key": ordered[0]["subject_key"],
                    "relation": ordered[0]["relation"],
                    "value_by_id": {item["memory"].id: item["value_key"] for item in ordered},
                    "resolution_strategy": LEXICAL_CONFLICT_SELECTION_STRATEGY,
                    "resolution_outcome": "abstained",
                    "tie_fields": LEXICAL_CONFLICT_ABSTENTION_TIE_FIELDS,
                    "ignored_tie_breakers": ["retrieval_rank", "memory_id"],
                }
            )
            continue
        chosen_current_id = ordered[0]["memory"].id
        conflict_sets.append(
            {
                "reason": "lexical-current-conflict",
                "involved_candidate_ids": [item["memory"].id for item in ordered],
                "current_ids": [item["memory"].id for item in ordered],
                "chosen_current_id": chosen_current_id,
                "dropped_current_ids": [item["memory"].id for item in ordered[1:]],
                "abstained_current_ids": [],
                "tied_current_ids": [chosen_current_id],
                "subject_key": ordered[0]["subject_key"],
                "relation": ordered[0]["relation"],
                "value_by_id": {item["memory"].id: item["value_key"] for item in ordered},
                "resolution_strategy": LEXICAL_CONFLICT_SELECTION_STRATEGY,
                "resolution_outcome": "resolved",
            }
        )
    return conflict_sets


def _temporal_selection_metadata(
    *,
    query_terms: list[str],
    query_lookup: dict[str, Any] | None,
    candidate_by_id: dict[str, MemoryRecord],
    candidate_ids_in_rank_order: list[str],
    temporal_state_by_id: dict[str, str],
    current_conflict_sets: list[dict[str, Any]],
) -> dict[str, Any]:
    matched_history_terms = sorted({term for term in query_terms if term in TEMPORAL_HISTORY_TERMS})
    matched_earliest_history_terms = [term for term in matched_history_terms if term in EARLIEST_HISTORY_TERMS]
    matched_recent_history_terms = [term for term in matched_history_terms if term not in EARLIEST_HISTORY_TERMS]
    matched_current_terms = sorted({term for term in query_terms if term in TEMPORAL_CURRENT_TERMS})
    matched_chronology_terms = sorted({term for term in query_terms if term in TEMPORAL_CHRONOLOGY_TERMS})
    update_lookup = dict((query_lookup or {}).get("update", {}))
    matched_update_history_terms = []
    if update_lookup.get("direction") == "history":
        matched_update_history_terms = [
            str(term) for term in update_lookup.get("direction_terms", []) if str(term)
        ]
    superseded_ids = [
        memory_id for memory_id in candidate_ids_in_rank_order if temporal_state_by_id.get(memory_id) == "superseded"
    ]
    current_ids = [memory_id for memory_id in candidate_ids_in_rank_order if temporal_state_by_id.get(memory_id) == "current"]
    eligible_ids = [
        memory_id
        for memory_id in candidate_ids_in_rank_order
        if temporal_state_by_id.get(memory_id) in {"current", "superseded"}
    ]
    rank_by_id = {
        memory_id: rank
        for rank, memory_id in enumerate(candidate_ids_in_rank_order, start=1)
    }
    default_abstention = {
        "applied": False,
        "reason": None,
        "abstained_ids": [],
        "conflict_reasons": [],
    }
    relation = str((query_lookup or {}).get("lookup_relation") or "")
    history_conflict_sets = [
        conflict_set
        for conflict_set in current_conflict_sets
        if conflict_set.get("reason") == "subject-lookup-cross-provenance-conflict"
        and str(conflict_set.get("query_lookup_relation") or "") == relation
    ]
    if history_conflict_sets and relation in SUBJECT_LOOKUP_HISTORY_RELATIONS:
        abstained_ids = [
            memory_id
            for memory_id in candidate_ids_in_rank_order
            if any(memory_id in conflict_set.get("abstained_current_ids", []) for conflict_set in history_conflict_sets)
        ]
        history_abstention = {
            "applied": True,
            "reason": "unresolved-cross-provenance-history",
            "abstained_ids": abstained_ids,
            "conflict_reasons": ["subject-lookup-cross-provenance-conflict"],
        }
        if matched_chronology_terms:
            return {
                "selection_strategy": "history_conflict_abstained_v1",
                "selection_reason": "chronology-cross-provenance-conflict-abstained",
                "selected_ids": [],
                "matched_terms": matched_chronology_terms,
                "selection_order": "chronological_asc_abstained",
                "abstention": history_abstention,
            }
        if matched_earliest_history_terms:
            return {
                "selection_strategy": "history_conflict_abstained_v1",
                "selection_reason": "earliest-history-cross-provenance-conflict-abstained",
                "selected_ids": [],
                "matched_terms": matched_earliest_history_terms,
                "selection_order": "chronological_asc_prefer_earliest_abstained",
                "abstention": history_abstention,
            }
        history_terms = matched_recent_history_terms or matched_update_history_terms
        if history_terms:
            return {
                "selection_strategy": "history_conflict_abstained_v1",
                "selection_reason": (
                    "history-cross-provenance-conflict-abstained"
                    if matched_recent_history_terms
                    else "update-history-cross-provenance-conflict-abstained"
                ),
                "selected_ids": [],
                "matched_terms": history_terms,
                "selection_order": "ranked_history_conflict_abstained",
                "abstention": history_abstention,
            }

    if matched_chronology_terms and eligible_ids:
        selected_ids = _chronology_ordered_ids(
            eligible_ids,
            candidate_by_id=candidate_by_id,
            rank_by_id=rank_by_id,
        )
        return {
            "selection_strategy": "chronological_timeline_v1",
            "selection_reason": "chronology-query-terms",
            "selected_ids": selected_ids,
            "matched_terms": matched_chronology_terms,
            "selection_order": "chronological_asc",
            "abstention": default_abstention,
        }
    if matched_chronology_terms:
        return {
            "selection_strategy": "current_only_v1",
            "selection_reason": "chronology-query-without-eligible-candidates",
            "selected_ids": [],
            "matched_terms": matched_chronology_terms,
            "selection_order": "chronological_asc",
            "abstention": default_abstention,
        }

    if matched_earliest_history_terms and superseded_ids:
        selected_ids = _chronology_ordered_ids(
            eligible_ids,
            candidate_by_id=candidate_by_id,
            rank_by_id=rank_by_id,
        )
        return {
            "selection_strategy": "earliest_history_preferred_v1",
            "selection_reason": "earliest-history-query-terms",
            "selected_ids": selected_ids,
            "matched_terms": matched_earliest_history_terms,
            "selection_order": "chronological_asc_prefer_earliest",
            "abstention": default_abstention,
        }
    if matched_earliest_history_terms:
        return {
            "selection_strategy": "current_only_v1",
            "selection_reason": "earliest-history-query-without-superseded-candidates",
            "selected_ids": current_ids,
            "matched_terms": matched_earliest_history_terms,
            "selection_order": "ranked",
            "abstention": default_abstention,
        }

    history_terms = matched_recent_history_terms or matched_update_history_terms
    history_reason = "history-query-terms" if matched_recent_history_terms else "update-history-query-terms"
    history_no_superseded_reason = (
        "history-query-without-superseded-candidates"
        if matched_recent_history_terms
        else "update-history-query-without-superseded-candidates"
    )
    history_lookup = dict((query_lookup or {}).get("history", {}))
    observation_support = dict(history_lookup.get("observation_support", {}))

    if history_terms and not superseded_ids:
        target_history_selected_ids = _target_history_support_ordered_ids(
            query_lookup=query_lookup,
            current_ids=current_ids,
            candidate_by_id=candidate_by_id,
            rank_by_id=rank_by_id,
        )
        if target_history_selected_ids:
            return {
                "selection_strategy": "target_history_support_preferred_v1",
                "selection_reason": "history-target-query-terms",
                "selected_ids": target_history_selected_ids,
                "matched_terms": history_terms,
                "selection_order": "chronological_support_then_current_target",
                "abstention": default_abstention,
            }
        observation_support_ids = [
            str(memory_id)
            for memory_id in observation_support.get("selected_support_candidate_ids", [])
            if str(memory_id) in current_ids
        ]
        observation_anchor_ids = [
            str(memory_id)
            for memory_id in observation_support.get("selected_anchor_candidate_ids", [])
            if str(memory_id) in current_ids
        ]
        if not observation_anchor_ids:
            observation_anchor_ids = [
                str(memory_id)
                for memory_id in observation_support.get("anchor_candidate_ids", [])
                if str(memory_id) in current_ids
            ]
        if observation_support.get("applied") and observation_support_ids and observation_anchor_ids:
            selected_ids = observation_support_ids + [
                memory_id
                for memory_id in observation_anchor_ids
                if memory_id not in observation_support_ids
            ]
            return {
                "selection_strategy": "history_observation_support_v1",
                "selection_reason": "history-observation-support-query-terms",
                "selected_ids": selected_ids,
                "matched_terms": history_terms,
                "selection_order": "observation_support_then_anchor",
                "abstention": default_abstention,
            }

    if history_terms and superseded_ids:
        selected_superseded_ids = _chronology_ordered_ids(
            superseded_ids,
            candidate_by_id=candidate_by_id,
            rank_by_id=rank_by_id,
            reverse=True,
        )
        selection_order = "chronological_desc_prefer_latest_superseded"
        if matched_update_history_terms:
            superseded_id_set = set(selected_superseded_ids)
            preferred_superseded_ids: list[str] = []
            explicit_update_conflict_sets = sorted(
                (
                    conflict_set
                    for conflict_set in current_conflict_sets
                    if conflict_set.get("reason") == "explicit-update-candidate"
                    and conflict_set.get("update_previous_value")
                    and conflict_set.get("chosen_current_id") in candidate_by_id
                ),
                key=lambda conflict_set: _chronology_sort_key(
                    candidate_by_id[str(conflict_set["chosen_current_id"])],
                    temporal_rank=rank_by_id.get(str(conflict_set["chosen_current_id"]), len(rank_by_id) + 1),
                ),
                reverse=True,
            )
            for conflict_set in explicit_update_conflict_sets:
                for memory_id in conflict_set.get("stale_ids", []):
                    stale_memory_id = str(memory_id)
                    if stale_memory_id in superseded_id_set and stale_memory_id not in preferred_superseded_ids:
                        preferred_superseded_ids.append(stale_memory_id)
            if preferred_superseded_ids:
                selected_superseded_ids = preferred_superseded_ids + [
                    memory_id
                    for memory_id in selected_superseded_ids
                    if memory_id not in preferred_superseded_ids
                ]
                selection_order = "explicit_previous_then_chronological_desc"
        selected_ids = selected_superseded_ids + [
            memory_id for memory_id in current_ids if memory_id not in selected_superseded_ids
        ]
        return {
            "selection_strategy": "historical_preferred_v1",
            "selection_reason": history_reason,
            "selected_ids": selected_ids,
            "matched_terms": history_terms,
            "selection_order": selection_order,
            "abstention": default_abstention,
        }
    if history_terms:
        return {
            "selection_strategy": "current_only_v1",
            "selection_reason": history_no_superseded_reason,
            "selected_ids": current_ids,
            "matched_terms": history_terms,
            "selection_order": "ranked",
            "abstention": default_abstention,
        }
    current_update_selected_ids = _current_update_preferred_ids(
        query_lookup=query_lookup or {},
        current_ids=current_ids,
        candidate_by_id=candidate_by_id,
    )
    if current_update_selected_ids:
        return {
            "selection_strategy": "current_update_preferred_v1",
            "selection_reason": "current-update-query-terms",
            "selected_ids": current_update_selected_ids,
            "matched_terms": matched_current_terms,
            "selection_order": "explicit_update_current_only",
            "abstention": default_abstention,
        }
    conflict_dropped_ids = {
        memory_id
        for conflict_set in current_conflict_sets
        if conflict_set.get("reason") == "lexical-current-conflict"
        and conflict_set.get("resolution_outcome") != "abstained"
        for memory_id in conflict_set.get("dropped_current_ids", [])
    }
    conflict_abstained_ids = {
        memory_id
        for conflict_set in current_conflict_sets
        if conflict_set.get("reason") == "lexical-current-conflict"
        and conflict_set.get("resolution_outcome") == "abstained"
        for memory_id in conflict_set.get("abstained_current_ids", [])
    }
    if conflict_abstained_ids:
        abstained_ids = [memory_id for memory_id in current_ids if memory_id in conflict_abstained_ids]
        return {
            "selection_strategy": "current_conflict_abstained_v1",
            "selection_reason": "lexical-current-conflict-abstained",
            "selected_ids": [
                memory_id
                for memory_id in current_ids
                if memory_id not in conflict_dropped_ids and memory_id not in conflict_abstained_ids
            ],
            "matched_terms": matched_current_terms,
            "selection_order": "ranked_conflict_abstained",
            "abstention": {
                "applied": True,
                "reason": "unresolved-current-conflict",
                "abstained_ids": abstained_ids,
                "conflict_reasons": ["lexical-current-conflict"],
            },
        }
    if conflict_dropped_ids:
        return {
            "selection_strategy": "current_conflict_resolved_v1",
            "selection_reason": "lexical-current-conflict",
            "selected_ids": [memory_id for memory_id in current_ids if memory_id not in conflict_dropped_ids],
            "matched_terms": matched_current_terms,
            "selection_order": "ranked_conflict_resolved",
            "abstention": default_abstention,
        }
    if matched_current_terms:
        return {
            "selection_strategy": "current_only_v1",
            "selection_reason": "current-query-terms",
            "selected_ids": current_ids,
            "matched_terms": matched_current_terms,
            "selection_order": "ranked",
            "abstention": default_abstention,
        }
    return {
        "selection_strategy": "current_only_v1",
        "selection_reason": "default-current-only",
        "selected_ids": current_ids,
        "matched_terms": [],
        "selection_order": "ranked",
        "abstention": default_abstention,
    }


def resolve_temporal_lifecycle(
    candidates: list[MemoryRecord],
    retrieval: dict[str, Any],
) -> dict[str, Any]:
    candidate_by_id = {memory.id: memory for memory in candidates}
    candidate_ids = set(candidate_by_id)
    candidate_meta = {
        str(candidate.get("memory_id")): candidate
        for candidate in retrieval.get("candidates", [])
        if candidate.get("memory_id")
    }
    current_ids: list[str] = []
    stale_ids: list[str] = []
    decisions: list[dict[str, Any]] = []
    superseded_by: dict[str, str] = {}
    child_ids_by_parent: dict[str, list[str]] = {}
    expired_ids: list[str] = []
    revoked_ids: list[str] = []
    temporal_state_by_id: dict[str, str] = {}
    clock = now_iso()

    for memory in candidates:
        for parent_id in memory.parents:
            if parent_id in candidate_ids and memory.status == "active":
                child_ids_by_parent.setdefault(parent_id, []).append(memory.id)

    for parent_id, child_ids in child_ids_by_parent.items():
        chosen_child_id = sorted(
            child_ids,
            key=lambda child_id: (
                candidate_by_id[child_id].updated_at,
                candidate_by_id[child_id].created_at,
                child_id,
            ),
            reverse=True,
        )[0]
        superseded_by[parent_id] = chosen_child_id

    for memory in candidates:
        is_expired = bool(memory.expires_at and memory.expires_at <= clock)
        child_candidate_ids = sorted(child_ids_by_parent.get(memory.id, []))
        superseding_child_id = superseded_by.get(memory.id)
        if memory.status == "revoked":
            temporal_state = "revoked"
            stale_ids.append(memory.id)
            revoked_ids.append(memory.id)
            decisions.append({"memory_id": memory.id, "decision": "stale", "reason": "revoked"})
        elif is_expired:
            temporal_state = "expired"
            stale_ids.append(memory.id)
            expired_ids.append(memory.id)
            decisions.append(
                {
                    "memory_id": memory.id,
                    "decision": "stale",
                    "reason": "expired",
                    "expires_at": memory.expires_at,
                }
            )
        elif superseding_child_id:
            temporal_state = "superseded"
            stale_ids.append(memory.id)
            decisions.append(
                {
                    "memory_id": memory.id,
                    "decision": "stale",
                    "reason": "active-child-candidate",
                    "superseded_by_candidate": superseding_child_id,
                }
            )
        else:
            temporal_state = "current"
            current_ids.append(memory.id)
            decisions.append({"memory_id": memory.id, "decision": "current", "reason": "lifecycle-current"})

        temporal_state_by_id[memory.id] = temporal_state
        candidate = candidate_meta.get(memory.id)
        if candidate is None:
            continue
        features = candidate.setdefault("features", {})
        features["temporal_state"] = temporal_state
        features["superseded_by_candidate"] = superseding_child_id
        features["child_candidate_ids"] = child_candidate_ids
        features["is_expired"] = is_expired
        features["updated_at"] = memory.updated_at
        features["expires_at"] = memory.expires_at
        candidate["temporal_state"] = temporal_state
        candidate["superseded_by_candidate"] = superseding_child_id
        candidate["child_candidate_ids"] = child_candidate_ids
        candidate["is_expired"] = is_expired
        candidate["updated_at"] = memory.updated_at
        candidate["expires_at"] = memory.expires_at

    current_id_set = set(current_ids)
    stale_id_set = set(stale_ids)
    conflict_sets: list[dict[str, Any]] = []
    for parent_id in sorted(child_ids_by_parent):
        child_ids = sorted(child_ids_by_parent[parent_id])
        involved_ids = [parent_id] + child_ids
        current_child_ids = [child_id for child_id in child_ids if child_id in current_id_set]
        chosen_child_id = superseded_by[parent_id]
        conflict_sets.append(
            {
                "reason": "active-child-candidate",
                "involved_candidate_ids": involved_ids,
                "parent_id": parent_id,
                "superseding_candidate_ids": child_ids,
                "chosen_current_id": chosen_child_id if chosen_child_id in current_id_set else None,
                "current_ids": current_child_ids,
                "stale_ids": [parent_id] if parent_id in stale_id_set else [],
                "superseded_ids": [parent_id] if temporal_state_by_id.get(parent_id) == "superseded" else [],
            }
        )

    conflict_sets.extend(
        _apply_explicit_updates(
            candidate_by_id=candidate_by_id,
            candidate_meta=candidate_meta,
            current_ids=current_ids,
            stale_ids=stale_ids,
            temporal_state_by_id=temporal_state_by_id,
            decisions=decisions,
        )
    )
    conflict_sets.extend(
        _apply_subject_lookup_restatements(
            query_lookup=dict(retrieval.get("query_lookup", {})),
            candidate_by_id=candidate_by_id,
            candidate_meta=candidate_meta,
            current_ids=current_ids,
            stale_ids=stale_ids,
            temporal_state_by_id=temporal_state_by_id,
            decisions=decisions,
        )
    )
    conflict_sets.extend(
        _collect_subject_lookup_cross_provenance_conflicts(
            query_lookup=dict(retrieval.get("query_lookup", {})),
            candidate_by_id=candidate_by_id,
            candidate_meta=candidate_meta,
            current_ids=current_ids,
        )
    )

    for memory_id in expired_ids:
        memory = candidate_by_id[memory_id]
        related_ids = [memory_id]
        related_ids.extend(parent_id for parent_id in memory.parents if parent_id in candidate_ids)
        related_ids.extend(child_ids_by_parent.get(memory_id, []))
        involved_ids = sorted(set(related_ids))
        current_related_ids = [candidate_id for candidate_id in involved_ids if candidate_id in current_id_set]
        conflict_sets.append(
            {
                "reason": "expired",
                "involved_candidate_ids": involved_ids,
                "chosen_current_id": current_related_ids[0] if len(current_related_ids) == 1 else None,
                "current_ids": current_related_ids,
                "stale_ids": [memory_id],
                "expired_ids": [memory_id],
                "expires_at_by_id": {memory_id: memory.expires_at},
            }
        )

    for memory_id in revoked_ids:
        memory = candidate_by_id[memory_id]
        related_ids = [memory_id]
        related_ids.extend(parent_id for parent_id in memory.parents if parent_id in candidate_ids)
        related_ids.extend(child_ids_by_parent.get(memory_id, []))
        involved_ids = sorted(set(related_ids))
        current_related_ids = [candidate_id for candidate_id in involved_ids if candidate_id in current_id_set]
        conflict_sets.append(
            {
                "reason": "revoked",
                "involved_candidate_ids": involved_ids,
                "chosen_current_id": current_related_ids[0] if len(current_related_ids) == 1 else None,
                "current_ids": current_related_ids,
                "stale_ids": [memory_id],
                "revoked_ids": [memory_id],
            }
        )

    candidate_ids_in_rank_order = [
        str(candidate["memory_id"])
        for candidate in retrieval.get("candidates", [])
        if candidate.get("memory_id")
    ]
    conflict_sets.extend(
        _resolve_current_conflicts(
            candidate_by_id=candidate_by_id,
            current_ids=current_ids,
            candidate_ids_in_rank_order=candidate_ids_in_rank_order,
        )
    )
    selection = _temporal_selection_metadata(
        query_terms=[str(term) for term in retrieval.get("query_terms", [])],
        query_lookup=dict(retrieval.get("query_lookup", {})),
        candidate_by_id=candidate_by_id,
        candidate_ids_in_rank_order=candidate_ids_in_rank_order,
        temporal_state_by_id=temporal_state_by_id,
        current_conflict_sets=conflict_sets,
    )
    selection["selected_superseded_ids"] = [
        memory_id for memory_id in selection["selected_ids"] if temporal_state_by_id.get(memory_id) == "superseded"
    ]
    selection["selected_current_ids"] = [
        memory_id for memory_id in selection["selected_ids"] if temporal_state_by_id.get(memory_id) == "current"
    ]
    selection["selected_stale_anchor_id"] = (
        selection["selected_superseded_ids"][0] if selection["selected_superseded_ids"] else None
    )
    selection["selected_current_anchor_id"] = (
        selection["selected_current_ids"][-1] if selection["selected_current_ids"] else None
    )
    injection_preference = _chronology_mutation_injection_preference(
        selection=selection,
        candidate_by_id=candidate_by_id,
        temporal_state_by_id=temporal_state_by_id,
    )
    if not injection_preference["applied"]:
        injection_preference = _chronology_relation_current_anchor_injection_preference(
            selection=selection,
            query_lookup=dict(retrieval.get("query_lookup", {})),
            candidate_by_id=candidate_by_id,
            temporal_state_by_id=temporal_state_by_id,
        )
    if not injection_preference["applied"]:
        injection_preference = _history_target_current_anchor_injection_preference(
            selection=selection,
            query_lookup=dict(retrieval.get("query_lookup", {})),
            candidate_by_id=candidate_by_id,
            temporal_state_by_id=temporal_state_by_id,
        )
    if not injection_preference["applied"]:
        injection_preference = _history_current_anchor_injection_preference(
            selection=selection,
            candidate_by_id=candidate_by_id,
            temporal_state_by_id=temporal_state_by_id,
        )
    if not injection_preference["applied"]:
        injection_preference = _history_relation_current_anchor_injection_preference(
            selection=selection,
            query_lookup=dict(retrieval.get("query_lookup", {})),
            candidate_by_id=candidate_by_id,
            temporal_state_by_id=temporal_state_by_id,
        )
    if not injection_preference["applied"]:
        injection_preference = _update_current_relation_support_injection_preference(
            selection=selection,
            query_lookup=dict(retrieval.get("query_lookup", {})),
            candidate_by_id=candidate_by_id,
        )
    selection["injection_strategy"] = injection_preference["strategy"]
    selection["injection_reason"] = injection_preference["reason"]
    selection["injection_order"] = injection_preference["order"]
    selection["injection_preferred_ids"] = injection_preference["preferred_ids"]
    selection["selected_mutation_anchor_id"] = injection_preference["selected_mutation_anchor_id"]
    selection["selected_mutation_anchor_ids"] = injection_preference["selected_mutation_anchor_ids"]
    selection["selected_target_current_id"] = injection_preference.get("selected_target_current_id")
    selection["selected_target_support_ids"] = injection_preference.get("selected_target_support_ids", [])
    selection["selected_relation_current_id"] = injection_preference.get("selected_relation_current_id")
    selection["selected_relation_support_ids"] = injection_preference.get("selected_relation_support_ids", [])
    selection["selected_update_current_id"] = injection_preference.get("selected_update_current_id")
    selection["selected_current_support_ids"] = injection_preference.get("selected_current_support_ids", [])
    if injection_preference.get("current_anchor_id"):
        selection["selected_current_anchor_id"] = injection_preference["current_anchor_id"]
    if (
        selection["selection_strategy"] == "target_history_support_preferred_v1"
        and not selection["selected_target_current_id"]
        and selection["selected_current_anchor_id"]
    ):
        selection["selected_target_current_id"] = selection["selected_current_anchor_id"]
        selection["selected_target_support_ids"] = [
            memory_id
            for memory_id in selection["selected_ids"]
            if memory_id != selection["selected_current_anchor_id"]
        ]
    selected_id_set = set(selection["selected_ids"])
    selection_exclusions: list[dict[str, Any]] = []
    if selection["selection_strategy"] == "target_history_support_preferred_v1":
        selected_target_pair = [*selection["selected_target_support_ids"]]
        if selection["selected_target_current_id"]:
            selected_target_pair.append(selection["selected_target_current_id"])
        target_term_set = {
            str(term)
            for term in query_terms(
                str(((retrieval.get("query_lookup") or {}).get("target_history") or {}).get("target_query") or "")
            )
            if str(term)
        }
        history_term_set = {
            str(term)
            for term in (((retrieval.get("query_lookup") or {}).get("target_history") or {}).get("history_terms") or [])
            if str(term)
        }
        for memory_id in current_ids:
            if memory_id in selected_id_set:
                continue
            memory = candidate_by_id.get(memory_id)
            if memory is None:
                continue
            haystack_terms = set(_query_tokens(f"{memory.content} {' '.join(memory.labels)}"))
            is_target_current_candidate = bool(target_term_set) and all(term in haystack_terms for term in target_term_set)
            is_history_support_candidate = bool(history_term_set.intersection(haystack_terms))
            if is_target_current_candidate:
                reason = "target-history-current-anchor-not-selected"
                detail = "explicit-target-history-support-pair-selected"
                candidate_role = "target-current"
            elif is_history_support_candidate:
                reason = "target-history-support-candidate-not-selected"
                detail = "strongest-explicit-target-support-selected"
                candidate_role = "history-support"
            else:
                reason = "target-history-current-anchor-not-selected"
                detail = "explicit-target-history-support-pair-selected"
                candidate_role = "generic-current"
            selection_exclusions.append(
                {
                    "memory_id": memory_id,
                    "reason": reason,
                    "detail": detail,
                    "selection_strategy": selection["selection_strategy"],
                    "candidate_role": candidate_role,
                    "selected_target_current_id": selection["selected_target_current_id"],
                    "selected_target_support_ids": selection["selected_target_support_ids"],
                    "selected_target_pair_ids": selected_target_pair,
                }
            )
    elif selection["selection_strategy"] == "history_observation_support_v1":
        observation_support = dict(((retrieval.get("query_lookup") or {}).get("history") or {}).get("observation_support", {}))
        selected_anchor_candidate_ids = [
            str(memory_id)
            for memory_id in observation_support.get("selected_anchor_candidate_ids", [])
            if str(memory_id)
        ]
        anchor_candidate_ids = [
            str(memory_id)
            for memory_id in observation_support.get("anchor_candidate_ids", [])
            if str(memory_id)
        ]
        for memory_id in observation_support.get("excluded_anchor_candidate_ids", []):
            memory_id = str(memory_id)
            if not memory_id or memory_id not in anchor_candidate_ids:
                continue
            selection_exclusions.append(
                {
                    "memory_id": memory_id,
                    "reason": "history-observation-anchor-not-selected",
                    "detail": "earliest-and-strongest-observation-anchor-chain-selected",
                    "selection_strategy": selection["selection_strategy"],
                    "selected_anchor_candidate_ids": selected_anchor_candidate_ids,
                    "anchor_candidate_ids": anchor_candidate_ids,
                    "anchor_selection_strategy": observation_support.get("anchor_selection_strategy"),
                }
            )
    elif selection["selection_strategy"] == "current_only_v1":
        excluded_update_anchor_ids: set[str] = set()
        for conflict_set in conflict_sets:
            if conflict_set.get("reason") != "explicit-update-candidate":
                continue
            if conflict_set.get("resolution_strategy") != "explicit_update_current_value_restatement_prefers_direct_fact_v1":
                continue
            chosen_current_id = str(conflict_set.get("chosen_current_id") or "")
            if not chosen_current_id or chosen_current_id not in selected_id_set:
                continue
            matching_current_value_ids = [
                str(memory_id)
                for memory_id in conflict_set.get("matching_current_value_ids", [])
                if str(memory_id)
            ]
            update_current_value = str(conflict_set.get("update_current_value") or "")
            for memory_id in conflict_set.get("stale_ids", []):
                memory_id = str(memory_id)
                if not memory_id or memory_id in selected_id_set or memory_id in excluded_update_anchor_ids:
                    continue
                memory = candidate_by_id.get(memory_id)
                if memory is None:
                    continue
                update_signature = _lexical_update_signature(memory)
                if update_signature is None:
                    continue
                if str(update_signature.get("next_value_key") or "") != update_current_value:
                    continue
                selection_exclusions.append(
                    {
                        "memory_id": memory_id,
                        "reason": "explicit-update-anchor-not-selected",
                        "detail": "direct-current-restatement-selected",
                        "selection_strategy": selection["selection_strategy"],
                        "chosen_current_id": chosen_current_id,
                        "matching_current_value_ids": matching_current_value_ids,
                        "update_current_value": update_current_value,
                        "update_pattern": conflict_set.get("update_pattern"),
                    }
                )
                excluded_update_anchor_ids.add(memory_id)
    selection["selection_exclusions"] = selection_exclusions
    selection_exclusion_by_id = {
        str(item["memory_id"]): item
        for item in selection_exclusions
    }
    current_ordering = _current_only_ordering_metadata(
        retrieval=retrieval,
        selection=selection,
        candidate_meta=candidate_meta,
        current_ids=current_ids,
        conflict_sets=conflict_sets,
    )
    history_ordering = _history_ordering_metadata(
        selection=selection,
        candidate_by_id=candidate_by_id,
        candidate_ids_in_rank_order=candidate_ids_in_rank_order,
        current_ids=current_ids,
        conflict_sets=conflict_sets,
        query_lookup=dict(retrieval.get("query_lookup", {})),
    )
    temporal_fusion = None
    temporal_fusion_signal = _temporal_fusion_signal(selection)
    temporal_fusion_source_rankings = _temporal_support_fusion_source_rankings(
        candidate_ids_in_rank_order=candidate_ids_in_rank_order,
        selection=selection,
    )
    if temporal_fusion_source_rankings:
        temporal_fusion = _reciprocal_rank_fusion(
            temporal_fusion_source_rankings,
            selected_candidate_ids=selection["selected_ids"],
        )
    temporal_fusion_by_id = {
        str(item["memory_id"]): item
        for item in (
            temporal_fusion.get("candidate_scores", [])
            if isinstance(temporal_fusion, dict)
            else []
        )
    }
    selection_rank_by_id = {
        memory_id: index
        for index, memory_id in enumerate(selection["selected_ids"], start=1)
    }
    injection_rank_by_id = {
        memory_id: index
        for index, memory_id in enumerate(selection["injection_preferred_ids"], start=1)
    } if injection_preference["applied"] else {}
    for memory_id, candidate in candidate_meta.items():
        selected = memory_id in selected_id_set
        candidate["selected_by_temporal_strategy"] = selected
        candidate["temporal_selection_rank"] = selection_rank_by_id.get(memory_id)
        candidate["temporal_injection_rank"] = injection_rank_by_id.get(memory_id)
        candidate["temporal_selection_exclusion"] = selection_exclusion_by_id.get(memory_id)
        candidate["temporal_selection_exclusion_reason"] = (
            selection_exclusion_by_id.get(memory_id, {}).get("reason")
        )
        fusion_item = temporal_fusion_by_id.get(memory_id, {})
        candidate["temporal_fusion_rank"] = fusion_item.get("fusion_rank")
        candidate["temporal_fusion_score"] = fusion_item.get("score")
        candidate["temporal_fusion_sources"] = [
            contribution.get("source")
            for contribution in fusion_item.get("source_contributions", [])
            if contribution.get("source")
        ]
        candidate["temporal_fusion_source_count"] = len(fusion_item.get("source_contributions", []))
        features = candidate.setdefault("features", {})
        features["selected_by_temporal_strategy"] = selected
        features["temporal_selection_rank"] = selection_rank_by_id.get(memory_id)
        features["temporal_injection_rank"] = injection_rank_by_id.get(memory_id)
        features["temporal_selection_exclusion"] = selection_exclusion_by_id.get(memory_id)
        features["temporal_selection_exclusion_reason"] = (
            selection_exclusion_by_id.get(memory_id, {}).get("reason")
        )
        features["temporal_fusion_rank"] = fusion_item.get("fusion_rank")
        features["temporal_fusion_score"] = fusion_item.get("score")
        features["temporal_fusion_sources"] = candidate["temporal_fusion_sources"]
        features["temporal_fusion_source_count"] = candidate["temporal_fusion_source_count"]

    retrieval["temporal"] = {
        "schema": TEMPORAL_RESOLUTION_SCHEMA,
        "strategy": "lifecycle_fields_v1",
        "decisions": decisions,
        "current_ids": current_ids,
        "stale_ids": stale_ids,
        "conflict_sets": conflict_sets,
        "selection_strategy": selection["selection_strategy"],
        "selection_reason": selection["selection_reason"],
        "selection_matched_terms": selection["matched_terms"],
        "selection_order": selection["selection_order"],
        "selected_ids": selection["selected_ids"],
        "selection_exclusions": selection["selection_exclusions"],
        "current_ordering": current_ordering,
        "history_ordering": history_ordering,
        "selected_superseded_ids": selection["selected_superseded_ids"],
        "selected_current_ids": selection["selected_current_ids"],
        "selected_stale_anchor_id": selection["selected_stale_anchor_id"],
        "selected_current_anchor_id": selection["selected_current_anchor_id"],
        "selected_target_current_id": selection["selected_target_current_id"],
        "selected_target_support_ids": selection["selected_target_support_ids"],
        "selected_relation_current_id": selection["selected_relation_current_id"],
        "selected_relation_support_ids": selection["selected_relation_support_ids"],
        "selected_update_current_id": selection["selected_update_current_id"],
        "selected_current_support_ids": selection["selected_current_support_ids"],
        "injection_strategy": selection["injection_strategy"],
        "injection_reason": selection["injection_reason"],
        "injection_order": selection["injection_order"],
        "injection_preferred_ids": selection["injection_preferred_ids"],
        "fusion": (
            {
                **temporal_fusion,
                "applied": True,
                "signal": temporal_fusion_signal,
                "basis": _temporal_fusion_basis(temporal_fusion_signal),
                "selection_exclusion_ids": [
                    str(item["memory_id"])
                    for item in selection["selection_exclusions"]
                    if str(item.get("memory_id"))
                ],
                "selected_candidate_ids": [str(memory_id) for memory_id in selection["selected_ids"] if str(memory_id)],
                "injection_candidate_ids": [
                    str(memory_id)
                    for memory_id in selection["injection_preferred_ids"]
                    if str(memory_id)
                ],
            }
            if isinstance(temporal_fusion, dict)
            else {
                "applied": False,
                "disabled_reason": (
                    "no-support-chain-or-mutation-temporal-merge"
                    if not temporal_fusion_source_rankings
                    else "no-fusion-candidates"
                ),
                "signal": temporal_fusion_signal,
                "basis": _temporal_fusion_basis(temporal_fusion_signal),
                "source_rankings": temporal_fusion_source_rankings,
                "selection_exclusion_ids": [
                    str(item["memory_id"])
                    for item in selection["selection_exclusions"]
                    if str(item.get("memory_id"))
                ],
                "selected_candidate_ids": [str(memory_id) for memory_id in selection["selected_ids"] if str(memory_id)],
                "injection_candidate_ids": [
                    str(memory_id)
                    for memory_id in selection["injection_preferred_ids"]
                    if str(memory_id)
                ],
            }
        ),
        "selected_mutation_anchor_id": selection["selected_mutation_anchor_id"],
        "selected_mutation_anchor_ids": selection["selected_mutation_anchor_ids"],
        "abstention": selection["abstention"],
    }
    return {
        "memories": [memory for memory in candidates if memory.id in set(current_ids)],
        "selected_memories": [candidate_by_id[memory_id] for memory_id in selection["selected_ids"] if memory_id in candidate_by_id],
        "metadata": retrieval["temporal"],
    }


def _empty_memory_type_buckets() -> dict[str, list[str]]:
    return {memory_type: [] for memory_type in sorted(MEMORY_TYPES)}


def _memory_ids_by_type(memories: list["MemoryRecord"]) -> dict[str, list[str]]:
    buckets = _empty_memory_type_buckets()
    for memory in memories:
        buckets.setdefault(memory.type, []).append(memory.id)
    return buckets


def _memory_ids_by_type_from_ids(
    memory_ids: list[str],
    *,
    memory_by_id: dict[str, "MemoryRecord"],
) -> dict[str, list[str]]:
    buckets = _empty_memory_type_buckets()
    for memory_id in memory_ids:
        memory = memory_by_id.get(memory_id)
        if memory is None:
            continue
        buckets.setdefault(memory.type, []).append(memory.id)
    return buckets


def pack_memory_context(
    authorized: list[MemoryRecord],
    *,
    retrieval: dict[str, Any],
    max_tokens: int | None = None,
) -> dict[str, Any]:
    ranks = _rank_lookup(retrieval)
    candidate_by_id = _candidate_by_id(retrieval)
    temporal_fusion_signal = str(
        ((retrieval.get("temporal") or {}) if isinstance(retrieval.get("temporal"), dict) else {})
        .get("fusion", {})
        .get("signal")
        or ""
    )
    multi_hop_fusion_applied = bool(
        ((retrieval.get("multi_hop") or {}) if isinstance(retrieval.get("multi_hop"), dict) else {})
        .get("fusion", {})
        .get("applied")
    )
    hybrid_semantic_applied = bool(
        ((retrieval.get("hybrid") or {}) if isinstance(retrieval.get("hybrid"), dict) else {}).get("applied")
    )
    embedding_enabled = bool(
        ((retrieval.get("embedding") or {}) if isinstance(retrieval.get("embedding"), dict) else {}).get("enabled")
    )
    reranker_enabled = bool(
        ((retrieval.get("reranker") or {}) if isinstance(retrieval.get("reranker"), dict) else {}).get("enabled")
    )
    temporal_metadata = (retrieval.get("temporal") or {}) if isinstance(retrieval.get("temporal"), dict) else {}
    temporal_selection_strategy = str(temporal_metadata.get("selection_strategy") or "")
    temporal_injection_strategy = temporal_metadata.get("injection_strategy")
    prefer_temporal_fusion_rank = temporal_fusion_signal in {
        "temporal_history_relation_pair_rrf_score_v1",
        "temporal_update_relation_pair_rrf_score_v1",
        "temporal_earliest_relation_pair_rrf_score_v1",
    }
    prefer_multi_hop_fusion_rank = multi_hop_fusion_applied and not prefer_temporal_fusion_rank
    allow_default_current_selection_override = (
        temporal_selection_strategy == "current_only_v1"
        and temporal_injection_strategy in {None, ""}
        and not prefer_temporal_fusion_rank
        and not prefer_multi_hop_fusion_rank
    )
    prefer_reranker_rank = reranker_enabled and not prefer_temporal_fusion_rank and not prefer_multi_hop_fusion_rank
    prefer_embedding_rank = (
        embedding_enabled
        and not prefer_temporal_fusion_rank
        and not prefer_multi_hop_fusion_rank
        and not prefer_reranker_rank
    )
    prefer_hybrid_semantic_rank = (
        hybrid_semantic_applied
        and not prefer_temporal_fusion_rank
        and not prefer_multi_hop_fusion_rank
        and not prefer_reranker_rank
        and not prefer_embedding_rank
    )
    if max_tokens is not None and max_tokens < 0:
        raise ValueError("context budget cannot be negative")

    authorized_entries = []
    candidate_count = len(retrieval.get("candidates", []))
    for memory in authorized:
        candidate = candidate_by_id.get(memory.id)
        hybrid_semantic_rank = candidate.get("hybrid_semantic_rank") if candidate else None
        multi_hop_fusion_rank = candidate.get("multi_hop_fusion_rank") if candidate else None
        temporal_fusion_rank = candidate.get("temporal_fusion_rank") if candidate else None
        temporal_injection_rank = candidate.get("temporal_injection_rank") if candidate else None
        temporal_selection_rank = candidate.get("temporal_selection_rank") if candidate else None
        selected_by_temporal_strategy = bool(candidate.get("selected_by_temporal_strategy")) if candidate else False
        if (
            prefer_temporal_fusion_rank
            and selected_by_temporal_strategy
            and isinstance(temporal_fusion_rank, int)
            and temporal_fusion_rank > 0
        ):
            packing_rank = temporal_fusion_rank
            packing_rank_basis = "temporal_fusion_rank"
        elif prefer_multi_hop_fusion_rank and isinstance(multi_hop_fusion_rank, int) and multi_hop_fusion_rank > 0:
            packing_rank = multi_hop_fusion_rank
            packing_rank_basis = "multi_hop_fusion_rank"
        elif (
            prefer_reranker_rank
            and isinstance(candidate.get("reranker_rank"), int)
            and int(candidate["reranker_rank"]) > 0
            and (not selected_by_temporal_strategy or allow_default_current_selection_override)
        ):
            packing_rank = int(candidate["reranker_rank"])
            packing_rank_basis = "reranker_rank"
        elif (
            prefer_embedding_rank
            and isinstance(candidate.get("embedding_rank"), int)
            and int(candidate["embedding_rank"]) > 0
            and (not selected_by_temporal_strategy or allow_default_current_selection_override)
        ):
            packing_rank = int(candidate["embedding_rank"])
            packing_rank_basis = "embedding_rank"
        elif (
            prefer_hybrid_semantic_rank
            and isinstance(hybrid_semantic_rank, int)
            and hybrid_semantic_rank > 0
            and (not selected_by_temporal_strategy or allow_default_current_selection_override)
        ):
            packing_rank = hybrid_semantic_rank
            packing_rank_basis = "hybrid_semantic_rank"
        elif selected_by_temporal_strategy and isinstance(temporal_injection_rank, int) and temporal_injection_rank > 0:
            packing_rank = temporal_injection_rank
            packing_rank_basis = "temporal_injection_rank"
        elif selected_by_temporal_strategy and isinstance(temporal_selection_rank, int) and temporal_selection_rank > 0:
            packing_rank = temporal_selection_rank
            packing_rank_basis = "temporal_selection_rank"
        else:
            packing_rank = ranks.get(memory.id, len(ranks) + 1)
            packing_rank_basis = "retrieval_rank"
        authorized_entries.append(
            {
                "memory": memory,
                "rank": ranks.get(memory.id, len(ranks) + 1),
                "packing_rank": packing_rank,
                "packing_rank_basis": packing_rank_basis,
                "approx_tokens": approx_memory_tokens(memory),
                "selected_by_temporal_strategy": selected_by_temporal_strategy,
                "hybrid_semantic_rank": hybrid_semantic_rank if isinstance(hybrid_semantic_rank, int) else None,
                "hybrid_outranked_by_semantic_backfill": (
                    bool(candidate.get("hybrid_outranked_by_semantic_backfill")) if candidate else False
                ),
                "hybrid_outranked_reason": candidate.get("hybrid_outranked_reason") if candidate else None,
                "multi_hop_fusion_rank": multi_hop_fusion_rank if isinstance(multi_hop_fusion_rank, int) else None,
                "multi_hop_outranked_by_fusion": bool(candidate.get("multi_hop_outranked_by_fusion")) if candidate else False,
                "multi_hop_outranked_reason": candidate.get("multi_hop_outranked_reason") if candidate else None,
                "temporal_fusion_rank": temporal_fusion_rank if isinstance(temporal_fusion_rank, int) else None,
                "temporal_selection_rank": temporal_selection_rank if isinstance(temporal_selection_rank, int) else None,
                "temporal_injection_rank": temporal_injection_rank if isinstance(temporal_injection_rank, int) else None,
                "temporal_state": candidate.get("temporal_state") if candidate else None,
                "priority": _packing_priority(
                    memory,
                    candidate=candidate,
                    candidate_count=candidate_count,
                    prefer_temporal_fusion_rank=prefer_temporal_fusion_rank,
                    prefer_multi_hop_fusion_rank=prefer_multi_hop_fusion_rank,
                    prefer_reranker_rank=prefer_reranker_rank,
                    prefer_embedding_rank=prefer_embedding_rank,
                    prefer_hybrid_semantic_rank=prefer_hybrid_semantic_rank,
                    allow_default_current_selection_override=allow_default_current_selection_override,
                ),
                **_overlay_receipt_fields(candidate, include_empty=True),
            }
        )

    total_authorized_tokens = sum(int(entry["approx_tokens"]) for entry in authorized_entries)
    reservation = _packing_reservation(authorized_entries, retrieval)
    reserved_id_set = set(reservation["requested_ids"])
    for entry in authorized_entries:
        entry["reserved_by_strategy"] = entry["memory"].id in reserved_id_set
    injected: list[MemoryRecord] = []
    budget_dropped: list[dict[str, Any]] = []
    used_tokens = 0

    def ordered_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            entries,
            key=lambda entry: (
                int(entry["packing_rank"]),
                int(entry["rank"]),
                str(entry["memory"].id),
            ),
        )

    if max_tokens is None or total_authorized_tokens <= max_tokens:
        injected = [entry["memory"] for entry in ordered_entries(authorized_entries)]
        used_tokens = total_authorized_tokens
        reservation["applied"] = bool(reservation["requested_ids"])
        reservation["applied_ids"] = list(reservation["requested_ids"])
    else:
        def choose_entry_ids(entries: list[dict[str, Any]], *, budget_tokens: int) -> tuple[set[str], int]:
            states: dict[int, tuple[int, int, int, tuple[int, ...]]] = {
                0: (0, 0, 0, ())
            }
            state_history = [states]
            for entry in entries:
                next_states = dict(states)
                tokens = int(entry["approx_tokens"])
                rank = int(entry["packing_rank"])
                priority = int(entry["priority"])
                for used, state in states.items():
                    next_used = used + tokens
                    if next_used > budget_tokens:
                        continue
                    candidate_state = (
                        state[0] + priority,
                        state[1] + 1,
                        state[2] + rank,
                        state[3] + (rank,),
                    )
                    if _packing_state_is_better(candidate_state, next_states.get(next_used)):
                        next_states[next_used] = candidate_state
                states = next_states
                state_history.append(states)

            best_used_tokens, _ = max(
                states.items(),
                key=lambda item: (
                    item[1][0],
                    item[1][1],
                    -item[1][2],
                    tuple(-rank for rank in item[1][3]),
                    -item[0],
                ),
            )
            remaining_tokens = best_used_tokens
            selected_ids: set[str] = set()
            for index in range(len(entries) - 1, -1, -1):
                entry = entries[index]
                tokens = int(entry["approx_tokens"])
                rank = int(entry["packing_rank"])
                priority = int(entry["priority"])
                previous_used = remaining_tokens - tokens
                current_states = state_history[index + 1]
                previous_states = state_history[index]
                if previous_used < 0 or previous_used not in previous_states:
                    continue
                previous_state = previous_states[previous_used]
                expected_state = (
                    previous_state[0] + priority,
                    previous_state[1] + 1,
                    previous_state[2] + rank,
                    previous_state[3] + (rank,),
                )
                if current_states.get(remaining_tokens) == expected_state:
                    selected_ids.add(entry["memory"].id)
                    remaining_tokens = previous_used
            return selected_ids, best_used_tokens

        selected_ids: set[str]
        if reservation["requested_ids"]:
            def apply_reserved_ids(reserved_ids: list[str]) -> tuple[set[str], int] | None:
                reserved_ids_set = set(reserved_ids)
                reserved_entries = [entry for entry in authorized_entries if entry["memory"].id in reserved_ids_set]
                reserved_tokens = sum(int(entry["approx_tokens"]) for entry in reserved_entries)
                if reserved_tokens > max_tokens:
                    return None
                remaining_entries = [entry for entry in authorized_entries if entry["memory"].id not in reserved_ids_set]
                chosen_ids, additional_used_tokens = choose_entry_ids(
                    remaining_entries,
                    budget_tokens=max_tokens - reserved_tokens,
                )
                chosen_ids.update(reserved_ids_set)
                return chosen_ids, reserved_tokens + additional_used_tokens

            reservation_result = apply_reserved_ids(reservation["requested_ids"])
            if reservation_result is not None:
                selected_ids, used_tokens = reservation_result
                reservation["applied"] = True
                reservation["applied_ids"] = list(reservation["requested_ids"])
            else:
                fallback_requested_ids = [
                    str(memory_id)
                    for memory_id in reservation.get("fallback_requested_ids", [])
                    if str(memory_id)
                ]
                fallback_result = (
                    apply_reserved_ids(fallback_requested_ids)
                    if fallback_requested_ids and fallback_requested_ids != reservation["requested_ids"]
                    else None
                )
                if fallback_result is not None:
                    selected_ids, used_tokens = fallback_result
                    reservation["applied"] = True
                    reservation["applied_ids"] = list(fallback_requested_ids)
                    reservation["fallback_applied"] = True
                    reservation["fallback_reason"] = "support-chain-exceeds-budget-keep-anchor-pair"
                else:
                    reservation["blocked_reason"] = "reservation-exceeds-budget"
                    if reservation.get("strategy") == "target_history_support_chain_v1":
                        blocked_current_id, blocked_support_ids, blocked_pair_ids = _target_history_selected_pair(
                            temporal_metadata
                        )
                        if blocked_current_id and blocked_support_ids and blocked_pair_ids:
                            blocked_pair_token_total = sum(
                                int(entry["approx_tokens"])
                                for entry in authorized_entries
                                if entry["memory"].id in set(blocked_pair_ids)
                            )
                            reservation["blocked_detail"] = "selected-target-support-current-pair-exceeds-budget"
                            reservation["blocked_target_current_id"] = blocked_current_id
                            reservation["blocked_target_support_ids"] = blocked_support_ids
                            reservation["blocked_pair_ids"] = blocked_pair_ids
                            reservation["blocked_pair_tokens"] = blocked_pair_token_total
                            reservation["blocked_pair_excess_tokens"] = max(
                                blocked_pair_token_total - max_tokens,
                                0,
                            )
                    selected_ids, used_tokens = choose_entry_ids(authorized_entries, budget_tokens=max_tokens)
        else:
            selected_ids, used_tokens = choose_entry_ids(authorized_entries, budget_tokens=max_tokens)

        selected_id_set = set(selected_ids)
        for entry in authorized_entries:
            reservation_exclusion = _packing_reservation_exclusion(
                entry=entry,
                selected_ids=selected_id_set,
                reservation=reservation,
                temporal=temporal_metadata,
            )
            if reservation_exclusion is None:
                reservation_exclusion = _packing_blocked_target_history_pair_metadata(
                    entry=entry,
                    reservation=reservation,
                    temporal=temporal_metadata,
                )
            entry["reservation_exclusion"] = reservation_exclusion
            entry["reservation_exclusion_reason"] = (
                reservation_exclusion.get("reason")
                if isinstance(reservation_exclusion, dict)
                else None
            )

        selected_entries = []
        for entry in authorized_entries:
            if entry["memory"].id in selected_id_set:
                selected_entries.append(entry)
                continue
            budget_dropped.append(
                {
                    "memory_id": entry["memory"].id,
                    "reason": "context-budget",
                    "approx_tokens": entry["approx_tokens"],
                    "rank": entry["rank"],
                    "packing_rank": entry["packing_rank"],
                    "packing_rank_basis": entry["packing_rank_basis"],
                    "packing_priority": entry["priority"],
                    "selected_by_temporal_strategy": entry["selected_by_temporal_strategy"],
                    "embedding_rank": entry["embedding_rank"],
                    "embedding_rank_delta": entry["embedding_rank_delta"],
                    "embedding_promoted": entry["embedding_promoted"],
                    "embedding_outranked": entry["embedding_outranked"],
                    "embedding_outranked_reason": entry["embedding_outranked_reason"],
                    "reranker_rank": entry["reranker_rank"],
                    "reranker_rank_delta": entry["reranker_rank_delta"],
                    "reranker_promoted": entry["reranker_promoted"],
                    "reranker_outranked": entry["reranker_outranked"],
                    "reranker_outranked_reason": entry["reranker_outranked_reason"],
                    "hybrid_semantic_rank": entry["hybrid_semantic_rank"],
                    "hybrid_outranked_by_semantic_backfill": entry["hybrid_outranked_by_semantic_backfill"],
                    "hybrid_outranked_reason": entry["hybrid_outranked_reason"],
                    "multi_hop_fusion_rank": entry["multi_hop_fusion_rank"],
                    "multi_hop_outranked_by_fusion": entry["multi_hop_outranked_by_fusion"],
                    "multi_hop_outranked_reason": entry["multi_hop_outranked_reason"],
                    "temporal_fusion_rank": entry["temporal_fusion_rank"],
                    "temporal_selection_rank": entry["temporal_selection_rank"],
                    "temporal_injection_rank": entry["temporal_injection_rank"],
                    "temporal_state": entry["temporal_state"],
                    "reserved_by_strategy": entry["reserved_by_strategy"],
                    "reservation_exclusion": entry["reservation_exclusion"],
                    "reservation_exclusion_reason": entry["reservation_exclusion_reason"],
                }
            )
        injected = [entry["memory"] for entry in ordered_entries(selected_entries)]

    packing = {
        "schema": CONTEXT_PACKING_SCHEMA,
        "strategy": "priority_knapsack_budget_v1",
        "max_tokens": max_tokens,
        "budget_enforced": max_tokens is not None,
        "approximation": CONTEXT_TOKEN_APPROXIMATION,
        "used_tokens": used_tokens,
        "available_tokens": total_authorized_tokens,
        "injected_ids": [memory.id for memory in injected],
        "budget_dropped": budget_dropped,
        "diversity_dropped": [],
        "priority_model": (
            "temporal_fusion_rank_score_authority_current_v1"
            if prefer_temporal_fusion_rank
            else (
                "multi_hop_fusion_rank_score_authority_current_v1"
                if prefer_multi_hop_fusion_rank
                else (
                    "reranker_rank_score_authority_current_v1"
                    if any(entry["packing_rank_basis"] == "reranker_rank" for entry in authorized_entries)
                    else (
                        "embedding_rank_score_authority_current_v1"
                        if any(entry["packing_rank_basis"] == "embedding_rank" for entry in authorized_entries)
                        else (
                    "hybrid_semantic_rank_score_authority_current_v1"
                    if any(entry["packing_rank_basis"] == "hybrid_semantic_rank" for entry in authorized_entries)
                    else "temporal_selection_rank_score_authority_current_v1"
                        )
                    )
                )
            )
        ),
        "reservation": reservation,
        "candidate_priorities": [
            {
                "memory_id": entry["memory"].id,
                "rank": entry["rank"],
                "packing_rank": entry["packing_rank"],
                "packing_rank_basis": entry["packing_rank_basis"],
                "approx_tokens": entry["approx_tokens"],
                "packing_priority": entry["priority"],
                "selected_by_temporal_strategy": entry["selected_by_temporal_strategy"],
                "embedding_rank": entry["embedding_rank"],
                "embedding_rank_delta": entry["embedding_rank_delta"],
                "embedding_promoted": entry["embedding_promoted"],
                "embedding_outranked": entry["embedding_outranked"],
                "embedding_outranked_reason": entry["embedding_outranked_reason"],
                "reranker_rank": entry["reranker_rank"],
                "reranker_rank_delta": entry["reranker_rank_delta"],
                "reranker_promoted": entry["reranker_promoted"],
                "reranker_outranked": entry["reranker_outranked"],
                "reranker_outranked_reason": entry["reranker_outranked_reason"],
                "hybrid_semantic_rank": entry["hybrid_semantic_rank"],
                "hybrid_outranked_by_semantic_backfill": entry["hybrid_outranked_by_semantic_backfill"],
                "hybrid_outranked_reason": entry["hybrid_outranked_reason"],
                "multi_hop_fusion_rank": entry["multi_hop_fusion_rank"],
                "multi_hop_outranked_by_fusion": entry["multi_hop_outranked_by_fusion"],
                "multi_hop_outranked_reason": entry["multi_hop_outranked_reason"],
                "temporal_fusion_rank": entry["temporal_fusion_rank"],
                "temporal_selection_rank": entry["temporal_selection_rank"],
                "temporal_injection_rank": entry["temporal_injection_rank"],
                "temporal_state": entry["temporal_state"],
                "reserved_by_strategy": entry["reserved_by_strategy"],
                "reservation_exclusion": entry.get("reservation_exclusion"),
                "reservation_exclusion_reason": entry.get("reservation_exclusion_reason"),
            }
            for entry in authorized_entries
        ],
    }
    return {"memories": injected, "metadata": packing}


def merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return sha256_text("")
    level = hashes[:]
    while len(level) > 1:
        nxt: list[str] = []
        for idx in range(0, len(level), 2):
            left = level[idx]
            right = level[idx + 1] if idx + 1 < len(level) else left
            nxt.append(sha256_text(left + right))
        level = nxt
    return level[0]


def merkle_proof(hashes: list[str], index: int) -> list[dict[str, Any]]:
    if index < 0 or index >= len(hashes):
        raise IndexError("merkle proof index out of range")
    proof: list[dict[str, Any]] = []
    level = hashes[:]
    cursor = index
    while len(level) > 1:
        sibling_index = cursor - 1 if cursor % 2 else cursor + 1
        if sibling_index >= len(level):
            sibling_index = cursor
        proof.append(
            {
                "position": "left" if sibling_index < cursor else "right",
                "hash": level[sibling_index],
            }
        )
        nxt: list[str] = []
        for idx in range(0, len(level), 2):
            left = level[idx]
            right = level[idx + 1] if idx + 1 < len(level) else left
            nxt.append(sha256_text(left + right))
        cursor //= 2
        level = nxt
    return proof


def verify_merkle_proof(leaf_hash: str, proof: list[dict[str, Any]], root: str) -> bool:
    computed = leaf_hash
    for item in proof:
        sibling = str(item.get("hash", ""))
        if item.get("position") == "left":
            computed = sha256_text(sibling + computed)
        elif item.get("position") == "right":
            computed = sha256_text(computed + sibling)
        else:
            return False
    return computed == root


def event_hash_from_record(event: Mapping[str, Any]) -> str:
    required_string_fields = (
        "event_schema",
        "hash_alg",
        "event_type",
        "actor_id",
        "payload_hash",
        "prev_event_hash",
        "created_at",
    )
    for field in required_string_fields:
        if not isinstance(event.get(field), str) or not event[field]:
            raise ValueError(f"event witness {field} is invalid")
    if event.get("event_schema") != EVENT_SCHEMA:
        raise ValueError("event witness schema is unsupported")
    if event.get("hash_alg") != HASH_ALG:
        raise ValueError("event witness hash algorithm is unsupported")
    for field in ("memory_id", "action_id"):
        if field not in event or event[field] is not None and not isinstance(event[field], str):
            raise ValueError(f"event witness {field} is invalid")
    return sha256_text(
        stable_json(
            {
                "event_schema": event["event_schema"],
                "hash_alg": event["hash_alg"],
                "event_type": event["event_type"],
                "memory_id": event["memory_id"],
                "action_id": event["action_id"],
                "actor_id": event["actor_id"],
                "payload_hash": event["payload_hash"],
                "prev_event_hash": event["prev_event_hash"],
                "created_at": event["created_at"],
            }
        )
    )


def validate_indexed_merkle_witness(
    *,
    leaf_hash: str,
    leaf_index: int,
    leaf_count: int,
    proof: list[dict[str, Any]],
    root: str,
) -> None:
    if type(leaf_count) is not int or leaf_count <= 0:
        raise ValueError("event witness leaf_count is invalid")
    if type(leaf_index) is not int or leaf_index < 0 or leaf_index >= leaf_count:
        raise ValueError("event witness leaf_index is invalid")
    if not isinstance(root, str) or not root:
        raise ValueError("event witness root is invalid")
    if not isinstance(proof, list):
        raise ValueError("event witness proof is invalid")

    cursor = leaf_index
    level_count = leaf_count
    for item in proof:
        if not isinstance(item, dict):
            raise ValueError("event witness proof entry is invalid")
        sibling_index = cursor - 1 if cursor % 2 else cursor + 1
        if sibling_index >= level_count:
            sibling_index = cursor
        expected_position = "left" if sibling_index < cursor else "right"
        if item.get("position") != expected_position:
            raise ValueError("event witness proof position is invalid")
        if not isinstance(item.get("hash"), str) or not item["hash"]:
            raise ValueError("event witness proof hash is invalid")
        cursor //= 2
        level_count = (level_count + 1) // 2
    if level_count != 1:
        raise ValueError("event witness proof length is invalid")
    if not verify_merkle_proof(leaf_hash, proof, root):
        raise ValueError("event witness Merkle proof is invalid")


def validate_receipt_bundle_core(bundle: Mapping[str, Any]) -> dict[str, Any]:
    schema = bundle.get("bundle_schema")
    if schema not in BUNDLE_SCHEMAS:
        raise ValueError("unsupported bundle schema")
    if bundle.get("hash_alg") != HASH_ALG:
        raise ValueError("unsupported bundle hash algorithm")
    if bundle.get("merkle_alg") != MERKLE_ALG:
        raise ValueError("unsupported bundle merkle algorithm")
    bundle_hash = bundle.get("bundle_hash")
    if not isinstance(bundle_hash, str) or not bundle_hash:
        raise ValueError("bundle missing bundle_hash")
    without_hash = dict(bundle)
    without_hash.pop("bundle_hash", None)
    if sha256_text(stable_json(without_hash)) != bundle_hash:
        raise ValueError("bundle_hash mismatch")

    receipt = bundle.get("receipt")
    if not isinstance(receipt, Mapping):
        raise ValueError("bundle missing receipt")
    if bundle.get("action_id") != receipt.get("action_id"):
        raise ValueError("bundle action_id mismatch")
    receipt_merkle_root = receipt.get("merkle_root")
    if not isinstance(receipt_merkle_root, str) or not receipt_merkle_root:
        raise ValueError("bundle receipt merkle_root is invalid")
    proof = bundle.get("proof")
    if not isinstance(proof, Mapping):
        raise ValueError("bundle missing proof")

    if schema == BUNDLE_SCHEMA_V1:
        events = bundle.get("supporting_events")
        if not isinstance(events, list):
            raise ValueError("bundle supporting_events must be a list")
        if any(not isinstance(event, Mapping) for event in events):
            raise ValueError("bundle supporting event is invalid")
        computed_merkle_root = merkle_root([str(event.get("event_hash", "")) for event in events])
        if computed_merkle_root != receipt_merkle_root:
            raise ValueError("bundle merkle_root mismatch")
        if proof.get("computed_merkle_root") != computed_merkle_root:
            raise ValueError("bundle proof computed_merkle_root mismatch")
        if proof.get("receipt_merkle_root") != receipt_merkle_root:
            raise ValueError("bundle proof receipt_merkle_root mismatch")
        if proof.get("event_count") != len(events):
            raise ValueError("bundle proof event_count mismatch")
        if proof.get("verified") is not True:
            raise ValueError("bundle proof is not verified")
        return {
            "computed_merkle_root": computed_merkle_root,
            "event_count": len(events),
            "event_witness_count": 0,
            "event_witnesses_verified": None,
            "proof_event_count": proof.get("event_count"),
            "proof_verified": proof.get("verified"),
        }

    event_log = bundle.get("event_log")
    witnesses = bundle.get("event_witnesses")
    if not isinstance(event_log, Mapping):
        raise ValueError("bundle event_log is invalid")
    if not isinstance(witnesses, list):
        raise ValueError("bundle event_witnesses must be a list")
    event_count = event_log.get("event_count")
    if type(event_count) is not int or event_count < 0:
        raise ValueError("bundle event_log event_count is invalid")
    event_log_root = event_log.get("merkle_root")
    if event_log_root != receipt_merkle_root:
        raise ValueError("bundle event_log merkle_root mismatch")
    if proof.get("event_count") != event_count:
        raise ValueError("bundle proof event_count mismatch")
    if proof.get("event_witness_count") != len(witnesses):
        raise ValueError("bundle proof event_witness_count mismatch")
    if proof.get("event_log_merkle_root") != event_log_root:
        raise ValueError("bundle proof event_log_merkle_root mismatch")
    if proof.get("receipt_merkle_root") != receipt_merkle_root:
        raise ValueError("bundle proof receipt_merkle_root mismatch")
    if proof.get("event_witnesses_verified") is not True:
        raise ValueError("bundle proof event_witnesses_verified mismatch")
    if proof.get("verified") is not True:
        raise ValueError("bundle proof is not verified")

    first_seq = event_log.get("first_seq")
    last_seq = event_log.get("last_seq")
    last_event_hash = event_log.get("last_event_hash")
    if event_count == 0:
        if witnesses:
            raise ValueError("empty event log cannot contain witnesses")
        if first_seq is not None or last_seq is not None or last_event_hash is not None:
            raise ValueError("empty event log anchors are invalid")
        if event_log_root != merkle_root([]):
            raise ValueError("empty event log merkle_root mismatch")
    else:
        if type(first_seq) is not int or type(last_seq) is not int:
            raise ValueError("bundle event_log sequence anchors are invalid")
        if last_seq < first_seq or event_count > last_seq - first_seq + 1:
            raise ValueError("bundle event_log sequence anchors are invalid")
        if not isinstance(last_event_hash, str) or not last_event_hash:
            raise ValueError("bundle event_log last_event_hash is invalid")
        if not witnesses:
            raise ValueError("non-empty event log requires witnesses")

    witnessed_indexes: set[int] = set()
    witnessed_hashes: set[str] = set()
    witnessed_sequences: list[tuple[int, int]] = []
    for witness in witnesses:
        if not isinstance(witness, Mapping):
            raise ValueError("bundle event witness is invalid")
        leaf_index = witness.get("leaf_index")
        event = witness.get("event")
        witness_proof = witness.get("proof")
        if type(leaf_index) is not int:
            raise ValueError("event witness leaf_index is invalid")
        if leaf_index in witnessed_indexes:
            raise ValueError("bundle event witness leaf_index is duplicated")
        if not isinstance(event, Mapping):
            raise ValueError("bundle event witness event is invalid")
        event_hash = event.get("event_hash")
        if not isinstance(event_hash, str) or not event_hash:
            raise ValueError("event witness event_hash is invalid")
        if event_hash in witnessed_hashes:
            raise ValueError("bundle event witness event_hash is duplicated")
        if event_hash_from_record(event) != event_hash:
            raise ValueError("event witness event_hash mismatch")
        if (
            type(event.get("seq")) is not int
            or event["seq"] < first_seq
            or event["seq"] > last_seq
        ):
            raise ValueError("event witness sequence mismatch")
        validate_indexed_merkle_witness(
            leaf_hash=event_hash,
            leaf_index=leaf_index,
            leaf_count=event_count,
            proof=witness_proof,
            root=event_log_root,
        )
        witnessed_indexes.add(leaf_index)
        witnessed_hashes.add(event_hash)
        witnessed_sequences.append((leaf_index, event["seq"]))

    ordered_sequences = [seq for _, seq in sorted(witnessed_sequences)]
    if any(left >= right for left, right in zip(ordered_sequences, ordered_sequences[1:])):
        raise ValueError("event witness sequence order mismatch")

    if event_count and (
        event_count - 1 not in witnessed_indexes
        or not any(
            witness.get("leaf_index") == event_count - 1
            and isinstance(witness.get("event"), Mapping)
            and witness["event"].get("event_hash") == last_event_hash
            and witness["event"].get("seq") == last_seq
            for witness in witnesses
        )
    ):
        raise ValueError("bundle final event anchor witness is missing")

    supporting_receipts = bundle.get("supporting_memory_write_receipts") or {}
    if not isinstance(supporting_receipts, Mapping):
        raise ValueError("bundle supporting_memory_write_receipts is invalid")
    for supporting_receipt in supporting_receipts.values():
        if not isinstance(supporting_receipt, Mapping):
            raise ValueError("bundle supporting write receipt is invalid")
        event_hash = supporting_receipt.get("event_hash")
        if not isinstance(event_hash, str) or event_hash not in witnessed_hashes:
            raise ValueError("bundle supporting write event witness is missing")

    return {
        "computed_merkle_root": event_log_root,
        "event_count": event_count,
        "event_witness_count": len(witnesses),
        "event_witnesses_verified": True,
        "proof_event_count": proof.get("event_count"),
        "proof_verified": proof.get("verified"),
    }


def _status_from_event(event_type: str, payload: dict[str, Any]) -> str | None:
    if event_type in {"PROPOSED", "OBSERVED"}:
        status = str(payload.get("status") or "")
        if status in STATUSES:
            return status
        return "active" if event_type == "OBSERVED" else "quarantined"
    if event_type == "PROMOTED":
        return "active"
    if event_type == "REJECTED":
        return "deprecated"
    if event_type == "REVOKED":
        return "revoked"
    if event_type == "FORGOTTEN":
        return "forgotten"
    return None


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    type: str
    content: str
    scope: str
    source_kind: str
    trust: float
    authority: str
    status: str
    parents: list[str]
    labels: list[str]
    created_at: str
    updated_at: str
    expires_at: str | None
    content_hash: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "MemoryRecord":
        return cls(
            id=row["id"],
            type=row["type"],
            content=row["content"],
            scope=row["scope"],
            source_kind=row["source_kind"],
            trust=row["trust"],
            authority=row["authority"],
            status=row["status"],
            parents=json.loads(row["parents_json"]),
            labels=json.loads(row["labels_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            content_hash=row["content_hash"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "scope": self.scope,
            "source_kind": self.source_kind,
            "trust": self.trust,
            "authority": self.authority,
            "status": self.status,
            "parents": self.parents,
            "labels": self.labels,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "content_hash": self.content_hash,
        }


class MemoryStore:
    def __init__(
        self,
        db_path: Path | None = None,
        *,
        policy_path: Path | None = None,
        treeship_auto_sign: bool | None = None,
        treeship_config_path: Path | None = None,
        treeship_strict: bool | None = None,
    ):
        self.db_path = expand_user_path(db_path or default_db_path())
        self.policy_path = expand_user_path(policy_path) if policy_path is not None else None
        self.treeship_auto_sign = _env_flag("ZMEM_TREESHIP_AUTO_SIGN") if treeship_auto_sign is None else treeship_auto_sign
        resolved_treeship_config = treeship_config_path or _env_path("ZMEM_TREESHIP_CONFIG")
        self.treeship_config_path = expand_user_path(resolved_treeship_config) if resolved_treeship_config is not None else None
        self.treeship_strict = _env_flag("ZMEM_TREESHIP_STRICT") if treeship_strict is None else treeship_strict
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.parent.name == ".zerker":
            try:
                self.db_path.parent.chmod(0o700)
            except OSError:
                pass
        self.conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            self.db_path.chmod(0o600)
        except OSError:
            pass
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")

    def init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
              id TEXT PRIMARY KEY,
              type TEXT NOT NULL,
              content TEXT NOT NULL,
              scope TEXT NOT NULL,
              source_kind TEXT NOT NULL,
              trust REAL NOT NULL,
              authority TEXT NOT NULL,
              status TEXT NOT NULL,
              parents_json TEXT NOT NULL,
              labels_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              expires_at TEXT,
              content_hash TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
              USING fts5(id UNINDEXED, content, labels);

            CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event_type TEXT NOT NULL,
              memory_id TEXT,
              action_id TEXT,
              actor_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              prev_event_hash TEXT NOT NULL,
              event_hash TEXT NOT NULL,
              merkle_root TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS events_memory_id_seq_idx
              ON events(memory_id, seq);

            CREATE TABLE IF NOT EXISTS receipts (
              action_id TEXT PRIMARY KEY,
              receipt_schema TEXT NOT NULL DEFAULT 'zerker.memory_action.v1',
              hash_alg TEXT NOT NULL DEFAULT 'sha256',
              merkle_alg TEXT NOT NULL DEFAULT 'binary-sha256-v1',
              agent_id TEXT NOT NULL,
              task TEXT NOT NULL,
              task_hash TEXT NOT NULL,
              risk TEXT NOT NULL,
              retrieved_ids_json TEXT NOT NULL,
              retrieval_json TEXT NOT NULL DEFAULT '{}',
              injected_ids_json TEXT NOT NULL,
              withheld_json TEXT NOT NULL,
              policy_checks_json TEXT NOT NULL,
              memory_tree_json TEXT NOT NULL DEFAULT '{}',
              merkle_root TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_write_receipts (
              receipt_id TEXT PRIMARY KEY,
              receipt_schema TEXT NOT NULL DEFAULT 'zerker.memory_write.v1',
              hash_alg TEXT NOT NULL DEFAULT 'sha256',
              merkle_alg TEXT NOT NULL DEFAULT 'binary-sha256-v1',
              memory_id TEXT NOT NULL,
              actor_uri TEXT NOT NULL,
              session_id TEXT NOT NULL,
              parent_action_id TEXT,
              source_uri TEXT,
              content_digest TEXT NOT NULL,
              environment_hash TEXT NOT NULL,
              event_hash TEXT NOT NULL,
              merkle_root TEXT NOT NULL,
              treeship_statement_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              receipt_hash TEXT NOT NULL,
              FOREIGN KEY(memory_id) REFERENCES memories(id)
            );

            CREATE TABLE IF NOT EXISTS session_snapshot_payloads (
              session_snapshot_id TEXT PRIMARY KEY,
              event_hash TEXT NOT NULL,
              snapshot_hash TEXT NOT NULL,
              snapshot_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              deleted_at TEXT,
              deleted_by TEXT,
              deleted_reason TEXT,
              deleted_event_hash TEXT
            );
            """
        )
        self._ensure_column("receipts", "retrieval_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("receipts", "memory_tree_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("session_snapshot_payloads", "deleted_at", "TEXT")
        self._ensure_column("session_snapshot_payloads", "deleted_by", "TEXT")
        self._ensure_column("session_snapshot_payloads", "deleted_reason", "TEXT")
        self._ensure_column("session_snapshot_payloads", "deleted_event_hash", "TEXT")
        self.conn.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def remember(
        self,
        content: str,
        *,
        memory_type: str,
        scope: str,
        source_kind: str,
        trust: float | None = None,
        authority: str | None = None,
        status: str | None = None,
        actor_id: str = "human",
        parents: list[str] | None = None,
        labels: list[str] | None = None,
        source_uri: str | None = None,
        actor_uri: str | None = None,
        session_id: str | None = None,
        caused_by_event: str | None = None,
        parent_action_id: str | None = None,
        environment_hash: str | None = None,
        memory_id: str | None = None,
        created_at: str | None = None,
    ) -> MemoryRecord:
        self.init()
        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"unsupported memory type: {memory_type}")
        parents = parents or []
        labels = labels or []
        trust = self._default_trust(source_kind) if trust is None else trust
        authority = self._default_authority(memory_type, source_kind) if authority is None else authority
        if authority not in AUTHORITIES:
            raise ValueError(f"unsupported authority: {authority}")
        status = status or self._default_status(source_kind, memory_type)
        if status not in STATUSES:
            raise ValueError(f"unsupported status: {status}")
        if memory_id is None:
            memory_id = "mem_" + uuid.uuid4().hex[:16]
        elif not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError("memory_id must be a non-empty string")
        elif self.conn.execute("SELECT 1 FROM memories WHERE id = ?", (memory_id,)).fetchone() is not None:
            raise ValueError(f"memory id already exists: {memory_id}")
        if created_at is None:
            created_at = now_iso()
        elif not isinstance(created_at, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", created_at):
            raise ValueError("created_at must be in ISO 8601 UTC form like 2024-01-01T00:00:00Z")
        content_hash = sha256_text(content)
        self.conn.execute(
            """
            INSERT INTO memories (
              id, type, content, scope, source_kind, trust, authority, status,
              parents_json, labels_json, created_at, updated_at, expires_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                memory_type,
                content,
                scope,
                source_kind,
                trust,
                authority,
                status,
                stable_json(parents),
                stable_json(labels),
                created_at,
                created_at,
                None,
                content_hash,
            ),
        )
        self.conn.execute(
            "INSERT INTO memories_fts (id, content, labels) VALUES (?, ?, ?)",
            (memory_id, content, " ".join(labels)),
        )
        event = self._append_event(
            "PROPOSED" if status in {"proposed", "quarantined"} else "OBSERVED",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={
                "id": memory_id,
                "type": memory_type,
                "scope": scope,
                "source_kind": source_kind,
                "trust": trust,
                "authority": authority,
                "status": status,
                "content_hash": content_hash,
                "source_uri": source_uri,
                "caused_by_event": caused_by_event,
                "parent_action_id": parent_action_id,
            },
            created_at=created_at,
        )
        self._append_write_receipt(
            memory_id=memory_id,
            actor_uri=actor_uri or actor_uri_for(actor_id),
            session_id=session_id or f"session://{self.db_path.resolve()}",
            parent_action_id=parent_action_id,
            source_uri=source_uri,
            caused_by_event=caused_by_event,
            content_digest=digest_uri(content),
            environment_hash=environment_hash or default_environment_hash(),
            event=event,
            created_at=created_at,
            object_updates={
                "actor_id": actor_id,
                "memory_type": memory_type,
                "scope": scope,
                "source_kind": source_kind,
                "trust": trust,
                "authority": authority,
                "status": status,
                "semantic_truth_guaranteed": False,
            },
        )
        self.conn.commit()
        return self.get(memory_id)

    def import_external(
        self,
        candidate: Any,
        *,
        memory_type: str = "semantic",
        scope: str = "global",
        actor_id: str = "zerker",
        trust: float | None = None,
        authority: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
    ) -> MemoryRecord:
        merged_labels = [f"provider:{candidate.provider}", f"external:{candidate.external_id}"]
        if candidate.score is not None:
            merged_labels.append(f"score:{candidate.score:.3f}")
        if labels:
            merged_labels.extend(str(label) for label in labels)
        source_uri = candidate.source_uri or f"{candidate.provider}://{candidate.external_id}"
        return self.remember(
            candidate.content,
            memory_type=memory_type,
            scope=scope,
            source_kind="import",
            actor_id=actor_id,
            trust=trust,
            authority=authority,
            status=status,
            labels=merged_labels,
            source_uri=source_uri,
        )

    def get(self, memory_id: str) -> MemoryRecord:
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            raise KeyError(f"memory not found: {memory_id}")
        return MemoryRecord.from_row(row)

    def list_memories(
        self,
        *,
        scope: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        self.init()
        if status is not None and status not in STATUSES:
            raise ValueError(f"unsupported status: {status}")
        params: list[Any] = []
        where: list[str] = []
        if scope:
            where.append("(scope = ? OR scope = 'global')")
            params.append(scope)
        if status:
            where.append("status = ?")
            params.append(status)
        where_sql = "WHERE " + " AND ".join(where) if where else ""
        params.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM memories
            {where_sql}
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [MemoryRecord.from_row(row) for row in rows]

    def _project_temporal_state(
        self,
        memories: list[MemoryRecord],
        *,
        timestamp: str,
    ) -> dict[str, Any]:
        if not memories:
            return {
                "entries": [],
                "temporal_graph": {},
                "history_memory_ids": [],
                "current_memory_ids": [],
                "resolved_current_memory_ids": [],
                "dropped_current_memory_ids": [],
                "abstained_current_memory_ids": [],
                "future_memory_ids": [],
                "superseded_memory_ids": [],
                "unlearned_memory_ids": [],
                "learned_memory_ids": [],
                "conflict_sets": [],
                "abstention": {
                    "applied": False,
                    "reason": None,
                    "abstained_ids": [],
                    "conflict_reasons": [],
                },
            }

        memories_by_id = {memory.id: memory for memory in memories}
        memory_ids = [memory.id for memory in memories]
        placeholders = ",".join("?" for _ in memory_ids)
        event_rows = self.conn.execute(
            f"""
            SELECT seq, memory_id, event_type, payload_json, created_at
            FROM events
            WHERE memory_id IN ({placeholders})
            ORDER BY seq ASC
            """,
            memory_ids,
        ).fetchall()
        status_history_by_id: dict[str, list[dict[str, Any]]] = {memory_id: [] for memory_id in memory_ids}
        updated_at_query_by_id: dict[str, str | None] = {
            memory_id: None for memory_id in memory_ids
        }
        serial_at_query_by_id: dict[str, int | None] = {memory_id: None for memory_id in memory_ids}
        for row in event_rows:
            payload = json.loads(row["payload_json"])
            memory_id = str(row["memory_id"])
            if str(row["created_at"]) <= timestamp:
                updated_at_query_by_id[memory_id] = str(row["created_at"])
                prior_serial = serial_at_query_by_id.get(memory_id)
                next_serial = int(row["seq"])
                serial_at_query_by_id[memory_id] = (
                    next_serial
                    if prior_serial is None or next_serial > prior_serial
                    else prior_serial
                )
            status = _status_from_event(str(row["event_type"]), payload)
            if status is None:
                continue
            status_history_by_id[memory_id].append(
                {
                    "at": str(row["created_at"]),
                    "event_type": str(row["event_type"]),
                    "status": status,
                }
            )

        valid_from_by_id: dict[str, str | None] = {}
        unlearned_at_by_id: dict[str, str | None] = {}
        status_at_query_by_id: dict[str, str] = {}
        for memory in memories:
            status_history = status_history_by_id.get(memory.id, [])
            valid_from = next((item["at"] for item in status_history if item["status"] == "active"), None)
            unlearned_at = next(
                (
                    item["at"]
                    for item in status_history
                    if item["status"] in {"deprecated", "revoked", "forgotten"}
                ),
                None,
            )
            status_at_query = "future"
            for item in status_history:
                if item["at"] > timestamp:
                    break
                status_at_query = str(item["status"])
            valid_from_by_id[memory.id] = valid_from
            unlearned_at_by_id[memory.id] = unlearned_at
            status_at_query_by_id[memory.id] = status_at_query

        child_ids_by_parent: dict[str, list[str]] = {}
        for memory in memories:
            if valid_from_by_id.get(memory.id) is None:
                continue
            for parent_id in memory.parents:
                if parent_id in memories_by_id:
                    child_ids_by_parent.setdefault(parent_id, []).append(memory.id)

        superseded_at_by_id: dict[str, str | None] = {memory.id: None for memory in memories}
        superseded_by_ids: dict[str, list[str]] = {memory.id: [] for memory in memories}
        supersession_reasons_by_id: dict[str, list[str]] = {memory.id: [] for memory in memories}
        for parent_id, child_ids in child_ids_by_parent.items():
            child_events = [
                (str(valid_from_by_id[child_id]), child_id)
                for child_id in child_ids
                if valid_from_by_id.get(child_id) is not None
            ]
            if not child_events:
                continue
            child_events.sort(key=lambda item: (item[0], item[1]))
            superseded_at = child_events[0][0]
            superseded_at_by_id[parent_id] = superseded_at
            superseded_by_ids[parent_id] = [
                child_id for child_at, child_id in child_events if child_at == superseded_at
            ]
            supersession_reasons_by_id[parent_id] = ["active-child-candidate"]
        _apply_query_at_explicit_updates(
            memories_by_id=memories_by_id,
            valid_from_by_id=valid_from_by_id,
            updated_at_query_by_id=updated_at_query_by_id,
            unlearned_at_by_id=unlearned_at_by_id,
            status_at_query_by_id=status_at_query_by_id,
            superseded_at_by_id=superseded_at_by_id,
            superseded_by_ids=superseded_by_ids,
            supersession_reasons_by_id=supersession_reasons_by_id,
            serial_at_query_by_id=serial_at_query_by_id,
            timestamp=timestamp,
        )
        _apply_query_at_subject_lookup_restatements(
            memories_by_id=memories_by_id,
            valid_from_by_id=valid_from_by_id,
            updated_at_query_by_id=updated_at_query_by_id,
            unlearned_at_by_id=unlearned_at_by_id,
            status_at_query_by_id=status_at_query_by_id,
            superseded_at_by_id=superseded_at_by_id,
            superseded_by_ids=superseded_by_ids,
            supersession_reasons_by_id=supersession_reasons_by_id,
            serial_at_query_by_id=serial_at_query_by_id,
            timestamp=timestamp,
        )

        entries = []
        temporal_graph: dict[str, dict[str, Any]] = {}
        history_memory_ids: list[str] = []
        current_memory_ids: list[str] = []
        future_memory_ids: list[str] = []
        superseded_memory_ids: list[str] = []
        unlearned_memory_ids: list[str] = []
        learned_memory_ids: list[str] = []
        for memory in memories:
            learned_at = memory.created_at
            valid_from = valid_from_by_id.get(memory.id)
            superseded_at = superseded_at_by_id.get(memory.id)
            unlearned_at = unlearned_at_by_id.get(memory.id)
            valid_to = min(
                [item for item in (superseded_at, unlearned_at) if item is not None],
                default=None,
            )
            status_at_query = status_at_query_by_id.get(memory.id, "future")

            if learned_at > timestamp:
                temporal_state = "future"
                future_memory_ids.append(memory.id)
            elif unlearned_at is not None and unlearned_at <= timestamp:
                temporal_state = "unlearned"
                history_memory_ids.append(memory.id)
                unlearned_memory_ids.append(memory.id)
            elif valid_from is not None and valid_from <= timestamp and superseded_at is not None and superseded_at <= timestamp:
                temporal_state = "superseded"
                history_memory_ids.append(memory.id)
                superseded_memory_ids.append(memory.id)
            elif valid_from is not None and valid_from <= timestamp and status_at_query == "active":
                temporal_state = "current"
                history_memory_ids.append(memory.id)
                current_memory_ids.append(memory.id)
            else:
                temporal_state = "learned"
                history_memory_ids.append(memory.id)
                learned_memory_ids.append(memory.id)

            temporal_resolution_kind = None
            temporal_resolution_reasons: list[str] = []
            if temporal_state == "superseded":
                temporal_resolution_kind = "supersession"
                temporal_resolution_reasons = list(supersession_reasons_by_id.get(memory.id, []))
            elif temporal_state == "unlearned":
                temporal_resolution_kind = "unlearned"
                if status_at_query in {"deprecated", "revoked", "forgotten"}:
                    temporal_resolution_reasons = [status_at_query]

            envelope = {
                "memory_id": memory.id,
                "parents": list(memory.parents),
                "serial": serial_at_query_by_id.get(memory.id),
                "learned_at": learned_at,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "superseded_at": superseded_at,
                "superseded_by_ids": superseded_by_ids.get(memory.id, []),
                "unlearned_at": unlearned_at,
                "status_at_query": status_at_query,
                "temporal_state": temporal_state,
                "current_resolution": None,
                "current_conflict_reasons": [],
                "temporal_resolution_kind": temporal_resolution_kind,
                "temporal_resolution_reasons": temporal_resolution_reasons,
            }
            temporal_graph[memory.id] = envelope
            entries.append(
                {
                    "memory": memory.to_dict(),
                    "temporal": envelope,
                }
            )

        current_conflict_sets = _resolve_current_conflicts(
            candidate_by_id=memories_by_id,
            current_ids=current_memory_ids,
            candidate_ids_in_rank_order=[memory.id for memory in memories],
        )
        dropped_current_memory_ids = [
            str(memory_id)
            for conflict_set in current_conflict_sets
            if conflict_set.get("reason") == "lexical-current-conflict"
            and conflict_set.get("resolution_outcome") != "abstained"
            for memory_id in conflict_set.get("dropped_current_ids", [])
            if str(memory_id)
        ]
        abstained_current_memory_ids = [
            str(memory_id)
            for conflict_set in current_conflict_sets
            if conflict_set.get("reason") == "lexical-current-conflict"
            and conflict_set.get("resolution_outcome") == "abstained"
            for memory_id in conflict_set.get("abstained_current_ids", [])
            if str(memory_id)
        ]
        dropped_current_id_set = set(dropped_current_memory_ids)
        abstained_current_id_set = set(abstained_current_memory_ids)
        resolved_current_memory_ids = [
            memory_id
            for memory_id in current_memory_ids
            if memory_id not in dropped_current_id_set and memory_id not in abstained_current_id_set
        ]
        conflict_reasons_by_id: dict[str, list[str]] = {}
        for conflict_set in current_conflict_sets:
            reason = str(conflict_set.get("reason") or "")
            if not reason:
                continue
            for memory_id in conflict_set.get("involved_candidate_ids", []):
                current_memory_id = str(memory_id)
                if current_memory_id not in temporal_graph:
                    continue
                reasons = conflict_reasons_by_id.setdefault(current_memory_id, [])
                if reason not in reasons:
                    reasons.append(reason)
        for memory_id in current_memory_ids:
            envelope = temporal_graph.get(memory_id)
            if envelope is None:
                continue
            if memory_id in abstained_current_id_set:
                envelope["current_resolution"] = "abstained"
            elif memory_id in dropped_current_id_set:
                envelope["current_resolution"] = "dropped"
            else:
                envelope["current_resolution"] = "selected"
            conflict_reasons = conflict_reasons_by_id.get(memory_id, [])
            envelope["current_conflict_reasons"] = conflict_reasons
            if conflict_reasons:
                envelope["temporal_resolution_kind"] = "contradiction"
                envelope["temporal_resolution_reasons"] = list(conflict_reasons)

        abstention = {
            "applied": False,
            "reason": None,
            "abstained_ids": [],
            "conflict_reasons": [],
        }
        if abstained_current_memory_ids:
            abstention = {
                "applied": True,
                "reason": "unresolved-current-conflict",
                "abstained_ids": abstained_current_memory_ids,
                "conflict_reasons": ["lexical-current-conflict"],
            }

        return {
            "entries": entries,
            "temporal_graph": temporal_graph,
            "history_memory_ids": history_memory_ids,
            "current_memory_ids": current_memory_ids,
            "resolved_current_memory_ids": resolved_current_memory_ids,
            "dropped_current_memory_ids": dropped_current_memory_ids,
            "abstained_current_memory_ids": abstained_current_memory_ids,
            "future_memory_ids": future_memory_ids,
            "superseded_memory_ids": superseded_memory_ids,
            "unlearned_memory_ids": unlearned_memory_ids,
            "learned_memory_ids": learned_memory_ids,
            "conflict_sets": current_conflict_sets,
            "abstention": abstention,
        }

    @staticmethod
    def _filter_temporal_projection(
        projection: dict[str, Any],
        *,
        include_abstained_current: bool,
        current_resolution: str,
        learned_only: bool,
        unlearned_only: bool,
        superseded_only: bool,
        future_only: bool,
    ) -> dict[str, Any]:
        filtered = dict(projection)
        if current_resolution in {"abstained", "selected", "dropped"}:
            resolution_id_key = {
                "abstained": "abstained_current_memory_ids",
                "selected": "resolved_current_memory_ids",
                "dropped": "dropped_current_memory_ids",
            }[current_resolution]
            visible_ids = {
                str(memory_id)
                for memory_id in projection.get(resolution_id_key, [])
                if str(memory_id)
            }
            filtered["entries"] = [
                entry
                for entry in projection.get("entries", [])
                if str(entry.get("memory", {}).get("id") or "") in visible_ids
            ]
            filtered["temporal_graph"] = {
                memory_id: envelope
                for memory_id, envelope in projection.get("temporal_graph", {}).items()
                if memory_id in visible_ids
            }
            for key in (
                "history_memory_ids",
                "current_memory_ids",
                "resolved_current_memory_ids",
                "dropped_current_memory_ids",
                "abstained_current_memory_ids",
                "future_memory_ids",
                "superseded_memory_ids",
                "unlearned_memory_ids",
                "learned_memory_ids",
            ):
                filtered[key] = [
                    memory_id
                    for memory_id in projection.get(key, [])
                    if memory_id in visible_ids
                ]
            if current_resolution == "abstained":
                filtered["conflict_sets"] = [
                    conflict_set
                    for conflict_set in projection.get("conflict_sets", [])
                    if str(conflict_set.get("resolution_outcome") or "") == "abstained"
                    and any(
                        str(memory_id) in visible_ids
                        for memory_id in conflict_set.get("abstained_current_ids", [])
                    )
                ]
            elif current_resolution == "dropped":
                filtered["conflict_sets"] = [
                    conflict_set
                    for conflict_set in projection.get("conflict_sets", [])
                    if str(conflict_set.get("resolution_outcome") or "") == "resolved"
                    and any(
                        str(memory_id) in visible_ids
                        for memory_id in conflict_set.get("dropped_current_ids", [])
                    )
                ]
            else:
                filtered["conflict_sets"] = [
                    conflict_set
                    for conflict_set in projection.get("conflict_sets", [])
                    if str(conflict_set.get("resolution_outcome") or "") == "resolved"
                    and str(conflict_set.get("chosen_current_id") or "") in visible_ids
                ]
            if not visible_ids:
                filtered["abstention"] = {
                    "applied": False,
                    "reason": None,
                    "abstained_ids": [],
                    "conflict_reasons": [],
                }
        elif not include_abstained_current:
            hidden_ids = {
                str(memory_id)
                for memory_id in projection.get("abstained_current_memory_ids", [])
                if str(memory_id)
            }
            if hidden_ids:
                filtered["entries"] = [
                    entry
                    for entry in projection.get("entries", [])
                    if str(entry.get("memory", {}).get("id") or "") not in hidden_ids
                ]
                filtered["temporal_graph"] = {
                    memory_id: envelope
                    for memory_id, envelope in projection.get("temporal_graph", {}).items()
                    if memory_id not in hidden_ids
                }
                for key in (
                    "history_memory_ids",
                    "current_memory_ids",
                    "resolved_current_memory_ids",
                    "dropped_current_memory_ids",
                    "future_memory_ids",
                    "superseded_memory_ids",
                    "unlearned_memory_ids",
                    "learned_memory_ids",
                ):
                    filtered[key] = [
                        memory_id
                        for memory_id in projection.get(key, [])
                        if memory_id not in hidden_ids
                    ]

        if learned_only:
            visible_ids = {
                str(memory_id)
                for memory_id in filtered.get("learned_memory_ids", [])
                if str(memory_id)
            }
            filtered["entries"] = [
                entry
                for entry in filtered.get("entries", [])
                if str(entry.get("memory", {}).get("id") or "") in visible_ids
            ]
            filtered["temporal_graph"] = {
                memory_id: envelope
                for memory_id, envelope in filtered.get("temporal_graph", {}).items()
                if memory_id in visible_ids
            }
            filtered["history_memory_ids"] = [
                memory_id
                for memory_id in filtered.get("history_memory_ids", [])
                if memory_id in visible_ids
            ]
            filtered["current_memory_ids"] = []
            filtered["resolved_current_memory_ids"] = []
            filtered["dropped_current_memory_ids"] = []
            filtered["abstained_current_memory_ids"] = []
            filtered["future_memory_ids"] = []
            filtered["superseded_memory_ids"] = []
            filtered["unlearned_memory_ids"] = []
            filtered["learned_memory_ids"] = [
                memory_id
                for memory_id in filtered.get("learned_memory_ids", [])
                if memory_id in visible_ids
            ]
            filtered["conflict_sets"] = []
            filtered["abstention"] = {
                "applied": False,
                "reason": None,
                "abstained_ids": [],
                "conflict_reasons": [],
            }
        if unlearned_only:
            visible_ids = {
                str(memory_id)
                for memory_id in filtered.get("unlearned_memory_ids", [])
                if str(memory_id)
            }
            filtered["entries"] = [
                entry
                for entry in filtered.get("entries", [])
                if str(entry.get("memory", {}).get("id") or "") in visible_ids
            ]
            filtered["temporal_graph"] = {
                memory_id: envelope
                for memory_id, envelope in filtered.get("temporal_graph", {}).items()
                if memory_id in visible_ids
            }
            filtered["history_memory_ids"] = [
                memory_id
                for memory_id in filtered.get("history_memory_ids", [])
                if memory_id in visible_ids
            ]
            filtered["current_memory_ids"] = []
            filtered["resolved_current_memory_ids"] = []
            filtered["dropped_current_memory_ids"] = []
            filtered["abstained_current_memory_ids"] = []
            filtered["future_memory_ids"] = []
            filtered["superseded_memory_ids"] = []
            filtered["unlearned_memory_ids"] = [
                memory_id
                for memory_id in filtered.get("unlearned_memory_ids", [])
                if memory_id in visible_ids
            ]
            filtered["learned_memory_ids"] = []
            filtered["conflict_sets"] = []
            filtered["abstention"] = {
                "applied": False,
                "reason": None,
                "abstained_ids": [],
                "conflict_reasons": [],
            }
        if superseded_only:
            visible_ids = {
                str(memory_id)
                for memory_id in filtered.get("superseded_memory_ids", [])
                if str(memory_id)
            }
            filtered["entries"] = [
                entry
                for entry in filtered.get("entries", [])
                if str(entry.get("memory", {}).get("id") or "") in visible_ids
            ]
            filtered["temporal_graph"] = {
                memory_id: envelope
                for memory_id, envelope in filtered.get("temporal_graph", {}).items()
                if memory_id in visible_ids
            }
            filtered["history_memory_ids"] = [
                memory_id
                for memory_id in filtered.get("history_memory_ids", [])
                if memory_id in visible_ids
            ]
            filtered["current_memory_ids"] = []
            filtered["resolved_current_memory_ids"] = []
            filtered["dropped_current_memory_ids"] = []
            filtered["abstained_current_memory_ids"] = []
            filtered["future_memory_ids"] = []
            filtered["superseded_memory_ids"] = [
                memory_id
                for memory_id in filtered.get("superseded_memory_ids", [])
                if memory_id in visible_ids
            ]
            filtered["unlearned_memory_ids"] = []
            filtered["learned_memory_ids"] = []
            filtered["conflict_sets"] = []
            filtered["abstention"] = {
                "applied": False,
                "reason": None,
                "abstained_ids": [],
                "conflict_reasons": [],
            }
        if future_only:
            visible_ids = {
                str(memory_id)
                for memory_id in filtered.get("future_memory_ids", [])
                if str(memory_id)
            }
            filtered["entries"] = [
                entry
                for entry in filtered.get("entries", [])
                if str(entry.get("memory", {}).get("id") or "") in visible_ids
            ]
            filtered["temporal_graph"] = {
                memory_id: envelope
                for memory_id, envelope in filtered.get("temporal_graph", {}).items()
                if memory_id in visible_ids
            }
            filtered["history_memory_ids"] = []
            filtered["current_memory_ids"] = []
            filtered["resolved_current_memory_ids"] = []
            filtered["dropped_current_memory_ids"] = []
            filtered["abstained_current_memory_ids"] = []
            filtered["future_memory_ids"] = [
                memory_id
                for memory_id in filtered.get("future_memory_ids", [])
                if memory_id in visible_ids
            ]
            filtered["superseded_memory_ids"] = []
            filtered["unlearned_memory_ids"] = []
            filtered["learned_memory_ids"] = []
            filtered["conflict_sets"] = []
            filtered["abstention"] = {
                "applied": False,
                "reason": None,
                "abstained_ids": [],
                "conflict_reasons": [],
            }
        return filtered

    @staticmethod
    def _add_temporal_projection_subset_graphs(projection: dict[str, Any]) -> dict[str, Any]:
        filtered = dict(projection)
        temporal_graph = filtered.get("temporal_graph", {})
        subset_specs = (
            ("history_temporal_graph", "history_memory_ids"),
            ("current_temporal_graph", "current_memory_ids"),
            ("future_temporal_graph", "future_memory_ids"),
            ("superseded_temporal_graph", "superseded_memory_ids"),
            ("unlearned_temporal_graph", "unlearned_memory_ids"),
            ("learned_temporal_graph", "learned_memory_ids"),
            ("selected_temporal_graph", "resolved_current_memory_ids"),
            ("abstained_temporal_graph", "abstained_current_memory_ids"),
            ("dropped_current_temporal_graph", "dropped_current_memory_ids"),
        )
        for subset_key, ids_key in subset_specs:
            filtered[subset_key] = _select_temporal_graph_subset(
                temporal_graph,
                [
                    str(memory_id)
                    for memory_id in filtered.get(ids_key, [])
                    if str(memory_id)
                ],
            )
        return filtered

    def query_at(
        self,
        timestamp: str,
        *,
        scope: str | None = None,
        search_query: str | None = None,
        include_abstained_current: bool = True,
        current_resolution: str = "all",
        learned_only: bool = False,
        unlearned_only: bool = False,
        superseded_only: bool = False,
        future_only: bool = False,
    ) -> dict[str, Any]:
        self.init()
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", timestamp):
            raise ValueError("query_at timestamp must be in ISO 8601 UTC form like 2024-01-01T00:00:00Z")
        if current_resolution not in {"all", "abstained", "selected", "dropped"}:
            raise ValueError("query_at current_resolution must be 'all', 'abstained', 'selected', or 'dropped'")
        if current_resolution == "abstained" and not include_abstained_current:
            raise ValueError("query_at current_resolution='abstained' requires include_abstained_current=True")
        if learned_only and current_resolution != "all":
            raise ValueError("query_at learned_only=True requires current_resolution='all'")
        if unlearned_only and current_resolution != "all":
            raise ValueError("query_at unlearned_only=True requires current_resolution='all'")
        if superseded_only and current_resolution != "all":
            raise ValueError("query_at superseded_only=True requires current_resolution='all'")
        if future_only and current_resolution != "all":
            raise ValueError("query_at future_only=True requires current_resolution='all'")
        if learned_only and unlearned_only:
            raise ValueError("query_at learned_only=True cannot be combined with unlearned_only=True")
        if learned_only and superseded_only:
            raise ValueError("query_at learned_only=True cannot be combined with superseded_only=True")
        if learned_only and future_only:
            raise ValueError("query_at learned_only=True cannot be combined with future_only=True")
        if unlearned_only and superseded_only:
            raise ValueError("query_at superseded_only=True cannot be combined with unlearned_only=True")
        if future_only and unlearned_only:
            raise ValueError("query_at future_only=True cannot be combined with unlearned_only=True")
        if future_only and superseded_only:
            raise ValueError("query_at future_only=True cannot be combined with superseded_only=True")

        params: list[Any] = []
        where_sql = ""
        if scope:
            where_sql = "WHERE (scope = ? OR scope = 'global')"
            params.append(scope)
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM memories
            {where_sql}
            ORDER BY created_at ASC, updated_at ASC, id ASC
            """,
            params,
        ).fetchall()
        memories = [MemoryRecord.from_row(row) for row in rows]
        memories_by_id = {memory.id: memory for memory in memories}

        if search_query:
            search_terms = query_terms(search_query)
            matched_ids = {
                memory.id
                for memory in memories
                if all(
                    term in _query_tokens(f"{memory.content} {' '.join(memory.labels)}")
                    for term in search_terms
                )
            } if search_terms else {memory.id for memory in memories}
            expanded_ids = set(matched_ids)
            changed = True
            while changed:
                changed = False
                for memory in memories:
                    if memory.id in expanded_ids:
                        for parent_id in memory.parents:
                            if parent_id in memories_by_id and parent_id not in expanded_ids:
                                expanded_ids.add(parent_id)
                                changed = True
                        continue
                    if any(parent_id in expanded_ids for parent_id in memory.parents):
                        expanded_ids.add(memory.id)
                        changed = True
            memories = [memory for memory in memories if memory.id in expanded_ids]

        base_projection = self._project_temporal_state(memories, timestamp=timestamp)
        projection = self._filter_temporal_projection(
            base_projection,
            include_abstained_current=include_abstained_current,
            current_resolution=current_resolution,
            learned_only=learned_only,
            unlearned_only=unlearned_only,
            superseded_only=superseded_only,
            future_only=future_only,
        )
        if (
            search_query
            and current_resolution == "selected"
            and not learned_only
            and not unlearned_only
            and not superseded_only
            and not future_only
            and projection.get("resolved_current_memory_ids")
        ):
            query_lookup = _subject_lookup_query_plan(search_query, query_terms(search_query))
            candidate_ids_in_rank_order = [memory.id for memory in memories]
            temporal_state_by_id = {
                memory_id: str(envelope.get("temporal_state") or "")
                for memory_id, envelope in base_projection.get("temporal_graph", {}).items()
            }
            selection = _temporal_selection_metadata(
                query_terms=query_terms(search_query),
                query_lookup=query_lookup,
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=candidate_ids_in_rank_order,
                temporal_state_by_id=temporal_state_by_id,
                current_conflict_sets=base_projection.get("conflict_sets", []),
            )
            selection = {
                **selection,
                "selected_current_ids": [
                    memory_id
                    for memory_id in selection.get("selected_ids", [])
                    if temporal_state_by_id.get(memory_id) == "current"
                ],
            }
            candidate_meta = {
                memory.id: {"memory_id": memory.id, "rank": index}
                for index, memory in enumerate(memories, start=1)
            }
            projection["selection_strategy"] = selection["selection_strategy"]
            projection["selection_reason"] = selection["selection_reason"]
            projection["selected_ids"] = [
                memory_id
                for memory_id in selection.get("selected_ids", [])
                if memory_id in projection.get("temporal_graph", {})
            ]
            projection["current_ordering"] = _current_only_ordering_metadata(
                retrieval={},
                selection=selection,
                candidate_meta=candidate_meta,
                current_ids=list(base_projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
            )
            projection["history_ordering"] = _history_ordering_metadata(
                selection=selection,
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=candidate_ids_in_rank_order,
                current_ids=list(base_projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
                query_lookup=query_lookup,
            )
        elif (
            current_resolution == "selected"
            and not learned_only
            and not unlearned_only
            and not superseded_only
            and not future_only
            and projection.get("resolved_current_memory_ids")
        ):
            selection = {
                "selection_strategy": "current_only_v1",
                "selection_reason": "default-current-only",
                "selected_ids": list(projection.get("resolved_current_memory_ids", [])),
                "selected_current_ids": list(projection.get("resolved_current_memory_ids", [])),
            }
            candidate_ids_in_rank_order = [memory.id for memory in memories]
            candidate_meta = {
                memory.id: {"memory_id": memory.id, "rank": index}
                for index, memory in enumerate(memories, start=1)
            }
            projection["selection_strategy"] = selection["selection_strategy"]
            projection["selection_reason"] = selection["selection_reason"]
            projection["selected_ids"] = list(selection["selected_ids"])
            projection["current_ordering"] = _current_only_ordering_metadata(
                retrieval={},
                selection=selection,
                candidate_meta=candidate_meta,
                current_ids=list(base_projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
            )
            projection["history_ordering"] = _history_ordering_metadata(
                selection=selection,
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=candidate_ids_in_rank_order,
                current_ids=list(base_projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
                query_lookup=None,
            )
        elif learned_only:
            projection["selection_strategy"] = "learned_only_v1"
            projection["selection_reason"] = "explicit-learned-only-filter"
            projection["selected_ids"] = list(projection.get("learned_memory_ids", []))
            projection["history_ordering"] = _history_ordering_metadata(
                selection={
                    "selection_strategy": "historical_preferred_v1",
                    "selection_reason": "explicit-learned-only-filter",
                    "selected_ids": list(projection.get("history_memory_ids", [])),
                },
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=[memory.id for memory in memories],
                current_ids=list(base_projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
                query_lookup=None,
            )
        elif current_resolution == "abstained":
            selection = {
                "selection_strategy": "abstained_only_v1",
                "selection_reason": "explicit-abstained-current-filter",
                "selected_ids": list(projection.get("abstained_current_memory_ids", [])),
                "selected_current_ids": list(projection.get("abstained_current_memory_ids", [])),
            }
            candidate_ids_in_rank_order = [memory.id for memory in memories]
            query_lookup = (
                _subject_lookup_query_plan(search_query, query_terms(search_query))
                if search_query
                else None
            )
            candidate_meta = {
                memory.id: {"memory_id": memory.id, "rank": index}
                for index, memory in enumerate(memories, start=1)
            }
            projection["selection_strategy"] = selection["selection_strategy"]
            projection["selection_reason"] = selection["selection_reason"]
            projection["selected_ids"] = list(selection["selected_ids"])
            projection["current_ordering"] = _current_only_ordering_metadata(
                retrieval={},
                selection=selection,
                candidate_meta=candidate_meta,
                current_ids=list(projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
            )
            projection["history_ordering"] = _history_ordering_metadata(
                selection=selection,
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=candidate_ids_in_rank_order,
                current_ids=list(projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
                query_lookup=query_lookup,
            )
        elif current_resolution == "dropped":
            selection = {
                "selection_strategy": "dropped_only_v1",
                "selection_reason": "explicit-dropped-current-filter",
                "selected_ids": list(projection.get("dropped_current_memory_ids", [])),
                "selected_current_ids": list(projection.get("dropped_current_memory_ids", [])),
            }
            ordering_current_ids = (
                list(base_projection.get("current_memory_ids", []))
                if selection["selected_ids"]
                else list(projection.get("current_memory_ids", []))
            )
            candidate_ids_in_rank_order = [memory.id for memory in memories]
            query_lookup = (
                _subject_lookup_query_plan(search_query, query_terms(search_query))
                if search_query
                else None
            )
            candidate_meta = {
                memory.id: {"memory_id": memory.id, "rank": index}
                for index, memory in enumerate(memories, start=1)
            }
            projection["selection_strategy"] = selection["selection_strategy"]
            projection["selection_reason"] = selection["selection_reason"]
            projection["selected_ids"] = list(selection["selected_ids"])
            projection["current_ordering"] = _current_only_ordering_metadata(
                retrieval={},
                selection=selection,
                candidate_meta=candidate_meta,
                current_ids=ordering_current_ids,
                conflict_sets=list(base_projection.get("conflict_sets", [])),
            )
            projection["history_ordering"] = _history_ordering_metadata(
                selection=selection,
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=candidate_ids_in_rank_order,
                current_ids=ordering_current_ids,
                conflict_sets=list(base_projection.get("conflict_sets", [])),
                query_lookup=query_lookup,
            )
        elif unlearned_only:
            projection["selection_strategy"] = "unlearned_only_v1"
            projection["selection_reason"] = "explicit-unlearned-only-filter"
            projection["selected_ids"] = list(projection.get("unlearned_memory_ids", []))
            projection["history_ordering"] = _history_ordering_metadata(
                selection={
                    "selection_strategy": "historical_preferred_v1",
                    "selection_reason": "explicit-unlearned-only-filter",
                    "selected_ids": list(projection.get("history_memory_ids", [])),
                },
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=[memory.id for memory in memories],
                current_ids=list(base_projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
                query_lookup=None,
            )
        elif superseded_only:
            projection["selection_strategy"] = "superseded_only_v1"
            projection["selection_reason"] = "explicit-superseded-only-filter"
            projection["selected_ids"] = list(projection.get("superseded_memory_ids", []))
            projection["history_ordering"] = _history_ordering_metadata(
                selection={
                    "selection_strategy": "historical_preferred_v1",
                    "selection_reason": "explicit-superseded-only-filter",
                    "selected_ids": list(projection.get("history_memory_ids", [])),
                },
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=[memory.id for memory in memories],
                current_ids=list(base_projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
                query_lookup=None,
            )
        elif future_only:
            projection["selection_strategy"] = "future_only_v1"
            projection["selection_reason"] = "explicit-future-only-filter"
            projection["selected_ids"] = list(projection.get("future_memory_ids", []))
            projection["history_ordering"] = _history_ordering_metadata(
                selection={
                    "selection_strategy": "historical_preferred_v1",
                    "selection_reason": "explicit-future-only-filter",
                    "selected_ids": list(projection.get("future_memory_ids", [])),
                },
                candidate_by_id={memory.id: memory for memory in memories},
                candidate_ids_in_rank_order=[memory.id for memory in memories],
                current_ids=list(base_projection.get("current_memory_ids", [])),
                conflict_sets=list(base_projection.get("conflict_sets", [])),
                query_lookup=None,
            )
        current_history_metadata_filter: str | None = None
        if current_resolution in {"selected", "abstained", "dropped"}:
            current_history_metadata_filter = f"current_resolution:{current_resolution}"
        elif learned_only:
            current_history_metadata_filter = "learned_only"
        elif unlearned_only:
            current_history_metadata_filter = "unlearned_only"
        elif superseded_only:
            current_history_metadata_filter = "superseded_only"
        elif future_only:
            current_history_metadata_filter = "future_only"
        elif (
            not include_abstained_current
            and base_projection.get("abstained_current_memory_ids")
        ):
            current_history_metadata_filter = "include_abstained_current:false"
        elif (
            current_resolution == "all"
            and (
                projection.get("history_memory_ids")
                or projection.get("current_memory_ids")
            )
        ):
            current_history_metadata_filter = "current_resolution:all"
        if current_history_metadata_filter:
            base_history_ids = [
                str(memory_id)
                for memory_id in base_projection.get("history_memory_ids", [])
                if str(memory_id)
            ]
            base_current_ids = [
                str(memory_id)
                for memory_id in base_projection.get("current_memory_ids", [])
                if str(memory_id)
            ]
            included_history_ids = [
                str(memory_id)
                for memory_id in projection.get("history_memory_ids", [])
                if str(memory_id)
            ]
            included_current_ids = [
                str(memory_id)
                for memory_id in projection.get("current_memory_ids", [])
                if str(memory_id)
            ]
            included_history_id_set = set(included_history_ids)
            included_current_id_set = set(included_current_ids)
            projection["current_history_receipt_metadata"] = {
                "filter": current_history_metadata_filter,
                "base_history_memory_ids": base_history_ids,
                "base_current_memory_ids": base_current_ids,
                "included_history_memory_ids": included_history_ids,
                "included_current_memory_ids": included_current_ids,
                "omitted_history_memory_ids": [
                    memory_id for memory_id in base_history_ids if memory_id not in included_history_id_set
                ],
                "omitted_current_memory_ids": [
                    memory_id for memory_id in base_current_ids if memory_id not in included_current_id_set
                ],
            }
        projection = self._add_temporal_projection_subset_graphs(projection)
        return {
            "schema": TEMPORAL_QUERY_SCHEMA,
            "query_at": timestamp,
            "scope": scope,
            "search_query": search_query,
            "include_abstained_current": include_abstained_current,
            "current_resolution": current_resolution,
            "learned_only": learned_only,
            "unlearned_only": unlearned_only,
            "superseded_only": superseded_only,
            "future_only": future_only,
            **projection,
        }

    def memory_leaf(self, memory: MemoryRecord) -> dict[str, Any]:
        material = {
            "memory_id": memory.id,
            "type": memory.type,
            "content_hash": memory.content_hash,
            "scope": memory.scope,
            "source_kind": memory.source_kind,
            "trust": memory.trust,
            "authority": memory.authority,
            "status": memory.status,
            "parents": memory.parents,
            "labels": memory.labels,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "expires_at": memory.expires_at,
        }
        return {
            "schema": "zerker.memory_leaf.v1",
            "hash_alg": HASH_ALG,
            "memory_id": memory.id,
            "content_hash": memory.content_hash,
            "material": material,
            "leaf_hash": sha256_text(stable_json(material)),
        }

    def memory_tree(self, memories: list[MemoryRecord], *, scope: str = "selected") -> dict[str, Any]:
        leaves = [self.memory_leaf(memory) for memory in sorted(memories, key=lambda item: item.id)]
        leaf_hashes = [leaf["leaf_hash"] for leaf in leaves]
        root = merkle_root(leaf_hashes)
        proofs = {
            leaf["memory_id"]: {
                "memory_id": leaf["memory_id"],
                "leaf_hash": leaf["leaf_hash"],
                "root": root,
                "leaf_index": index,
                "leaf_count": len(leaves),
                "proof": merkle_proof(leaf_hashes, index),
            }
            for index, leaf in enumerate(leaves)
        }
        return {
            "schema": MEMORY_TREE_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "scope": scope,
            "root": root,
            "leaf_count": len(leaves),
            "leaves": leaves,
            "proofs": proofs,
        }

    def list_receipts(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self.init()
        rows = self.conn.execute(
            """
            SELECT action_id, agent_id, task, risk, merkle_root, created_at
            FROM receipts
            ORDER BY created_at DESC, action_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, Any]:
        self.init()
        memory_status = {
            row["status"]: row["count"]
            for row in self.conn.execute("SELECT status, COUNT(*) AS count FROM memories GROUP BY status").fetchall()
        }
        memory_types = {
            row["type"]: row["count"]
            for row in self.conn.execute("SELECT type, COUNT(*) AS count FROM memories GROUP BY type").fetchall()
        }
        receipt_count = self.conn.execute("SELECT COUNT(*) AS count FROM receipts").fetchone()["count"]
        write_receipt_count = self.conn.execute("SELECT COUNT(*) AS count FROM memory_write_receipts").fetchone()["count"]
        event_count = self.conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
        active_memory_tree = self.memory_tree(self.list_memories(status="active", limit=10_000), scope="active")
        return {
            "db_path": str(self.db_path),
            "merkle_root": self.current_merkle_root(),
            "memory_merkle_root": active_memory_tree["root"],
            "memory_status": memory_status,
            "memory_types": memory_types,
            "memory_count": sum(memory_status.values()),
            "receipt_count": receipt_count,
            "write_receipt_count": write_receipt_count,
            "event_count": event_count,
        }

    def _exists(self, memory_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM memories WHERE id = ? LIMIT 1", (memory_id,)).fetchone()
        return row is not None

    def _has_write_receipt(self, memory_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM memory_write_receipts WHERE memory_id = ? LIMIT 1",
            (memory_id,),
        ).fetchone()
        return row is not None

    def search(self, query: str, *, scope: str | None = None, include_quarantined: bool = False) -> list[MemoryRecord]:
        return self.search_with_meta(query, scope=scope, include_quarantined=include_quarantined)["memories"]

    def _semantic_rescue_rows(
        self,
        query: str,
        *,
        scope: str | None,
        include_quarantined: bool,
        limit: int,
        required_terms: list[str] | None = None,
        activation_reason: str = "no-lexical-match",
        confidence_profile: dict[str, Any] | None = None,
        effective_query: str | None = None,
        effective_query_terms: list[str] | None = None,
    ) -> dict[str, Any]:
        query_semantic_terms = semantic_query_terms(query)
        semantic_terms = _ordered_unique(
            [str(term) for term in (effective_query_terms or query_semantic_terms) if str(term)]
        )
        required_terms = [term for term in (required_terms or []) if term]
        confidence_profile = dict(confidence_profile or {})
        effective_query = str(effective_query or query)
        metadata = {
            "schema": SEMANTIC_RESCUE_SCHEMA,
            "applied": False,
            "reason": "no-query-terms",
            "query": query,
            "query_terms": query_semantic_terms,
            "effective_query": effective_query,
            "effective_query_terms": semantic_terms,
            "required_terms": required_terms,
            "model_id": PSEUDO_EMBEDDING_MODEL_ID,
            "candidate_pool_size": 0,
            "matched_candidate_count": 0,
            "selected_candidate_ids": [],
            "selected_candidates": [],
            "morphology": {
                "strategy": "conservative_regular_inflection_v1",
                "minimum_exact_overlap": 2,
                "minimum_gain": 2,
                "selected_candidate_ids": [],
            },
            "confidence": {
                "enabled": bool(confidence_profile.get("enabled")),
                "profile": confidence_profile.get("profile"),
                "minimum_score": confidence_profile.get("minimum_score"),
                "require_full_query_overlap": bool(confidence_profile.get("require_full_query_overlap")),
                "query_term_count": len(semantic_terms),
                "top_score": None,
                "top_term_overlap": 0,
                "top_overlap_ratio": 0.0,
                "passed": None,
                "reason": None,
            },
            "abstention": {
                "applied": False,
                "reason": None,
                "dropped_candidate_ids": [],
            },
        }
        ignored_query_terms = [str(term) for term in confidence_profile.get("ignored_query_terms", []) if str(term)]
        if ignored_query_terms:
            metadata["ignored_query_terms"] = ignored_query_terms
        if not semantic_terms or limit <= 0:
            return {"rows": [], "metadata": metadata}

        status_sql = "m.status IN ('active')"
        if include_quarantined:
            status_sql = "m.status IN ('active', 'quarantined', 'proposed')"
        scope_sql = ""
        params: list[Any] = []
        if scope:
            scope_sql = "AND (m.scope = ? OR m.scope = 'global')"
            params.append(scope)
        rows = self.conn.execute(
            f"""
            SELECT m.*,
                   COALESCE((SELECT MAX(e.seq) FROM events e WHERE e.memory_id = m.id), 0) AS observation_seq
            FROM memories m
            WHERE {status_sql}
              {scope_sql}
            """,
            params,
        ).fetchall()
        metadata["candidate_pool_size"] = len(rows)
        query_vector = pseudo_embedding(" ".join(semantic_terms))
        scored = []
        for row in rows:
            memory = MemoryRecord.from_row(row)
            haystack = f"{memory.content} {' '.join(memory.labels)}".strip()
            candidate_terms = semantic_query_terms(haystack)
            if required_terms and not set(required_terms).issubset(candidate_terms):
                continue
            exact_overlap = len(set(semantic_terms).intersection(candidate_terms))
            if not exact_overlap:
                continue
            inflectional_overlap = _inflectional_term_overlap(semantic_terms, candidate_terms)
            morphology_applied = exact_overlap >= 2 and inflectional_overlap - exact_overlap >= 2
            overlap = inflectional_overlap if morphology_applied else exact_overlap
            similarity = cosine_similarity(query_vector, pseudo_embedding(haystack))
            if similarity <= 0.0:
                continue
            scored.append(
                (
                    row,
                    similarity,
                    overlap,
                    authority_rank(memory.authority),
                    float(memory.trust),
                    memory.id,
                    exact_overlap,
                    inflectional_overlap,
                    morphology_applied,
                )
            )
        scored.sort(key=lambda item: (-item[2], -item[1], -item[3], -item[4], item[5]))
        metadata["matched_candidate_count"] = len(scored)
        selected = scored[:limit]
        if not selected:
            metadata["reason"] = "no-semantic-overlap"
            metadata["confidence"]["passed"] = False if confidence_profile.get("enabled") else None
            metadata["confidence"]["reason"] = "no-semantic-overlap" if confidence_profile.get("enabled") else None
            return {"rows": [], "metadata": metadata}
        top_row, top_score, top_overlap, *_ = selected[0]
        top_overlap_ratio = round(top_overlap / len(semantic_terms), 6) if semantic_terms else 0.0
        metadata["confidence"]["top_score"] = round(top_score, 6)
        metadata["confidence"]["top_term_overlap"] = top_overlap
        metadata["confidence"]["top_overlap_ratio"] = top_overlap_ratio
        if confidence_profile.get("enabled"):
            minimum_score = float(confidence_profile.get("minimum_score", 0.0))
            require_full_query_overlap = bool(confidence_profile.get("require_full_query_overlap"))
            score_passed = top_score >= minimum_score
            overlap_passed = (top_overlap >= len(semantic_terms)) if require_full_query_overlap else top_overlap > 0
            passed = score_passed and overlap_passed
            metadata["confidence"]["passed"] = passed
            if not overlap_passed:
                metadata["confidence"]["reason"] = "query-overlap-below-threshold"
            elif not score_passed:
                metadata["confidence"]["reason"] = "score-below-threshold"
            else:
                metadata["confidence"]["reason"] = "passed"
            if not passed:
                metadata["reason"] = "low-confidence-declarative-match"
                metadata["abstention"] = {
                    "applied": True,
                    "reason": "low-confidence-declarative-match",
                    "dropped_candidate_ids": [row["id"] for row, *_ in selected],
                }
                return {"rows": [], "metadata": metadata}
            selected = [
                item
                for item in selected
                if item[1] >= minimum_score and ((item[2] >= len(semantic_terms)) if require_full_query_overlap else item[2] > 0)
            ]
            if not selected:
                metadata["reason"] = "low-confidence-declarative-match"
                metadata["confidence"]["passed"] = False
                metadata["confidence"]["reason"] = "no-candidates-cleared-threshold"
                metadata["abstention"] = {
                    "applied": True,
                    "reason": "low-confidence-declarative-match",
                    "dropped_candidate_ids": [row["id"] for row, *_ in scored[:limit]],
                }
                return {"rows": [], "metadata": metadata}
        metadata["applied"] = True
        metadata["reason"] = activation_reason
        metadata["selected_candidate_ids"] = [row["id"] for row, *_ in selected]
        metadata["selected_candidates"] = [
            {
                "memory_id": row["id"],
                "score": round(similarity, 6),
                "term_overlap": overlap,
                "exact_term_overlap": exact_overlap,
                "inflectional_term_overlap": inflectional_overlap,
                "morphology_gain": inflectional_overlap - exact_overlap,
                "morphology_applied": morphology_applied,
            }
            for row, similarity, overlap, _, _, _, exact_overlap, inflectional_overlap, morphology_applied in selected
        ]
        metadata["morphology"]["selected_candidate_ids"] = [
            row["id"]
            for row, _, _, _, _, _, _, _, morphology_applied in selected
            if morphology_applied
        ]
        if confidence_profile.get("enabled"):
            metadata["confidence"]["passed"] = True
            metadata["confidence"]["reason"] = "passed"
        return {"rows": [row for row, *_ in selected], "metadata": metadata}

    def _history_observation_support_rows(
        self,
        *,
        query: str,
        raw_tokens: list[str],
        raw_terms: list[str],
        query_lookup: dict[str, Any],
        rows: list[sqlite3.Row],
        search_mode: str,
        scope: str | None,
        include_quarantined: bool,
        limit: int,
    ) -> tuple[list[sqlite3.Row], dict[str, Any]]:
        metadata = {
            "applied": False,
            "reason": "not-needed",
            "trigger_terms": [],
            "anchor_candidate_ids": [],
            "ordered_anchor_candidate_ids": [],
            "anchor_observation_seq": None,
            "anchor_observation_seqs": [],
            "selected_anchor_candidate_ids": [],
            "excluded_anchor_candidate_ids": [],
            "anchor_selection_strategy": None,
            "considered_candidate_ids": [],
            "scored_candidates": [],
            "ordered_support_candidate_ids": [],
            "selected_support_candidate_ids": [],
            "selection_strategy": None,
            "selection_order": None,
        }
        if (
            limit <= 1
            or scope is None
            or not rows
            or search_mode not in {"fallback", "semantic"}
            or not raw_tokens
            or raw_tokens[0] != "who"
            or "before" not in raw_terms
            or str(query_lookup.get("lookup_basis") or "") != "question-wrapper"
        ):
            return rows, metadata

        anchor_rows = []
        for row in rows:
            anchor_terms = set(query_terms(str(row["content"])))
            trigger_terms = sorted(anchor_terms.intersection(CHRONOLOGY_QUERY_MUTATION_TERMS))
            if trigger_terms:
                anchor_rows.append((row, trigger_terms))
        if not anchor_rows:
            metadata["reason"] = "no-anchor-candidates"
            return rows, metadata

        anchor_rows_by_id = {
            str(row["id"]): {
                "memory_id": str(row["id"]),
                "row": row,
                "observation_seq": int(row["observation_seq"]) if "observation_seq" in row.keys() else 0,
                "trigger_terms": trigger_terms,
            }
            for row, trigger_terms in anchor_rows
        }
        ordered_anchor_items = sorted(
            anchor_rows_by_id.values(),
            key=lambda item: (
                int(item["observation_seq"]),
                str(item["memory_id"]),
            ),
        )
        anchor_ids = [str(item["memory_id"]) for item in ordered_anchor_items]
        anchor_seq = max(item["observation_seq"] for item in anchor_rows_by_id.values())
        if anchor_seq <= 1:
            metadata["reason"] = "anchor-has-no-earlier-observations"
            return rows, metadata
        selected_anchor_ids = list(anchor_ids)
        if len(ordered_anchor_items) > 2:
            earliest_anchor = ordered_anchor_items[0]
            strongest_anchor = max(
                ordered_anchor_items,
                key=lambda item: (
                    len(item["trigger_terms"]),
                    int(item["observation_seq"]),
                    str(item["memory_id"]),
                ),
            )
            selected_anchor_ids = [str(earliest_anchor["memory_id"])]
            strongest_anchor_id = str(strongest_anchor["memory_id"])
            if strongest_anchor_id not in selected_anchor_ids:
                selected_anchor_ids.append(strongest_anchor_id)
            elif len(ordered_anchor_items) > 1:
                fallback_anchor = max(
                    ordered_anchor_items[1:],
                    key=lambda item: (
                        int(item["observation_seq"]),
                        str(item["memory_id"]),
                    ),
                )
                selected_anchor_ids.append(str(fallback_anchor["memory_id"]))
            selected_anchor_ids = [
                str(item["memory_id"])
                for item in ordered_anchor_items
                if str(item["memory_id"]) in set(selected_anchor_ids)
            ]
        selected_anchor_id_set = set(selected_anchor_ids)
        status_sql = "m.status IN ('active')"
        if include_quarantined:
            status_sql = "m.status IN ('active', 'quarantined', 'proposed')"
        anchor_placeholders = ",".join("?" for _ in anchor_ids)
        candidate_rows = self.conn.execute(
            f"""
            SELECT m.*,
                   COALESCE((SELECT MAX(e.seq) FROM events e WHERE e.memory_id = m.id), 0) AS observation_seq
            FROM memories m
            WHERE {status_sql}
              AND (m.scope = ? OR m.scope = 'global')
              AND m.id NOT IN ({anchor_placeholders})
              AND COALESCE((SELECT MAX(e.seq) FROM events e WHERE e.memory_id = m.id), 0) < ?
            ORDER BY observation_seq ASC, m.id ASC
            LIMIT {max(1, limit - len(rows) + 2)}
            """,
            (scope, *anchor_ids, anchor_seq),
        ).fetchall()
        metadata["trigger_terms"] = sorted(
            {
                term
                for item in anchor_rows_by_id.values()
                for term in item["trigger_terms"]
            }
        )
        metadata["anchor_candidate_ids"] = anchor_ids
        metadata["ordered_anchor_candidate_ids"] = list(anchor_ids)
        metadata["anchor_observation_seq"] = anchor_seq
        metadata["anchor_observation_seqs"] = [
            {
                "memory_id": anchor_rows_by_id[memory_id]["memory_id"],
                "observation_seq": anchor_rows_by_id[memory_id]["observation_seq"],
                "trigger_terms": anchor_rows_by_id[memory_id]["trigger_terms"],
            }
            for memory_id in anchor_ids
        ]
        metadata["selected_anchor_candidate_ids"] = list(selected_anchor_ids)
        metadata["excluded_anchor_candidate_ids"] = [
            memory_id for memory_id in anchor_ids if memory_id not in selected_anchor_id_set
        ]
        metadata["anchor_selection_strategy"] = (
            "observation_anchor_earliest_plus_strongest_v1"
            if len(anchor_ids) > len(selected_anchor_ids)
            else "all_anchor_candidates_retained_v1"
        )
        metadata["considered_candidate_ids"] = [str(row["id"]) for row in candidate_rows]
        if not candidate_rows:
            metadata["reason"] = "no-earlier-observation-candidates"
            return rows, metadata

        query_action_requested = bool(
            set(raw_terms).intersection(HISTORY_OBSERVATION_SUPPORT_QUERY_ACTION_TERMS)
        )
        scored_candidates: list[tuple[tuple[int, int, int, int, int], sqlite3.Row]] = []
        for row in candidate_rows:
            candidate_content = str(row["content"] or "")
            candidate_terms = set(query_terms(str(row["content"])))
            earliest_markers = len(candidate_terms.intersection(HISTORY_OBSERVATION_SUPPORT_EARLIEST_MARKERS))
            history_markers = len(candidate_terms.intersection(TEMPORAL_HISTORY_TERMS))
            later_markers = len(candidate_terms.intersection(HISTORY_OBSERVATION_SUPPORT_LATER_MARKERS))
            action_overlap = int(
                query_action_requested
                and bool(candidate_terms.intersection(HISTORY_OBSERVATION_SUPPORT_ACTION_TERMS))
            )
            support_context_overlap = len(candidate_terms.intersection(HISTORY_OBSERVATION_SUPPORT_CONTEXT_TERMS))
            person_lead_action = 0
            lead_match = re.match(r"^\s*([A-Z][\w'-]*)\s+([a-z]+)\b", candidate_content)
            if lead_match:
                lead_subject = lead_match.group(1)
                lead_verb = lead_match.group(2).lower()
                if lead_subject.lower() not in {"a", "an", "after", "at", "before", "by", "from", "in", "on", "the"}:
                    person_lead_action = int(lead_verb in HISTORY_OBSERVATION_SUPPORT_PERSON_LEAD_VERBS)
            metadata["scored_candidates"].append(
                {
                    "memory_id": str(row["id"]),
                    "earliest_markers": earliest_markers,
                    "history_markers": history_markers,
                    "later_markers": later_markers,
                    "action_overlap": action_overlap,
                    "support_context_overlap": support_context_overlap,
                    "person_lead_action": person_lead_action,
                }
            )
            if earliest_markers <= 0 and action_overlap <= 0 and support_context_overlap <= 0 and person_lead_action <= 0:
                continue
            observation_seq = int(row["observation_seq"]) if "observation_seq" in row.keys() else 0
            score = (
                person_lead_action,
                support_context_overlap,
                int(earliest_markers > 0),
                action_overlap,
                history_markers,
                -later_markers,
                -observation_seq,
            )
            scored_candidates.append((score, row))
        if not scored_candidates:
            metadata["reason"] = "no-support-candidate-cleared-history-threshold"
            return rows, metadata

        scored_candidates.sort(
            key=lambda item: (
                item[0][0],
                item[0][1],
                item[0][2],
                item[0][3],
                item[0][4],
                str(item[1]["id"]),
            ),
            reverse=True,
        )
        metadata["ordered_support_candidate_ids"] = [str(row["id"]) for _, row in scored_candidates]
        support_row = scored_candidates[0][1]
        updated_rows = []
        seen_ids: set[str] = set()
        for row in [support_row, *rows]:
            memory_id = str(row["id"])
            if memory_id in anchor_rows_by_id and memory_id not in selected_anchor_id_set:
                continue
            if memory_id in seen_ids:
                continue
            seen_ids.add(memory_id)
            updated_rows.append(row)
        metadata["applied"] = True
        metadata["reason"] = "history-before-anchor-observation-support"
        metadata["selected_support_candidate_ids"] = [str(support_row["id"])]
        metadata["selection_strategy"] = "history_anchor_observation_support_v1"
        metadata["selection_order"] = "temporal_marker_then_observation_seq_asc"
        return updated_rows, metadata

    def _retrieval_rows(
        self,
        query: str,
        *,
        scope: str | None,
        include_quarantined: bool,
        limit: int,
    ) -> dict[str, Any]:
        status_sql = "m.status IN ('active')"
        raw_tokens = _query_tokens(query)
        raw_terms = query_terms(query)
        query_lookup = _subject_lookup_query_plan(query, raw_terms)
        semantic_alias_variant = _direct_subject_core_alias_variant(query_lookup, raw_tokens)
        if query_lookup.get("lookup_relation") is None:
            semantic_alias_variant = _direct_deploy_target_alias_variant(raw_tokens) or semantic_alias_variant
            if semantic_alias_variant is None:
                semantic_alias_variant = _generic_subject_alias_variant(raw_tokens)
        raw_search_query = _normalize_conflict_fragment(query) or query
        semantic_anchor_terms = []
        semantic_anchor_source = semantic_query_terms(str(query_lookup.get("search_query") or raw_search_query))
        if query_lookup.get("lookup_relation") and semantic_anchor_source:
            semantic_anchor_terms = [semantic_anchor_source[-1]]
        elif semantic_alias_variant is not None:
            semantic_anchor_terms = [str(term) for term in semantic_alias_variant.get("core_terms", []) if str(term)]
        chronology = _chronology_query_variants(query, raw_tokens, raw_terms)
        current_lookup = _current_query_variants(query, raw_terms)
        history_lookup = _history_query_variants(query, raw_terms)
        update_lookup = _update_query_variants(query)
        target_history_lookup = _target_qualified_history_variants(query)
        planned_search_terms = [str(term) for term in query_lookup.get("search_terms", []) if str(term)]
        search_variants = []
        planned_variant_inputs = []
        if chronology is not None:
            planned_variant_inputs.extend(
                (variant["query"], variant["basis"], variant["terms"])
                for variant in chronology.get("variants", [])
            )
        if history_lookup is not None:
            planned_variant_inputs.extend(
                (variant["query"], variant["basis"], variant["terms"])
                for variant in history_lookup.get("variants", [])
            )
        if current_lookup is not None:
            planned_variant_inputs.extend(
                (variant["query"], variant["basis"], variant["terms"])
                for variant in current_lookup.get("variants", [])
            )
        if update_lookup is not None:
            planned_variant_inputs.extend(
                (variant["query"], variant["basis"], variant["terms"])
                for variant in update_lookup.get("variants", [])
            )
        if target_history_lookup is not None:
            planned_variant_inputs.extend(
                (variant["query"], variant["basis"], variant["terms"])
                for variant in target_history_lookup.get("variants", [])
            )
        if semantic_alias_variant is not None:
            alias_variants = semantic_alias_variant.get("variants")
            if alias_variants:
                planned_variant_inputs.extend(
                    (
                        str(variant["query"]),
                        str(variant["basis"]),
                        [str(term) for term in variant.get("terms", []) if str(term)],
                    )
                    for variant in alias_variants
                )
            else:
                planned_variant_inputs.append(
                    (
                        str(semantic_alias_variant["search_query"]),
                        str(semantic_alias_variant["lookup_basis"]),
                        [str(term) for term in semantic_alias_variant.get("search_terms", []) if str(term)],
                    )
                )
        planned_variant_inputs.extend(
            [
                (
                    str(query_lookup.get("search_query") or ""),
                    str(query_lookup.get("lookup_basis") or "direct-subject"),
                    planned_search_terms,
                ),
                (raw_search_query, "raw-query", raw_terms),
            ]
        )
        for search_query, basis, preferred_terms in planned_variant_inputs:
            normalized_query = " ".join(search_query.split())
            if not normalized_query:
                continue
            terms = [term for term in preferred_terms if term] or query_terms(normalized_query)
            variant = {
                "query": normalized_query,
                "basis": basis,
                "terms": terms,
                "fts_query": fts_safe_query_terms(terms),
            }
            if any(existing["query"] == variant["query"] for existing in search_variants):
                continue
            search_variants.append(variant)
        authority_order_sql = """
          CASE m.authority
            WHEN 'policy' THEN 4
            WHEN 'high' THEN 3
            WHEN 'medium' THEN 2
            WHEN 'low' THEN 1
            ELSE 0
          END
        """
        if include_quarantined:
            status_sql = "m.status IN ('active', 'quarantined', 'proposed')"
        scope_sql = ""
        if scope:
            scope_sql = "AND (m.scope = ? OR m.scope = 'global')"
        prefer_earliest_observation = history_lookup is not None or target_history_lookup is not None
        observation_tie_break_sql = (
            "observation_seq ASC, m.id ASC" if prefer_earliest_observation else "observation_seq DESC, m.id ASC"
        )
        rows = []
        search_mode = "none"
        selected_variant = {
            "query": raw_search_query,
            "basis": "raw-query",
            "terms": raw_terms,
            "fts_query": fts_safe_query(raw_search_query),
        }
        semantic_rescue = {
            "schema": SEMANTIC_RESCUE_SCHEMA,
            "applied": False,
            "reason": "not-needed",
            "query": str(query_lookup.get("search_query") or raw_search_query),
            "query_terms": semantic_query_terms(str(query_lookup.get("search_query") or raw_search_query)),
            "model_id": PSEUDO_EMBEDDING_MODEL_ID,
            "candidate_pool_size": 0,
            "matched_candidate_count": 0,
            "selected_candidate_ids": [],
            "selected_candidates": [],
        }
        hybrid = {
            "schema": HYBRID_RETRIEVAL_SCHEMA,
            "applied": False,
            "strategy": "fts_semantic_backfill_v1",
            "base_search_mode": "none",
            "reason": "not-needed",
            "effective_query": str(query_lookup.get("search_query") or raw_search_query),
            "effective_query_terms": [],
            "required_terms": [],
            "lexical_candidate_ids": [],
            "kept_lexical_candidate_ids": [],
            "dropped_lexical_candidate_ids": [],
            "semantic_candidate_ids": [],
            "introduced_candidate_ids": [],
            "selected_candidate_ids": [],
            "selection_exclusions": [],
            "fusion": None,
            "confidence": {
                "minimum_score": HYBRID_SEMANTIC_BACKFILL_MIN_SCORE,
                "minimum_margin": HYBRID_SEMANTIC_BACKFILL_MIN_MARGIN,
                "top_semantic_score": None,
                "top_lexical_score": None,
                "passed": None,
                "reason": None,
            },
        }
        candidate_metadata: dict[str, dict[str, Any]] = {}
        fts_preselection = {
            "applied": False,
            "strategy": "fts_window_rescore_prune_v1",
            "sql_window_order": "authority_trust_bm25_observation_v1",
            "window_multiplier": FTS_CANDIDATE_WINDOW_MULTIPLIER,
            "window_candidate_count": 0,
            "selected_candidate_ids": [],
            "dropped_candidate_ids": [],
            "requested_limit": limit,
            "search_query": str(selected_variant["query"]),
            "query": query,
            "search_terms": list(selected_variant["terms"]),
            "fts_query": str(selected_variant["fts_query"]),
        }
        limit = max(0, int(limit))
        fts_window_limit = _fts_candidate_window_limit(limit)
        for variant in search_variants:
            if not fts_window_limit or not variant["fts_query"]:
                continue
            params: list[Any] = [variant["fts_query"]]
            if scope:
                params.append(scope)
            try:
                rows = self.conn.execute(
                    f"""
                    SELECT m.*, bm25(memories_fts) AS bm25_score,
                           COALESCE((SELECT MAX(e.seq) FROM events e WHERE e.memory_id = m.id), 0) AS observation_seq
                    FROM memories_fts f
                    JOIN memories m ON m.id = f.id
                    WHERE memories_fts MATCH ?
                      AND {status_sql}
                      {scope_sql}
                    ORDER BY {authority_order_sql} DESC, m.trust DESC, bm25(memories_fts), {observation_tie_break_sql}
                    LIMIT {fts_window_limit}
                    """,
                    params,
                ).fetchall()
                if rows:
                    search_mode = "fts"
                    selected_variant = variant
                    rows, fts_candidate_metadata, fts_preselection = _preselect_fts_rows(
                        rows,
                        query=query,
                        search_query=str(variant["query"]),
                        search_terms=[str(term) for term in variant["terms"] if str(term)],
                        fts_query=str(variant["fts_query"]),
                        query_lookup=query_lookup,
                        limit=limit,
                    )
                    candidate_metadata.update(fts_candidate_metadata)
                    break
            except sqlite3.OperationalError:
                rows = []
        if search_mode == "none":
            for variant in search_variants:
                if not limit or not variant["terms"]:
                    continue
                like_sql = " OR ".join(["lower(m.content) LIKE ?" for _ in variant["terms"]])
                like_params: list[Any] = [f"%{term}%" for term in variant["terms"]]
                if scope:
                    like_params.append(scope)
                rows = self.conn.execute(
                    f"""
                    SELECT m.*,
                           COALESCE((SELECT MAX(e.seq) FROM events e WHERE e.memory_id = m.id), 0) AS observation_seq
                    FROM memories m
                    WHERE ({like_sql})
                      AND {status_sql}
                      {scope_sql}
                    ORDER BY {authority_order_sql} DESC, m.trust DESC, {observation_tie_break_sql}
                    LIMIT {limit}
                    """,
                    like_params,
                ).fetchall()
                if rows:
                    search_mode = "fallback"
                    selected_variant = variant
                    break
        current_update_anchor_terms = _current_update_anchor_terms(current_lookup)
        current_update_sibling_ids: list[str] = []
        if current_update_anchor_terms and rows and len(rows) < limit:
            anchor_sql = " OR ".join(["lower(m.content) LIKE ?" for _ in current_update_anchor_terms])
            update_terms = sorted(CHRONOLOGY_QUERY_MUTATION_TERMS | {"again"})
            update_sql = " OR ".join(["lower(m.content) LIKE ?" for _ in update_terms])
            sibling_params: list[Any] = (
                [f"%{term}%" for term in current_update_anchor_terms]
                + [f"%{term}%" for term in update_terms]
            )
            if scope:
                sibling_params.append(scope)
            sibling_rows = self.conn.execute(
                f"""
                SELECT m.*,
                       COALESCE((SELECT MAX(e.seq) FROM events e WHERE e.memory_id = m.id), 0) AS observation_seq
                FROM memories m
                WHERE ({anchor_sql})
                  AND ({update_sql})
                  AND {status_sql}
                  {scope_sql}
                ORDER BY {authority_order_sql} DESC, m.trust DESC, observation_seq DESC, m.id ASC
                LIMIT {limit}
                """,
                sibling_params,
            ).fetchall()
            existing_ids = {row["id"] for row in rows}
            for sibling_row in sibling_rows:
                if sibling_row["id"] in existing_ids:
                    continue
                rows.append(sibling_row)
                existing_ids.add(sibling_row["id"])
                current_update_sibling_ids.append(sibling_row["id"])
                if len(rows) >= limit:
                    break
        chronology_support = {
            "applied": False,
            "reason": "not-needed",
            "subject_term": None,
            "relation": None,
            "relation_terms": [],
            "mutation_terms": [],
            "selected_candidate_ids": [],
            "support_kind": "chronology",
        }
        history_support = {
            "applied": False,
            "reason": "not-needed",
            "subject_term": None,
            "relation": None,
            "relation_terms": [],
            "mutation_terms": [],
            "selected_candidate_ids": [],
            "support_kind": "history",
        }
        update_history_support = {
            "applied": False,
            "reason": "not-needed",
            "subject_term": None,
            "relation": None,
            "relation_terms": [],
            "mutation_terms": [],
            "selected_candidate_ids": [],
            "support_kind": "update-history",
        }
        update_current_support = {
            "applied": False,
            "reason": "not-needed",
            "subject_term": None,
            "relation": None,
            "relation_terms": [],
            "mutation_terms": [],
            "selected_candidate_ids": [],
            "support_kind": "update-current",
        }
        chronology_support_profile = _chronology_support_anchor_profile(
            query_lookup=query_lookup,
            chronology=chronology,
            selected_variant=selected_variant,
        )
        if chronology_support_profile is not None:
            chronology_support.update(chronology_support_profile)
        _append_relation_support_rows(
            self.conn,
            support=chronology_support,
            rows=rows,
            candidate_metadata=candidate_metadata,
            status_sql=status_sql,
            scope_sql=scope_sql,
            authority_order_sql=authority_order_sql,
            scope=scope,
            limit=limit,
        )
        history_support_profile = _history_support_anchor_profile(
            query_lookup=query_lookup,
            history_lookup=history_lookup,
            selected_variant=selected_variant,
        )
        if history_support_profile is not None:
            history_support.update(history_support_profile)
        _append_relation_support_rows(
            self.conn,
            support=history_support,
            rows=rows,
            candidate_metadata=candidate_metadata,
            status_sql=status_sql,
            scope_sql=scope_sql,
            authority_order_sql=authority_order_sql,
            scope=scope,
            limit=limit,
        )
        update_history_support_profile = _update_history_support_anchor_profile(
            query_lookup=query_lookup,
            update_lookup=update_lookup,
            selected_variant=selected_variant,
        )
        if update_history_support_profile is not None:
            update_history_support.update(update_history_support_profile)
        _append_relation_support_rows(
            self.conn,
            support=update_history_support,
            rows=rows,
            candidate_metadata=candidate_metadata,
            status_sql=status_sql,
            scope_sql=scope_sql,
            authority_order_sql=authority_order_sql,
            scope=scope,
            limit=limit,
        )
        update_current_support_profile = _update_current_support_anchor_profile(
            query_lookup=query_lookup,
            update_lookup=update_lookup,
            selected_variant=selected_variant,
        )
        if update_current_support_profile is not None:
            update_current_support.update(update_current_support_profile)
        _append_relation_support_rows(
            self.conn,
            support=update_current_support,
            rows=rows,
            candidate_metadata=candidate_metadata,
            status_sql=status_sql,
            scope_sql=scope_sql,
            authority_order_sql=authority_order_sql,
            scope=scope,
            limit=limit,
        )
        current_direct_deploy_hybrid_override = _current_direct_deploy_target_hybrid_override(
            query_lookup=query_lookup,
            current_lookup=current_lookup,
            semantic_alias_variant=semantic_alias_variant,
        )
        history_direct_deploy_hybrid_override = _history_direct_deploy_target_hybrid_override(
            query_lookup=query_lookup,
            history_lookup=history_lookup,
            semantic_alias_variant=semantic_alias_variant,
        )
        update_direct_deploy_hybrid_override = _update_direct_deploy_target_hybrid_override(
            query_lookup=query_lookup,
            update_lookup=update_lookup,
            semantic_alias_variant=semantic_alias_variant,
        )
        update_history_direct_deploy_hybrid_override = _update_history_direct_deploy_target_hybrid_override(
            query_lookup=query_lookup,
            update_lookup=update_lookup,
        )
        semantic_query = str(query_lookup.get("search_query") or raw_search_query)
        semantic_terms = semantic_query_terms(semantic_query)
        declarative_semantic_profile = _declarative_semantic_rescue_profile(
            raw_tokens=raw_tokens,
            raw_terms=raw_terms,
            query_lookup=query_lookup,
            current_lookup=current_lookup,
            chronology=chronology,
            history_lookup=history_lookup,
            update_lookup=update_lookup,
            rows=rows,
            selected_terms=list(selected_variant["terms"]),
            search_mode=search_mode,
        )
        semantic_rescue_query_like = bool(
            query_lookup.get("lookup_relation")
            or semantic_alias_variant
            or (raw_tokens and raw_tokens[0] in SUBJECT_LOOKUP_QUERY_WRAPPERS)
        )
        should_try_semantic_rescue = (
            limit > 0
            and len(semantic_terms) >= 2
            and search_mode in {"none", "fallback"}
            and (semantic_rescue_query_like or declarative_semantic_profile is not None)
        )
        if should_try_semantic_rescue:
            fallback_candidate_ids = [row["id"] for row in rows]
            rescue_required_terms = [] if declarative_semantic_profile is not None else semantic_anchor_terms
            semantic_query = str(
                (declarative_semantic_profile or {}).get("effective_query")
                or query_lookup.get("search_query")
                or raw_search_query
            )
            semantic_terms_override = (declarative_semantic_profile or {}).get("effective_query_terms")
            semantic_result = self._semantic_rescue_rows(
                str(query_lookup.get("search_query") or raw_search_query),
                scope=scope,
                include_quarantined=include_quarantined,
                limit=limit,
                required_terms=rescue_required_terms,
                activation_reason="no-lexical-match" if search_mode == "none" else "fallback-paraphrase-match",
                confidence_profile=declarative_semantic_profile,
                effective_query=semantic_query,
                effective_query_terms=semantic_terms_override,
            )
            semantic_rescue = semantic_result["metadata"]
            if semantic_result["rows"]:
                rows = semantic_result["rows"]
                search_mode = "semantic"
                selected_variant = {
                    "query": semantic_query,
                    "basis": str(
                        (declarative_semantic_profile or {}).get("search_basis")
                        or query_lookup.get("lookup_basis")
                        or "semantic-rescue"
                    ),
                    "terms": [str(term) for term in (semantic_terms_override or semantic_terms) if str(term)],
                    "fts_query": fts_safe_query_terms(
                        [str(term) for term in (semantic_terms_override or semantic_terms) if str(term)]
                    ),
                }
            elif declarative_semantic_profile is not None and fallback_candidate_ids:
                rows = []
                search_mode = "none"
                semantic_rescue["abstention"] = {
                    "applied": True,
                    "reason": semantic_rescue.get("reason") or "low-confidence-declarative-match",
                    "dropped_candidate_ids": fallback_candidate_ids,
                }
        should_try_hybrid_backfill = (
            limit > 0
            and bool(rows)
            and search_mode == "fts"
            and len(semantic_terms) >= 2
            and (semantic_rescue_query_like or declarative_semantic_profile is not None)
        )
        if should_try_hybrid_backfill:
            hybrid_semantic_override = (
                current_direct_deploy_hybrid_override
                or history_direct_deploy_hybrid_override
                or update_direct_deploy_hybrid_override
                or update_history_direct_deploy_hybrid_override
                or {}
            )
            rescue_required_terms = (
                list(hybrid_semantic_override.get("required_terms", []))
                if hybrid_semantic_override
                else ([] if declarative_semantic_profile is not None else semantic_anchor_terms)
            )
            semantic_query = str(
                hybrid_semantic_override.get("effective_query")
                or (declarative_semantic_profile or {}).get("effective_query")
                or query_lookup.get("search_query")
                or raw_search_query
            )
            semantic_terms_override = [
                str(term)
                for term in (
                    hybrid_semantic_override.get("effective_query_terms")
                    or (declarative_semantic_profile or {}).get("effective_query_terms")
                    or semantic_terms
                )
                if str(term)
            ]
            hybrid_confidence_profile = (
                {"ignored_query_terms": list(hybrid_semantic_override.get("ignored_query_terms", []))}
                if hybrid_semantic_override.get("ignored_query_terms")
                else None
            )
            hybrid["base_search_mode"] = search_mode
            hybrid["effective_query"] = semantic_query
            hybrid["effective_query_terms"] = semantic_terms_override
            hybrid["required_terms"] = list(rescue_required_terms)
            hybrid["lexical_candidate_ids"] = [row["id"] for row in rows]
            semantic_result = self._semantic_rescue_rows(
                str(query_lookup.get("search_query") or raw_search_query),
                scope=scope,
                include_quarantined=include_quarantined,
                limit=limit,
                required_terms=rescue_required_terms,
                activation_reason="fts-paraphrase-backfill",
                confidence_profile=hybrid_confidence_profile,
                effective_query=semantic_query,
                effective_query_terms=semantic_terms_override,
            )
            semantic_probe = semantic_result["metadata"]
            hybrid["semantic_probe"] = semantic_probe
            hybrid["semantic_candidate_ids"] = list(semantic_probe.get("selected_candidate_ids", []))
            semantic_selected_by_id = {
                str(item["memory_id"]): item
                for item in semantic_probe.get("selected_candidates", [])
                if "memory_id" in item
            }
            introduced_ids = [
                memory_id
                for memory_id in hybrid["semantic_candidate_ids"]
                if memory_id not in set(hybrid["lexical_candidate_ids"])
            ]
            top_semantic_candidates = list(semantic_probe.get("selected_candidate_ids", []))
            top_semantic_id = top_semantic_candidates[0] if top_semantic_candidates else None
            top_semantic_score = None
            if top_semantic_id in semantic_selected_by_id:
                top_semantic_score = float(semantic_selected_by_id[top_semantic_id]["score"])
            hybrid["confidence"]["top_semantic_score"] = round(top_semantic_score, 6) if top_semantic_score is not None else None
            query_vector = pseudo_embedding(" ".join(semantic_terms_override))
            lexical_infos = []
            for index, row in enumerate(rows, start=1):
                memory = MemoryRecord.from_row(row)
                haystack = f"{memory.content} {' '.join(memory.labels)}".strip()
                candidate_terms = semantic_query_terms(haystack)
                overlap = len(set(semantic_terms_override).intersection(candidate_terms))
                similarity = cosine_similarity(query_vector, pseudo_embedding(haystack)) if overlap else 0.0
                lexical_infos.append(
                    {
                        "row": row,
                        "memory": memory,
                        "pre_hybrid_rank": index,
                        "semantic_score": similarity,
                        "semantic_term_overlap": overlap,
                        "structured_fact": _row_has_structured_fact(row),
                    }
                )
            top_lexical_score = max((float(item["semantic_score"]) for item in lexical_infos), default=0.0)
            hybrid["confidence"]["top_lexical_score"] = round(top_lexical_score, 6)
            if semantic_probe.get("abstention", {}).get("applied"):
                hybrid["reason"] = "semantic-probe-abstained"
                hybrid["confidence"]["passed"] = False
                hybrid["confidence"]["reason"] = str(semantic_probe["abstention"].get("reason"))
            elif not introduced_ids:
                hybrid["reason"] = "semantic-candidates-already-lexical"
                hybrid["confidence"]["passed"] = False
                hybrid["confidence"]["reason"] = "no-introduced-candidates"
            elif top_semantic_score is None:
                hybrid["reason"] = "no-semantic-candidates"
                hybrid["confidence"]["passed"] = False
                hybrid["confidence"]["reason"] = "no-semantic-candidates"
            else:
                passed = (
                    top_semantic_score >= HYBRID_SEMANTIC_BACKFILL_MIN_SCORE
                    and top_semantic_score > top_lexical_score + HYBRID_SEMANTIC_BACKFILL_MIN_MARGIN
                )
                hybrid["confidence"]["passed"] = passed
                if not passed:
                    hybrid["reason"] = "semantic-candidate-not-stronger-than-lexical"
                    hybrid["confidence"]["reason"] = "semantic-margin-below-threshold"
                else:
                    lexical_keep_threshold = top_semantic_score - HYBRID_SEMANTIC_BACKFILL_MIN_MARGIN
                    kept_lexical_infos = [
                        item
                        for item in lexical_infos
                        if item["structured_fact"] or float(item["semantic_score"]) >= lexical_keep_threshold
                    ]
                    introduced_rows = []
                    introduced_metadata = []
                    for row in semantic_result["rows"]:
                        if row["id"] not in introduced_ids:
                            continue
                        candidate = semantic_selected_by_id.get(row["id"])
                        if candidate is None:
                            continue
                        if float(candidate["score"]) < HYBRID_SEMANTIC_BACKFILL_MIN_SCORE:
                            continue
                        introduced_rows.append(row)
                        introduced_metadata.append(candidate)
                        break
                    if introduced_rows:
                        rows = [item["row"] for item in kept_lexical_infos] + introduced_rows
                        hybrid["applied"] = True
                        hybrid["reason"] = "stronger-semantic-fact-replaced-weak-lexical-hit"
                        hybrid["confidence"]["reason"] = "semantic-margin-cleared"
                        hybrid["kept_lexical_candidate_ids"] = [
                            item["memory"].id for item in kept_lexical_infos
                        ]
                        kept_lexical_id_set = set(hybrid["kept_lexical_candidate_ids"])
                        hybrid["dropped_lexical_candidate_ids"] = [
                            item["memory"].id
                            for item in lexical_infos
                            if item["memory"].id not in kept_lexical_id_set
                        ]
                        hybrid["selection_exclusions"] = [
                            {
                                "memory_id": item["memory"].id,
                                "reason": "hybrid-semantic-backfill-replaced-weak-lexical-hit",
                                "pre_hybrid_rank": item["pre_hybrid_rank"],
                                "semantic_backfill_score": round(float(item["semantic_score"]), 6),
                                "semantic_backfill_term_overlap": int(item["semantic_term_overlap"]),
                                "structured_fact_candidate": bool(item["structured_fact"]),
                            }
                            for item in lexical_infos
                            if item["memory"].id not in kept_lexical_id_set
                        ]
                        hybrid["introduced_candidate_ids"] = [row["id"] for row in introduced_rows]
                        hybrid["selected_candidate_ids"] = [row["id"] for row in rows]
                        hybrid["fusion"] = _reciprocal_rank_fusion(
                            {
                                "lexical": hybrid["kept_lexical_candidate_ids"],
                                "semantic": hybrid["introduced_candidate_ids"],
                            },
                            selected_candidate_ids=hybrid["selected_candidate_ids"],
                        )
                        hybrid["fusion"]["considered_source_rankings"] = {
                            "lexical": hybrid["lexical_candidate_ids"],
                            "semantic": hybrid["semantic_candidate_ids"],
                        }
                        fusion_by_id = {
                            str(item["memory_id"]): item
                            for item in hybrid["fusion"]["candidate_scores"]
                        }
                        for item in kept_lexical_infos:
                            fusion_item = fusion_by_id.get(item["memory"].id, {})
                            candidate_metadata[item["memory"].id] = {
                                "pre_hybrid_rank": item["pre_hybrid_rank"],
                                "hybrid_candidate_source": "lexical",
                                "structured_fact_candidate": item["structured_fact"],
                                "semantic_backfill_score": round(float(item["semantic_score"]), 6),
                                "semantic_backfill_term_overlap": int(item["semantic_term_overlap"]),
                                "fusion_rank": fusion_item.get("fusion_rank"),
                                "fusion_score": fusion_item.get("score"),
                                "fusion_sources": [
                                    contribution["source"]
                                    for contribution in fusion_item.get("source_contributions", [])
                                ],
                            }
                        for row, candidate in zip(introduced_rows, introduced_metadata):
                            fusion_item = fusion_by_id.get(row["id"], {})
                            candidate_metadata[row["id"]] = {
                                "pre_hybrid_rank": None,
                                "hybrid_candidate_source": "semantic-backfill",
                                "structured_fact_candidate": _row_has_structured_fact(row),
                                "semantic_backfill_score": round(float(candidate["score"]), 6),
                                "semantic_backfill_term_overlap": int(candidate["term_overlap"]),
                                "fusion_rank": fusion_item.get("fusion_rank"),
                                "fusion_score": fusion_item.get("score"),
                                "fusion_sources": [
                                    contribution["source"]
                                    for contribution in fusion_item.get("source_contributions", [])
                                ],
                            }
                    else:
                        hybrid["reason"] = "no-introduced-candidate-cleared-threshold"
                        hybrid["confidence"]["passed"] = False
                        hybrid["confidence"]["reason"] = "no-introduced-candidate-cleared-threshold"
        rows, history_observation_support = self._history_observation_support_rows(
            query=query,
            raw_tokens=raw_tokens,
            raw_terms=raw_terms,
            query_lookup=query_lookup,
            rows=rows,
            search_mode=search_mode,
            scope=scope,
            include_quarantined=include_quarantined,
            limit=limit,
        )
        rows, completion_support = _completion_support_expansion(
            self.conn,
            query=query,
            search_mode=search_mode,
            rows=rows,
            candidate_metadata=candidate_metadata,
            status_sql=status_sql,
            scope_sql=scope_sql,
            authority_order_sql=authority_order_sql,
            scope=scope,
            limit=limit,
        )
        for index, row in enumerate(rows, start=1):
            candidate_metadata.setdefault(
                row["id"],
                {
                    "pre_hybrid_rank": index if hybrid["applied"] else None,
                    "hybrid_candidate_source": "lexical" if search_mode in {"fts", "fallback"} else None,
                    "structured_fact_candidate": _row_has_structured_fact(row) if search_mode in {"fts", "fallback"} else None,
                    "semantic_backfill_score": None,
                    "semantic_backfill_term_overlap": None,
                    "observation_seq": int(row["observation_seq"]) if "observation_seq" in row.keys() else 0,
                },
            )
        return {
            "rows": rows,
            "search_mode": search_mode,
            "fts_query": str(selected_variant["fts_query"]),
            "terms": list(selected_variant["terms"]),
            "raw_terms": raw_terms,
            "search_query": str(selected_variant["query"]),
            "fusion_query": str(selected_variant["query"]),
            "fusion_query_basis": str(selected_variant["basis"]),
            "chronology_support": chronology_support,
            "history_support": history_support,
            "update_history_support": update_history_support,
            "update_current_support": update_current_support,
            "completion_support": completion_support,
            "candidate_metadata": candidate_metadata,
            "query_lookup": {
                "schema": QUERY_LOOKUP_SCHEMA,
                "lookup_key": query_lookup.get("lookup_key"),
                "lookup_basis": query_lookup.get("lookup_basis"),
                "lookup_relation": query_lookup.get("lookup_relation"),
                "selected_search_query": selected_variant["query"],
                "selected_search_terms": selected_variant["terms"],
                "selected_search_basis": selected_variant["basis"],
                "chronology": {
                    "matched_terms": chronology.get("matched_terms", []) if chronology else [],
                    "raw_core_terms": chronology.get("raw_core_terms", []) if chronology else [],
                    "core_terms": chronology.get("core_terms", []) if chronology else [],
                    "matched_aliases": chronology.get("matched_aliases", []) if chronology else [],
                    "alias_expanded": bool(chronology and chronology.get("alias_expanded")),
                    "search_alias_variants": chronology.get("search_alias_variants", []) if chronology else [],
                    "search_alias_expanded": bool(chronology and chronology.get("search_alias_expanded")),
                    "expanded": bool(chronology and chronology.get("variants")),
                    "support_candidate_ids": chronology_support["selected_candidate_ids"],
                    "support_relation_terms": chronology_support["relation_terms"],
                    "support_subject_term": chronology_support["subject_term"],
                },
                "history": {
                    "matched_terms": history_lookup.get("matched_terms", []) if history_lookup else [],
                    "raw_core_terms": history_lookup.get("raw_core_terms", []) if history_lookup else [],
                    "core_terms": history_lookup.get("core_terms", []) if history_lookup else [],
                    "matched_aliases": history_lookup.get("matched_aliases", []) if history_lookup else [],
                    "alias_expanded": bool(history_lookup and history_lookup.get("alias_expanded")),
                    "search_alias_variants": history_lookup.get("search_alias_variants", []) if history_lookup else [],
                    "search_alias_expanded": bool(history_lookup and history_lookup.get("search_alias_expanded")),
                    "role_inferred": history_lookup.get("role_inferred") if history_lookup else None,
                    "role_inference_reason": history_lookup.get("role_inference_reason") if history_lookup else None,
                    "expanded": bool(history_lookup and history_lookup.get("expanded")),
                    "support_candidate_ids": history_support["selected_candidate_ids"],
                    "support_relation_terms": history_support["relation_terms"],
                    "support_subject_term": history_support["subject_term"],
                    "observation_support": history_observation_support,
                },
                "current": {
                    "matched_terms": current_lookup.get("matched_terms", []) if current_lookup else [],
                    "raw_core_terms": current_lookup.get("raw_core_terms", []) if current_lookup else [],
                    "core_terms": current_lookup.get("core_terms", []) if current_lookup else [],
                    "matched_aliases": current_lookup.get("matched_aliases", []) if current_lookup else [],
                    "alias_expanded": bool(current_lookup and current_lookup.get("alias_expanded")),
                    "search_alias_variants": current_lookup.get("search_alias_variants", []) if current_lookup else [],
                    "search_alias_expanded": bool(current_lookup and current_lookup.get("search_alias_expanded")),
                    "role_inferred": current_lookup.get("role_inferred") if current_lookup else None,
                    "role_inference_reason": current_lookup.get("role_inference_reason") if current_lookup else None,
                    "expanded": bool(current_lookup and current_lookup.get("expanded")),
                    "update_anchor_terms": current_update_anchor_terms,
                    "update_sibling_candidate_ids": current_update_sibling_ids,
                },
                "update": {
                    "matched_terms": update_lookup.get("matched_terms", []) if update_lookup else [],
                    "raw_core_terms": update_lookup.get("raw_core_terms", []) if update_lookup else [],
                    "core_terms": update_lookup.get("core_terms", []) if update_lookup else [],
                    "matched_aliases": update_lookup.get("matched_aliases", []) if update_lookup else [],
                    "alias_expanded": bool(update_lookup and update_lookup.get("alias_expanded")),
                    "search_alias_variants": update_lookup.get("search_alias_variants", []) if update_lookup else [],
                    "search_alias_expanded": bool(update_lookup and update_lookup.get("search_alias_expanded")),
                    "direction": update_lookup.get("direction") if update_lookup else None,
                    "direction_terms": update_lookup.get("direction_terms", []) if update_lookup else [],
                    "role_inferred": update_lookup.get("role_inferred") if update_lookup else None,
                    "role_inference_reason": update_lookup.get("role_inference_reason") if update_lookup else None,
                    "expanded": bool(update_lookup and update_lookup.get("expanded")),
                    "support_candidate_ids": (
                        update_current_support["selected_candidate_ids"]
                        if str((update_lookup or {}).get("direction") or "") == "current"
                        else update_history_support["selected_candidate_ids"]
                    ),
                    "support_relation_terms": (
                        update_current_support["relation_terms"]
                        if str((update_lookup or {}).get("direction") or "") == "current"
                        else update_history_support["relation_terms"]
                    ),
                    "support_subject_term": (
                        update_current_support["subject_term"]
                        if str((update_lookup or {}).get("direction") or "") == "current"
                        else update_history_support["subject_term"]
                    ),
                },
                "target_history": {
                    "applied": bool(target_history_lookup and target_history_lookup.get("applied")),
                    "relation": target_history_lookup.get("relation") if target_history_lookup else None,
                    "history_terms": target_history_lookup.get("history_terms", []) if target_history_lookup else [],
                    "mutation_terms": target_history_lookup.get("mutation_terms", []) if target_history_lookup else [],
                    "target_query": target_history_lookup.get("target_query") if target_history_lookup else None,
                    "search_variants": (
                        [
                            {
                                "query": str(variant["query"]),
                                "terms": [str(term) for term in variant.get("terms", []) if str(term)],
                                "basis": str(variant["basis"]),
                            }
                            for variant in target_history_lookup.get("variants", [])
                        ]
                        if target_history_lookup
                        else []
                    ),
                },
                "semantic_aliases": {
                    "matched_aliases": semantic_alias_variant.get("matched_aliases", []) if semantic_alias_variant else [],
                    "raw_core_terms": semantic_alias_variant.get("raw_core_terms", []) if semantic_alias_variant else [],
                    "core_terms": semantic_alias_variant.get("core_terms", []) if semantic_alias_variant else [],
                    "alias_expanded": bool(semantic_alias_variant and semantic_alias_variant.get("alias_expanded")),
                    "search_alias_variants": (
                        semantic_alias_variant.get("search_alias_variants", []) if semantic_alias_variant else []
                    ),
                    "search_alias_expanded": bool(
                        semantic_alias_variant and semantic_alias_variant.get("search_alias_expanded")
                    ),
                    "expanded": bool(semantic_alias_variant),
                },
                "semantic_rescue": semantic_rescue,
                "variants": [
                    {
                        "query": variant["query"],
                        "terms": variant["terms"],
                        "fts_query": variant["fts_query"],
                        "basis": variant["basis"],
                    }
                    for variant in search_variants
                ],
            },
            "bm25_scores": {
                row["id"]: (float(row["bm25_score"]) if "bm25_score" in row.keys() else None)
                for row in rows
            },
            "fts_preselection": fts_preselection,
            "semantic_rescue": semantic_rescue,
            "hybrid": hybrid,
        }

    def _multi_hop_candidate_union(
        self,
        query: str,
        *,
        scope: str | None,
        include_quarantined: bool,
        parent_rows: list[sqlite3.Row],
        parent_bm25_scores: dict[str, float | None],
        retrieval_config: dict[str, Any] | None,
        query_lookup: dict[str, Any] | None = None,
    ) -> tuple[list[MemoryRecord], dict[str, float | None], dict[str, Any], dict[str, dict[str, Any]]]:
        multi_hop_config = _candidate_config(retrieval_config, "multi_hop")
        enabled = bool(multi_hop_config.get("enabled", False))
        max_subqueries = min(
            MULTI_HOP_MAX_SUBQUERIES,
            max(0, int(multi_hop_config.get("max_subqueries", MULTI_HOP_MAX_SUBQUERIES))),
        )
        per_subquery_limit = min(
            MULTI_HOP_PER_SUBQUERY_LIMIT,
            max(0, int(multi_hop_config.get("per_subquery_limit", MULTI_HOP_PER_SUBQUERY_LIMIT))),
        )
        limits = {
            "max_subqueries": max_subqueries,
            "per_subquery_results": per_subquery_limit,
            "candidate_limit": RETRIEVAL_CANDIDATE_LIMIT,
        }
        parent_query_hash = sha256_text(query)
        config_hash = sha256_text(stable_json(multi_hop_config))
        parent_memories = [MemoryRecord.from_row(row) for row in parent_rows]
        observation_seq_by_id = {
            row["id"]: int(row["observation_seq"]) if "observation_seq" in row.keys() else 0
            for row in parent_rows
        }
        parent_rank_by_id = {memory.id: index for index, memory in enumerate(parent_memories, start=1)}
        memories_by_id = {memory.id: memory for memory in parent_memories}
        ordered_ids = [memory.id for memory in parent_memories]
        bm25_scores = dict(parent_bm25_scores)
        attribution: dict[str, dict[str, Any]] = {
            memory.id: {
                "memory_id": memory.id,
                "sources": ["parent"],
                "subquery_ids": ["parent"],
                "introduced_by_subquery_id": None,
                "pre_multi_hop_rank": parent_rank_by_id[memory.id],
                "duplicate_count": 0,
            }
            for memory in parent_memories
        }
        subqueries: list[dict[str, Any]] = []
        rank_transitions: list[dict[str, Any]] = []
        multi_hop_fusion = None
        disabled_reason = None if enabled else str(multi_hop_config.get("suppression_reason") or "disabled-by-config")

        if enabled and max_subqueries and per_subquery_limit:
            subqueries = decompose_multi_hop_query(
                query,
                max_subqueries=max_subqueries,
                query_lookup=query_lookup,
            )
            if not subqueries:
                disabled_reason = "no-subqueries"
            for subquery in subqueries:
                result = self._retrieval_rows(
                    subquery["query"],
                    scope=scope,
                    include_quarantined=include_quarantined,
                    limit=per_subquery_limit,
                )
                subquery_rows = list(result["rows"])
                activation_reason = str(multi_hop_config.get("activation_reason") or "")
                if (
                    activation_reason in {"fts-entity-intent-compound-query", "fts-identifier-compound-query"}
                    and str(subquery.get("source") or "") in {"entity_or_title", "quoted_phrase"}
                ):
                    filtered_parent_candidate_ids = [
                        str(row["id"])
                        for row in subquery_rows
                        if str(row["id"]) in parent_rank_by_id and not _row_has_structured_fact(row)
                    ]
                    if filtered_parent_candidate_ids:
                        subquery["filtered_parent_candidate_ids"] = filtered_parent_candidate_ids
                        subquery["filtered_parent_candidate_reason"] = (
                            "prefer-subquery-introduced-specific-facts"
                        )
                        subquery_rows = [
                            row
                            for row in subquery_rows
                            if str(row["id"]) not in filtered_parent_candidate_ids
                        ]
                elif _should_filter_parent_only_multi_hop_candidates(
                    activation_reason=activation_reason,
                    subquery=subquery,
                ):
                    introduced_candidate_ids = [
                        str(row["id"])
                        for row in subquery_rows
                        if str(row["id"]) not in parent_rank_by_id
                    ]
                    if introduced_candidate_ids:
                        filtered_parent_candidate_ids = [
                            str(row["id"])
                            for row in subquery_rows
                            if str(row["id"]) in parent_rank_by_id
                        ]
                        if filtered_parent_candidate_ids:
                            subquery["filtered_parent_candidate_ids"] = filtered_parent_candidate_ids
                            subquery["filtered_parent_candidate_reason"] = (
                                "prefer-subquery-introduced-specific-facts"
                            )
                            subquery_rows = [
                                row
                                for row in subquery_rows
                                if str(row["id"]) not in parent_rank_by_id
                            ]
                subquery["fts_query"] = result["fts_query"]
                subquery["search_mode"] = result["search_mode"]
                subquery["candidate_ids"] = [row["id"] for row in subquery_rows]
                subquery["candidate_count"] = len(subquery["candidate_ids"])
                for row in subquery_rows:
                    memory = MemoryRecord.from_row(row)
                    item = attribution.setdefault(
                        memory.id,
                        {
                            "memory_id": memory.id,
                            "sources": [],
                            "subquery_ids": [],
                            "introduced_by_subquery_id": subquery["id"],
                            "pre_multi_hop_rank": parent_rank_by_id.get(memory.id),
                            "duplicate_count": 0,
                        },
                    )
                    if subquery["id"] in item["subquery_ids"]:
                        item["duplicate_count"] += 1
                    elif item["subquery_ids"]:
                        item["duplicate_count"] += 1
                    item["sources"].append(subquery["source"])
                    item["subquery_ids"].append(subquery["id"])
                    memories_by_id.setdefault(memory.id, memory)
                    observation_seq_by_id[memory.id] = max(
                        observation_seq_by_id.get(memory.id, 0),
                        int(row["observation_seq"]) if "observation_seq" in row.keys() else 0,
                    )
                    if memory.id not in ordered_ids and len(ordered_ids) < RETRIEVAL_CANDIDATE_LIMIT:
                        ordered_ids.append(memory.id)
                    if memory.id not in bm25_scores or bm25_scores[memory.id] is None:
                        bm25_scores[memory.id] = result["bm25_scores"].get(memory.id)
        elif enabled:
            disabled_reason = "limits-exhausted"

        source_rankings: dict[str, list[str]] = {"parent": [memory.id for memory in parent_memories]}
        for subquery in subqueries:
            candidate_ids = [str(memory_id) for memory_id in subquery.get("candidate_ids", []) if str(memory_id)]
            if candidate_ids:
                source_rankings[str(subquery["id"])] = candidate_ids
        if enabled and len(source_rankings) > 1:
            initial_fusion = _reciprocal_rank_fusion(source_rankings)
            fused_ids = [
                memory_id
                for memory_id in initial_fusion["ranked_candidate_ids"]
                if memory_id in memories_by_id
            ]
            if fused_ids:
                ordered_ids = fused_ids[:RETRIEVAL_CANDIDATE_LIMIT]
                multi_hop_fusion = _reciprocal_rank_fusion(source_rankings, selected_candidate_ids=ordered_ids)

        memories = [memories_by_id[memory_id] for memory_id in ordered_ids[:RETRIEVAL_CANDIDATE_LIMIT]]
        candidate_metadata: dict[str, dict[str, Any]] = {}
        introduced_ids = []
        duplicate_ids = []
        promoted_ids = []
        outranked_ids = []
        multi_hop_fusion_by_id = {
            str(item["memory_id"]): item
            for item in (
                multi_hop_fusion.get("candidate_scores", [])
                if isinstance(multi_hop_fusion, dict)
                else []
            )
        }
        for rank, memory in enumerate(memories, start=1):
            item = attribution.setdefault(
                memory.id,
                {
                    "memory_id": memory.id,
                    "sources": ["parent"],
                    "subquery_ids": ["parent"],
                    "introduced_by_subquery_id": None,
                    "pre_multi_hop_rank": parent_rank_by_id.get(memory.id),
                    "duplicate_count": 0,
                },
            )
            if item["introduced_by_subquery_id"]:
                introduced_ids.append(memory.id)
            if item["duplicate_count"]:
                duplicate_ids.append(memory.id)
            fusion_item = multi_hop_fusion_by_id.get(memory.id, {})
            pre_multi_hop_rank = item["pre_multi_hop_rank"]
            fusion_rank = fusion_item.get("fusion_rank")
            rank_delta = None
            promoted_by_fusion = False
            outranked_by_fusion = False
            outranked_reason = None
            if isinstance(pre_multi_hop_rank, int) and isinstance(fusion_rank, int):
                rank_delta = fusion_rank - pre_multi_hop_rank
                promoted_by_fusion = fusion_rank < pre_multi_hop_rank
                outranked_by_fusion = fusion_rank > pre_multi_hop_rank
                if promoted_by_fusion:
                    promoted_ids.append(memory.id)
                if outranked_by_fusion:
                    outranked_ids.append(memory.id)
                    outranked_reason = "multi-hop-fusion-ranked-lower"
            candidate_metadata[memory.id] = {
                "pre_multi_hop_rank": pre_multi_hop_rank,
                "multi_hop_rank": rank,
                "introduced_by_subquery_id": item["introduced_by_subquery_id"],
                "multi_hop_subquery_ids": item["subquery_ids"],
                "multi_hop_duplicate_count": item["duplicate_count"],
                "multi_hop_fusion_rank": fusion_rank,
                "multi_hop_fusion_score": fusion_item.get("score"),
                "multi_hop_fusion_sources": [
                    contribution.get("source")
                    for contribution in fusion_item.get("source_contributions", [])
                    if contribution.get("source")
                ],
                "multi_hop_fusion_source_count": len(fusion_item.get("source_contributions", [])),
                "multi_hop_rank_delta": rank_delta,
                "multi_hop_promoted_by_fusion": promoted_by_fusion,
                "multi_hop_outranked_by_fusion": outranked_by_fusion,
                "multi_hop_outranked_reason": outranked_reason,
                "observation_seq": observation_seq_by_id.get(memory.id, 0),
            }
            rank_transitions.append(
                {
                    "memory_id": memory.id,
                    "pre_multi_hop_rank": pre_multi_hop_rank,
                    "multi_hop_rank": rank,
                    "introduced_by_subquery_id": item["introduced_by_subquery_id"],
                    "multi_hop_fusion_rank": fusion_rank,
                    "multi_hop_rank_delta": rank_delta,
                    "multi_hop_promoted_by_fusion": promoted_by_fusion,
                    "multi_hop_outranked_by_fusion": outranked_by_fusion,
                }
            )

        metadata = {
            "schema": MULTI_HOP_DECOMPOSITION_SCHEMA,
            "enabled": enabled,
            "auto_enabled": bool(multi_hop_config.get("auto_enabled", False)),
            "auto_evaluated": bool(multi_hop_config.get("auto_evaluated", False)),
            "activation_reason": multi_hop_config.get("activation_reason"),
            "suppression_reason": multi_hop_config.get("suppression_reason"),
            "decomposer_id": MULTI_HOP_DECOMPOSER_ID if enabled else None,
            "strategy": MULTI_HOP_STRATEGY,
            "parent_query_hash": parent_query_hash,
            "config_hash": config_hash,
            "decomposition_hash": sha256_text(stable_json(subqueries)),
            "limits": limits,
            "subqueries": subqueries,
            "candidate_attribution": {
                memory_id: attribution[memory_id]
                for memory_id in sorted(attribution)
                if memory_id in candidate_metadata
            },
            "fusion": (
                {
                    **multi_hop_fusion,
                    "applied": True,
                }
                if isinstance(multi_hop_fusion, dict)
                else {
                    "applied": False,
                    "disabled_reason": "no-subquery-rankings" if enabled else "disabled-by-config",
                    "source_rankings": source_rankings,
                    "selected_candidate_ids": ordered_ids[:RETRIEVAL_CANDIDATE_LIMIT],
                }
            ),
            "merge": {
                "strategy": (
                    "parent_subquery_rrf_union_v1"
                    if isinstance(multi_hop_fusion, dict)
                    else "stable_parent_then_subquery_union_v1"
                ),
                "input_candidate_count": len(parent_memories),
                "merged_candidate_count": len(memories),
                "introduced_candidate_ids": introduced_ids,
                "duplicate_candidate_ids": duplicate_ids,
                "promoted_candidate_ids": promoted_ids,
                "outranked_candidate_ids": outranked_ids,
            },
            "rank_transitions": rank_transitions,
            "disabled_reason": disabled_reason,
        }
        return memories, bm25_scores, metadata, candidate_metadata

    def search_with_meta(
        self,
        query: str,
        *,
        scope: str | None = None,
        include_quarantined: bool = False,
        retrieval_config: dict[str, Any] | None = None,
        retrieval_provider_config: dict[str, Any] | None = None,
        allow_network_providers: bool = False,
    ) -> dict[str, Any]:
        self.init()
        parent = self._retrieval_rows(
            query,
            scope=scope,
            include_quarantined=include_quarantined,
            limit=RETRIEVAL_CANDIDATE_LIMIT,
        )
        fts_query = parent["fts_query"]
        search_terms = parent["terms"]
        raw_terms = parent["raw_terms"]
        rows = parent["rows"]
        search_mode = parent["search_mode"]
        fusion_query = parent.get("fusion_query", parent["search_query"])
        fusion_query_basis = parent.get("fusion_query_basis", parent["query_lookup"].get("selected_search_basis"))
        effective_multi_hop_config = _effective_multi_hop_retrieval_config(
            query,
            retrieval_config,
            search_mode=search_mode,
            query_lookup=parent["query_lookup"],
        )
        memories, bm25_scores, multi_hop_metadata, multi_hop_candidate_metadata = self._multi_hop_candidate_union(
            query,
            scope=scope,
            include_quarantined=include_quarantined,
            parent_rows=rows,
            parent_bm25_scores=parent["bm25_scores"],
            retrieval_config=effective_multi_hop_config,
            query_lookup=parent["query_lookup"],
        )
        base_candidate_metadata = parent.get("candidate_metadata", {})
        combined_candidate_metadata = {
            memory.id: {
                **base_candidate_metadata.get(memory.id, {}),
                **multi_hop_candidate_metadata.get(memory.id, {}),
            }
            for memory in memories
        }
        ranking = _ranking_payload(
            memories,
            query=query,
            query_terms=raw_terms,
            search_query=parent["search_query"],
            search_terms=search_terms,
            fts_query=fts_query,
            search_mode=search_mode,
            bm25_scores=bm25_scores,
            query_lookup=parent["query_lookup"],
            candidate_metadata=combined_candidate_metadata,
        )
        memories = _apply_baseline_ranking(memories, ranking)
        ranking["multi_hop"] = multi_hop_metadata
        ranking["fts_preselection"] = parent["fts_preselection"]
        ranking["chronology_support"] = parent["chronology_support"]
        ranking["history_support"] = parent["history_support"]
        ranking["update_history_support"] = parent["update_history_support"]
        ranking["update_current_support"] = parent["update_current_support"]
        ranking["support_expansion"] = parent["completion_support"]
        ranking["semantic_rescue"] = parent["semantic_rescue"]
        ranking["hybrid"] = parent["hybrid"]
        _annotate_hybrid_semantic_ranking(ranking)
        ranking["fusion_query"] = fusion_query
        ranking["fusion_query_basis"] = fusion_query_basis
        model_query = (
            fusion_query
            if parent["semantic_rescue"].get("applied") or parent["hybrid"].get("applied")
            else query
        )
        effective_retrieval_config = _effective_retrieval_config(
            retrieval_config,
            semantic_rescue_applied=bool(parent["semantic_rescue"].get("applied")),
            hybrid_backfill_applied=bool(parent["hybrid"].get("applied")),
            candidate_count=len(memories),
        )
        memories, _embedding_metadata = apply_embedding_overlay(
            model_query,
            memories,
            ranking,
            effective_retrieval_config,
            retrieval_provider_config=retrieval_provider_config,
            allow_network_providers=allow_network_providers,
        )
        memories, _reranker_metadata = apply_reranker(
            model_query,
            memories,
            ranking,
            effective_retrieval_config,
            retrieval_provider_config=retrieval_provider_config,
            allow_network_providers=allow_network_providers,
        )
        temporal = resolve_temporal_lifecycle(memories, ranking)
        if ranking.get("temporal", {}).get("fusion", {}).get("applied"):
            memories = _apply_baseline_ranking(memories, ranking)
            _annotate_hybrid_semantic_ranking(ranking)
            memory_by_id = {memory.id: memory for memory in memories}
            current_ids = {
                str(memory_id)
                for memory_id in ranking.get("temporal", {}).get("current_ids", [])
                if str(memory_id)
            }
            selected_ids = [
                str(memory_id)
                for memory_id in ranking.get("temporal", {}).get("selected_ids", [])
                if str(memory_id)
            ]
            temporal = {
                "memories": [memory for memory in memories if memory.id in current_ids],
                "selected_memories": [memory_by_id[memory_id] for memory_id in selected_ids if memory_id in memory_by_id],
                "metadata": ranking.get("temporal", {}),
            }
        return {
            "memories": memories,
            "current_memories": temporal["memories"],
            "selected_memories": temporal["selected_memories"],
            "query": query,
            "fts_query": fts_query,
            "search_mode": search_mode,
            "ranking": ranking,
            "retrieval": ranking,
            "metadata": ranking,
        }

    def queue(self, *, scope: str | None = None, status: str | None = None) -> list[MemoryRecord]:
        self.init()
        if status is not None and status not in STATUSES:
            raise ValueError(f"unsupported status: {status}")
        statuses = [status] if status else ["quarantined", "proposed"]
        placeholders = ",".join(["?"] * len(statuses))
        params: list[Any] = statuses[:]
        scope_sql = ""
        if scope:
            scope_sql = "AND (scope = ? OR scope = 'global')"
            params.append(scope)
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM memories
            WHERE status IN ({placeholders})
              {scope_sql}
            ORDER BY created_at ASC
            """,
            params,
        ).fetchall()
        return [MemoryRecord.from_row(row) for row in rows]

    def children(self, memory_id: str) -> list[MemoryRecord]:
        self.init()
        rows = self.conn.execute("SELECT * FROM memories ORDER BY created_at ASC").fetchall()
        children = []
        for row in rows:
            memory = MemoryRecord.from_row(row)
            if memory_id in memory.parents:
                children.append(memory)
        return children

    def descendants(self, memory_id: str) -> list[MemoryRecord]:
        seen: set[str] = set()
        ordered: list[MemoryRecord] = []
        stack = self.children(memory_id)
        while stack:
            memory = stack.pop(0)
            if memory.id in seen:
                continue
            seen.add(memory.id)
            ordered.append(memory)
            stack.extend(self.children(memory.id))
        return ordered

    def lineage(self, memory_id: str) -> dict[str, Any]:
        memory = self.get(memory_id)
        parents = [self.get(parent_id).to_dict() for parent_id in memory.parents if self._exists(parent_id)]
        descendants = [child.to_dict() for child in self.descendants(memory_id)]
        return {
            "memory": memory.to_dict(),
            "write_receipt": self.memory_write_receipt(memory_id),
            "write_receipts": self.memory_write_receipts(memory_id),
            "parents": parents,
            "parent_write_receipts": {
                parent_id: self.memory_write_receipt(parent_id)
                for parent_id in memory.parents
                if self._exists(parent_id)
            },
            "descendants": descendants,
        }

    def memory_write_receipt(self, memory_id: str) -> dict[str, Any]:
        self.init()
        row = self.conn.execute(
            """
            SELECT receipts.*
            FROM memory_write_receipts AS receipts
            LEFT JOIN events ON events.event_hash = receipts.event_hash
            WHERE receipts.memory_id = ?
            ORDER BY COALESCE(events.seq, 0) ASC, receipts.created_at ASC, receipts.receipt_id ASC
            LIMIT 1
            """,
            (memory_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"write receipt not found for memory: {memory_id}")
        return self._memory_write_receipt_from_row(row)

    def memory_write_receipts(self, memory_id: str) -> list[dict[str, Any]]:
        self.init()
        rows = self.conn.execute(
            """
            SELECT receipts.*
            FROM memory_write_receipts AS receipts
            LEFT JOIN events ON events.event_hash = receipts.event_hash
            WHERE receipts.memory_id = ?
            ORDER BY COALESCE(events.seq, 0) ASC, receipts.created_at ASC, receipts.receipt_id ASC
            """,
            (memory_id,),
        ).fetchall()
        return [self._memory_write_receipt_from_row(row) for row in rows]

    def _memory_write_receipt_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        treeship_statement = json.loads(row["treeship_statement_json"])
        receipt = {
            "receipt_schema": row["receipt_schema"],
            "hash_alg": row["hash_alg"],
            "merkle_alg": row["merkle_alg"],
            "receipt_id": row["receipt_id"],
            "memory_id": row["memory_id"],
            "actor_uri": row["actor_uri"],
            "session_id": row["session_id"],
            "parent_action_id": row["parent_action_id"],
            "source_uri": row["source_uri"],
            "content_digest": row["content_digest"],
            "environment_hash": row["environment_hash"],
            "event_hash": row["event_hash"],
            "merkle_root": row["merkle_root"],
            "treeship_statement": treeship_statement,
            "created_at": row["created_at"],
            "receipt_hash": row["receipt_hash"],
        }
        if isinstance(treeship_statement.get("attestation"), dict):
            receipt["treeship_attestation"] = treeship_statement["attestation"]
        return receipt

    def reject(self, memory_id: str, *, actor_id: str = "human", reason: str | None = None) -> MemoryRecord:
        self.init()
        memory = self.get(memory_id)
        prior_receipts = self.memory_write_receipts(memory_id)
        prior_receipt = prior_receipts[-1] if prior_receipts else None
        prior_merkle_root = self.current_merkle_root()
        self.conn.execute(
            "UPDATE memories SET status = 'deprecated', authority = 'none', updated_at = ? WHERE id = ?",
            (now_iso(), memory_id),
        )
        event = self._append_event(
            "REJECTED",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={"id": memory_id, "previous_status": memory.status, "reason": reason},
        )
        rejected = self.get(memory_id)
        self._append_write_receipt(
            memory_id=memory_id,
            actor_uri=actor_uri_for(actor_id),
            session_id=prior_receipt["session_id"] if prior_receipt is not None else f"session://{self.db_path.resolve()}",
            parent_action_id=prior_receipt.get("parent_action_id") if prior_receipt is not None else None,
            source_uri=prior_receipt.get("source_uri") if prior_receipt is not None else None,
            content_digest=digest_uri(rejected.content),
            environment_hash=prior_receipt["environment_hash"] if prior_receipt is not None else default_environment_hash(),
            event=event,
            created_at=event["created_at"],
            statement_kind="zerker.memory.mutation_receipt",
            predicate="memory.mutation.receipt.generated",
            subject_type="memory_mutation",
            object_updates={
                "mutation": "reject",
                "status": rejected.status,
                "authority": rejected.authority,
                "actor_id": actor_id,
                "reason": reason,
                "previous_status": memory.status,
            },
            evidence_updates={
                "prior_event_hash": event["prev_event_hash"],
                "prior_merkle_root": prior_merkle_root,
                "new_merkle_root": event["merkle_root"],
            },
            source_updates={
                "prior_receipt_id": prior_receipt["receipt_id"] if prior_receipt is not None else None,
                "prior_receipt_hash": prior_receipt["receipt_hash"] if prior_receipt is not None else None,
            },
        )
        self.conn.commit()
        return rejected

    def revoke(self, memory_id: str, *, actor_id: str = "human", reason: str | None = None) -> dict[str, Any]:
        self.init()
        root_memory = self.get(memory_id)
        prior_receipts = self.memory_write_receipts(memory_id)
        prior_receipt = prior_receipts[-1] if prior_receipts else None
        prior_merkle_root = self.current_merkle_root()
        affected = [root_memory] + self.descendants(memory_id)
        descendant_ids = [memory.id for memory in affected[1:]]
        revoked_ids: list[str] = []
        for memory in affected:
            self.conn.execute(
                "UPDATE memories SET status = 'revoked', authority = 'none', updated_at = ? WHERE id = ?",
                (now_iso(), memory.id),
            )
            revoked_ids.append(memory.id)
        event = self._append_event(
            "REVOKED",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={
                "id": memory_id,
                "previous_status": root_memory.status,
                "reason": reason,
                "revoked_ids": revoked_ids,
                "descendant_count": len(revoked_ids) - 1,
            },
        )
        revoked_root = self.get(memory_id)
        self._append_write_receipt(
            memory_id=memory_id,
            actor_uri=actor_uri_for(actor_id),
            session_id=prior_receipt["session_id"] if prior_receipt is not None else f"session://{self.db_path.resolve()}",
            parent_action_id=prior_receipt.get("parent_action_id") if prior_receipt is not None else None,
            source_uri=prior_receipt.get("source_uri") if prior_receipt is not None else None,
            content_digest=digest_uri(revoked_root.content),
            environment_hash=prior_receipt["environment_hash"] if prior_receipt is not None else default_environment_hash(),
            event=event,
            created_at=event["created_at"],
            statement_kind="zerker.memory.mutation_receipt",
            predicate="memory.mutation.receipt.generated",
            subject_type="memory_mutation",
            object_updates={
                "mutation": "revoke",
                "status": revoked_root.status,
                "authority": revoked_root.authority,
                "actor_id": actor_id,
                "reason": reason,
                "previous_status": root_memory.status,
                "revoked_ids": revoked_ids,
                "descendant_ids": descendant_ids,
                "descendant_count": len(descendant_ids),
            },
            evidence_updates={
                "prior_event_hash": event["prev_event_hash"],
                "prior_merkle_root": prior_merkle_root,
                "new_merkle_root": event["merkle_root"],
            },
            source_updates={
                "prior_receipt_id": prior_receipt["receipt_id"] if prior_receipt is not None else None,
                "prior_receipt_hash": prior_receipt["receipt_hash"] if prior_receipt is not None else None,
            },
        )
        self.conn.commit()
        return {
            "memory_id": memory_id,
            "reason": reason,
            "revoked_ids": revoked_ids,
            "descendant_count": len(revoked_ids) - 1,
        }

    def promote(self, memory_id: str, *, actor_id: str = "human") -> MemoryRecord:
        self.init()
        memory = self.get(memory_id)
        prior_receipts = self.memory_write_receipts(memory_id)
        prior_receipt = prior_receipts[-1] if prior_receipts else None
        prior_merkle_root = self.current_merkle_root()
        authority = "policy" if memory.type == "policy" else max_authority(memory.authority, "medium")
        self.conn.execute(
            "UPDATE memories SET status = 'active', trust = ?, authority = ?, updated_at = ? WHERE id = ?",
            (max(memory.trust, 0.9), authority, now_iso(), memory_id),
        )
        event = self._append_event(
            "PROMOTED",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={"id": memory_id, "authority": authority},
        )
        promoted = self.get(memory_id)
        self._append_write_receipt(
            memory_id=memory_id,
            actor_uri=actor_uri_for(actor_id),
            session_id=prior_receipt["session_id"] if prior_receipt is not None else f"session://{self.db_path.resolve()}",
            parent_action_id=prior_receipt.get("parent_action_id") if prior_receipt is not None else None,
            source_uri=prior_receipt.get("source_uri") if prior_receipt is not None else None,
            content_digest=digest_uri(promoted.content),
            environment_hash=prior_receipt["environment_hash"] if prior_receipt is not None else default_environment_hash(),
            event=event,
            created_at=event["created_at"],
            statement_kind="zerker.memory.mutation_receipt",
            predicate="memory.mutation.receipt.generated",
            subject_type="memory_mutation",
            object_updates={
                "mutation": "promote",
                "status": promoted.status,
                "authority": promoted.authority,
                "actor_id": actor_id,
            },
            evidence_updates={
                "prior_event_hash": event["prev_event_hash"],
                "prior_merkle_root": prior_merkle_root,
                "new_merkle_root": event["merkle_root"],
            },
            source_updates={
                "prior_receipt_id": prior_receipt["receipt_id"] if prior_receipt is not None else None,
                "prior_receipt_hash": prior_receipt["receipt_hash"] if prior_receipt is not None else None,
            },
        )
        self.conn.commit()
        return promoted

    def forget(self, memory_id: str, *, actor_id: str = "human") -> None:
        self.init()
        memory = self.get(memory_id)
        prior_receipts = self.memory_write_receipts(memory_id)
        prior_receipt = prior_receipts[-1] if prior_receipts else None
        prior_merkle_root = self.current_merkle_root()
        self.conn.execute(
            "UPDATE memories SET status = 'forgotten', updated_at = ? WHERE id = ?",
            (now_iso(), memory_id),
        )
        event = self._append_event(
            "FORGOTTEN",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={
                "id": memory_id,
                "content_hash": memory.content_hash,
                "previous_status": memory.status,
            },
        )
        forgotten = self.get(memory_id)
        self._append_write_receipt(
            memory_id=memory_id,
            actor_uri=actor_uri_for(actor_id),
            session_id=prior_receipt["session_id"] if prior_receipt is not None else f"session://{self.db_path.resolve()}",
            parent_action_id=prior_receipt.get("parent_action_id") if prior_receipt is not None else None,
            source_uri=prior_receipt.get("source_uri") if prior_receipt is not None else None,
            content_digest=digest_uri(forgotten.content),
            environment_hash=prior_receipt["environment_hash"] if prior_receipt is not None else default_environment_hash(),
            event=event,
            created_at=event["created_at"],
            statement_kind="zerker.memory.mutation_receipt",
            predicate="memory.mutation.receipt.generated",
            subject_type="memory_mutation",
            object_updates={
                "mutation": "forget",
                "status": forgotten.status,
                "authority": forgotten.authority,
                "actor_id": actor_id,
                "previous_status": memory.status,
            },
            evidence_updates={
                "prior_event_hash": event["prev_event_hash"],
                "prior_merkle_root": prior_merkle_root,
                "new_merkle_root": event["merkle_root"],
            },
            source_updates={
                "prior_receipt_id": prior_receipt["receipt_id"] if prior_receipt is not None else None,
                "prior_receipt_hash": prior_receipt["receipt_hash"] if prior_receipt is not None else None,
            },
        )
        self.conn.commit()

    def inject(
        self,
        task: str,
        *,
        agent_id: str,
        risk: str,
        scope: str | None = None,
        context_budget_tokens: int | None = None,
        retrieval_config: dict[str, Any] | None = None,
        retrieval_provider_config: dict[str, Any] | None = None,
        allow_network_providers: bool = False,
    ) -> dict[str, Any]:
        self.init()
        search_result = self.search_with_meta(
            task,
            scope=scope,
            include_quarantined=True,
            retrieval_config=retrieval_config,
            retrieval_provider_config=retrieval_provider_config,
            allow_network_providers=allow_network_providers,
        )
        candidates = search_result["memories"]
        current_candidates = search_result["current_memories"]
        selected_candidates = search_result.get("selected_memories", current_candidates)
        selected_candidate_ids = {memory.id for memory in selected_candidates}
        candidate_metadata_by_id = _candidate_by_id(search_result["retrieval"])
        policy_candidates = list(current_candidates)
        seen_policy_candidate_ids = {memory.id for memory in policy_candidates}
        for memory in selected_candidates:
            if memory.id in seen_policy_candidate_ids:
                continue
            policy_candidates.append(memory)
            seen_policy_candidate_ids.add(memory.id)
        injected: list[MemoryRecord] = []
        withheld: list[dict[str, str]] = []
        policy_checks: list[str] = []
        policy_decisions: list[dict[str, str]] = []
        policy_config = load_policy_config(self.policy_path or default_policy_path())
        policy_digest = f"{HASH_ALG}:{sha256_text(stable_json(policy_config.to_dict()))}"
        for memory in policy_candidates:
            candidate_metadata = candidate_metadata_by_id.get(memory.id)
            decision = decide_memory(memory, risk=risk, config=policy_config)
            policy_decisions.append(decision.to_dict())
            if decision.decision == "withhold":
                withheld_entry = {"memory_id": memory.id, "reason": decision.reason, "rule": decision.rule}
                withheld_entry.update(_overlay_receipt_fields(candidate_metadata))
                withheld.append(withheld_entry)
                continue
            if memory.id not in selected_candidate_ids:
                continue
            injected.append(memory)
            if memory.type == "policy":
                policy_checks.append(memory.id)
        retrieval = dict(search_result["retrieval"])
        retrieval["scope"] = scope
        retrieval["policy"] = {
            "engine": POLICY_ENGINE,
            "policy_digest": policy_digest,
            "authorized_ids": [memory.id for memory in injected],
            "withheld_ids": [item["memory_id"] for item in withheld],
            "decisions": policy_decisions,
        }
        packing = pack_memory_context(injected, retrieval=retrieval, max_tokens=context_budget_tokens)
        injected = packing["memories"]
        policy_checks = [memory.id for memory in injected if memory.type == "policy"]
        memory_by_id = {memory.id: memory for memory in candidates}
        packing["metadata"]["memory_type_summary"] = {
            "instruction_types": list(INSTRUCTION_MEMORY_TYPES),
            "recall_types": list(RECALL_MEMORY_TYPES),
            "injected_ids_by_type": _memory_ids_by_type(injected),
            "withheld_ids_by_type": _memory_ids_by_type_from_ids(
                [item["memory_id"] for item in withheld],
                memory_by_id=memory_by_id,
            ),
            "budget_dropped_ids_by_type": _memory_ids_by_type_from_ids(
                [str(item["memory_id"]) for item in packing["metadata"]["budget_dropped"]],
                memory_by_id=memory_by_id,
            ),
        }
        retrieval["packing"] = packing["metadata"]
        action_id = "act_" + uuid.uuid4().hex[:16]
        root = self.current_merkle_root()
        receipt_created_at = now_iso()
        temporal_projection = self._project_temporal_state(candidates, timestamp=receipt_created_at)
        temporal_graph = temporal_projection["temporal_graph"]
        temporal_metadata = retrieval.get("temporal")
        if isinstance(temporal_metadata, dict):
            withheld_ids = [
                str(item["memory_id"])
                for item in withheld
                if str(item.get("memory_id"))
            ]
            budget_dropped_ids = [
                str(item["memory_id"])
                for item in packing["metadata"]["budget_dropped"]
                if str(item.get("memory_id"))
            ]
            temporal_metadata["temporal_projection_at"] = receipt_created_at
            temporal_metadata["temporal_graph"] = temporal_graph
            temporal_metadata["history_memory_ids"] = temporal_projection["history_memory_ids"]
            temporal_metadata["current_memory_ids"] = temporal_projection["current_memory_ids"]
            temporal_metadata["resolved_current_memory_ids"] = temporal_projection["resolved_current_memory_ids"]
            temporal_metadata["dropped_current_memory_ids"] = temporal_projection["dropped_current_memory_ids"]
            temporal_metadata["abstained_current_memory_ids"] = temporal_projection["abstained_current_memory_ids"]
            temporal_metadata["future_memory_ids"] = temporal_projection["future_memory_ids"]
            temporal_metadata["superseded_memory_ids"] = temporal_projection["superseded_memory_ids"]
            temporal_metadata["unlearned_memory_ids"] = temporal_projection["unlearned_memory_ids"]
            temporal_metadata["learned_memory_ids"] = temporal_projection["learned_memory_ids"]
            temporal_metadata["history_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_projection["history_memory_ids"],
            )
            temporal_metadata["current_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_projection["current_memory_ids"],
            )
            temporal_metadata["future_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_projection["future_memory_ids"],
            )
            temporal_metadata["superseded_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_projection["superseded_memory_ids"],
            )
            temporal_metadata["unlearned_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_projection["unlearned_memory_ids"],
            )
            temporal_metadata["learned_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_projection["learned_memory_ids"],
            )
            temporal_metadata["selected_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_metadata.get("selected_ids", []),
            )
            temporal_metadata["abstained_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_projection["abstained_current_memory_ids"],
            )
            temporal_metadata["dropped_current_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                temporal_projection["dropped_current_memory_ids"],
            )
            temporal_metadata["injected_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                [memory.id for memory in injected],
            )
            temporal_metadata["withheld_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                withheld_ids,
            )
            temporal_metadata["budget_dropped_temporal_graph"] = _select_temporal_graph_subset(
                temporal_graph,
                budget_dropped_ids,
            )
        memory_tree = self.memory_tree(candidates, scope="retrieved")
        injected_memory_proofs = {
            memory.id: memory_tree["proofs"][memory.id]
            for memory in injected
            if memory.id in memory_tree["proofs"]
        }
        injected_write_receipts = {
            memory.id: self.memory_write_receipt(memory.id)
            for memory in injected
            if self._has_write_receipt(memory.id)
        }
        receipt = {
            "receipt_schema": RECEIPT_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "action_id": action_id,
            "agent_id": agent_id,
            "task": task,
            "task_hash": sha256_text(task),
            "risk": risk,
            "retrieved_memory_ids": [m.id for m in candidates],
            "retrieval": retrieval,
            "injected_memory_ids": [m.id for m in injected],
            "withheld": withheld,
            "policy_checks": policy_checks,
            "policy_engine": POLICY_ENGINE,
            "policy_decisions": policy_decisions,
            "memory_tree": memory_tree,
            "injected_memory_proofs": injected_memory_proofs,
            "injected_memory_write_receipts": injected_write_receipts,
            "merkle_root": root,
            "created_at": receipt_created_at,
        }
        from .runner import build_context, memory_context_commitment

        context_receipt = dict(receipt)
        context_receipt["memories"] = [memory.to_dict() for memory in injected]
        context = build_context(context_receipt)
        context_commitment = memory_context_commitment(context)
        retrieval["context_commitment"] = context_commitment
        receipt["memory_context"] = context_commitment
        self.conn.execute(
            """
            INSERT INTO receipts (
              action_id, receipt_schema, hash_alg, merkle_alg, agent_id, task, task_hash, risk, retrieved_ids_json,
              retrieval_json, injected_ids_json, withheld_json, policy_checks_json, memory_tree_json, merkle_root, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                RECEIPT_SCHEMA,
                HASH_ALG,
                MERKLE_ALG,
                agent_id,
                task,
                receipt["task_hash"],
                risk,
                stable_json(receipt["retrieved_memory_ids"]),
                stable_json(receipt["retrieval"]),
                stable_json(receipt["injected_memory_ids"]),
                stable_json(withheld),
                stable_json(policy_checks),
                stable_json(memory_tree),
                root,
                receipt["created_at"],
            ),
        )
        self._append_event(
            "INJECTED",
            actor_id=agent_id,
            action_id=action_id,
            payload=receipt,
        )
        self.conn.commit()
        receipt["memories"] = [m.to_dict() for m in injected]
        return receipt

    def why(self, action_id: str) -> dict[str, Any]:
        self.init()
        row = self.conn.execute("SELECT * FROM receipts WHERE action_id = ?", (action_id,)).fetchone()
        if row is None:
            raise KeyError(f"action receipt not found: {action_id}")
        injected_ids = json.loads(row["injected_ids_json"])
        retrieved_ids = json.loads(row["retrieved_ids_json"])
        withheld = json.loads(row["withheld_json"])
        memory_tree = json.loads(row["memory_tree_json"] or "{}")
        retrieval = json.loads(row["retrieval_json"])
        policy = retrieval.get("policy") if isinstance(retrieval.get("policy"), dict) else {}
        injected_memory_proofs = {
            memory_id: memory_tree.get("proofs", {}).get(memory_id)
            for memory_id in injected_ids
            if memory_tree.get("proofs", {}).get(memory_id)
        }
        receipt = {
            "receipt_schema": row["receipt_schema"],
            "hash_alg": row["hash_alg"],
            "merkle_alg": row["merkle_alg"],
            "action_id": row["action_id"],
            "agent_id": row["agent_id"],
            "task": row["task"],
            "task_hash": row["task_hash"],
            "risk": row["risk"],
            "retrieved_memory_ids": retrieved_ids,
            "injected_memory_ids": injected_ids,
            "withheld_memory_ids": [item["memory_id"] for item in withheld],
            "injected": [self.get(mid).to_dict() for mid in injected_ids],
            "withheld": withheld,
            "policy_checks": json.loads(row["policy_checks_json"]),
            "policy_engine": POLICY_ENGINE,
            "policy_decisions": policy.get("decisions", []),
            "retrieval": retrieval,
            "memory_tree": memory_tree,
            "injected_memory_proofs": injected_memory_proofs,
            "injected_memory_write_receipts": {
                memory_id: self.memory_write_receipt(memory_id)
                for memory_id in injected_ids
                if self._has_write_receipt(memory_id)
            },
            "merkle_root": row["merkle_root"],
            "created_at": row["created_at"],
        }
        context_commitment = retrieval.get("context_commitment")
        if isinstance(context_commitment, Mapping):
            receipt["memory_context"] = dict(context_commitment)
        return receipt

    def receipt(self, action_id: str) -> dict[str, Any]:
        return self.why(action_id)

    def receipt_bundle(self, action_id: str, *, compact: bool = True) -> dict[str, Any]:
        self.init()
        receipt = self.why(action_id)
        action_row = self.conn.execute(
            "SELECT seq FROM events WHERE action_id = ? ORDER BY seq LIMIT 1",
            (action_id,),
        ).fetchone()
        if action_row is None:
            raise KeyError(f"action event not found: {action_id}")
        event_rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE seq < ?
            ORDER BY seq
            """,
            (action_row["seq"],),
        ).fetchall()
        events = [
            {
                "seq": row["seq"],
                "event_schema": EVENT_SCHEMA,
                "event_type": row["event_type"],
                "memory_id": row["memory_id"],
                "action_id": row["action_id"],
                "actor_id": row["actor_id"],
                "payload_json": row["payload_json"],
                "payload_hash": row["payload_hash"],
                "prev_event_hash": row["prev_event_hash"],
                "event_hash": row["event_hash"],
                "merkle_root": row["merkle_root"],
                "created_at": row["created_at"],
            }
            for row in event_rows
        ]
        event_hashes = [event["event_hash"] for event in events]
        supporting_memory_ids = receipt["retrieved_memory_ids"]
        supporting_memories = [self.get(mid).to_dict() for mid in supporting_memory_ids if self._exists(mid)]
        supporting_write_receipts = {
            mid: self.memory_write_receipt(mid)
            for mid in supporting_memory_ids
            if self._exists(mid) and self._has_write_receipt(mid)
        }
        event_log_root = merkle_root(event_hashes)
        bundle: dict[str, Any] = {
            "bundle_schema": BUNDLE_SCHEMA if compact else BUNDLE_SCHEMA_V1,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "created_at": now_iso(),
            "action_id": action_id,
            "receipt": receipt,
            "supporting_memory_ids": supporting_memory_ids,
            "supporting_memories": supporting_memories,
            "supporting_memory_write_receipts": supporting_write_receipts,
        }
        memory_tree_root = receipt.get("memory_tree", {}).get("root")
        memory_tree_verified = (
            self.verify_memory_tree(receipt.get("memory_tree", {})) if receipt.get("memory_tree") else None
        )
        if not compact:
            bundle["supporting_events"] = events
            bundle["proof"] = {
                "event_count": len(events),
                "computed_merkle_root": event_log_root,
                "receipt_merkle_root": receipt["merkle_root"],
                "memory_tree_root": memory_tree_root,
                "memory_tree_verified": memory_tree_verified,
                "verified": event_log_root == receipt["merkle_root"],
            }
            bundle["bundle_hash"] = sha256_text(stable_json(bundle))
            return bundle

        event_index_by_hash = {event_hash: index for index, event_hash in enumerate(event_hashes)}
        witness_event_hashes = {
            str(write_receipt.get("event_hash") or "")
            for write_receipt in supporting_write_receipts.values()
        }
        witness_event_hashes.discard("")
        if event_hashes:
            witness_event_hashes.add(event_hashes[-1])
        missing_event_hashes = sorted(witness_event_hashes - set(event_index_by_hash))
        if missing_event_hashes:
            raise ValueError(
                "supporting write event not found before action: " + ", ".join(missing_event_hashes)
            )

        event_witnesses = []
        for event_hash in sorted(witness_event_hashes, key=event_index_by_hash.__getitem__):
            index = event_index_by_hash[event_hash]
            row = event_rows[index]
            event_witnesses.append(
                {
                    "leaf_index": index,
                    "event": {
                        "seq": row["seq"],
                        "event_schema": EVENT_SCHEMA,
                        "hash_alg": HASH_ALG,
                        "event_type": row["event_type"],
                        "memory_id": row["memory_id"],
                        "action_id": row["action_id"],
                        "actor_id": row["actor_id"],
                        "payload_hash": row["payload_hash"],
                        "prev_event_hash": row["prev_event_hash"],
                        "event_hash": row["event_hash"],
                        "created_at": row["created_at"],
                    },
                    "proof": merkle_proof(event_hashes, index),
                }
            )

        bundle["event_log"] = {
            "event_count": len(events),
            "first_seq": events[0]["seq"] if events else None,
            "last_seq": events[-1]["seq"] if events else None,
            "last_event_hash": event_hashes[-1] if event_hashes else None,
            "merkle_root": event_log_root,
        }
        bundle["event_witnesses"] = event_witnesses
        bundle["proof"] = {
            "event_count": len(events),
            "event_witness_count": len(event_witnesses),
            "event_log_merkle_root": event_log_root,
            "receipt_merkle_root": receipt["merkle_root"],
            "memory_tree_root": memory_tree_root,
            "memory_tree_verified": memory_tree_verified,
            "event_witnesses_verified": event_log_root == receipt["merkle_root"],
            "verified": event_log_root == receipt["merkle_root"],
        }
        bundle["bundle_hash"] = sha256_text(stable_json(bundle))
        return bundle

    def verify_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        without_hash = dict(bundle)
        without_hash.pop("bundle_hash", None)
        computed_bundle_hash = sha256_text(stable_json(without_hash))
        receipt = bundle.get("receipt", {})
        if not isinstance(receipt, Mapping):
            receipt = {}
        events = bundle.get("supporting_events", [])
        event_log = bundle.get("event_log", {})
        supporting_memory_ids = bundle.get("supporting_memory_ids", [])
        proof = bundle.get("proof", {})
        computed_merkle_root = (
            merkle_root(
                [event.get("event_hash", "") for event in events if isinstance(event, Mapping)]
            )
            if bundle.get("bundle_schema") == BUNDLE_SCHEMA_V1 and isinstance(events, list)
            else event_log.get("merkle_root")
            if isinstance(event_log, Mapping)
            else None
        )
        result = {
            "ok": True,
            "bundle_schema": bundle.get("bundle_schema"),
            "action_id": bundle.get("action_id"),
            "bundle_hash": bundle.get("bundle_hash"),
            "computed_bundle_hash": computed_bundle_hash,
            "receipt_merkle_root": receipt.get("merkle_root"),
            "computed_merkle_root": computed_merkle_root,
            "event_count": len(events)
            if bundle.get("bundle_schema") == BUNDLE_SCHEMA_V1 and isinstance(events, list)
            else event_log.get("event_count")
            if isinstance(event_log, Mapping)
            else 0,
            "event_witness_count": len(bundle.get("event_witnesses", []))
            if isinstance(bundle.get("event_witnesses"), list)
            else 0,
            "event_witnesses_verified": None,
            "proof_event_count": proof.get("event_count") if isinstance(proof, dict) else None,
            "proof_verified": proof.get("verified") if isinstance(proof, dict) else None,
            "memory_tree_verified": self.verify_memory_tree(receipt.get("memory_tree", {})) if receipt.get("memory_tree") else None,
            "supporting_write_receipt_count": 0,
            "verified_supporting_write_receipt_count": 0,
            "supporting_provenance_verified": True,
            "supporting_provenance_receipts": [],
            "attestation_artifacts": [],
            "trusted_provenance_verified": True,
            "semantic_truth_guaranteed": False,
        }
        try:
            core_verification = validate_receipt_bundle_core(bundle)
            result.update(core_verification)
            if receipt.get("memory_tree") and not self.verify_memory_tree(receipt["memory_tree"]):
                raise ValueError("bundle memory_tree verification failed")
            if receipt.get("memory_tree") and proof.get("memory_tree_verified") is not True:
                raise ValueError("bundle proof memory_tree_verified mismatch")
            if not isinstance(supporting_memory_ids, list):
                raise ValueError("bundle supporting_memory_ids is invalid")

            supporting_receipts = bundle.get("supporting_memory_write_receipts")
            if supporting_receipts is None:
                supporting_receipts = {}
            if not isinstance(supporting_receipts, dict):
                raise ValueError("bundle supporting_memory_write_receipts is invalid")

            result["supporting_write_receipt_count"] = len(supporting_receipts)
            for memory_id in sorted(supporting_receipts):
                if memory_id not in supporting_memory_ids:
                    raise ValueError("bundle supporting write receipt key missing from supporting_memory_ids")
                supporting_receipt = supporting_receipts[memory_id]
                if not isinstance(supporting_receipt, dict):
                    raise ValueError(f"bundle supporting write receipt for {memory_id} is invalid")
                if supporting_receipt.get("memory_id") != memory_id:
                    raise ValueError("bundle supporting write receipt memory_id mismatch")
                verification = self.verify_memory_write_receipt(supporting_receipt)
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
                        "new_merkle_root": statement_evidence.get(
                            "new_merkle_root",
                            supporting_receipt.get("merkle_root"),
                        ),
                        "treeship_artifact_id": attestation.get("artifact_id") if isinstance(attestation, dict) else None,
                        "trusted_provenance_verified": True,
                        "semantic_truth_guaranteed": bool(verification.get("semantic_truth_guaranteed")),
                    }
                )
                if isinstance(attestation, dict):
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
                if not isinstance(memory, dict):
                    raise ValueError("bundle supporting memory entry is invalid")
                memory_id = memory.get("id")
                if not isinstance(memory_id, str) or not memory_id:
                    raise ValueError("bundle supporting memory id is invalid")
                if memory_id not in supporting_memory_ids:
                    raise ValueError("bundle supporting memory id missing from supporting_memory_ids")
                if memory_id in seen_supporting_memory_ids:
                    raise ValueError("bundle supporting memory id is duplicated")
                seen_supporting_memory_ids.add(memory_id)
        except (KeyError, ValueError) as exc:
            result["ok"] = False
            result["supporting_provenance_verified"] = False
            result["trusted_provenance_verified"] = False
            result["error"] = str(exc)
        else:
            result["supporting_provenance_verified"] = (
                result["verified_supporting_write_receipt_count"] == result["supporting_write_receipt_count"]
            )
            result["trusted_provenance_verified"] = bool(result["ok"] and result["supporting_provenance_verified"])
        return result

    def snapshot(self) -> dict[str, Any]:
        self.init()
        memories = [
            MemoryRecord.from_row(row).to_dict()
            for row in self.conn.execute("SELECT * FROM memories ORDER BY created_at, id").fetchall()
        ]
        events = []
        for row in self.conn.execute("SELECT * FROM events ORDER BY seq").fetchall():
            events.append(
                {
                    "seq": row["seq"],
                    "event_schema": EVENT_SCHEMA,
                    "event_type": row["event_type"],
                    "memory_id": row["memory_id"],
                    "action_id": row["action_id"],
                    "actor_id": row["actor_id"],
                    "payload_json": row["payload_json"],
                    "payload_hash": row["payload_hash"],
                    "prev_event_hash": row["prev_event_hash"],
                    "event_hash": row["event_hash"],
                    "merkle_root": row["merkle_root"],
                    "created_at": row["created_at"],
                }
            )
        receipts = [
            self.why(row["action_id"])
            for row in self.conn.execute("SELECT action_id FROM receipts ORDER BY created_at, action_id").fetchall()
        ]
        write_receipts = [
            self._memory_write_receipt_from_row(row)
            for row in self.conn.execute(
                """
                SELECT receipts.*
                FROM memory_write_receipts AS receipts
                LEFT JOIN events ON events.event_hash = receipts.event_hash
                ORDER BY COALESCE(events.seq, 0) ASC, receipts.created_at ASC, receipts.receipt_id ASC
                """
            ).fetchall()
        ]
        payload = {
            "snapshot_schema": SNAPSHOT_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "created_at": now_iso(),
            "db_path": str(self.db_path),
            "merkle_root": self.current_merkle_root(),
            "memory_count": len(memories),
            "event_count": len(events),
            "receipt_count": len(receipts),
            "write_receipt_count": len(write_receipts),
            "memories": memories,
            "events": events,
            "receipts": receipts,
            "write_receipts": write_receipts,
        }
        payload["snapshot_hash"] = sha256_text(stable_json(payload))
        return payload

    def checkpoint_session(
        self,
        session_id: str,
        *,
        actor_id: str,
        scope: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        self.init()
        checkpoint_id = "chk_" + uuid.uuid4().hex[:16]
        prior_merkle_root = self.current_merkle_root()
        active_memories = self.list_memories(scope=scope, status="active", limit=10_000)
        memory_tree = self.memory_tree(active_memories, scope="session-checkpoint")
        memory_ids_by_type = _memory_ids_by_type(active_memories)
        snapshot = self.snapshot()
        payload = {
            "schema": SESSION_CHECKPOINT_SCHEMA,
            "checkpoint_id": checkpoint_id,
            "session_id": session_id,
            "scope": scope,
            "summary": summary,
            "prior_merkle_root": prior_merkle_root,
            "snapshot_hash": snapshot["snapshot_hash"],
            "snapshot_merkle_root": snapshot["merkle_root"],
            "snapshot_memory_count": snapshot["memory_count"],
            "snapshot_event_count": snapshot["event_count"],
            "active_memory_ids": [memory.id for memory in active_memories],
            "memory_count": len(active_memories),
            "memory_tree_root": memory_tree["root"],
            "memory_tree_leaf_count": memory_tree["leaf_count"],
            "memory_type_summary": {
                "instruction_types": list(INSTRUCTION_MEMORY_TYPES),
                "recall_types": list(RECALL_MEMORY_TYPES),
                "active_ids_by_type": memory_ids_by_type,
                "active_counts_by_type": {
                    memory_type: len(memory_ids_by_type.get(memory_type, []))
                    for memory_type in sorted(MEMORY_TYPES)
                },
            },
        }
        event = self._append_event(
            "SESSION_CHECKPOINTED",
            actor_id=actor_id,
            payload=payload,
        )
        self.conn.commit()
        return self._session_checkpoint_from_event_row(
            self.conn.execute("SELECT * FROM events WHERE event_hash = ?", (event["event_hash"],)).fetchone()
        )

    def start_session(
        self,
        session_id: str,
        *,
        actor_id: str,
        scope: str | None = None,
        summary: str | None = None,
        context_budget_tokens: int | None = None,
    ) -> dict[str, Any]:
        self.init()
        if context_budget_tokens is not None and context_budget_tokens < 0:
            raise ValueError("context budget hint cannot be negative")
        session_start_id = "sst_" + uuid.uuid4().hex[:16]
        prior_merkle_root = self.current_merkle_root()
        active_memories = self.list_memories(scope=scope, status="active", limit=10_000)
        memory_tree = self.memory_tree(active_memories, scope="session-start")
        memory_ids_by_type = _memory_ids_by_type(active_memories)
        snapshot = self.snapshot()
        payload = {
            "schema": SESSION_START_SCHEMA,
            "session_start_id": session_start_id,
            "session_id": session_id,
            "scope": scope,
            "summary": summary,
            "prior_merkle_root": prior_merkle_root,
            "snapshot_hash": snapshot["snapshot_hash"],
            "snapshot_merkle_root": snapshot["merkle_root"],
            "snapshot_memory_count": snapshot["memory_count"],
            "snapshot_event_count": snapshot["event_count"],
            "active_memory_ids": [memory.id for memory in active_memories],
            "memory_count": len(active_memories),
            "memory_tree_root": memory_tree["root"],
            "memory_tree_leaf_count": memory_tree["leaf_count"],
            "memory_type_summary": {
                "instruction_types": list(INSTRUCTION_MEMORY_TYPES),
                "recall_types": list(RECALL_MEMORY_TYPES),
                "active_ids_by_type": memory_ids_by_type,
                "active_counts_by_type": {
                    memory_type: len(memory_ids_by_type.get(memory_type, []))
                    for memory_type in sorted(MEMORY_TYPES)
                },
            },
        }
        if context_budget_tokens is not None:
            payload["context_budget_tokens"] = int(context_budget_tokens)
        event = self._append_event(
            "SESSION_STARTED",
            actor_id=actor_id,
            payload=payload,
        )
        self.conn.commit()
        return self._session_start_from_event_row(
            self.conn.execute("SELECT * FROM events WHERE event_hash = ?", (event["event_hash"],)).fetchone()
        )

    def end_session(
        self,
        session_id: str,
        *,
        actor_id: str,
        scope: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        self.init()
        session_end_id = "sed_" + uuid.uuid4().hex[:16]
        prior_merkle_root = self.current_merkle_root()
        active_memories = self.list_memories(scope=scope, status="active", limit=10_000)
        memory_tree = self.memory_tree(active_memories, scope="session-end")
        memory_ids_by_type = _memory_ids_by_type(active_memories)
        snapshot = self.snapshot()
        payload = {
            "schema": SESSION_END_SCHEMA,
            "session_end_id": session_end_id,
            "session_id": session_id,
            "scope": scope,
            "summary": summary,
            "prior_merkle_root": prior_merkle_root,
            "snapshot_hash": snapshot["snapshot_hash"],
            "snapshot_merkle_root": snapshot["merkle_root"],
            "snapshot_memory_count": snapshot["memory_count"],
            "snapshot_event_count": snapshot["event_count"],
            "active_memory_ids": [memory.id for memory in active_memories],
            "memory_count": len(active_memories),
            "memory_tree_root": memory_tree["root"],
            "memory_tree_leaf_count": memory_tree["leaf_count"],
            "memory_type_summary": {
                "instruction_types": list(INSTRUCTION_MEMORY_TYPES),
                "recall_types": list(RECALL_MEMORY_TYPES),
                "active_ids_by_type": memory_ids_by_type,
                "active_counts_by_type": {
                    memory_type: len(memory_ids_by_type.get(memory_type, []))
                    for memory_type in sorted(MEMORY_TYPES)
                },
            },
        }
        event = self._append_event(
            "SESSION_ENDED",
            actor_id=actor_id,
            payload=payload,
        )
        self.conn.commit()
        return self._session_end_from_event_row(
            self.conn.execute("SELECT * FROM events WHERE event_hash = ?", (event["event_hash"],)).fetchone()
        )

    def snapshot_session(
        self,
        session_id: str,
        *,
        actor_id: str,
        scope: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        self.init()
        session_snapshot_id = "ssn_" + uuid.uuid4().hex[:16]
        prior_merkle_root = self.current_merkle_root()
        active_memories = self.list_memories(scope=scope, status="active", limit=10_000)
        memory_tree = self.memory_tree(active_memories, scope="session-snapshot")
        memory_ids_by_type = _memory_ids_by_type(active_memories)
        snapshot = self.snapshot()
        payload = {
            "schema": SESSION_SNAPSHOT_SCHEMA,
            "session_snapshot_id": session_snapshot_id,
            "session_id": session_id,
            "scope": scope,
            "summary": summary,
            "prior_merkle_root": prior_merkle_root,
            "snapshot_hash": snapshot["snapshot_hash"],
            "snapshot_merkle_root": snapshot["merkle_root"],
            "snapshot_memory_count": snapshot["memory_count"],
            "snapshot_event_count": snapshot["event_count"],
            "snapshot_receipt_count": snapshot["receipt_count"],
            "snapshot_write_receipt_count": snapshot["write_receipt_count"],
            "active_memory_ids": [memory.id for memory in active_memories],
            "memory_count": len(active_memories),
            "memory_tree_root": memory_tree["root"],
            "memory_tree_leaf_count": memory_tree["leaf_count"],
            "memory_type_summary": {
                "instruction_types": list(INSTRUCTION_MEMORY_TYPES),
                "recall_types": list(RECALL_MEMORY_TYPES),
                "active_ids_by_type": memory_ids_by_type,
                "active_counts_by_type": {
                    memory_type: len(memory_ids_by_type.get(memory_type, []))
                    for memory_type in sorted(MEMORY_TYPES)
                },
            },
        }
        event = self._append_event(
            "SESSION_SNAPSHOTTED",
            actor_id=actor_id,
            payload=payload,
        )
        self.conn.execute(
            """
            INSERT INTO session_snapshot_payloads (
              session_snapshot_id, event_hash, snapshot_hash, snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_snapshot_id,
                event["event_hash"],
                snapshot["snapshot_hash"],
                stable_json(snapshot),
                now_iso(),
            ),
        )
        self.conn.commit()
        return self._session_snapshot_from_event_row(
            self.conn.execute("SELECT * FROM events WHERE event_hash = ?", (event["event_hash"],)).fetchone()
        )

    def restore_snapshot(self, snapshot: dict[str, Any], *, actor_id: str = "snapshot_restore") -> dict[str, Any]:
        self.init()
        self._validate_snapshot(snapshot)
        existing = self.conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM memories) AS memory_count,
              (SELECT COUNT(*) FROM events) AS event_count,
              (SELECT COUNT(*) FROM receipts) AS receipt_count,
              (SELECT COUNT(*) FROM memory_write_receipts) AS write_receipt_count
            """
        ).fetchone()
        if existing["memory_count"] or existing["event_count"] or existing["receipt_count"] or existing["write_receipt_count"]:
            raise ValueError("restore requires an empty memory store")
        prior_merkle_root = self.current_merkle_root()

        for memory in snapshot["memories"]:
            self.conn.execute(
                """
                INSERT INTO memories (
                  id, type, content, scope, source_kind, trust, authority, status,
                  parents_json, labels_json, created_at, updated_at, expires_at, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory["id"],
                    memory["type"],
                    memory["content"],
                    memory["scope"],
                    memory["source_kind"],
                    memory["trust"],
                    memory["authority"],
                    memory["status"],
                    stable_json(memory.get("parents", [])),
                    stable_json(memory.get("labels", [])),
                    memory["created_at"],
                    memory["updated_at"],
                    memory.get("expires_at"),
                    memory["content_hash"],
                ),
            )
            self.conn.execute(
                "INSERT INTO memories_fts (id, content, labels) VALUES (?, ?, ?)",
                (memory["id"], memory["content"], " ".join(memory.get("labels", []))),
            )

        for event in snapshot["events"]:
            self.conn.execute(
                """
                INSERT INTO events (
                  seq, event_type, memory_id, action_id, actor_id, payload_json, payload_hash,
                  prev_event_hash, event_hash, merkle_root, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["seq"],
                    event["event_type"],
                    event.get("memory_id"),
                    event.get("action_id"),
                    event["actor_id"],
                    event["payload_json"],
                    event["payload_hash"],
                    event["prev_event_hash"],
                    event["event_hash"],
                    event["merkle_root"],
                    event["created_at"],
                ),
            )

        for receipt in snapshot["receipts"]:
            self.conn.execute(
                """
                INSERT INTO receipts (
                  action_id, receipt_schema, hash_alg, merkle_alg, agent_id, task, task_hash, risk, retrieved_ids_json,
                  retrieval_json, injected_ids_json, withheld_json, policy_checks_json, memory_tree_json, merkle_root, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt["action_id"],
                    receipt["receipt_schema"],
                    receipt["hash_alg"],
                    receipt["merkle_alg"],
                    receipt["agent_id"],
                    receipt["task"],
                    receipt["task_hash"],
                    receipt["risk"],
                    stable_json(receipt["retrieved_memory_ids"]),
                    stable_json(receipt.get("retrieval", {})),
                    stable_json(receipt["injected_memory_ids"]),
                    stable_json(receipt.get("withheld", [])),
                    stable_json(receipt["policy_checks"]),
                    stable_json(receipt.get("memory_tree", {})),
                    receipt["merkle_root"],
                    receipt["created_at"],
                ),
            )

        for write_receipt in snapshot.get("write_receipts", []):
            self.conn.execute(
                """
                INSERT INTO memory_write_receipts (
                  receipt_id, receipt_schema, hash_alg, merkle_alg, memory_id, actor_uri, session_id,
                  parent_action_id, source_uri, content_digest, environment_hash, event_hash, merkle_root,
                  treeship_statement_json, created_at, receipt_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    write_receipt["receipt_id"],
                    write_receipt["receipt_schema"],
                    write_receipt["hash_alg"],
                    write_receipt["merkle_alg"],
                    write_receipt["memory_id"],
                    write_receipt["actor_uri"],
                    write_receipt["session_id"],
                    write_receipt.get("parent_action_id"),
                    write_receipt.get("source_uri"),
                    write_receipt["content_digest"],
                    write_receipt["environment_hash"],
                    write_receipt["event_hash"],
                    write_receipt["merkle_root"],
                    stable_json(write_receipt["treeship_statement"]),
                    write_receipt["created_at"],
                    write_receipt["receipt_hash"],
                ),
            )

        self.conn.commit()
        restore_receipt = self._restore_snapshot_receipt(
            snapshot,
            actor_id=actor_id,
            prior_merkle_root=prior_merkle_root,
            new_merkle_root=self.current_merkle_root(),
        )
        return {
            "ok": True,
            "snapshot_hash": snapshot["snapshot_hash"],
            "merkle_root": self.current_merkle_root(),
            "memory_count": snapshot["memory_count"],
            "event_count": snapshot["event_count"],
            "receipt_count": snapshot["receipt_count"],
            "write_receipt_count": snapshot.get("write_receipt_count", len(snapshot.get("write_receipts", []))),
            "receipt": restore_receipt,
        }

    def soft_delete_session_snapshot_payload(
        self,
        session_snapshot_id: str,
        *,
        actor_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        self.init()
        snapshot_event_row = self.conn.execute(
            """
            SELECT events.*
            FROM events
            INNER JOIN session_snapshot_payloads
              ON session_snapshot_payloads.event_hash = events.event_hash
            WHERE session_snapshot_payloads.session_snapshot_id = ?
              AND events.event_type = 'SESSION_SNAPSHOTTED'
            """,
            (session_snapshot_id,),
        ).fetchone()
        if snapshot_event_row is None:
            raise KeyError(f"session snapshot payload not found: {session_snapshot_id}")
        payload_row = self.conn.execute(
            "SELECT * FROM session_snapshot_payloads WHERE session_snapshot_id = ?",
            (session_snapshot_id,),
        ).fetchone()
        if payload_row is None:
            raise KeyError(f"session snapshot payload not found: {session_snapshot_id}")
        if payload_row["deleted_at"]:
            return self._session_snapshot_from_event_row(snapshot_event_row)

        payload = json.loads(snapshot_event_row["payload_json"])
        deleted_reason = reason or "manual-soft-delete"
        retention_event = self._append_event(
            "SESSION_SNAPSHOT_PAYLOAD_SOFT_DELETED",
            actor_id=actor_id,
            payload={
                "schema": SESSION_SNAPSHOT_RETENTION_SCHEMA,
                "session_snapshot_id": session_snapshot_id,
                "session_id": payload["session_id"],
                "scope": payload.get("scope"),
                "summary": payload.get("summary"),
                "snapshot_hash": payload["snapshot_hash"],
                "prior_merkle_root": self.current_merkle_root(),
                "deleted_reason": deleted_reason,
            },
        )
        self.conn.execute(
            """
            UPDATE session_snapshot_payloads
            SET deleted_at = ?, deleted_by = ?, deleted_reason = ?, deleted_event_hash = ?
            WHERE session_snapshot_id = ?
            """,
            (
                retention_event["created_at"],
                actor_id,
                deleted_reason,
                retention_event["event_hash"],
                session_snapshot_id,
            ),
        )
        self.conn.commit()
        return self._session_snapshot_from_event_row(snapshot_event_row)

    def prune_session_snapshot_payloads(
        self,
        session_id: str,
        *,
        actor_id: str,
        scope: str | None = None,
        keep_latest: int = 1,
        reason: str | None = None,
    ) -> dict[str, Any]:
        self.init()
        if keep_latest < 0:
            raise ValueError("keep_latest must be >= 0")

        snapshots_before = self.session_snapshots(session_id=session_id, scope=scope, limit=10_000)
        available_before_snapshots = [
            snapshot for snapshot in snapshots_before if snapshot.get("payload_status") == "available"
        ]
        already_soft_deleted_snapshot_ids = [
            snapshot["session_snapshot_id"]
            for snapshot in snapshots_before
            if snapshot.get("payload_status") == "soft_deleted"
        ]
        kept_snapshot_ids = [
            snapshot["session_snapshot_id"]
            for snapshot in available_before_snapshots[:keep_latest]
        ]
        prune_reason = reason or "retention-prune-keep-latest"
        pruned_snapshots = [
            self.soft_delete_session_snapshot_payload(
                snapshot["session_snapshot_id"],
                actor_id=actor_id,
                reason=prune_reason,
            )
            for snapshot in available_before_snapshots[keep_latest:]
        ]
        snapshots_after = self.session_snapshots(session_id=session_id, scope=scope, limit=10_000)
        available_after = sum(1 for snapshot in snapshots_after if snapshot.get("payload_status") == "available")
        soft_deleted_after = sum(1 for snapshot in snapshots_after if snapshot.get("payload_status") == "soft_deleted")
        return {
            "ok": True,
            "schema": "zerker.session_snapshot_prune.v1",
            "session_id": session_id,
            "scope": scope,
            "actor_id": actor_id,
            "keep_latest": keep_latest,
            "reason": prune_reason,
            "available_before": len(available_before_snapshots),
            "available_after": available_after,
            "soft_deleted_before": len(already_soft_deleted_snapshot_ids),
            "soft_deleted_after": soft_deleted_after,
            "kept_snapshot_ids": kept_snapshot_ids,
            "already_soft_deleted_snapshot_ids": already_soft_deleted_snapshot_ids,
            "pruned_snapshot_ids": [snapshot["session_snapshot_id"] for snapshot in pruned_snapshots],
            "pruned_snapshots": pruned_snapshots,
        }

    def verify_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        without_hash = dict(snapshot)
        without_hash.pop("snapshot_hash", None)
        computed_snapshot_hash = sha256_text(stable_json(without_hash))
        events = snapshot.get("events", [])
        computed_merkle_root = merkle_root([event.get("event_hash", "") for event in events])
        result = {
            "ok": True,
            "snapshot_schema": snapshot.get("snapshot_schema"),
            "snapshot_hash": snapshot.get("snapshot_hash"),
            "computed_snapshot_hash": computed_snapshot_hash,
            "merkle_root": snapshot.get("merkle_root"),
            "computed_merkle_root": computed_merkle_root,
            "memory_count": snapshot.get("memory_count"),
            "event_count": snapshot.get("event_count"),
            "receipt_count": snapshot.get("receipt_count"),
            "write_receipt_count": snapshot.get("write_receipt_count"),
            "write_receipt_chain_count": 0,
            "verified_write_receipt_count": 0,
            "verified_write_receipt_transition_count": 0,
            "total_intervening_event_count": 0,
            "total_intervening_other_memory_event_count": 0,
            "write_receipt_attestation_count": 0,
            "write_receipt_chains": [],
            "provenance_receipt_count": 0,
            "verified_provenance_receipt_count": 0,
            "provenance_receipts": [],
            "supersession_transition_count": 0,
            "verified_supersession_transition_count": 0,
            "supersession_transitions": [],
            "attestation_artifacts": [],
        }
        try:
            write_receipt_verification = self._validate_snapshot(snapshot)
            result["write_receipt_chain_count"] = write_receipt_verification["chain_count"]
            result["verified_write_receipt_count"] = write_receipt_verification["verified_write_receipt_count"]
            result["verified_write_receipt_transition_count"] = write_receipt_verification["verified_transition_count"]
            result["total_intervening_event_count"] = write_receipt_verification["total_intervening_event_count"]
            result["total_intervening_other_memory_event_count"] = write_receipt_verification[
                "total_intervening_other_memory_event_count"
            ]
            result["write_receipt_attestation_count"] = len(write_receipt_verification["attestation_artifacts"])
            result["write_receipt_chains"] = write_receipt_verification["write_receipt_chains"]
            result["provenance_receipt_count"] = write_receipt_verification["provenance_receipt_count"]
            result["verified_provenance_receipt_count"] = write_receipt_verification["verified_provenance_receipt_count"]
            result["provenance_receipts"] = write_receipt_verification["provenance_receipts"]
            result["supersession_transition_count"] = write_receipt_verification["supersession_transition_count"]
            result["verified_supersession_transition_count"] = write_receipt_verification[
                "verified_supersession_transition_count"
            ]
            result["supersession_transitions"] = write_receipt_verification["supersession_transitions"]
            result["attestation_artifacts"] = write_receipt_verification["attestation_artifacts"]
        except (KeyError, ValueError) as exc:
            result["ok"] = False
            result["error"] = str(exc)
        return result

    def verify_memory_write_receipt(
        self,
        receipt: dict[str, Any],
        *,
        prior_receipt: dict[str, Any] | None = None,
        allow_intervening_prior_merkle_root: bool = False,
    ) -> dict[str, Any]:
        treeship_statement = receipt.get("treeship_statement")
        statement_object = treeship_statement.get("object", {}) if isinstance(treeship_statement, dict) else {}
        statement_evidence = treeship_statement.get("evidence", {}) if isinstance(treeship_statement, dict) else {}
        statement_source = treeship_statement.get("source", {}) if isinstance(treeship_statement, dict) else {}
        source_receipt = statement_source.get("receipt", {}) if isinstance(statement_source, dict) else {}
        source_event = statement_source.get("event", {}) if isinstance(statement_source, dict) else {}
        source_event_payload: dict[str, Any] = {}
        statement_attestation = treeship_statement.get("attestation") if isinstance(treeship_statement, dict) else None
        receipt_attestation = receipt.get("treeship_attestation")
        result = {
            "ok": True,
            "receipt_schema": receipt.get("receipt_schema"),
            "receipt_id": receipt.get("receipt_id"),
            "memory_id": receipt.get("memory_id"),
            "receipt_hash": receipt.get("receipt_hash"),
            "computed_receipt_hash": None,
            "content_digest": receipt.get("content_digest"),
            "computed_content_digest": statement_object.get("content_digest") if isinstance(statement_object, dict) else None,
            "merkle_root": receipt.get("merkle_root"),
            "treeship_statement_kind": treeship_statement.get("kind") if isinstance(treeship_statement, dict) else None,
            "treeship_statement_verified": False,
            "treeship_attestation_verified": False,
            "prior_receipt_id": statement_source.get("prior_receipt_id") if isinstance(statement_source, dict) else None,
            "prior_receipt_hash": statement_source.get("prior_receipt_hash") if isinstance(statement_source, dict) else None,
            "semantic_truth_guaranteed": False,
        }
        try:
            if receipt.get("receipt_schema") != WRITE_RECEIPT_SCHEMA:
                raise ValueError("unsupported write receipt schema")
            if receipt.get("hash_alg") != HASH_ALG:
                raise ValueError("unsupported write receipt hash algorithm")
            if receipt.get("merkle_alg") != MERKLE_ALG:
                raise ValueError("unsupported write receipt merkle algorithm")
            if not isinstance(receipt.get("receipt_hash"), str):
                raise ValueError("write receipt missing receipt_hash")
            if not isinstance(treeship_statement, dict):
                raise ValueError("write receipt missing treeship_statement")
            if not isinstance(statement_object, dict):
                raise ValueError("write receipt missing treeship object")
            if not isinstance(statement_evidence, dict):
                raise ValueError("write receipt missing treeship evidence")
            if not isinstance(statement_source, dict):
                raise ValueError("write receipt missing treeship source")
            if not isinstance(source_receipt, dict):
                raise ValueError("write receipt missing treeship source receipt")

            stripped_statement = receipt.get("treeship_statement")
            if isinstance(stripped_statement, dict):
                stripped_statement = json.loads(stable_json(stripped_statement))
                stripped_statement.pop("attestation", None)
            canonical_receipt_without_hash = json.loads(stable_json(source_receipt))
            canonical_receipt_without_hash["treeship_statement"] = stripped_statement
            computed_receipt_hash = sha256_text(stable_json(canonical_receipt_without_hash))
            result["computed_receipt_hash"] = computed_receipt_hash

            if computed_receipt_hash != receipt["receipt_hash"]:
                raise ValueError("write receipt_hash mismatch")

            kind = treeship_statement.get("kind")
            if kind not in {"zerker.memory.write_provenance", "zerker.memory.mutation_receipt"}:
                raise ValueError("unsupported write receipt treeship kind")
            expected_predicate = (
                "memory.write.provenance.generated"
                if kind == "zerker.memory.write_provenance"
                else "memory.mutation.receipt.generated"
            )
            if treeship_statement.get("predicate") != expected_predicate:
                raise ValueError("write receipt treeship predicate mismatch")
            if treeship_statement.get("created_at") != receipt.get("created_at"):
                raise ValueError("write receipt treeship created_at mismatch")

            subject = treeship_statement.get("subject")
            if not isinstance(subject, dict):
                raise ValueError("write receipt missing treeship subject")
            if subject.get("id") != receipt.get("receipt_id"):
                raise ValueError("write receipt treeship subject id mismatch")
            if subject.get("memory_id") != receipt.get("memory_id"):
                raise ValueError("write receipt treeship subject memory_id mismatch")

            for key in (
                "actor_uri",
                "session_id",
                "parent_action_id",
                "source_uri",
                "content_digest",
                "environment_hash",
            ):
                if statement_object.get(key) != receipt.get(key):
                    raise ValueError(f"write receipt treeship {key} mismatch")
            actor_id = statement_object.get("actor_id")
            if actor_id is not None:
                if not isinstance(actor_id, str) or not actor_id:
                    raise ValueError("write receipt treeship actor_id mismatch")
                if source_event.get("actor_id") != actor_id:
                    raise ValueError("write receipt source event actor_id mismatch")
            if statement_object.get("semantic_truth_guaranteed") is True:
                raise ValueError("write receipt semantic_truth_guaranteed must not be true")

            if statement_evidence.get("hash_alg") != HASH_ALG:
                raise ValueError("write receipt treeship hash algorithm mismatch")
            if statement_evidence.get("merkle_alg") != MERKLE_ALG:
                raise ValueError("write receipt treeship merkle algorithm mismatch")
            if statement_evidence.get("event_hash") != receipt.get("event_hash"):
                raise ValueError("write receipt treeship event_hash mismatch")
            if statement_evidence.get("merkle_root") != receipt.get("merkle_root"):
                raise ValueError("write receipt treeship merkle_root mismatch")
            if "new_merkle_root" in statement_evidence and statement_evidence.get("new_merkle_root") != receipt.get("merkle_root"):
                raise ValueError("write receipt treeship new_merkle_root mismatch")

            if statement_source.get("system") != "zerker-memory":
                raise ValueError("write receipt treeship source system mismatch")
            if source_event and source_event.get("event_hash") != receipt.get("event_hash"):
                raise ValueError("write receipt source event_hash mismatch")
            if source_event and source_event.get("merkle_root") != receipt.get("merkle_root"):
                raise ValueError("write receipt source event merkle_root mismatch")
            if "prior_event_hash" in statement_evidence and statement_evidence.get("prior_event_hash") != source_event.get("prev_event_hash"):
                raise ValueError("write receipt source event prior_event_hash mismatch")
            if "prior_merkle_root" in statement_evidence and statement_evidence.get("prior_merkle_root") != source_event.get("prior_merkle_root"):
                raise ValueError("prior_merkle_root mismatch")
            if isinstance(source_event, dict):
                payload_json = source_event.get("payload_json")
                if isinstance(payload_json, str):
                    try:
                        loaded_payload = json.loads(payload_json)
                    except json.JSONDecodeError as exc:
                        raise ValueError("write receipt source event payload_json mismatch") from exc
                    if isinstance(loaded_payload, dict):
                        source_event_payload = loaded_payload
            for key in (
                "receipt_schema",
                "hash_alg",
                "merkle_alg",
                "receipt_id",
                "memory_id",
                "actor_uri",
                "session_id",
                "parent_action_id",
                "source_uri",
                "content_digest",
                "environment_hash",
                "event_hash",
                "merkle_root",
                "created_at",
            ):
                if source_receipt.get(key) != receipt.get(key):
                    raise ValueError(f"write receipt source {key} mismatch")
            if "receipt_hash" in source_receipt:
                raise ValueError("write receipt source receipt must not include receipt_hash")

            if kind == "zerker.memory.write_provenance":
                if "actor_id" in statement_object and statement_object.get("actor_id") != source_event.get("actor_id"):
                    raise ValueError("write receipt source event actor_id mismatch")
                if "memory_type" in statement_object and statement_object.get("memory_type") != source_event_payload.get("type"):
                    raise ValueError("write receipt source event memory_type mismatch")
                if "scope" in statement_object and statement_object.get("scope") != source_event_payload.get("scope"):
                    raise ValueError("write receipt source event scope mismatch")
                if "source_kind" in statement_object and statement_object.get("source_kind") != source_event_payload.get("source_kind"):
                    raise ValueError("write receipt source event source_kind mismatch")
                if "trust" in statement_object and statement_object.get("trust") != source_event_payload.get("trust"):
                    raise ValueError("write receipt source event trust mismatch")
                if "authority" in statement_object and statement_object.get("authority") != source_event_payload.get("authority"):
                    raise ValueError("write receipt source event authority mismatch")
                if "status" in statement_object:
                    status = statement_object.get("status")
                    if status != source_event_payload.get("status"):
                        raise ValueError("write receipt source event status mismatch")
                    expected_event_type = "PROPOSED" if status in {"proposed", "quarantined"} else "OBSERVED"
                    if source_event.get("event_type") != expected_event_type:
                        raise ValueError("write receipt source event type mismatch")
            elif kind == "zerker.memory.mutation_receipt":
                expected_mutation_by_event_type = {
                    "FORGOTTEN": ("forget", "forgotten"),
                    "PROMOTED": ("promote", "active"),
                    "REJECTED": ("reject", "deprecated"),
                    "REVOKED": ("revoke", "revoked"),
                }
                event_type = source_event.get("event_type")
                expected_mutation = expected_mutation_by_event_type.get(str(event_type))
                if expected_mutation is None:
                    raise ValueError("write receipt source event type mismatch")
                expected_mutation_name, expected_status = expected_mutation
                if statement_object.get("mutation") != expected_mutation_name:
                    raise ValueError("write receipt source event mutation mismatch")
                if statement_object.get("status") != expected_status:
                    raise ValueError("write receipt source event mutation status mismatch")
                if expected_mutation_name == "promote":
                    if statement_object.get("authority") != source_event_payload.get("authority"):
                        raise ValueError("write receipt source event promote authority mismatch")
                elif expected_mutation_name == "reject":
                    if statement_object.get("reason") != source_event_payload.get("reason"):
                        raise ValueError("write receipt source event reject reason mismatch")
                    if statement_object.get("previous_status") != source_event_payload.get("previous_status"):
                        raise ValueError("write receipt source event previous_status mismatch")
                elif expected_mutation_name == "forget":
                    if statement_object.get("previous_status") != source_event_payload.get("previous_status"):
                        raise ValueError("write receipt source event previous_status mismatch")
                elif expected_mutation_name == "revoke":
                    expected_revoked_ids = source_event_payload.get("revoked_ids")
                    expected_previous_status = source_event_payload.get("previous_status")
                    if expected_previous_status is None and prior_receipt is not None:
                        expected_previous_status = _write_receipt_status(prior_receipt)
                    if (
                        expected_previous_status is not None
                        and statement_object.get("previous_status") != expected_previous_status
                    ):
                        raise ValueError("write receipt source event previous_status mismatch")
                    if statement_object.get("reason") != source_event_payload.get("reason"):
                        raise ValueError("write receipt source event revoke reason mismatch")
                    if statement_object.get("revoked_ids") != expected_revoked_ids:
                        raise ValueError("write receipt source event revoked_ids mismatch")
                    expected_descendant_ids = expected_revoked_ids[1:] if isinstance(expected_revoked_ids, list) else None
                    if statement_object.get("descendant_ids") != expected_descendant_ids:
                        raise ValueError("write receipt source event descendant_ids mismatch")
                    if statement_object.get("descendant_count") != source_event_payload.get("descendant_count"):
                        raise ValueError("write receipt source event descendant_count mismatch")

            if isinstance(statement_attestation, dict):
                if not isinstance(receipt_attestation, dict):
                    raise ValueError("write receipt top-level attestation missing")
                if receipt_attestation != statement_attestation:
                    raise ValueError("write receipt attestation mismatch")
                if statement_attestation.get("schema") != "zerker.memory.treeship_attestation.v1":
                    raise ValueError("write receipt attestation schema mismatch")
                if statement_attestation.get("system") != "system://zmem":
                    raise ValueError("write receipt attestation system mismatch")
                if statement_attestation.get("kind") != "memory.write":
                    raise ValueError("write receipt attestation kind mismatch")
                if statement_attestation.get("subject") != receipt.get("receipt_id"):
                    raise ValueError("write receipt attestation subject mismatch")
                if statement_attestation.get("payload_digest") != f"{HASH_ALG}:{receipt['receipt_hash']}":
                    raise ValueError("write receipt attestation payload_digest mismatch")
                status = statement_attestation.get("status")
                if status not in {"signed", "failed", "unavailable"}:
                    raise ValueError("write receipt attestation status mismatch")
                artifact_id = statement_attestation.get("artifact_id")
                signed_at = statement_attestation.get("signed_at")
                if status == "signed":
                    if not isinstance(artifact_id, str) or not artifact_id:
                        raise ValueError("write receipt attestation artifact_id mismatch")
                    if not isinstance(signed_at, str) or not signed_at:
                        raise ValueError("write receipt attestation signed_at mismatch")
                else:
                    if artifact_id is not None:
                        raise ValueError("write receipt attestation artifact_id mismatch")
                    if signed_at is not None:
                        raise ValueError("write receipt attestation signed_at mismatch")
                result["treeship_attestation_verified"] = True
            elif receipt_attestation is not None:
                raise ValueError("write receipt top-level attestation missing statement copy")

            if prior_receipt is not None:
                if prior_receipt.get("memory_id") != receipt.get("memory_id"):
                    raise ValueError("prior receipt memory_id mismatch")
                if statement_source.get("prior_receipt_id") != prior_receipt.get("receipt_id"):
                    raise ValueError("prior_receipt_id mismatch")
                if statement_source.get("prior_receipt_hash") != prior_receipt.get("receipt_hash"):
                    raise ValueError("prior_receipt_hash mismatch")
                if (
                    not allow_intervening_prior_merkle_root
                    and statement_evidence.get("prior_merkle_root") != prior_receipt.get("merkle_root")
                ):
                    raise ValueError("prior_merkle_root mismatch")
            elif statement_source.get("prior_receipt_id") is not None or statement_source.get("prior_receipt_hash") is not None:
                raise ValueError("write receipt unexpectedly links to a prior receipt")

            result["treeship_statement_verified"] = True
        except Exception as exc:
            result["ok"] = False
            result["error"] = str(exc)
        return result

    def verify_memory_write_receipt_chain(self, receipts: list[dict[str, Any]]) -> dict[str, Any]:
        result = {
            "ok": True,
            "schema": "zerker.memory_write_receipt_chain_verification.v1",
            "memory_id": None,
            "receipt_count": 0,
            "verified_transition_count": 0,
            "total_intervening_event_count": 0,
            "total_intervening_other_memory_event_count": 0,
            "semantic_truth_guaranteed": False,
            "attestation_artifacts": [],
            "receipts": [],
            "transitions": [],
        }
        try:
            self.init()
            if not isinstance(receipts, list) or not receipts:
                raise ValueError("write receipt chain is empty")
            result["receipt_count"] = len(receipts)

            prior_receipt = None
            for index, receipt in enumerate(receipts):
                if not isinstance(receipt, dict):
                    raise ValueError(f"write receipt at index {index} is invalid")
                memory_id = receipt.get("memory_id")
                if result["memory_id"] is None:
                    result["memory_id"] = memory_id
                elif memory_id != result["memory_id"]:
                    raise ValueError("write receipt chain memory_id mismatch")

                verification = self.verify_memory_write_receipt(
                    receipt,
                    prior_receipt=prior_receipt,
                    allow_intervening_prior_merkle_root=prior_receipt is not None,
                )
                result["receipts"].append(
                    {
                        "receipt_id": receipt.get("receipt_id"),
                        "receipt_hash": receipt.get("receipt_hash"),
                        "verification": verification,
                    }
                )
                if not verification["ok"]:
                    raise ValueError(
                        f"receipt {receipt.get('receipt_id') or index} verification failed: {verification['error']}"
                    )

                if prior_receipt is not None:
                    event_row = self.conn.execute(
                        "SELECT seq, prev_event_hash FROM events WHERE event_hash = ?",
                        (receipt.get("event_hash"),),
                    ).fetchone()
                    if event_row is not None:
                        prev_event_hash = event_row["prev_event_hash"]
                        expected_prior_merkle_root = merkle_root([])
                        if prev_event_hash is not None:
                            prev_event_row = self.conn.execute(
                                "SELECT merkle_root FROM events WHERE event_hash = ?",
                                (prev_event_hash,),
                            ).fetchone()
                            if prev_event_row is None:
                                raise ValueError("prior_merkle_root mismatch")
                            expected_prior_merkle_root = prev_event_row["merkle_root"]
                        statement_evidence = (receipt.get("treeship_statement") or {}).get("evidence") or {}
                        if statement_evidence.get("prior_merkle_root") != expected_prior_merkle_root:
                            raise ValueError("prior_merkle_root mismatch")
                        prior_receipt_event_row = self.conn.execute(
                            "SELECT seq FROM events WHERE event_hash = ?",
                            (prior_receipt.get("event_hash"),),
                        ).fetchone()
                        intervening_event_count = 0
                        intervening_other_memory_event_count = 0
                        if prior_receipt_event_row is not None:
                            current_seq = int(event_row["seq"])
                            prior_receipt_seq = int(prior_receipt_event_row["seq"])
                            intervening_event_count = max(current_seq - prior_receipt_seq - 1, 0)
                            if intervening_event_count:
                                count_row = self.conn.execute(
                                    """
                                    SELECT COUNT(*) AS event_count
                                    FROM events
                                    WHERE seq > ? AND seq < ? AND COALESCE(memory_id, '') != ?
                                    """,
                                    (prior_receipt_seq, current_seq, str(receipt.get("memory_id") or "")),
                                ).fetchone()
                                intervening_other_memory_event_count = int(
                                    count_row["event_count"] if count_row is not None else 0
                                )
                        result["transitions"].append(
                            {
                                "receipt_id": receipt.get("receipt_id"),
                                "prior_receipt_id": prior_receipt.get("receipt_id"),
                                "prior_receipt_event_hash": prior_receipt.get("event_hash"),
                                "live_prior_event_hash": prev_event_hash,
                                "live_prior_merkle_root": expected_prior_merkle_root,
                                "intervening_event_count": intervening_event_count,
                                "intervening_other_memory_event_count": intervening_other_memory_event_count,
                                "continuity_basis": "prior_receipt_link_plus_live_previous_event_root",
                                "trusted_provenance_verified": True,
                                "semantic_truth_guaranteed": False,
                            }
                        )
                        result["total_intervening_event_count"] += intervening_event_count
                        result["total_intervening_other_memory_event_count"] += intervening_other_memory_event_count

                attestation = receipt.get("treeship_attestation")
                if isinstance(attestation, dict):
                    result["attestation_artifacts"].append(
                        {
                            "receipt_id": receipt.get("receipt_id"),
                            "artifact_id": attestation.get("artifact_id"),
                            "status": attestation.get("status"),
                            "signed_at": attestation.get("signed_at"),
                        }
                    )

                if prior_receipt is not None:
                    result["verified_transition_count"] += 1
                prior_receipt = receipt
        except Exception as exc:
            result["ok"] = False
            result["error"] = str(exc)
        return result

    def verify_lifecycle_receipt(
        self,
        receipt: dict[str, Any],
        *,
        source_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source_payload = receipt.get("source_payload")
        treeship_statement = receipt.get("treeship_statement")
        statement_object = treeship_statement.get("object", {}) if isinstance(treeship_statement, dict) else {}
        statement_evidence = treeship_statement.get("evidence", {}) if isinstance(treeship_statement, dict) else {}
        result = {
            "ok": True,
            "receipt_schema": receipt.get("receipt_schema"),
            "receipt_id": receipt.get("receipt_id"),
            "mutation": receipt.get("mutation"),
            "receipt_hash": receipt.get("receipt_hash"),
            "computed_receipt_hash": None,
            "content_digest": receipt.get("content_digest"),
            "computed_content_digest": None,
            "merkle_root": receipt.get("merkle_root"),
            "treeship_statement_kind": treeship_statement.get("kind") if isinstance(treeship_statement, dict) else None,
            "treeship_statement_verified": False,
            "semantic_truth_guaranteed": statement_object.get("semantic_truth_guaranteed") if isinstance(statement_object, dict) else None,
            "source_snapshot_hash": source_snapshot.get("snapshot_hash") if isinstance(source_snapshot, dict) else None,
            "source_snapshot_verified": None,
        }
        try:
            if receipt.get("receipt_schema") != LIFECYCLE_RECEIPT_SCHEMA:
                raise ValueError("unsupported lifecycle receipt schema")
            if receipt.get("hash_alg") != HASH_ALG:
                raise ValueError("unsupported lifecycle receipt hash algorithm")
            if receipt.get("merkle_alg") != MERKLE_ALG:
                raise ValueError("unsupported lifecycle receipt merkle algorithm")
            if not isinstance(receipt.get("receipt_hash"), str):
                raise ValueError("lifecycle receipt missing receipt_hash")
            if not isinstance(source_payload, dict):
                raise ValueError("lifecycle receipt missing source_payload")
            if not isinstance(treeship_statement, dict):
                raise ValueError("lifecycle receipt missing treeship_statement")

            receipt_without_hash = dict(receipt)
            receipt_without_hash.pop("receipt_hash", None)
            computed_receipt_hash = sha256_text(stable_json(receipt_without_hash))
            result["computed_receipt_hash"] = computed_receipt_hash

            computed_content_digest = digest_uri(stable_json(source_payload))
            result["computed_content_digest"] = computed_content_digest

            if computed_receipt_hash != receipt["receipt_hash"]:
                raise ValueError("lifecycle receipt_hash mismatch")
            if computed_content_digest != receipt.get("content_digest"):
                raise ValueError("lifecycle content_digest mismatch")
            if treeship_statement.get("kind") != "zerker.memory.mutation_receipt":
                raise ValueError("lifecycle treeship kind mismatch")
            if treeship_statement.get("predicate") != "memory.mutation.receipt.generated":
                raise ValueError("lifecycle treeship predicate mismatch")
            if treeship_statement.get("created_at") != receipt.get("created_at"):
                raise ValueError("lifecycle treeship created_at mismatch")
            if not isinstance(statement_object, dict):
                raise ValueError("lifecycle receipt missing treeship object")
            if not isinstance(statement_evidence, dict):
                raise ValueError("lifecycle receipt missing treeship evidence")
            if statement_object.get("mutation") != receipt.get("mutation"):
                raise ValueError("lifecycle treeship mutation mismatch")
            if statement_object.get("content_digest") != computed_content_digest:
                raise ValueError("lifecycle treeship content_digest mismatch")
            actor_id = statement_object.get("actor_id")
            if not isinstance(actor_id, str) or not actor_id:
                raise ValueError("lifecycle treeship actor_id mismatch")
            if actor_uri_for(actor_id) != receipt.get("actor_uri"):
                raise ValueError("lifecycle treeship actor identity mismatch")
            if "actor_uri" in statement_object and statement_object.get("actor_uri") != receipt.get("actor_uri"):
                raise ValueError("lifecycle treeship actor_uri mismatch")
            if statement_object.get("semantic_truth_guaranteed") is not False:
                raise ValueError("lifecycle semantic_truth_guaranteed must be false")
            if statement_evidence.get("hash_alg") != HASH_ALG:
                raise ValueError("lifecycle treeship hash algorithm mismatch")
            if statement_evidence.get("merkle_alg") != MERKLE_ALG:
                raise ValueError("lifecycle treeship merkle algorithm mismatch")
            if statement_evidence.get("new_merkle_root") != receipt.get("merkle_root"):
                raise ValueError("lifecycle treeship new_merkle_root mismatch")
            if statement_evidence.get("payload_digest") != computed_content_digest:
                raise ValueError("lifecycle treeship payload_digest mismatch")

            statement_source = treeship_statement.get("source")
            if not isinstance(statement_source, dict):
                raise ValueError("lifecycle receipt missing treeship source")
            if statement_source.get("system") != "zerker-memory":
                raise ValueError("lifecycle treeship source system mismatch")
            source_event = statement_source.get("event")
            if receipt.get("source_event_hash") is None:
                if source_event is not None:
                    raise ValueError("lifecycle source event mismatch")
            else:
                if not isinstance(source_event, dict):
                    raise ValueError("lifecycle source event mismatch")
                if source_event.get("event_schema") != EVENT_SCHEMA:
                    raise ValueError("lifecycle source event schema mismatch")
                if source_event.get("hash_alg") != HASH_ALG:
                    raise ValueError("lifecycle source event hash algorithm mismatch")
                if source_event.get("event_hash") != receipt.get("source_event_hash"):
                    raise ValueError("lifecycle source event_hash mismatch")
                if source_event.get("actor_id") != actor_id:
                    raise ValueError("lifecycle source event actor_id mismatch")
                if source_event.get("actor_uri") != receipt.get("actor_uri"):
                    raise ValueError("lifecycle source event actor_uri mismatch")
                expected_payload_hash = sha256_text(stable_json(source_payload))
                if source_event.get("payload_hash") != expected_payload_hash:
                    raise ValueError("lifecycle source event payload_hash mismatch")
                if source_event.get("prev_event_hash") != statement_evidence.get("prior_event_hash"):
                    raise ValueError("lifecycle source event prev_event_hash mismatch")
                if source_event.get("created_at") != receipt.get("created_at"):
                    raise ValueError("lifecycle source event created_at mismatch")
                computed_event_hash = sha256_text(
                    stable_json(
                        {
                            "event_schema": source_event.get("event_schema"),
                            "hash_alg": source_event.get("hash_alg"),
                            "event_type": source_event.get("event_type"),
                            "memory_id": source_event.get("memory_id"),
                            "action_id": source_event.get("action_id"),
                            "actor_id": source_event.get("actor_id"),
                            "payload_hash": source_event.get("payload_hash"),
                            "prev_event_hash": source_event.get("prev_event_hash"),
                            "created_at": source_event.get("created_at"),
                        }
                    )
                )
                if computed_event_hash != receipt.get("source_event_hash"):
                    raise ValueError("lifecycle source event_hash mismatch")
            if statement_source.get("treeship_artifact_id") != receipt.get("treeship_artifact_id"):
                raise ValueError("lifecycle treeship artifact mismatch")
            expected_source_receipt = dict(receipt)
            expected_source_receipt.pop("treeship_statement", None)
            expected_source_receipt.pop("receipt_hash", None)
            if statement_source.get("receipt") != expected_source_receipt:
                raise ValueError("lifecycle treeship source receipt mismatch")

            if source_snapshot is not None:
                snapshot_verification = self.verify_snapshot(source_snapshot)
                result["source_snapshot_verified"] = snapshot_verification["ok"]
                if not snapshot_verification["ok"]:
                    raise ValueError(f"source snapshot invalid: {snapshot_verification['error']}")
                if source_payload.get("snapshot_hash") != source_snapshot.get("snapshot_hash"):
                    raise ValueError("lifecycle snapshot_hash mismatch")
                if statement_evidence.get("snapshot_hash") != source_snapshot.get("snapshot_hash"):
                    raise ValueError("lifecycle treeship snapshot_hash mismatch")
                if statement_object.get("snapshot_hash") != source_snapshot.get("snapshot_hash"):
                    raise ValueError("lifecycle treeship object snapshot_hash mismatch")
                if "snapshot_merkle_root" in source_payload and source_payload.get("snapshot_merkle_root") != source_snapshot.get("merkle_root"):
                    raise ValueError("lifecycle snapshot_merkle_root mismatch")
                if "snapshot_merkle_root" in statement_object and statement_object.get("snapshot_merkle_root") != source_snapshot.get("merkle_root"):
                    raise ValueError("lifecycle treeship object snapshot_merkle_root mismatch")
                if "snapshot_memory_count" in source_payload and source_payload.get("snapshot_memory_count") != source_snapshot.get("memory_count"):
                    raise ValueError("lifecycle snapshot_memory_count mismatch")
                if "snapshot_event_count" in source_payload and source_payload.get("snapshot_event_count") != source_snapshot.get("event_count"):
                    raise ValueError("lifecycle snapshot_event_count mismatch")
                if "snapshot_receipt_count" in source_payload and source_payload.get("snapshot_receipt_count") != source_snapshot.get("receipt_count"):
                    raise ValueError("lifecycle snapshot_receipt_count mismatch")
                if "snapshot_write_receipt_count" in source_payload and source_payload.get("snapshot_write_receipt_count") != source_snapshot.get("write_receipt_count"):
                    raise ValueError("lifecycle snapshot_write_receipt_count mismatch")
                if receipt.get("mutation") == "restore_snapshot":
                    if source_payload.get("snapshot_merkle_root") != source_snapshot.get("merkle_root"):
                        raise ValueError("lifecycle snapshot_merkle_root mismatch")
                    if source_payload.get("memory_count") != source_snapshot.get("memory_count"):
                        raise ValueError("lifecycle memory_count mismatch")
                    if source_payload.get("event_count") != source_snapshot.get("event_count"):
                        raise ValueError("lifecycle event_count mismatch")
                    if source_payload.get("receipt_count") != source_snapshot.get("receipt_count"):
                        raise ValueError("lifecycle receipt_count mismatch")
                    if source_payload.get("write_receipt_count") != source_snapshot.get("write_receipt_count"):
                        raise ValueError("lifecycle write_receipt_count mismatch")
                    if statement_evidence.get("source_snapshot_verified") is not True:
                        raise ValueError("lifecycle treeship source_snapshot_verified mismatch")
            result["treeship_statement_verified"] = True
        except (KeyError, ValueError) as exc:
            result["ok"] = False
            result["error"] = str(exc)
        return result

    def _verify_snapshot_write_receipts(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        memories = snapshot.get("memories", [])
        memory_ids = {memory.get("id") for memory in memories if isinstance(memory, dict)}
        events = snapshot.get("events", [])
        event_by_hash = {
            event.get("event_hash"): event
            for event in events
            if isinstance(event, dict) and event.get("event_hash") is not None
        }
        event_hashes = {event.get("event_hash") for event in events if isinstance(event, dict)}
        receipts_by_memory: dict[str, list[dict[str, Any]]] = {}
        summary = {
            "chain_count": 0,
            "verified_write_receipt_count": 0,
            "verified_transition_count": 0,
            "total_intervening_event_count": 0,
            "total_intervening_other_memory_event_count": 0,
            "write_receipt_chains": [],
            "provenance_receipt_count": 0,
            "verified_provenance_receipt_count": 0,
            "provenance_receipts": [],
            "supersession_transition_count": 0,
            "verified_supersession_transition_count": 0,
            "supersession_transitions": [],
            "attestation_artifacts": [],
        }
        verified_receipts_by_memory_event: dict[tuple[str, str], dict[str, Any]] = {}
        for index, write_receipt in enumerate(snapshot.get("write_receipts", [])):
            if not isinstance(write_receipt, dict):
                raise ValueError(f"snapshot write_receipt at index {index} is invalid")
            memory_id = write_receipt.get("memory_id")
            if memory_id not in memory_ids:
                raise ValueError(f"snapshot write receipt memory_id missing from snapshot memories: {memory_id}")
            if write_receipt.get("event_hash") not in event_hashes:
                raise ValueError(
                    f"snapshot write receipt event_hash missing from snapshot events: {write_receipt.get('receipt_id') or index}"
                )
            receipts_by_memory.setdefault(str(memory_id), []).append(write_receipt)

        summary["chain_count"] = len(receipts_by_memory)
        for memory_id, receipts in receipts_by_memory.items():
            prior_receipt = None
            chain_summary = {
                "memory_id": memory_id,
                "ok": True,
                "receipt_count": len(receipts),
                "verified_transition_count": 0,
                "total_intervening_event_count": 0,
                "total_intervening_other_memory_event_count": 0,
                "semantic_truth_guaranteed": False,
                "transitions": [],
            }
            for index, receipt in enumerate(receipts):
                verification = self.verify_memory_write_receipt(
                    receipt,
                    prior_receipt=prior_receipt,
                    allow_intervening_prior_merkle_root=True,
                )
                if not verification["ok"]:
                    raise ValueError(
                        f"snapshot write receipt chain invalid for {memory_id}: "
                        f"receipt {receipt.get('receipt_id') or index} verification failed: {verification['error']}"
                    )
                receipt_event_key = (str(memory_id), str(receipt.get("event_hash")))
                verified_receipts_by_memory_event[receipt_event_key] = {
                    "receipt": receipt,
                    "verification": verification,
                }
                event = event_by_hash.get(receipt.get("event_hash"))
                if event is None:
                    raise ValueError(
                        f"snapshot write receipt event_hash missing from snapshot events: {receipt.get('receipt_id') or index}"
                    )
                if event.get("merkle_root") != receipt.get("merkle_root"):
                    raise ValueError(
                        f"snapshot write receipt event merkle_root mismatch: {receipt.get('receipt_id') or index}"
                    )
                treeship_statement = receipt.get("treeship_statement") or {}
                statement_evidence = (receipt.get("treeship_statement") or {}).get("evidence") or {}
                statement_object = treeship_statement.get("object") or {}
                receipt_kind = treeship_statement.get("kind")
                prior_event_hash = event.get("prev_event_hash")
                prior_event = event_by_hash.get(prior_event_hash)
                expected_prior_merkle_root = prior_event.get("merkle_root") if prior_event is not None else merkle_root([])
                if receipt_kind == "zerker.memory.mutation_receipt" or "prior_merkle_root" in statement_evidence:
                    if statement_evidence.get("prior_merkle_root") != expected_prior_merkle_root:
                        raise ValueError(
                            f"snapshot write receipt chain invalid for {memory_id}: "
                            f"receipt {receipt.get('receipt_id') or index} prior_merkle_root mismatch"
                        )
                if prior_receipt is not None:
                    prior_event = event_by_hash.get(prior_receipt.get("event_hash"))
                    intervening_event_count = 0
                    intervening_other_memory_event_count = 0
                    if prior_event is not None:
                        current_seq = int(event.get("seq"))
                        prior_seq = int(prior_event.get("seq"))
                        intervening_event_count = max(current_seq - prior_seq - 1, 0)
                        if intervening_event_count:
                            intervening_other_memory_event_count = sum(
                                1
                                for candidate in events
                                if isinstance(candidate, dict)
                                and candidate.get("seq") is not None
                                and prior_seq < int(candidate.get("seq")) < current_seq
                                and str(candidate.get("memory_id") or "") != memory_id
                            )
                    chain_summary["verified_transition_count"] += 1
                    chain_summary["total_intervening_event_count"] += intervening_event_count
                    chain_summary["total_intervening_other_memory_event_count"] += (
                        intervening_other_memory_event_count
                    )
                    chain_summary["transitions"].append(
                        {
                            "receipt_id": receipt.get("receipt_id"),
                            "prior_receipt_id": prior_receipt.get("receipt_id"),
                            "prior_receipt_event_hash": prior_receipt.get("event_hash"),
                            "snapshot_prior_event_hash": prior_event_hash,
                            "snapshot_prior_merkle_root": expected_prior_merkle_root,
                            "intervening_event_count": intervening_event_count,
                            "intervening_other_memory_event_count": intervening_other_memory_event_count,
                            "continuity_basis": "prior_receipt_link_plus_snapshot_previous_event_root",
                            "trusted_provenance_verified": True,
                            "semantic_truth_guaranteed": False,
                        }
                    )
                if (
                    receipt_kind == "zerker.memory.mutation_receipt" or "new_merkle_root" in statement_evidence
                ) and statement_evidence.get("new_merkle_root") != event.get("merkle_root"):
                    raise ValueError(
                        f"snapshot write receipt chain invalid for {memory_id}: "
                        f"receipt {receipt.get('receipt_id') or index} new_merkle_root mismatch"
                    )
                attestation = receipt.get("treeship_attestation")
                if isinstance(attestation, dict):
                    summary["attestation_artifacts"].append(
                        {
                            "receipt_id": receipt.get("receipt_id"),
                            "artifact_id": attestation.get("artifact_id"),
                            "status": attestation.get("status"),
                            "signed_at": attestation.get("signed_at"),
                        }
                    )
                summary["verified_write_receipt_count"] += 1
                if receipt_kind == "zerker.memory.write_provenance":
                    attestation = receipt.get("treeship_attestation")
                    summary["provenance_receipt_count"] += 1
                    summary["verified_provenance_receipt_count"] += 1
                    summary["provenance_receipts"].append(
                        {
                            "memory_id": receipt.get("memory_id"),
                            "receipt_id": receipt.get("receipt_id"),
                            "receipt_hash": receipt.get("receipt_hash"),
                            "actor_id": statement_object.get("actor_id"),
                            "actor_uri": receipt.get("actor_uri"),
                            "content_digest": receipt.get("content_digest"),
                            "prior_merkle_root": statement_evidence.get("prior_merkle_root"),
                            "merkle_root": receipt.get("merkle_root"),
                            "new_merkle_root": statement_evidence.get("new_merkle_root", receipt.get("merkle_root")),
                            "treeship_artifact_id": attestation.get("artifact_id") if isinstance(attestation, dict) else None,
                            "trusted_provenance_verified": bool(verification.get("ok")),
                            "semantic_truth_guaranteed": bool(verification.get("semantic_truth_guaranteed")),
                        }
                    )
                prior_receipt = receipt
            summary["verified_transition_count"] += chain_summary["verified_transition_count"]
            summary["total_intervening_event_count"] += chain_summary["total_intervening_event_count"]
            summary["total_intervening_other_memory_event_count"] += (
                chain_summary["total_intervening_other_memory_event_count"]
            )
            summary["write_receipt_chains"].append(chain_summary)
        supersession_context = self._build_snapshot_supersession_context(snapshot)
        for supersession_summary in (
            self._verify_snapshot_parent_supersession_transitions(
                supersession_context,
                verified_receipts_by_memory_event=verified_receipts_by_memory_event,
            ),
            self._verify_snapshot_explicit_update_supersession_transitions(
                supersession_context,
                verified_receipts_by_memory_event=verified_receipts_by_memory_event,
            ),
            self._verify_snapshot_subject_lookup_restatement_transitions(
                supersession_context,
                verified_receipts_by_memory_event=verified_receipts_by_memory_event,
            ),
        ):
            summary["supersession_transition_count"] += supersession_summary["supersession_transition_count"]
            summary["verified_supersession_transition_count"] += supersession_summary[
                "verified_supersession_transition_count"
            ]
            summary["supersession_transitions"].extend(supersession_summary["supersession_transitions"])
        return summary

    def _validate_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if snapshot.get("snapshot_schema") != SNAPSHOT_SCHEMA:
            raise ValueError("unsupported snapshot schema")
        if snapshot.get("hash_alg") != HASH_ALG:
            raise ValueError("unsupported snapshot hash algorithm")
        if snapshot.get("merkle_alg") != MERKLE_ALG:
            raise ValueError("unsupported snapshot merkle algorithm")
        snapshot_hash = snapshot.get("snapshot_hash")
        if not isinstance(snapshot_hash, str):
            raise ValueError("snapshot missing snapshot_hash")
        without_hash = dict(snapshot)
        without_hash.pop("snapshot_hash", None)
        if sha256_text(stable_json(without_hash)) != snapshot_hash:
            raise ValueError("snapshot_hash mismatch")
        events = snapshot.get("events", [])
        event_hashes = [event["event_hash"] for event in events]
        if merkle_root(event_hashes) != snapshot.get("merkle_root"):
            raise ValueError("snapshot merkle_root mismatch")
        if snapshot.get("memory_count") != len(snapshot.get("memories", [])):
            raise ValueError("snapshot memory_count mismatch")
        if snapshot.get("event_count") != len(events):
            raise ValueError("snapshot event_count mismatch")
        if snapshot.get("receipt_count") != len(snapshot.get("receipts", [])):
            raise ValueError("snapshot receipt_count mismatch")
        if snapshot.get("write_receipt_count", len(snapshot.get("write_receipts", []))) != len(snapshot.get("write_receipts", [])):
            raise ValueError("snapshot write_receipt_count mismatch")
        return self._verify_snapshot_write_receipts(snapshot)

    def _build_snapshot_supersession_context(self, snapshot: dict[str, Any]) -> dict[str, Any] | None:
        memories_payload = snapshot.get("memories", [])
        events = snapshot.get("events", [])
        if not memories_payload or not events:
            return None

        memories: list[MemoryRecord] = []
        for index, memory in enumerate(memories_payload):
            if not isinstance(memory, dict):
                raise ValueError(f"snapshot memory at index {index} is invalid")
            parents = memory.get("parents")
            labels = memory.get("labels")
            if not isinstance(parents, list) or not isinstance(labels, list):
                raise ValueError(f"snapshot memory at index {index} is invalid")
            memories.append(
                MemoryRecord(
                    id=str(memory.get("id")),
                    type=str(memory.get("type")),
                    content=str(memory.get("content")),
                    scope=str(memory.get("scope")),
                    source_kind=str(memory.get("source_kind")),
                    trust=float(memory.get("trust")),
                    authority=str(memory.get("authority")),
                    status=str(memory.get("status")),
                    parents=[str(parent_id) for parent_id in parents],
                    labels=[str(label) for label in labels],
                    created_at=str(memory.get("created_at")),
                    updated_at=str(memory.get("updated_at")),
                    expires_at=str(memory["expires_at"]) if memory.get("expires_at") is not None else None,
                    content_hash=str(memory.get("content_hash")),
                )
            )

        memories_by_id = {memory.id: memory for memory in memories}
        snapshot_timestamp = str(snapshot.get("created_at") or max(str(event.get("created_at")) for event in events))
        status_history_by_id: dict[str, list[dict[str, Any]]] = {memory.id: [] for memory in memories}
        valid_from_by_id: dict[str, str | None] = {memory.id: None for memory in memories}
        valid_from_event_hash_by_id: dict[str, str | None] = {memory.id: None for memory in memories}
        unlearned_at_by_id: dict[str, str | None] = {memory.id: None for memory in memories}
        status_at_snapshot_by_id: dict[str, str] = {memory.id: "future" for memory in memories}
        updated_at_snapshot_by_id: dict[str, str | None] = {memory.id: None for memory in memories}
        serial_at_snapshot_by_id: dict[str, int | None] = {memory.id: None for memory in memories}

        for index, event in enumerate(events):
            if not isinstance(event, dict):
                raise ValueError(f"snapshot event at index {index} is invalid")
            memory_id = event.get("memory_id")
            if memory_id not in memories_by_id:
                continue
            payload_json = event.get("payload_json")
            if not isinstance(payload_json, str):
                raise ValueError(f"snapshot event payload_json missing for {memory_id}")
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError as exc:
                raise ValueError(f"snapshot event payload_json invalid for {memory_id}") from exc
            status = _status_from_event(str(event.get("event_type")), payload)
            if status is None:
                continue
            event_created_at = str(event.get("created_at"))
            status_history_by_id[str(memory_id)].append(
                {
                    "at": event_created_at,
                    "event_hash": str(event.get("event_hash")),
                    "status": status,
                }
            )
            if event_created_at <= snapshot_timestamp:
                updated_at_snapshot_by_id[str(memory_id)] = event_created_at
                prior_serial = serial_at_snapshot_by_id.get(str(memory_id))
                try:
                    next_serial = int(event.get("seq"))
                except (TypeError, ValueError):
                    next_serial = None
                if next_serial is not None:
                    serial_at_snapshot_by_id[str(memory_id)] = (
                        next_serial
                        if prior_serial is None or next_serial > prior_serial
                        else prior_serial
                    )
                status_at_snapshot_by_id[str(memory_id)] = status
            if status == "active":
                prior_valid_from = valid_from_by_id[str(memory_id)]
                event_hash = str(event.get("event_hash"))
                if prior_valid_from is None or (event_created_at, event_hash) < (
                    prior_valid_from,
                    str(valid_from_event_hash_by_id[str(memory_id)]),
                ):
                    valid_from_by_id[str(memory_id)] = event_created_at
                    valid_from_event_hash_by_id[str(memory_id)] = event_hash
            elif status in {"deprecated", "revoked", "forgotten"}:
                prior_unlearned_at = unlearned_at_by_id[str(memory_id)]
                if prior_unlearned_at is None or event_created_at < prior_unlearned_at:
                    unlearned_at_by_id[str(memory_id)] = event_created_at

        return {
            "memories": memories,
            "memories_by_id": memories_by_id,
            "snapshot_timestamp": snapshot_timestamp,
            "status_history_by_id": status_history_by_id,
            "valid_from_by_id": valid_from_by_id,
            "valid_from_event_hash_by_id": valid_from_event_hash_by_id,
            "unlearned_at_by_id": unlearned_at_by_id,
            "status_at_snapshot_by_id": status_at_snapshot_by_id,
            "updated_at_snapshot_by_id": updated_at_snapshot_by_id,
            "serial_at_snapshot_by_id": serial_at_snapshot_by_id,
        }

    def _append_snapshot_supersession_transition(
        self,
        summary: dict[str, Any],
        *,
        superseded_memory_id: str,
        superseding_memory_ids: list[str],
        superseded_at: str,
        supersession_reasons: list[str],
        anchor_memory_id: str,
        anchor_event_hash: str | None,
        verified_receipts_by_memory_event: dict[tuple[str, str], dict[str, Any]],
    ) -> None:
        if anchor_event_hash is None:
            raise ValueError(f"snapshot supersession anchor missing event_hash for {anchor_memory_id}")
        anchor = verified_receipts_by_memory_event.get((anchor_memory_id, anchor_event_hash))
        if anchor is None:
            raise ValueError(
                f"snapshot supersession anchor missing verified receipt for {superseded_memory_id}->{anchor_memory_id}"
            )
        anchor_receipt = anchor["receipt"]
        anchor_verification = anchor["verification"]
        statement = anchor_receipt.get("treeship_statement") or {}
        statement_object = statement.get("object") or {}
        statement_evidence = statement.get("evidence") or {}
        attestation = anchor_receipt.get("treeship_attestation")
        summary["supersession_transition_count"] += 1
        if anchor_verification.get("ok"):
            summary["verified_supersession_transition_count"] += 1
        summary["supersession_transitions"].append(
            {
                "superseded_memory_id": superseded_memory_id,
                "superseding_memory_ids": superseding_memory_ids,
                "superseded_at": superseded_at,
                "supersession_reasons": supersession_reasons,
                "anchor_memory_id": anchor_memory_id,
                "anchor_receipt_id": anchor_receipt.get("receipt_id"),
                "anchor_receipt_hash": anchor_receipt.get("receipt_hash"),
                "anchor_receipt_kind": statement.get("kind"),
                "anchor_event_hash": anchor_event_hash,
                "actor_id": statement_object.get("actor_id"),
                "actor_uri": anchor_receipt.get("actor_uri"),
                "content_digest": anchor_receipt.get("content_digest"),
                "prior_merkle_root": statement_evidence.get("prior_merkle_root"),
                "merkle_root": anchor_receipt.get("merkle_root"),
                "new_merkle_root": statement_evidence.get("new_merkle_root", anchor_receipt.get("merkle_root")),
                "treeship_artifact_id": attestation.get("artifact_id") if isinstance(attestation, dict) else None,
                "trusted_provenance_verified": bool(anchor_verification.get("ok")),
                "semantic_truth_guaranteed": bool(anchor_verification.get("semantic_truth_guaranteed")),
            }
        )

    def _verify_snapshot_parent_supersession_transitions(
        self,
        supersession_context: dict[str, Any] | None,
        *,
        verified_receipts_by_memory_event: dict[tuple[str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        summary = {
            "supersession_transition_count": 0,
            "verified_supersession_transition_count": 0,
            "supersession_transitions": [],
        }
        if supersession_context is None:
            return summary
        memories = supersession_context["memories"]
        memories_by_id = supersession_context["memories_by_id"]
        valid_from_by_id = supersession_context["valid_from_by_id"]
        valid_from_event_hash_by_id = supersession_context["valid_from_event_hash_by_id"]
        unlearned_at_by_id = supersession_context["unlearned_at_by_id"]
        status_at_snapshot_by_id = supersession_context["status_at_snapshot_by_id"]

        child_ids_by_parent: dict[str, list[str]] = {}
        for memory in memories:
            if valid_from_by_id.get(memory.id) is None:
                continue
            for parent_id in memory.parents:
                if parent_id in memories_by_id:
                    child_ids_by_parent.setdefault(parent_id, []).append(memory.id)

        for parent_id, child_ids in sorted(child_ids_by_parent.items()):
            parent_valid_from = valid_from_by_id.get(parent_id)
            if parent_valid_from is None:
                continue
            parent_unlearned_at = unlearned_at_by_id.get(parent_id)
            child_activations = [
                (str(valid_from_by_id[child_id]), child_id)
                for child_id in child_ids
                if valid_from_by_id.get(child_id) is not None
            ]
            if not child_activations:
                continue
            child_activations.sort(key=lambda item: (item[0], item[1]))
            superseded_at = child_activations[0][0]
            if superseded_at <= parent_valid_from:
                continue
            if parent_unlearned_at is not None and parent_unlearned_at <= superseded_at:
                continue
            if status_at_snapshot_by_id.get(parent_id) != "active":
                continue

            superseding_memory_ids = [child_id for child_at, child_id in child_activations if child_at == superseded_at]
            anchor_memory_id = sorted(superseding_memory_ids)[0]
            self._append_snapshot_supersession_transition(
                summary,
                superseded_memory_id=parent_id,
                superseding_memory_ids=superseding_memory_ids,
                superseded_at=superseded_at,
                supersession_reasons=["active-child-candidate"],
                anchor_memory_id=anchor_memory_id,
                anchor_event_hash=valid_from_event_hash_by_id.get(anchor_memory_id),
                verified_receipts_by_memory_event=verified_receipts_by_memory_event,
            )
        return summary

    def _verify_snapshot_explicit_update_supersession_transitions(
        self,
        supersession_context: dict[str, Any] | None,
        *,
        verified_receipts_by_memory_event: dict[tuple[str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        summary = {
            "supersession_transition_count": 0,
            "verified_supersession_transition_count": 0,
            "supersession_transitions": [],
        }
        if supersession_context is None:
            return summary

        memories_by_id = supersession_context["memories_by_id"]
        valid_from_by_id = dict(supersession_context["valid_from_by_id"])
        valid_from_event_hash_by_id = supersession_context["valid_from_event_hash_by_id"]
        unlearned_at_by_id = dict(supersession_context["unlearned_at_by_id"])
        status_at_snapshot_by_id = dict(supersession_context["status_at_snapshot_by_id"])
        updated_at_snapshot_by_id = supersession_context["updated_at_snapshot_by_id"]
        serial_at_snapshot_by_id = supersession_context["serial_at_snapshot_by_id"]
        snapshot_timestamp = supersession_context["snapshot_timestamp"]

        child_ids_by_parent: dict[str, list[str]] = {}
        for memory in supersession_context["memories"]:
            if valid_from_by_id.get(memory.id) is None:
                continue
            for parent_id in memory.parents:
                if parent_id in memories_by_id:
                    child_ids_by_parent.setdefault(parent_id, []).append(memory.id)

        superseded_at_by_id: dict[str, str | None] = {memory_id: None for memory_id in memories_by_id}
        superseded_by_ids: dict[str, list[str]] = {memory_id: [] for memory_id in memories_by_id}
        supersession_reasons_by_id: dict[str, list[str]] = {memory_id: [] for memory_id in memories_by_id}
        for parent_id, child_ids in child_ids_by_parent.items():
            child_events = [
                (str(valid_from_by_id[child_id]), child_id)
                for child_id in child_ids
                if valid_from_by_id.get(child_id) is not None
            ]
            if not child_events:
                continue
            child_events.sort(key=lambda item: (item[0], item[1]))
            superseded_at = child_events[0][0]
            superseded_at_by_id[parent_id] = superseded_at
            superseded_by_ids[parent_id] = [
                child_id for child_at, child_id in child_events if child_at == superseded_at
            ]
            supersession_reasons_by_id[parent_id] = ["active-child-candidate"]

        _apply_query_at_explicit_updates(
            memories_by_id=memories_by_id,
            valid_from_by_id=valid_from_by_id,
            updated_at_query_by_id=updated_at_snapshot_by_id,
            unlearned_at_by_id=unlearned_at_by_id,
            status_at_query_by_id=status_at_snapshot_by_id,
            superseded_at_by_id=superseded_at_by_id,
            superseded_by_ids=superseded_by_ids,
            supersession_reasons_by_id=supersession_reasons_by_id,
            serial_at_query_by_id=serial_at_snapshot_by_id,
            timestamp=snapshot_timestamp,
        )

        for stale_memory_id in sorted(memories_by_id):
            reasons = supersession_reasons_by_id.get(stale_memory_id, [])
            if reasons != ["explicit-update-candidate"]:
                continue
            superseding_memory_ids = superseded_by_ids.get(stale_memory_id, [])
            superseded_at = superseded_at_by_id.get(stale_memory_id)
            if not superseding_memory_ids or superseded_at is None:
                continue
            anchor_memory_id = sorted(superseding_memory_ids)[0]
            self._append_snapshot_supersession_transition(
                summary,
                superseded_memory_id=stale_memory_id,
                superseding_memory_ids=superseding_memory_ids,
                superseded_at=superseded_at,
                supersession_reasons=reasons,
                anchor_memory_id=anchor_memory_id,
                anchor_event_hash=valid_from_event_hash_by_id.get(anchor_memory_id),
                verified_receipts_by_memory_event=verified_receipts_by_memory_event,
            )
        return summary

    def _verify_snapshot_subject_lookup_restatement_transitions(
        self,
        supersession_context: dict[str, Any] | None,
        *,
        verified_receipts_by_memory_event: dict[tuple[str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        summary = {
            "supersession_transition_count": 0,
            "verified_supersession_transition_count": 0,
            "supersession_transitions": [],
        }
        if supersession_context is None:
            return summary

        memories_by_id = supersession_context["memories_by_id"]
        valid_from_by_id = dict(supersession_context["valid_from_by_id"])
        valid_from_event_hash_by_id = supersession_context["valid_from_event_hash_by_id"]
        unlearned_at_by_id = dict(supersession_context["unlearned_at_by_id"])
        status_at_snapshot_by_id = dict(supersession_context["status_at_snapshot_by_id"])
        updated_at_snapshot_by_id = supersession_context["updated_at_snapshot_by_id"]
        serial_at_snapshot_by_id = supersession_context["serial_at_snapshot_by_id"]
        snapshot_timestamp = supersession_context["snapshot_timestamp"]

        child_ids_by_parent: dict[str, list[str]] = {}
        for memory in supersession_context["memories"]:
            if valid_from_by_id.get(memory.id) is None:
                continue
            for parent_id in memory.parents:
                if parent_id in memories_by_id:
                    child_ids_by_parent.setdefault(parent_id, []).append(memory.id)

        superseded_at_by_id: dict[str, str | None] = {memory_id: None for memory_id in memories_by_id}
        superseded_by_ids: dict[str, list[str]] = {memory_id: [] for memory_id in memories_by_id}
        supersession_reasons_by_id: dict[str, list[str]] = {memory_id: [] for memory_id in memories_by_id}
        for parent_id, child_ids in child_ids_by_parent.items():
            child_events = [
                (str(valid_from_by_id[child_id]), child_id)
                for child_id in child_ids
                if valid_from_by_id.get(child_id) is not None
            ]
            if not child_events:
                continue
            child_events.sort(key=lambda item: (item[0], item[1]))
            superseded_at = child_events[0][0]
            superseded_at_by_id[parent_id] = superseded_at
            superseded_by_ids[parent_id] = [
                child_id for child_at, child_id in child_events if child_at == superseded_at
            ]
            supersession_reasons_by_id[parent_id] = ["active-child-candidate"]

        _apply_query_at_explicit_updates(
            memories_by_id=memories_by_id,
            valid_from_by_id=valid_from_by_id,
            updated_at_query_by_id=updated_at_snapshot_by_id,
            unlearned_at_by_id=unlearned_at_by_id,
            status_at_query_by_id=status_at_snapshot_by_id,
            superseded_at_by_id=superseded_at_by_id,
            superseded_by_ids=superseded_by_ids,
            supersession_reasons_by_id=supersession_reasons_by_id,
            serial_at_query_by_id=serial_at_snapshot_by_id,
            timestamp=snapshot_timestamp,
        )
        _apply_query_at_subject_lookup_restatements(
            memories_by_id=memories_by_id,
            valid_from_by_id=valid_from_by_id,
            updated_at_query_by_id=updated_at_snapshot_by_id,
            unlearned_at_by_id=unlearned_at_by_id,
            status_at_query_by_id=status_at_snapshot_by_id,
            superseded_at_by_id=superseded_at_by_id,
            superseded_by_ids=superseded_by_ids,
            supersession_reasons_by_id=supersession_reasons_by_id,
            serial_at_query_by_id=serial_at_snapshot_by_id,
            timestamp=snapshot_timestamp,
        )

        for stale_memory_id in sorted(memories_by_id):
            reasons = supersession_reasons_by_id.get(stale_memory_id, [])
            if reasons != ["subject-lookup-restatement"]:
                continue
            superseding_memory_ids = superseded_by_ids.get(stale_memory_id, [])
            superseded_at = superseded_at_by_id.get(stale_memory_id)
            if not superseding_memory_ids or superseded_at is None:
                continue
            anchor_memory_id = sorted(superseding_memory_ids)[0]
            self._append_snapshot_supersession_transition(
                summary,
                superseded_memory_id=stale_memory_id,
                superseding_memory_ids=superseding_memory_ids,
                superseded_at=superseded_at,
                supersession_reasons=reasons,
                anchor_memory_id=anchor_memory_id,
                anchor_event_hash=valid_from_event_hash_by_id.get(anchor_memory_id),
                verified_receipts_by_memory_event=verified_receipts_by_memory_event,
            )
        return summary

    def verify(self, action_id: str) -> bool:
        self.init()
        row = self.conn.execute("SELECT merkle_root, memory_tree_json FROM receipts WHERE action_id = ?", (action_id,)).fetchone()
        if row is None:
            raise KeyError(f"action receipt not found: {action_id}")
        event_ok = row["merkle_root"] == self.current_merkle_root(before_action_id=action_id)
        memory_tree = json.loads(row["memory_tree_json"] or "{}")
        memory_tree_ok = True if not memory_tree else self.verify_memory_tree(memory_tree)
        return event_ok and memory_tree_ok

    def verify_memory_tree(self, tree: dict[str, Any]) -> bool:
        try:
            if tree.get("schema") != MEMORY_TREE_SCHEMA:
                return False
            leaves = tree.get("leaves")
            if not isinstance(leaves, list):
                return False
            leaf_hashes: list[str] = []
            for leaf in leaves:
                if not isinstance(leaf, dict):
                    return False
                material = leaf.get("material")
                if not isinstance(material, dict):
                    return False
                leaf_hash = leaf.get("leaf_hash")
                if leaf_hash != sha256_text(stable_json(material)):
                    return False
                leaf_hashes.append(leaf_hash)
            root = tree.get("root")
            if root != merkle_root(leaf_hashes):
                return False
            proofs = tree.get("proofs")
            if not isinstance(proofs, dict):
                return False
            for leaf in leaves:
                memory_id = leaf.get("memory_id")
                proof = proofs.get(memory_id)
                if not isinstance(proof, dict):
                    return False
                if proof.get("root") != root:
                    return False
                if proof.get("leaf_hash") != leaf.get("leaf_hash"):
                    return False
                proof_path = proof.get("proof")
                if not isinstance(proof_path, list):
                    return False
                if not verify_merkle_proof(leaf["leaf_hash"], proof_path, root):
                    return False
            return True
        except (KeyError, TypeError):
            return False

    def current_merkle_root(self, *, before_action_id: str | None = None) -> str:
        if before_action_id is None:
            rows = self.conn.execute("SELECT event_hash FROM events ORDER BY seq").fetchall()
        else:
            action_row = self.conn.execute(
                "SELECT seq FROM events WHERE action_id = ? ORDER BY seq LIMIT 1",
                (before_action_id,),
            ).fetchone()
            max_seq = action_row["seq"] - 1 if action_row else 0
            rows = self.conn.execute("SELECT event_hash FROM events WHERE seq <= ? ORDER BY seq", (max_seq,)).fetchall()
        return merkle_root([row["event_hash"] for row in rows])

    def session_starts(
        self,
        *,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE event_type = 'SESSION_STARTED'
            ORDER BY seq DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        starts: list[dict[str, Any]] = []
        for row in rows:
            session_start = self._session_start_from_event_row(row)
            if session_id is not None and session_start["session_id"] != session_id:
                continue
            if scope is not None and session_start["scope"] != scope:
                continue
            starts.append(session_start)
        return starts

    def session_ends(
        self,
        *,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE event_type = 'SESSION_ENDED'
            ORDER BY seq DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        ends: list[dict[str, Any]] = []
        for row in rows:
            session_end = self._session_end_from_event_row(row)
            if session_id is not None and session_end["session_id"] != session_id:
                continue
            if scope is not None and session_end["scope"] != scope:
                continue
            ends.append(session_end)
        return ends

    def session_checkpoints(
        self,
        *,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE event_type = 'SESSION_CHECKPOINTED'
            ORDER BY seq DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        checkpoints: list[dict[str, Any]] = []
        for row in rows:
            checkpoint = self._session_checkpoint_from_event_row(row)
            if session_id is not None and checkpoint["session_id"] != session_id:
                continue
            if scope is not None and checkpoint["scope"] != scope:
                continue
            checkpoints.append(checkpoint)
        return checkpoints

    def session_snapshots(
        self,
        *,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE event_type = 'SESSION_SNAPSHOTTED'
            ORDER BY seq DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        snapshots: list[dict[str, Any]] = []
        for row in rows:
            session_snapshot = self._session_snapshot_from_event_row(row)
            if session_id is not None and session_snapshot["session_id"] != session_id:
                continue
            if scope is not None and session_snapshot["scope"] != scope:
                continue
            snapshots.append(session_snapshot)
        return snapshots

    def session_snapshot_retention_rollup(
        self,
        *,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        if limit <= 0:
            return []
        rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE event_type = 'SESSION_SNAPSHOTTED'
            ORDER BY seq DESC
            """
        ).fetchall()
        rollups_by_key: dict[tuple[str, str | None], dict[str, Any]] = {}
        ordered_keys: list[tuple[str, str | None]] = []
        for row in rows:
            session_snapshot = self._session_snapshot_from_event_row(row)
            if session_id is not None and session_snapshot["session_id"] != session_id:
                continue
            if scope is not None and session_snapshot["scope"] != scope:
                continue
            key = (session_snapshot["session_id"], session_snapshot.get("scope"))
            rollup = rollups_by_key.get(key)
            if rollup is None:
                if len(ordered_keys) >= limit:
                    continue
                latest_payload_status = str(session_snapshot.get("payload_status") or "available")
                latest_retention = (
                    session_snapshot.get("retention")
                    if isinstance(session_snapshot.get("retention"), dict)
                    else {}
                )
                latest_status_root = (
                    latest_retention.get("soft_delete_merkle_root")
                    if latest_payload_status == "soft_deleted"
                    else session_snapshot["session_snapshot_merkle_root"]
                )
                rollup = {
                    "schema": "zerker.session_snapshot_retention_rollup_entry.v1",
                    "session_id": session_snapshot["session_id"],
                    "scope": session_snapshot.get("scope"),
                    "latest_session_snapshot_id": session_snapshot["session_snapshot_id"],
                    "latest_session_snapshot_created_at": session_snapshot["created_at"],
                    "latest_session_snapshot_hash": session_snapshot["snapshot_hash"],
                    "latest_session_snapshot_root": session_snapshot["session_snapshot_merkle_root"],
                    "latest_payload_status": latest_payload_status,
                    "latest_status_root": latest_status_root,
                    "latest_summary": session_snapshot.get("summary"),
                    "snapshot_count": 0,
                    "available_payload_count": 0,
                    "soft_deleted_payload_count": 0,
                    "latest_available_session_snapshot_id": None,
                    "latest_available_snapshot_hash": None,
                    "latest_available_snapshot_root": None,
                    "latest_available_created_at": None,
                    "latest_soft_deleted_session_snapshot_id": None,
                    "latest_soft_deleted_snapshot_hash": None,
                    "latest_soft_deleted_snapshot_root": None,
                    "latest_soft_deleted_deleted_at": None,
                    "latest_soft_deleted_deleted_by": None,
                    "latest_soft_deleted_reason": None,
                    "latest_soft_delete_root": None,
                    "retention_state": "all_available",
                }
                rollups_by_key[key] = rollup
                ordered_keys.append(key)
            rollup["snapshot_count"] += 1
            payload_status = str(session_snapshot.get("payload_status") or "available")
            if payload_status == "soft_deleted":
                rollup["soft_deleted_payload_count"] += 1
                if rollup["latest_soft_deleted_session_snapshot_id"] is None:
                    retention = (
                        session_snapshot.get("retention")
                        if isinstance(session_snapshot.get("retention"), dict)
                        else {}
                    )
                    rollup["latest_soft_deleted_session_snapshot_id"] = session_snapshot["session_snapshot_id"]
                    rollup["latest_soft_deleted_snapshot_hash"] = session_snapshot["snapshot_hash"]
                    rollup["latest_soft_deleted_snapshot_root"] = session_snapshot["session_snapshot_merkle_root"]
                    rollup["latest_soft_deleted_deleted_at"] = retention.get("deleted_at")
                    rollup["latest_soft_deleted_deleted_by"] = retention.get("deleted_by")
                    rollup["latest_soft_deleted_reason"] = retention.get("deleted_reason")
                    rollup["latest_soft_delete_root"] = retention.get("soft_delete_merkle_root")
            else:
                rollup["available_payload_count"] += 1
                if rollup["latest_available_session_snapshot_id"] is None:
                    rollup["latest_available_session_snapshot_id"] = session_snapshot["session_snapshot_id"]
                    rollup["latest_available_snapshot_hash"] = session_snapshot["snapshot_hash"]
                    rollup["latest_available_snapshot_root"] = session_snapshot["session_snapshot_merkle_root"]
                    rollup["latest_available_created_at"] = session_snapshot["created_at"]
        rollups: list[dict[str, Any]] = []
        for key in ordered_keys:
            rollup = rollups_by_key[key]
            available_payload_count = int(rollup["available_payload_count"])
            soft_deleted_payload_count = int(rollup["soft_deleted_payload_count"])
            if available_payload_count and soft_deleted_payload_count:
                rollup["retention_state"] = "mixed"
            elif soft_deleted_payload_count:
                rollup["retention_state"] = "soft_deleted_only"
            else:
                rollup["retention_state"] = "all_available"
            rollups.append(rollup)
        return rollups

    def session_lifecycle_rollup(
        self,
        *,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        if limit <= 0:
            return []
        rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE event_type IN (
              'SESSION_STARTED',
              'SESSION_ENDED',
              'SESSION_CHECKPOINTED',
              'SESSION_SNAPSHOTTED',
              'SESSION_SNAPSHOT_PAYLOAD_SOFT_DELETED'
            )
            ORDER BY seq DESC
            """
        ).fetchall()
        rollups_by_key: dict[tuple[str, str | None], dict[str, Any]] = {}
        ordered_keys: list[tuple[str, str | None]] = []
        for row in rows:
            entry = self._session_lifecycle_timeline_entry_from_event_row(row)
            if session_id is not None and entry["session_id"] != session_id:
                continue
            if scope is not None and entry["scope"] != scope:
                continue
            key = (entry["session_id"], entry.get("scope"))
            rollup = rollups_by_key.get(key)
            if rollup is None:
                if len(ordered_keys) >= limit:
                    continue
                rollup = {
                    "schema": "zerker.session_lifecycle_rollup_entry.v1",
                    "session_id": entry["session_id"],
                    "scope": entry.get("scope"),
                    "latest_event_kind": entry["event_kind"],
                    "latest_event_created_at": entry["created_at"],
                    "latest_lifecycle_id": entry["lifecycle_id"],
                    "latest_status_root": entry["timeline_root"],
                    "latest_summary": entry.get("summary"),
                    "latest_payload_status": entry.get("payload_status"),
                    "event_count": 0,
                    "start_count": 0,
                    "checkpoint_count": 0,
                    "snapshot_count": 0,
                    "snapshot_soft_delete_count": 0,
                    "end_count": 0,
                    "available_payload_count": 0,
                    "soft_deleted_payload_count": 0,
                    "verified_receipt_count": 0,
                    "failed_receipt_count": 0,
                    "linked_treeship_artifact_count": 0,
                    "latest_start_session_start_id": None,
                    "latest_start_root": None,
                    "latest_start_created_at": None,
                    "latest_start_token_budget_hint": None,
                    "latest_checkpoint_id": None,
                    "latest_checkpoint_root": None,
                    "latest_checkpoint_created_at": None,
                    "latest_session_snapshot_id": None,
                    "latest_session_snapshot_root": None,
                    "latest_session_snapshot_hash": None,
                    "latest_session_snapshot_created_at": None,
                    "latest_soft_deleted_session_snapshot_id": None,
                    "latest_soft_delete_root": None,
                    "latest_soft_deleted_deleted_at": None,
                    "latest_soft_deleted_deleted_by": None,
                    "latest_soft_deleted_reason": None,
                    "latest_session_end_id": None,
                    "latest_session_end_root": None,
                    "latest_session_end_created_at": None,
                    "latest_receipt_summary": None,
                }
                rollups_by_key[key] = rollup
                ordered_keys.append(key)

            rollup["event_count"] += 1
            event_kind = str(entry.get("event_kind") or "")
            count_key = f"{event_kind}_count"
            if count_key in rollup:
                rollup[count_key] += 1
            receipt_summary = self._session_lifecycle_receipt_summary(entry.get("receipt"))
            if receipt_summary.get("trusted_provenance_verified"):
                rollup["verified_receipt_count"] += 1
            else:
                rollup["failed_receipt_count"] += 1
            if receipt_summary.get("treeship_artifact_id"):
                rollup["linked_treeship_artifact_count"] += 1
            if rollup["latest_receipt_summary"] is None:
                rollup["latest_receipt_summary"] = dict(receipt_summary)

            if event_kind == "start" and rollup["latest_start_session_start_id"] is None:
                rollup["latest_start_session_start_id"] = entry["session_start_id"]
                rollup["latest_start_root"] = entry["session_start_merkle_root"]
                rollup["latest_start_created_at"] = entry["created_at"]
                token_budget_hint = entry.get("token_budget_hint")
                rollup["latest_start_token_budget_hint"] = (
                    dict(token_budget_hint) if isinstance(token_budget_hint, dict) else None
                )
            elif event_kind == "checkpoint" and rollup["latest_checkpoint_id"] is None:
                rollup["latest_checkpoint_id"] = entry["checkpoint_id"]
                rollup["latest_checkpoint_root"] = entry["checkpoint_merkle_root"]
                rollup["latest_checkpoint_created_at"] = entry["created_at"]
            elif event_kind == "snapshot":
                if rollup["latest_session_snapshot_id"] is None:
                    rollup["latest_session_snapshot_id"] = entry["session_snapshot_id"]
                    rollup["latest_session_snapshot_root"] = entry["session_snapshot_merkle_root"]
                    rollup["latest_session_snapshot_hash"] = entry["snapshot_hash"]
                    rollup["latest_session_snapshot_created_at"] = entry["created_at"]
                    rollup["latest_payload_status"] = entry.get("payload_status")
                payload_status = str(entry.get("payload_status") or "available")
                if payload_status == "soft_deleted":
                    rollup["soft_deleted_payload_count"] += 1
                else:
                    rollup["available_payload_count"] += 1
            elif event_kind == "snapshot_soft_delete" and rollup["latest_soft_deleted_session_snapshot_id"] is None:
                retention = entry.get("retention") if isinstance(entry.get("retention"), dict) else {}
                rollup["latest_soft_deleted_session_snapshot_id"] = entry["session_snapshot_id"]
                rollup["latest_soft_delete_root"] = retention.get("soft_delete_merkle_root")
                rollup["latest_soft_deleted_deleted_at"] = retention.get("deleted_at")
                rollup["latest_soft_deleted_deleted_by"] = retention.get("deleted_by")
                rollup["latest_soft_deleted_reason"] = retention.get("deleted_reason")
                rollup["latest_payload_status"] = entry.get("payload_status")
            elif event_kind == "end" and rollup["latest_session_end_id"] is None:
                rollup["latest_session_end_id"] = entry["session_end_id"]
                rollup["latest_session_end_root"] = entry["session_end_merkle_root"]
                rollup["latest_session_end_created_at"] = entry["created_at"]

        return [rollups_by_key[key] for key in ordered_keys]

    def _session_lifecycle_receipt_summary(self, receipt: Any) -> dict[str, Any]:
        if not isinstance(receipt, dict):
            return {
                "trusted_provenance_verified": False,
                "semantic_truth_guaranteed": False,
                "receipt_hash": None,
                "content_digest": None,
                "prior_merkle_root": None,
                "new_merkle_root": None,
                "treeship_artifact_id": None,
                "source_event_hash": None,
                "verification_error": "missing lifecycle receipt",
            }
        verification = self.verify_lifecycle_receipt(receipt)
        return {
            "trusted_provenance_verified": bool(verification.get("ok")),
            "semantic_truth_guaranteed": bool(verification.get("semantic_truth_guaranteed")),
            "receipt_hash": receipt.get("receipt_hash"),
            "content_digest": receipt.get("content_digest"),
            "prior_merkle_root": receipt.get("prior_merkle_root"),
            "new_merkle_root": receipt.get("merkle_root"),
            "treeship_artifact_id": receipt.get("treeship_artifact_id"),
            "source_event_hash": receipt.get("source_event_hash"),
            "verification_error": verification.get("error"),
        }

    def session_lifecycle_timeline(
        self,
        *,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        if limit <= 0:
            return []
        rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE event_type IN (
              'SESSION_STARTED',
              'SESSION_ENDED',
              'SESSION_CHECKPOINTED',
              'SESSION_SNAPSHOTTED',
              'SESSION_SNAPSHOT_PAYLOAD_SOFT_DELETED'
            )
            ORDER BY seq DESC
            """
        ).fetchall()
        timeline: list[dict[str, Any]] = []
        for row in rows:
            entry = self._session_lifecycle_timeline_entry_from_event_row(row)
            if session_id is not None and entry["session_id"] != session_id:
                continue
            if scope is not None and entry["scope"] != scope:
                continue
            timeline.append(entry)
            if len(timeline) >= limit:
                break
        return timeline

    def _session_checkpoint_from_event_row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise KeyError("session checkpoint event not found")
        payload = json.loads(row["payload_json"])
        if payload.get("schema") != SESSION_CHECKPOINT_SCHEMA:
            raise ValueError("event payload is not a session checkpoint")
        receipt = self._lifecycle_receipt_from_event_row(
            row,
            payload,
            mutation="checkpoint_session",
            mutation_id=payload["checkpoint_id"],
        )
        return {
            "schema": SESSION_CHECKPOINT_SCHEMA,
            "checkpoint_id": payload["checkpoint_id"],
            "session_id": payload["session_id"],
            "scope": payload.get("scope"),
            "summary": payload.get("summary"),
            "actor_id": row["actor_id"],
            "event_hash": row["event_hash"],
            "prior_event_hash": row["prev_event_hash"],
            "prior_merkle_root": payload["prior_merkle_root"],
            "checkpoint_merkle_root": row["merkle_root"],
            "created_at": row["created_at"],
            "snapshot": {
                "snapshot_hash": payload["snapshot_hash"],
                "snapshot_merkle_root": payload["snapshot_merkle_root"],
                "memory_count": payload["snapshot_memory_count"],
                "event_count": payload["snapshot_event_count"],
            },
            "memory_count": payload["memory_count"],
            "active_memory_ids": payload["active_memory_ids"],
            "memory_tree": {
                "root": payload["memory_tree_root"],
                "leaf_count": payload["memory_tree_leaf_count"],
            },
            "memory_type_summary": payload["memory_type_summary"],
            "receipt": receipt,
        }

    def _session_start_from_event_row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise KeyError("session start event not found")
        payload = json.loads(row["payload_json"])
        if payload.get("schema") != SESSION_START_SCHEMA:
            raise ValueError("event payload is not a session start")
        receipt = self._lifecycle_receipt_from_event_row(
            row,
            payload,
            mutation="start_session",
            mutation_id=payload["session_start_id"],
        )
        token_budget_hint = None
        if payload.get("context_budget_tokens") is not None:
            token_budget_hint = {"context_budget_tokens": payload["context_budget_tokens"]}
        return {
            "schema": SESSION_START_SCHEMA,
            "session_start_id": payload["session_start_id"],
            "session_id": payload["session_id"],
            "scope": payload.get("scope"),
            "summary": payload.get("summary"),
            "actor_id": row["actor_id"],
            "event_hash": row["event_hash"],
            "prior_event_hash": row["prev_event_hash"],
            "prior_merkle_root": payload["prior_merkle_root"],
            "session_start_merkle_root": row["merkle_root"],
            "created_at": row["created_at"],
            "snapshot": {
                "snapshot_hash": payload["snapshot_hash"],
                "snapshot_merkle_root": payload["snapshot_merkle_root"],
                "memory_count": payload["snapshot_memory_count"],
                "event_count": payload["snapshot_event_count"],
            },
            "memory_count": payload["memory_count"],
            "active_memory_ids": payload["active_memory_ids"],
            "memory_tree": {
                "root": payload["memory_tree_root"],
                "leaf_count": payload["memory_tree_leaf_count"],
            },
            "memory_type_summary": payload["memory_type_summary"],
            "token_budget_hint": token_budget_hint,
            "receipt": receipt,
        }

    def _session_end_from_event_row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise KeyError("session end event not found")
        payload = json.loads(row["payload_json"])
        if payload.get("schema") != SESSION_END_SCHEMA:
            raise ValueError("event payload is not a session end")
        receipt = self._lifecycle_receipt_from_event_row(
            row,
            payload,
            mutation="end_session",
            mutation_id=payload["session_end_id"],
        )
        return {
            "schema": SESSION_END_SCHEMA,
            "session_end_id": payload["session_end_id"],
            "session_id": payload["session_id"],
            "scope": payload.get("scope"),
            "summary": payload.get("summary"),
            "actor_id": row["actor_id"],
            "event_hash": row["event_hash"],
            "prior_event_hash": row["prev_event_hash"],
            "prior_merkle_root": payload["prior_merkle_root"],
            "session_end_merkle_root": row["merkle_root"],
            "created_at": row["created_at"],
            "snapshot": {
                "snapshot_hash": payload["snapshot_hash"],
                "snapshot_merkle_root": payload["snapshot_merkle_root"],
                "memory_count": payload["snapshot_memory_count"],
                "event_count": payload["snapshot_event_count"],
            },
            "memory_count": payload["memory_count"],
            "active_memory_ids": payload["active_memory_ids"],
            "memory_tree": {
                "root": payload["memory_tree_root"],
                "leaf_count": payload["memory_tree_leaf_count"],
            },
            "memory_type_summary": payload["memory_type_summary"],
            "receipt": receipt,
        }

    def _session_snapshot_from_event_row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise KeyError("session snapshot event not found")
        payload = json.loads(row["payload_json"])
        if payload.get("schema") != SESSION_SNAPSHOT_SCHEMA:
            raise ValueError("event payload is not a session snapshot")
        session_snapshot_id = payload["session_snapshot_id"]
        snapshot_row = self.conn.execute(
            """
            SELECT *
            FROM session_snapshot_payloads
            WHERE session_snapshot_id = ?
            """,
            (session_snapshot_id,),
        ).fetchone()
        if snapshot_row is None:
            raise KeyError(f"session snapshot payload not found: {session_snapshot_id}")
        if snapshot_row["snapshot_hash"] != payload["snapshot_hash"]:
            raise ValueError("session snapshot payload hash mismatch")
        snapshot = None
        retention = None
        payload_status = "available"
        if snapshot_row["deleted_at"]:
            payload_status = "soft_deleted"
            deleted_event_hash = snapshot_row["deleted_event_hash"]
            deleted_event_row = None
            deleted_payload = None
            retention_receipt = None
            if deleted_event_hash:
                deleted_event_row = self.conn.execute(
                    "SELECT * FROM events WHERE event_hash = ?",
                    (deleted_event_hash,),
                ).fetchone()
            if deleted_event_row is not None:
                deleted_payload = json.loads(deleted_event_row["payload_json"])
                if deleted_payload.get("schema") != SESSION_SNAPSHOT_RETENTION_SCHEMA:
                    raise ValueError("session snapshot retention payload schema mismatch")
                retention_receipt = self._lifecycle_receipt_from_event_row(
                    deleted_event_row,
                    deleted_payload,
                    mutation="soft_delete_session_snapshot_payload",
                    mutation_id=session_snapshot_id,
                )
            retention = {
                "deleted_at": snapshot_row["deleted_at"],
                "deleted_by": snapshot_row["deleted_by"],
                "deleted_reason": snapshot_row["deleted_reason"],
                "deleted_event_hash": deleted_event_hash,
                "prior_merkle_root": deleted_payload.get("prior_merkle_root") if isinstance(deleted_payload, dict) else None,
                "soft_delete_merkle_root": deleted_event_row["merkle_root"] if deleted_event_row is not None else None,
                "receipt": retention_receipt,
            }
        else:
            snapshot = json.loads(snapshot_row["snapshot_json"])
            if snapshot.get("snapshot_hash") != payload["snapshot_hash"]:
                raise ValueError("session snapshot stored snapshot_hash mismatch")
        receipt = self._lifecycle_receipt_from_event_row(
            row,
            payload,
            mutation="snapshot_session",
            mutation_id=session_snapshot_id,
        )
        return {
            "schema": SESSION_SNAPSHOT_SCHEMA,
            "session_snapshot_id": session_snapshot_id,
            "session_id": payload["session_id"],
            "scope": payload.get("scope"),
            "summary": payload.get("summary"),
            "actor_id": row["actor_id"],
            "event_hash": row["event_hash"],
            "prior_event_hash": row["prev_event_hash"],
            "prior_merkle_root": payload["prior_merkle_root"],
            "session_snapshot_merkle_root": row["merkle_root"],
            "created_at": row["created_at"],
            "snapshot_hash": payload["snapshot_hash"],
            "payload_status": payload_status,
            "retention": retention,
            "snapshot": snapshot,
            "memory_count": payload["memory_count"],
            "active_memory_ids": payload["active_memory_ids"],
            "memory_tree": {
                "root": payload["memory_tree_root"],
                "leaf_count": payload["memory_tree_leaf_count"],
            },
            "memory_type_summary": payload["memory_type_summary"],
            "receipt": receipt,
        }

    def _session_lifecycle_timeline_entry_from_event_row(self, row: sqlite3.Row) -> dict[str, Any]:
        event_type = row["event_type"]
        if event_type == "SESSION_STARTED":
            session_start = self._session_start_from_event_row(row)
            return {
                **session_start,
                "schema": "zerker.session_lifecycle_timeline_entry.v1",
                "event_kind": "start",
                "event_type": event_type,
                "lifecycle_id": session_start["session_start_id"],
                "timeline_root": session_start["session_start_merkle_root"],
            }
        if event_type == "SESSION_ENDED":
            session_end = self._session_end_from_event_row(row)
            return {
                **session_end,
                "schema": "zerker.session_lifecycle_timeline_entry.v1",
                "event_kind": "end",
                "event_type": event_type,
                "lifecycle_id": session_end["session_end_id"],
                "timeline_root": session_end["session_end_merkle_root"],
            }
        if event_type == "SESSION_CHECKPOINTED":
            checkpoint = self._session_checkpoint_from_event_row(row)
            return {
                **checkpoint,
                "schema": "zerker.session_lifecycle_timeline_entry.v1",
                "event_kind": "checkpoint",
                "event_type": event_type,
                "lifecycle_id": checkpoint["checkpoint_id"],
                "timeline_root": checkpoint["checkpoint_merkle_root"],
            }
        if event_type == "SESSION_SNAPSHOTTED":
            session_snapshot = self._session_snapshot_from_event_row(row)
            return {
                **session_snapshot,
                "schema": "zerker.session_lifecycle_timeline_entry.v1",
                "event_kind": "snapshot",
                "event_type": event_type,
                "lifecycle_id": session_snapshot["session_snapshot_id"],
                "timeline_root": session_snapshot["session_snapshot_merkle_root"],
            }
        if event_type == "SESSION_SNAPSHOT_PAYLOAD_SOFT_DELETED":
            payload = json.loads(row["payload_json"])
            if payload.get("schema") != SESSION_SNAPSHOT_RETENTION_SCHEMA:
                raise ValueError("event payload is not a session snapshot retention tombstone")
            snapshot_event_row = self.conn.execute(
                """
                SELECT events.*
                FROM events
                INNER JOIN session_snapshot_payloads
                  ON session_snapshot_payloads.event_hash = events.event_hash
                WHERE session_snapshot_payloads.session_snapshot_id = ?
                  AND events.event_type = 'SESSION_SNAPSHOTTED'
                """,
                (payload["session_snapshot_id"],),
            ).fetchone()
            session_snapshot = self._session_snapshot_from_event_row(snapshot_event_row)
            retention = session_snapshot.get("retention") if isinstance(session_snapshot.get("retention"), dict) else {}
            return {
                **session_snapshot,
                "schema": "zerker.session_lifecycle_timeline_entry.v1",
                "event_kind": "snapshot_soft_delete",
                "event_type": event_type,
                "lifecycle_id": payload["session_snapshot_id"],
                "timeline_root": row["merkle_root"],
                "snapshot_created_at": session_snapshot["created_at"],
                "created_at": row["created_at"],
                "actor_id": row["actor_id"],
                "event_hash": row["event_hash"],
                "prior_event_hash": row["prev_event_hash"],
                "prior_merkle_root": payload["prior_merkle_root"],
                "summary": payload.get("summary"),
                "receipt": retention.get("receipt"),
            }
        raise ValueError(f"unsupported lifecycle timeline event type: {event_type}")

    def _lifecycle_receipt_from_event_row(
        self,
        row: sqlite3.Row,
        payload: dict[str, Any],
        *,
        mutation: str,
        mutation_id: str,
    ) -> dict[str, Any]:
        actor_id = row["actor_id"]
        actor_uri = actor_uri_for(actor_id)
        source_payload = dict(payload)
        content_digest = digest_uri(stable_json(source_payload))
        receipt_id = "lr_" + sha256_text(f"{mutation}:{mutation_id}:{row['event_hash']}")[:24]
        receipt_without_hash = {
            "receipt_schema": LIFECYCLE_RECEIPT_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "receipt_id": receipt_id,
            "mutation": mutation,
            "session_id": payload["session_id"],
            "actor_uri": actor_uri,
            "scope": payload.get("scope"),
            "source_event_hash": row["event_hash"],
            "content_digest": content_digest,
            "merkle_root": row["merkle_root"],
            "treeship_artifact_id": None,
            "source_payload": source_payload,
            "created_at": row["created_at"],
        }
        treeship_statement = {
            "schema": "com.zerker.memory.treeship.statement",
            "schema_version": "0.1.0",
            "statement_version": "1",
            "kind": "zerker.memory.mutation_receipt",
            "producer": {"name": "zerker-memory"},
            "subject": {
                "type": "session_mutation",
                "id": receipt_id,
                "session_id": payload["session_id"],
                "mutation_id": mutation_id,
            },
            "predicate": "memory.mutation.receipt.generated",
            "object": {
                "mutation": mutation,
                "actor_id": actor_id,
                "session_id": payload["session_id"],
                "scope": payload.get("scope"),
                "summary": payload.get("summary"),
                "snapshot_hash": payload["snapshot_hash"],
                "content_digest": content_digest,
                "semantic_truth_guaranteed": False,
            },
            "evidence": {
                "hash_alg": HASH_ALG,
                "merkle_alg": MERKLE_ALG,
                "event_hash": row["event_hash"],
                "prior_event_hash": row["prev_event_hash"],
                "prior_merkle_root": payload["prior_merkle_root"],
                "new_merkle_root": row["merkle_root"],
                "snapshot_hash": payload["snapshot_hash"],
                "payload_digest": content_digest,
            },
            "source": {
                "system": "zerker-memory",
                "event": {
                    "event_schema": EVENT_SCHEMA,
                    "hash_alg": HASH_ALG,
                    "event_type": row["event_type"],
                    "memory_id": None,
                    "action_id": None,
                    "payload_hash": row["payload_hash"],
                    "prev_event_hash": row["prev_event_hash"],
                    "event_hash": row["event_hash"],
                    "actor_id": actor_id,
                    "actor_uri": actor_uri,
                    "created_at": row["created_at"],
                },
                "payload": source_payload,
                "treeship_artifact_id": None,
                "receipt": receipt_without_hash,
            },
            "created_at": row["created_at"],
        }
        if payload.get("context_budget_tokens") is not None:
            treeship_statement["object"]["context_budget_tokens"] = payload["context_budget_tokens"]
        receipt = dict(receipt_without_hash)
        receipt["treeship_statement"] = treeship_statement
        receipt["receipt_hash"] = sha256_text(stable_json(receipt))
        return receipt

    def _restore_snapshot_receipt(
        self,
        snapshot: dict[str, Any],
        *,
        actor_id: str,
        prior_merkle_root: str,
        new_merkle_root: str,
    ) -> dict[str, Any]:
        created_at = now_iso()
        source_payload = {
            "snapshot_hash": snapshot["snapshot_hash"],
            "snapshot_merkle_root": snapshot["merkle_root"],
            "memory_count": snapshot["memory_count"],
            "event_count": snapshot["event_count"],
            "receipt_count": snapshot["receipt_count"],
            "write_receipt_count": snapshot.get("write_receipt_count", len(snapshot.get("write_receipts", []))),
        }
        content_digest = digest_uri(stable_json(source_payload))
        receipt_id = "lr_" + sha256_text(f"restore_snapshot:{snapshot['snapshot_hash']}:{actor_id}:{new_merkle_root}")[:24]
        receipt_without_hash = {
            "receipt_schema": LIFECYCLE_RECEIPT_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "receipt_id": receipt_id,
            "mutation": "restore_snapshot",
            "session_id": None,
            "actor_uri": actor_uri_for(actor_id),
            "scope": None,
            "source_event_hash": None,
            "content_digest": content_digest,
            "merkle_root": new_merkle_root,
            "treeship_artifact_id": None,
            "source_payload": source_payload,
            "created_at": created_at,
        }
        treeship_statement = {
            "schema": "com.zerker.memory.treeship.statement",
            "schema_version": "0.1.0",
            "statement_version": "1",
            "kind": "zerker.memory.mutation_receipt",
            "producer": {"name": "zerker-memory"},
            "subject": {
                "type": "snapshot_restore",
                "id": receipt_id,
                "snapshot_hash": snapshot["snapshot_hash"],
            },
            "predicate": "memory.mutation.receipt.generated",
            "object": {
                "mutation": "restore_snapshot",
                "actor_id": actor_id,
                "actor_uri": actor_uri_for(actor_id),
                "snapshot_hash": snapshot["snapshot_hash"],
                "snapshot_merkle_root": snapshot["merkle_root"],
                "content_digest": content_digest,
                "semantic_truth_guaranteed": False,
            },
            "evidence": {
                "hash_alg": HASH_ALG,
                "merkle_alg": MERKLE_ALG,
                "prior_merkle_root": prior_merkle_root,
                "new_merkle_root": new_merkle_root,
                "snapshot_hash": snapshot["snapshot_hash"],
                "payload_digest": content_digest,
                "source_snapshot_verified": True,
            },
            "source": {
                "system": "zerker-memory",
                "snapshot": source_payload,
                "treeship_artifact_id": None,
                "receipt": receipt_without_hash,
            },
            "created_at": created_at,
        }
        receipt = dict(receipt_without_hash)
        receipt["treeship_statement"] = treeship_statement
        receipt["receipt_hash"] = sha256_text(stable_json(receipt))
        return receipt

    def _append_event(
        self,
        event_type: str,
        *,
        actor_id: str,
        payload: dict[str, Any],
        memory_id: str | None = None,
        action_id: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        # Read and advance the chain head while holding SQLite's cross-process writer lock.
        if not self.conn.in_transaction:
            self.conn.execute("BEGIN IMMEDIATE")
        prev_row = self.conn.execute("SELECT event_hash, merkle_root FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prev_row["event_hash"] if prev_row else sha256_text("genesis")
        prior_merkle_root = prev_row["merkle_root"] if prev_row else merkle_root([])
        payload_json = stable_json(payload)
        payload_hash = sha256_text(payload_json)
        created_at = created_at or now_iso()
        event_material = stable_json(
            {
                "event_schema": EVENT_SCHEMA,
                "hash_alg": HASH_ALG,
                "event_type": event_type,
                "memory_id": memory_id,
                "action_id": action_id,
                "actor_id": actor_id,
                "payload_hash": payload_hash,
                "prev_event_hash": prev_hash,
                "created_at": created_at,
            }
        )
        event_hash = sha256_text(event_material)
        existing_hashes = [row["event_hash"] for row in self.conn.execute("SELECT event_hash FROM events ORDER BY seq")]
        root = merkle_root(existing_hashes + [event_hash])
        self.conn.execute(
            """
            INSERT INTO events (
              event_type, memory_id, action_id, actor_id, payload_json, payload_hash,
              prev_event_hash, event_hash, merkle_root, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_type, memory_id, action_id, actor_id, payload_json, payload_hash, prev_hash, event_hash, root, created_at),
        )
        return {
            "event_schema": EVENT_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "event_type": event_type,
            "memory_id": memory_id,
            "action_id": action_id,
            "actor_id": actor_id,
            "payload_json": payload_json,
            "payload_hash": payload_hash,
            "prev_event_hash": prev_hash,
            "prior_merkle_root": prior_merkle_root,
            "event_hash": event_hash,
            "merkle_root": root,
            "created_at": created_at,
        }

    def _append_write_receipt(
        self,
        *,
        memory_id: str,
        actor_uri: str,
        session_id: str,
        parent_action_id: str | None,
        source_uri: str | None,
        content_digest: str,
        environment_hash: str,
        event: dict[str, Any],
        created_at: str,
        caused_by_event: str | None = None,
        statement_kind: str = "zerker.memory.write_provenance",
        predicate: str = "memory.write.provenance.generated",
        subject_type: str = "memory_write",
        object_updates: dict[str, Any] | None = None,
        evidence_updates: dict[str, Any] | None = None,
        source_updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        receipt_id = "wr_" + sha256_text(f"{memory_id}:{event['event_hash']}")[:24]
        receipt_without_hash = {
            "receipt_schema": WRITE_RECEIPT_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "receipt_id": receipt_id,
            "memory_id": memory_id,
            "actor_uri": actor_uri,
            "session_id": session_id,
            "parent_action_id": parent_action_id,
            "source_uri": source_uri,
            "caused_by_event": caused_by_event,
            "content_digest": content_digest,
            "environment_hash": environment_hash,
            "event_hash": event["event_hash"],
            "merkle_root": event["merkle_root"],
            "created_at": created_at,
        }
        statement_object = {
            "actor_uri": actor_uri,
            "session_id": session_id,
            "parent_action_id": parent_action_id,
            "source_uri": source_uri,
            "caused_by_event": caused_by_event,
            "content_digest": content_digest,
            "environment_hash": environment_hash,
        }
        if object_updates:
            statement_object.update(object_updates)
        statement_evidence = {
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "event_hash": event["event_hash"],
            "prior_event_hash": event.get("prev_event_hash"),
            "prior_merkle_root": event.get("prior_merkle_root"),
            "merkle_root": event["merkle_root"],
            "new_merkle_root": event["merkle_root"],
        }
        if evidence_updates:
            statement_evidence.update(evidence_updates)
        statement_source = {"system": "zerker-memory", "event": event, "receipt": receipt_without_hash}
        if source_updates:
            statement_source.update(source_updates)
        treeship_statement = {
            "schema": "com.zerker.memory.treeship.statement",
            "schema_version": "0.1.0",
            "statement_version": "1",
            "kind": statement_kind,
            "producer": {"name": "zerker-memory"},
            "subject": {"type": subject_type, "id": receipt_id, "memory_id": memory_id},
            "predicate": predicate,
            "object": statement_object,
            "evidence": statement_evidence,
            "source": statement_source,
            "created_at": created_at,
        }
        receipt = dict(receipt_without_hash)
        receipt["treeship_statement"] = treeship_statement
        receipt["receipt_hash"] = sha256_text(stable_json(receipt))
        treeship_attestation = self._maybe_attest_write_receipt(receipt)
        if treeship_attestation is not None:
            treeship_statement["attestation"] = treeship_attestation
            receipt["treeship_attestation"] = treeship_attestation
        self.conn.execute(
            """
            INSERT INTO memory_write_receipts (
              receipt_id, receipt_schema, hash_alg, merkle_alg, memory_id, actor_uri, session_id,
              parent_action_id, source_uri, content_digest, environment_hash, event_hash, merkle_root,
              treeship_statement_json, created_at, receipt_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                WRITE_RECEIPT_SCHEMA,
                HASH_ALG,
                MERKLE_ALG,
                memory_id,
                actor_uri,
                session_id,
                parent_action_id,
                source_uri,
                content_digest,
                environment_hash,
                event["event_hash"],
                event["merkle_root"],
                stable_json(treeship_statement),
                created_at,
                receipt["receipt_hash"],
            ),
        )
        return receipt

    def _maybe_attest_write_receipt(self, receipt: dict[str, Any]) -> dict[str, Any] | None:
        if not self.treeship_auto_sign:
            return None
        payload_digest = f"{HASH_ALG}:{receipt['receipt_hash']}"
        try:
            from .treeship import attest_treeship_payload_digest

            attestation = attest_treeship_payload_digest(
                payload_digest,
                system_uri="system://zmem",
                kind="memory.write",
                subject=receipt["receipt_id"],
                config_path=self.treeship_config_path,
            )
        except Exception as exc:  # pragma: no cover - defensive around external CLI boundaries
            if self.treeship_strict:
                raise RuntimeError(f"Treeship write receipt attestation failed: {exc}") from exc
            attestation = {
                "schema": "zerker.memory.treeship_attestation.v1",
                "system": "system://zmem",
                "kind": "memory.write",
                "payload_digest": payload_digest,
                "subject": receipt["receipt_id"],
                "status": "failed",
                "artifact_id": None,
                "signed_at": None,
                "error": str(exc),
            }
        if self.treeship_strict and attestation.get("status") != "signed":
            raise RuntimeError(attestation.get("error") or "Treeship write receipt attestation failed")
        return {
            "schema": attestation.get("schema", "zerker.memory.treeship_attestation.v1"),
            "status": attestation.get("status"),
            "system": attestation.get("system", "system://zmem"),
            "kind": attestation.get("kind", "memory.write"),
            "subject": attestation.get("subject", receipt["receipt_id"]),
            "payload_digest": attestation.get("payload_digest", payload_digest),
            "artifact_id": attestation.get("artifact_id"),
            "signed_at": attestation.get("signed_at"),
            "error": attestation.get("error"),
        }

    @staticmethod
    def _default_trust(source_kind: str) -> float:
        return {
            "human": 0.95,
            "system": 0.9,
            "tool": 0.75,
            "document": 0.65,
            "agent": 0.5,
            "import": 0.45,
        }.get(source_kind, 0.4)

    @staticmethod
    def _default_authority(memory_type: str, source_kind: str) -> str:
        if memory_type == "policy":
            return "policy" if source_kind in {"human", "system"} else "none"
        if memory_type == "procedural":
            return "medium" if source_kind in {"human", "system"} else "low"
        if memory_type == "semantic":
            return "medium" if source_kind in {"human", "system", "tool"} else "low"
        return "low"

    @staticmethod
    def _default_status(source_kind: str, memory_type: str) -> str:
        if memory_type == "policy" and source_kind not in {"human", "system"}:
            return "quarantined"
        if source_kind in {"agent", "tool", "document", "import"}:
            return "quarantined"
        return "active"


def _write_receipt_status(receipt: dict[str, Any] | None) -> str | None:
    if not isinstance(receipt, dict):
        return None
    status = receipt.get("status")
    if isinstance(status, str) and status:
        return status
    statement = receipt.get("treeship_statement")
    if not isinstance(statement, dict):
        return None
    statement_object = statement.get("object")
    if not isinstance(statement_object, dict):
        return None
    nested_status = statement_object.get("status")
    if isinstance(nested_status, str) and nested_status:
        return nested_status
    return None

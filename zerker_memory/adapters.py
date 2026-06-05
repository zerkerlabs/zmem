from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ExternalMemoryCandidate:
    provider: str
    external_id: str
    content: str
    score: float | None = None
    source_uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "external_id": self.external_id,
            "content": self.content,
            "score": self.score,
            "source_uri": self.source_uri,
            "metadata": self.metadata,
        }


class MemoryAdapter(Protocol):
    provider: str

    def search(self, query: str, *, user_id: str | None = None, limit: int = 10) -> list[ExternalMemoryCandidate]:
        ...


class Mem0RestAdapter:
    """Small REST adapter for Mem0 OSS/self-hosted or hosted-compatible endpoints.

    The adapter intentionally normalizes only search results. Zerker's local store
    remains the governance layer for trust, authority, quarantine, and receipts.
    """

    provider = "mem0"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.getenv("MEM0_BASE_URL") or "http://localhost:8888").rstrip("/")
        self.api_key = api_key or os.getenv("MEM0_API_KEY")

    def search(self, query: str, *, user_id: str | None = None, limit: int = 10) -> list[ExternalMemoryCandidate]:
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if user_id:
            payload["user_id"] = user_id
        data = self._post_json("/memories/search", payload)
        return normalize_mem0_search(data)

    def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            urllib.parse.urljoin(self.base_url + "/", path.lstrip("/")),
            data=body,
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class ZepRestAdapter:
    """Small REST adapter for common Zep-style search endpoints.

    The endpoint and response shape are intentionally configurable so Zerker can
    govern candidate recall without binding the product to one hosted topology.
    """

    provider = "zep"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        search_path: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("ZEP_BASE_URL") or "http://localhost:8000").rstrip("/")
        self.api_key = api_key or os.getenv("ZEP_API_KEY")
        self.search_path = search_path or os.getenv("ZEP_SEARCH_PATH") or "/api/v1/search"

    def search(self, query: str, *, user_id: str | None = None, limit: int = 10) -> list[ExternalMemoryCandidate]:
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if user_id:
            payload["user_id"] = user_id
            payload["userId"] = user_id
        data = self._post_json(self.search_path, payload)
        return normalize_zep_search(data)

    def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            urllib.parse.urljoin(self.base_url + "/", path.lstrip("/")),
            data=body,
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def normalize_mem0_search(data: Any) -> list[ExternalMemoryCandidate]:
    """Normalize common Mem0 OSS/platform search response shapes."""

    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            rows = data["results"]
        elif isinstance(data.get("data"), dict) and isinstance(data["data"].get("results"), list):
            rows = data["data"]["results"]
        elif isinstance(data.get("memories"), list):
            rows = data["memories"]
        else:
            rows = []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    candidates: list[ExternalMemoryCandidate] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        content = row.get("memory") or row.get("content") or row.get("text")
        if not isinstance(content, str) or not content:
            continue
        external_id = str(row.get("id") or row.get("memory_id") or f"mem0_{idx}")
        score = row.get("score")
        candidates.append(
            ExternalMemoryCandidate(
                provider="mem0",
                external_id=external_id,
                content=content,
                score=float(score) if isinstance(score, (float, int)) else None,
                source_uri=row.get("source") if isinstance(row.get("source"), str) else None,
                metadata={k: v for k, v in row.items() if k not in {"id", "memory_id", "memory", "content", "text", "score"}},
            )
        )
    return candidates


def normalize_zep_search(data: Any) -> list[ExternalMemoryCandidate]:
    """Normalize common Zep-style search response shapes."""

    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            rows = data["results"]
        elif isinstance(data.get("matches"), list):
            rows = data["matches"]
        elif isinstance(data.get("documents"), list):
            rows = data["documents"]
        elif isinstance(data.get("data"), dict) and isinstance(data["data"].get("results"), list):
            rows = data["data"]["results"]
        else:
            rows = []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    candidates: list[ExternalMemoryCandidate] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        content = (
            row.get("content")
            or row.get("text")
            or row.get("document")
            or row.get("page_content")
            or row.get("message")
        )
        if not isinstance(content, str) or not content:
            continue
        external_id = str(row.get("id") or row.get("uuid") or row.get("document_id") or f"zep_{idx}")
        score = row.get("score")
        if not isinstance(score, (float, int)):
            score = row.get("relevance_score")
        candidates.append(
            ExternalMemoryCandidate(
                provider="zep",
                external_id=external_id,
                content=content,
                score=float(score) if isinstance(score, (float, int)) else None,
                source_uri=row.get("source") if isinstance(row.get("source"), str) else None,
                metadata={
                    k: v
                    for k, v in row.items()
                    if k
                    not in {
                        "id",
                        "uuid",
                        "document_id",
                        "content",
                        "text",
                        "document",
                        "page_content",
                        "message",
                        "score",
                        "relevance_score",
                    }
                },
            )
        )
    return candidates

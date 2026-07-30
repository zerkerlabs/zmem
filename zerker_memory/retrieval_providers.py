from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


RETRIEVAL_PROVIDERS_SCHEMA = "zerker.retrieval_providers.v1"
REDACTED_CONFIG_SCHEMA = "zerker.redacted_config.v1"

_SECRET_KEY_RE = re.compile(r"(api[_-]?key|authorization|token|secret|password)", re.IGNORECASE)
_SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]+|bearer\s+\S+|secret|token|password|api[_-]?key)", re.IGNORECASE)
_REDACTED = "<redacted>"
_FASTEMBED_MODELS: dict[tuple[str, str, int | None], Any] = {}
_FASTEMBED_MODEL_DIGESTS: dict[str, str] = {}


@dataclass(frozen=True)
class RetrievalProviderEntry:
    kind: str
    provider_id: str
    enabled: bool
    network: bool
    model_id: str | None = None
    reranker_id: str | None = None
    settings: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class RetrievalNetworkPolicy:
    allow_network_providers: bool = False


@dataclass(frozen=True)
class EmbeddingProviderResult:
    provider_id: str
    model_id: str
    dims: int
    normalized: bool
    vectors: list[list[float]]
    latency_ms: float
    network_call: bool
    vector_hashes: list[str]
    model_digest: str | None = None


@dataclass(frozen=True)
class RerankerProviderResult:
    provider_id: str
    model_id: str
    reranker_id: str
    scores: list[float]
    latency_ms: float
    network_call: bool
    score_hashes: list[str]


def default_retrieval_provider_config_path() -> Path:
    return Path.cwd() / ".zerker" / "retrieval-providers.json"


def retrieval_provider_config_template() -> dict[str, Any]:
    return {
        "schema": RETRIEVAL_PROVIDERS_SCHEMA,
        "embedding": {
            "default": "local:pseudo",
            "providers": {
                "local:pseudo": {
                    "enabled": True,
                    "network": False,
                    "model_id": "zmem-pseudo-embedding-v1",
                    "dimensions": 384,
                    "normalized": True,
                },
                "local:fastembed": {
                    "enabled": False,
                    "network": False,
                    "model_id": "BAAI/bge-small-en-v1.5",
                    "dimensions": 384,
                    "normalized": True,
                    "cache_dir": ".zerker/models/fastembed",
                    "batch_size": 64,
                },
                "openai:text-embedding-3-small": {
                    "enabled": False,
                    "network": True,
                    "model_id": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
                    "base_url_env": "OPENAI_BASE_URL",
                    "timeout_seconds": 30,
                    "batch_size": 64,
                },
            },
        },
        "reranker": {
            "default": "local:deterministic",
            "providers": {
                "local:deterministic": {
                    "enabled": True,
                    "network": False,
                    "reranker_id": "zmem-deterministic-rerank-v1",
                },
                "cohere:rerank-v3.5": {
                    "enabled": False,
                    "network": True,
                    "reranker_id": "rerank-v3.5",
                    "api_key_env": "COHERE_API_KEY",
                    "timeout_seconds": 30,
                    "top_n": 20,
                },
            },
        },
    }


def local_dense_provider_config(*, cache_dir: Path | None = None) -> dict[str, Any]:
    config = retrieval_provider_config_template()
    embedding = config["embedding"]
    embedding["default"] = "local:fastembed"
    settings = embedding["providers"]["local:fastembed"]
    settings["enabled"] = True
    if cache_dir is not None:
        settings["cache_dir"] = str(cache_dir)
    return normalize_retrieval_provider_config(config)


def load_retrieval_provider_config(path: Path | None = None) -> dict[str, Any]:
    path = path or default_retrieval_provider_config_path()
    if not path.exists():
        return retrieval_provider_config_template()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed retrieval provider config: {path}: {exc.msg}") from exc
    return normalize_retrieval_provider_config(data)


def normalize_retrieval_provider_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(config, Mapping):
        raise ValueError("retrieval provider config must be an object")
    if config.get("schema") != RETRIEVAL_PROVIDERS_SCHEMA:
        raise ValueError("unsupported retrieval provider config schema")

    normalized: dict[str, Any] = {"schema": RETRIEVAL_PROVIDERS_SCHEMA}
    for kind in ("embedding", "reranker"):
        section = config.get(kind)
        if not isinstance(section, Mapping):
            raise ValueError(f"retrieval provider config missing {kind} object")
        providers = section.get("providers")
        if not isinstance(providers, Mapping):
            raise ValueError(f"retrieval provider config missing {kind}.providers object")
        default_provider = section.get("default")
        if not isinstance(default_provider, str) or not default_provider:
            raise ValueError(f"retrieval provider config missing {kind}.default")
        if default_provider not in providers:
            raise ValueError(f"retrieval provider config default not found: {kind}.{default_provider}")

        normalized_providers: dict[str, Any] = {}
        for provider_id in sorted(providers):
            settings = providers[provider_id]
            if not isinstance(provider_id, str) or not provider_id:
                raise ValueError(f"retrieval provider id must be a non-empty string: {kind}")
            if not isinstance(settings, Mapping):
                raise ValueError(f"retrieval provider settings must be an object: {kind}.{provider_id}")
            normalized_settings = dict(sorted(copy.deepcopy(dict(settings)).items()))
            normalized_settings["enabled"] = bool(normalized_settings.get("enabled", False))
            normalized_settings["network"] = bool(normalized_settings.get("network", False))
            normalized_providers[provider_id] = normalized_settings
        normalized[kind] = {"default": default_provider, "providers": normalized_providers}
    return normalized


def redacted_retrieval_provider_config(config: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_retrieval_provider_config(config)
    return {
        "schema": REDACTED_CONFIG_SCHEMA,
        "source_schema": RETRIEVAL_PROVIDERS_SCHEMA,
        "config": _redact_value(normalized),
    }


def retrieval_provider_config_hash(config: Mapping[str, Any]) -> str:
    redacted = redacted_retrieval_provider_config(config)
    payload = json.dumps(redacted, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def retrieval_provider_registry(config: Mapping[str, Any] | None = None) -> dict[str, RetrievalProviderEntry]:
    normalized = normalize_retrieval_provider_config(config or retrieval_provider_config_template())
    entries: dict[str, RetrievalProviderEntry] = {}
    for kind in ("embedding", "reranker"):
        for provider_id, settings in normalized[kind]["providers"].items():
            key = f"{kind}:{provider_id}"
            entries[key] = RetrievalProviderEntry(
                kind=kind,
                provider_id=provider_id,
                enabled=bool(settings.get("enabled")),
                network=bool(settings.get("network")),
                model_id=_string_or_none(settings.get("model_id")),
                reranker_id=_string_or_none(settings.get("reranker_id")),
                settings=settings,
            )
    return entries


def lookup_retrieval_provider(
    kind: str,
    provider_id: str,
    *,
    config: Mapping[str, Any] | None = None,
) -> RetrievalProviderEntry:
    key = f"{kind}:{provider_id}"
    registry = retrieval_provider_registry(config)
    if key not in registry:
        raise KeyError(f"unknown retrieval provider: {key}")
    return registry[key]


def resolve_embedding_provider(
    config: Mapping[str, Any] | None = None,
    provider_id: str | None = None,
    *,
    allow_network_providers: bool = False,
    env: Mapping[str, str] | None = None,
) -> RetrievalProviderEntry:
    normalized = normalize_retrieval_provider_config(config or retrieval_provider_config_template())
    provider_id = provider_id or str(normalized["embedding"]["default"])
    entry = lookup_retrieval_provider("embedding", provider_id, config=normalized)
    if not entry.enabled:
        raise ValueError(f"embedding provider is disabled: {provider_id}")
    if entry.network and not allow_network_providers:
        raise ValueError(f"network provider not allowed: embedding:{provider_id}")
    api_key_env = _string_or_none((entry.settings or {}).get("api_key_env"))
    env = os.environ if env is None else env
    if entry.network and api_key_env and not env.get(api_key_env):
        raise ValueError(f"embedding provider missing API key env: {api_key_env}")
    return entry


def resolve_reranker_provider(
    config: Mapping[str, Any] | None = None,
    provider_id: str | None = None,
    *,
    allow_network_providers: bool = False,
    env: Mapping[str, str] | None = None,
) -> RetrievalProviderEntry:
    normalized = normalize_retrieval_provider_config(config or retrieval_provider_config_template())
    provider_id = provider_id or str(normalized["reranker"]["default"])
    entry = lookup_retrieval_provider("reranker", provider_id, config=normalized)
    if not entry.enabled:
        raise ValueError(f"reranker provider is disabled: {provider_id}")
    if entry.network and not allow_network_providers:
        raise ValueError(f"network provider not allowed: reranker:{provider_id}")
    api_key_env = _string_or_none((entry.settings or {}).get("api_key_env"))
    env = os.environ if env is None else env
    if entry.network and api_key_env and not env.get(api_key_env):
        raise ValueError(f"reranker provider missing API key env: {api_key_env}")
    return entry


def embed_texts(
    provider_entry: RetrievalProviderEntry,
    texts: list[str],
    *,
    env: Mapping[str, str] | None = None,
    input_type: str = "document",
    allow_model_download: bool = False,
) -> EmbeddingProviderResult:
    settings = provider_entry.settings or {}
    model_id = provider_entry.model_id or str(settings.get("model_id") or provider_entry.provider_id)
    dims = int(settings.get("dimensions") or settings.get("dims") or (1536 if provider_entry.network else 384))
    normalized = bool(settings.get("normalized", True))
    started = time.perf_counter()
    model_digest = None
    if provider_entry.provider_id == "local:pseudo":
        vectors = [_pseudo_embedding(text, dims=dims) for text in texts]
        network_call = False
    elif provider_entry.provider_id == "local:fastembed":
        vectors, network_call, model_digest = _fastembed_vectors(
            provider_entry,
            texts,
            input_type=input_type,
            allow_model_download=allow_model_download,
        )
        if vectors:
            dims = len(vectors[0])
    elif provider_entry.provider_id == "openai:text-embedding-3-small":
        vectors = _openai_embedding_vectors(provider_entry, texts, env=env)
        network_call = True
        if vectors:
            dims = len(vectors[0])
    else:
        raise ValueError(f"unsupported embedding provider: {provider_entry.provider_id}")
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    return EmbeddingProviderResult(
        provider_id=provider_entry.provider_id,
        model_id=model_id,
        dims=dims,
        normalized=normalized,
        vectors=vectors,
        latency_ms=latency_ms,
        network_call=network_call,
        vector_hashes=[_vector_hash(vector) for vector in vectors],
        model_digest=model_digest,
    )


def fastembed_model_cached(provider_entry: RetrievalProviderEntry) -> bool:
    settings = provider_entry.settings or {}
    cache_dir = Path(str(settings.get("cache_dir") or ".zerker/models/fastembed")).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = Path.cwd() / cache_dir
    return cache_dir.exists() and any(cache_dir.rglob("*.onnx"))


def _fastembed_vectors(
    provider_entry: RetrievalProviderEntry,
    texts: list[str],
    *,
    input_type: str,
    allow_model_download: bool,
) -> tuple[list[list[float]], bool, str]:
    if input_type not in {"document", "query"}:
        raise ValueError(f"unsupported embedding input type: {input_type}")
    if not texts:
        return [], False, ""
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise ValueError("local dense embeddings require: pip install 'zerker-memory[dense]'") from exc

    settings = provider_entry.settings or {}
    model_id = provider_entry.model_id or str(settings.get("model_id") or provider_entry.provider_id)
    cache_dir = Path(str(settings.get("cache_dir") or ".zerker/models/fastembed")).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = Path.cwd() / cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    threads_value = settings.get("threads")
    threads = int(threads_value) if threads_value is not None else None
    key = (model_id, str(cache_dir.resolve()), threads)
    was_cached = fastembed_model_cached(provider_entry)
    model = _FASTEMBED_MODELS.get(key)
    if model is None and not allow_model_download and not was_cached:
        raise ValueError("local dense model is not cached; run 'zmem embeddings index --download-model'")
    if model is None:
        try:
            model = TextEmbedding(
                model_name=model_id,
                cache_dir=str(cache_dir),
                threads=threads,
                local_files_only=was_cached or not allow_model_download,
            )
        except ValueError as exc:
            if not allow_model_download:
                raise ValueError(
                    "local dense model is not cached; run 'zmem embeddings index --download-model'"
                ) from exc
            raise
        _FASTEMBED_MODELS[key] = model
    batch_size = int(settings.get("batch_size", 64))
    generator = model.query_embed(texts, batch_size=batch_size) if input_type == "query" else model.passage_embed(
        texts,
        batch_size=batch_size,
    )
    vectors = [[float(value) for value in vector.tolist()] for vector in generator]
    model_dir = Path(str(getattr(model.model, "_model_dir", "")))
    model_digest = _directory_digest(model_dir)
    return vectors, bool(allow_model_download and not was_cached), model_digest


def _directory_digest(path: Path) -> str:
    resolved = str(path.resolve())
    cached = _FASTEMBED_MODEL_DIGESTS.get(resolved)
    if cached is not None:
        return cached
    if not path.is_dir():
        raise ValueError("local dense model directory is unavailable")
    manifest = []
    for child in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: str(item.relative_to(path))):
        digest = hashlib.sha256()
        with child.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest.append(
            {
                "path": str(child.relative_to(path)),
                "size": child.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    result = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    _FASTEMBED_MODEL_DIGESTS[resolved] = result
    return result


def rerank_texts(
    provider_entry: RetrievalProviderEntry,
    query: str,
    documents: list[str],
    *,
    env: Mapping[str, str] | None = None,
) -> RerankerProviderResult:
    settings = provider_entry.settings or {}
    reranker_id = provider_entry.reranker_id or str(settings.get("reranker_id") or provider_entry.provider_id)
    model_id = provider_entry.model_id or reranker_id
    started = time.perf_counter()
    if provider_entry.provider_id == "local:deterministic":
        scores = _local_reranker_scores(query, documents)
        network_call = False
    elif provider_entry.provider_id == "cohere:rerank-v3.5":
        scores = _cohere_rerank_scores(provider_entry, query, documents, env=env)
        network_call = True
    else:
        raise ValueError(f"unsupported reranker provider: {provider_entry.provider_id}")
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    return RerankerProviderResult(
        provider_id=provider_entry.provider_id,
        model_id=model_id,
        reranker_id=reranker_id,
        scores=scores,
        latency_ms=latency_ms,
        network_call=network_call,
        score_hashes=[_score_hash(score) for score in scores],
    )


def retrieval_provider_readiness(
    config: Mapping[str, Any] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    normalized = normalize_retrieval_provider_config(config or retrieval_provider_config_template())
    env = os.environ if env is None else env
    checks: list[dict[str, Any]] = []
    for kind in ("embedding", "reranker"):
        default_provider = normalized[kind]["default"]
        for provider_id, settings in normalized[kind]["providers"].items():
            api_key_env = _string_or_none(settings.get("api_key_env"))
            checks.append(
                {
                    "kind": kind,
                    "provider_id": provider_id,
                    "default": provider_id == default_provider,
                    "enabled": bool(settings.get("enabled")),
                    "network": bool(settings.get("network")),
                    "hosted": bool(settings.get("network")),
                    "api_key_env": api_key_env,
                    "api_key_ready": bool(api_key_env and env.get(api_key_env)),
                    "runtime_ready": (
                        importlib.util.find_spec("fastembed") is not None
                        if provider_id == "local:fastembed"
                        else True
                    ),
                    "model_cached": (
                        fastembed_model_cached(
                            RetrievalProviderEntry(
                                kind=kind,
                                provider_id=provider_id,
                                enabled=bool(settings.get("enabled")),
                                network=bool(settings.get("network")),
                                model_id=_string_or_none(settings.get("model_id")),
                                settings=settings,
                            )
                        )
                        if provider_id == "local:fastembed"
                        else None
                    ),
                }
            )
    return {
        "schema": "zerker.retrieval_provider_readiness.v1",
        "ok": True,
        "config_hash": retrieval_provider_config_hash(normalized),
        "checks": checks,
    }


def _openai_embedding_vectors(
    provider_entry: RetrievalProviderEntry,
    texts: list[str],
    *,
    env: Mapping[str, str] | None = None,
) -> list[list[float]]:
    settings = provider_entry.settings or {}
    env = os.environ if env is None else env
    api_key_env = _string_or_none(settings.get("api_key_env")) or "OPENAI_API_KEY"
    api_key = env.get(api_key_env)
    if not api_key:
        raise ValueError(f"embedding provider missing API key env: {api_key_env}")
    base_url_env = _string_or_none(settings.get("base_url_env"))
    base_url = env.get(base_url_env, "") if base_url_env else ""
    endpoint = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/embeddings"
    payload = json.dumps(
        {
            "model": provider_entry.model_id or settings.get("model_id") or "text-embedding-3-small",
            "input": texts,
        },
        ensure_ascii=True,
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = int(settings.get("timeout_seconds", 30))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError("embedding provider request failed") from exc
    data = json.loads(body)
    vectors = [item.get("embedding") for item in data.get("data", [])]
    if len(vectors) != len(texts) or not all(isinstance(vector, list) for vector in vectors):
        raise RuntimeError("embedding provider returned malformed embedding data")
    return [[float(value) for value in vector] for vector in vectors]


def _local_reranker_scores(query: str, documents: list[str]) -> list[float]:
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_]+", query) if len(term) > 2]
    if not terms:
        return [0.0 for _ in documents]
    scores = []
    for document in documents:
        lowered = document.lower()
        score = sum(1 for term in terms if term in lowered) / len(terms)
        scores.append(round(score, 6))
    return scores


def _cohere_rerank_scores(
    provider_entry: RetrievalProviderEntry,
    query: str,
    documents: list[str],
    *,
    env: Mapping[str, str] | None = None,
) -> list[float]:
    settings = provider_entry.settings or {}
    env = os.environ if env is None else env
    api_key_env = _string_or_none(settings.get("api_key_env")) or "COHERE_API_KEY"
    api_key = env.get(api_key_env)
    if not api_key:
        raise ValueError(f"reranker provider missing API key env: {api_key_env}")
    base_url_env = _string_or_none(settings.get("base_url_env"))
    base_url = env.get(base_url_env, "") if base_url_env else ""
    endpoint = (base_url.rstrip("/") if base_url else "https://api.cohere.ai/v2") + "/rerank"
    payload = json.dumps(
        {
            "model": provider_entry.reranker_id or settings.get("reranker_id") or "rerank-v3.5",
            "query": query,
            "documents": documents,
            "top_n": len(documents),
            "max_tokens_per_doc": int(settings.get("max_tokens_per_doc", 4096)),
        },
        ensure_ascii=True,
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = int(settings.get("timeout_seconds", 30))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError("reranker provider request failed") from exc
    data = json.loads(body)
    results = data.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError("reranker provider returned malformed rerank data")
    scores = [0.0 for _ in documents]
    for item in results:
        if not isinstance(item, Mapping):
            raise RuntimeError("reranker provider returned malformed rerank data")
        index = item.get("index")
        relevance_score = item.get("relevance_score")
        if not isinstance(index, int) or index < 0 or index >= len(documents):
            raise RuntimeError("reranker provider returned malformed rerank data")
        if not isinstance(relevance_score, (int, float)):
            raise RuntimeError("reranker provider returned malformed rerank data")
        scores[index] = round(float(relevance_score), 6)
    return scores


def _pseudo_embedding(text: str, *, dims: int) -> list[float]:
    vector = [0.0 for _ in range(dims)]
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_]+", text) if len(term) > 2]
    if not terms and text:
        terms = [text.lower()]
    for term in terms:
        digest = hashlib.sha256(term.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        sign = -1.0 if digest[4] & 1 else 1.0
        weight = 1.0 + min(len(term), 12) / 12.0
        vector[index] += sign * weight
    return [round(value, 6) for value in vector]


def _vector_hash(vector: list[float]) -> str:
    payload = json.dumps([round(float(value), 9) for value in vector], sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _score_hash(score: float) -> str:
    payload = json.dumps(round(float(score), 9), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _redact_value(value: Any, *, parent_key: str | None = None) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _redact_value(child, parent_key=str(key)) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if _is_secret_key(parent_key):
        if parent_key and parent_key.endswith("_env") and isinstance(value, str):
            return value
        return _REDACTED
    if isinstance(value, list):
        return [_redact_value(item, parent_key=parent_key) for item in value]
    if isinstance(value, str) and _looks_secret_like(value):
        return _REDACTED
    return value


def _is_secret_key(key: str | None) -> bool:
    return bool(key and _SECRET_KEY_RE.search(key))


def _looks_secret_like(value: str) -> bool:
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
        return False
    return bool(_SECRET_VALUE_RE.search(value))


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None

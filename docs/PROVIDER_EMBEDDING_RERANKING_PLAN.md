# Provider Embedding And Reranking Plan

This is an implementation-ready plan for adding provider-backed embeddings and reranking to ZMem without changing the product's default trust posture.

Scope for this plan:

- Add real embedding and reranker provider support behind explicit opt-in.
- Preserve local/offline defaults, deterministic fallback modes, and receipt verification.
- Record enough metadata to reproduce and audit benchmark runs.
- Do not leak secrets, raw vectors, raw provider requests, or hidden provider responses into receipts, logs, benchmark artifacts, snapshots, or Treeship statements.

Out of scope for this plan:

- Changing the live `fts-multihop` implementation.
- Public benchmark claims.
- Dataset downloads, hosted judges, or automatic network access during benchmark runs.
- Replacing SQLite/FTS as the local-first source of truth.

## Assumptions

- Existing local modes are the baseline contract: `fts`, `pseudo-embedding`, and `pseudo-embedding-rerank`.
- Existing receipt metadata already supports rank transitions, vector ids/hashes, config hashes, fallback metadata, and no raw vectors.
- Existing provider config lives in `.zerker/providers.json` for Mem0/Zep governance imports. Embedding/reranking provider config should either extend that file under new keys or move to a new `.zerker/retrieval-providers.json` only if mixing import providers with inference providers becomes confusing.
- Network providers must be unavailable unless explicitly enabled by config and command flag.

## Product Rules

1. Local FTS remains the default retrieval mode.
2. Local deterministic pseudo providers remain the reproducible fallback.
3. Hosted embeddings and hosted rerankers are never used implicitly by `inject`, `bench`, `doctor`, or release smoke.
4. SQL, metadata filters, policy authorization, and lifecycle checks prune candidates before provider ranking.
5. Receipts prove what provider/config influenced ranking, not the raw vector space or provider secret material.
6. Benchmarks must be comparable across retrieval configs by stable config hash and must warn loudly when configs differ.

## Provider Abstraction Shape

Use small typed interfaces rather than SDK-shaped abstractions. The first implementation can use stdlib `typing.Protocol` and concrete adapter classes.

```python
class EmbeddingProvider(Protocol):
    provider_id: str
    model_id: str

    def embed_texts(
        self,
        texts: list[str],
        *,
        purpose: Literal["query", "memory"],
        config: "EmbeddingConfig",
    ) -> "EmbeddingBatch":
        ...


class RerankerProvider(Protocol):
    provider_id: str
    reranker_id: str

    def rerank(
        self,
        query: str,
        candidates: list["RerankCandidate"],
        *,
        config: "RerankerConfig",
    ) -> "RerankBatch":
        ...
```

Data objects should be plain dataclasses or typed dictionaries:

- `EmbeddingConfig`: provider id, model id, dimensions if known, normalization flag, input truncation rule, batch size, timeout seconds, optional base URL, request profile, and `network_enabled`.
- `RerankerConfig`: provider id, reranker id/model id, top-n, candidate text profile, prompt/template hash if LLM-based, timeout seconds, max input chars/tokens, and `network_enabled`.
- `EmbeddingBatch`: vector id, vector hash, text hash, model id, provider id, dimensions, latency, and normalized status. Raw vectors stay in memory or local index tables only, never receipts.
- `RerankBatch`: before/after ranks, score hashes or rounded scores, score scale id, fallback status, latency, token usage when available, and provider metadata. Raw prompts and raw provider responses stay out of receipts.

Recommended module placement when implemented:

- `zerker_memory/retrieval_providers.py` for config models, safe hashing, provider registry, and local deterministic adapters.
- `zerker_memory/retrieval_provider_http.py` only when the first hosted adapter is added.
- Keep `zerker_memory/providers.py` focused on external memory-provider import/search unless the team chooses to unify config loading.

## Config And Secrets UX

Add config with disabled hosted providers by default.

```json
{
  "schema": "zerker.retrieval_providers.v1",
  "embedding": {
    "default": "local:pseudo",
    "providers": {
      "local:pseudo": {
        "enabled": true,
        "network": false,
        "model_id": "zmem-pseudo-embedding-v1"
      },
      "openai:text-embedding-3-small": {
        "enabled": false,
        "network": true,
        "model_id": "text-embedding-3-small",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "timeout_seconds": 30,
        "batch_size": 64
      }
    }
  },
  "reranker": {
    "default": "local:deterministic",
    "providers": {
      "local:deterministic": {
        "enabled": true,
        "network": false,
        "reranker_id": "zmem-deterministic-rerank-v1"
      },
      "cohere:rerank-v3.5": {
        "enabled": false,
        "network": true,
        "reranker_id": "rerank-v3.5",
        "api_key_env": "COHERE_API_KEY",
        "timeout_seconds": 30,
        "top_n": 20
      }
    }
  }
}
```

Secrets rules:

- Store env var names in config, never secret values.
- Allow one-shot CLI overrides for env var names or base URLs, but do not persist secret values.
- Redact values for any key matching `api_key`, `authorization`, `token`, `secret`, `password`, or provider-specific auth headers.
- `doctor` may report `api_key_ready: true/false`, never the key prefix or length.
- Receipts, benchmark run manifests, comparison outputs, logs, snapshots, and Treeship statements record only the secret source name such as `OPENAI_API_KEY`, not its value.
- Config hashes must be computed from a redacted, normalized config object. Secret value changes must not alter reproducibility hashes; provider id, model id, parameters, and endpoint profile changes should.

Network opt-in UX:

- Config alone is not enough. Hosted providers require both `enabled: true` and a runtime opt-in such as `--allow-network-providers`.
- Benchmark commands should additionally require the retrieval mode to name a network-backed mode, for example `--retrieval-mode provider-embedding-rerank --allow-network-providers`.
- If the provider is configured but the flag is absent, fall back to deterministic local mode and record the fallback reason.

## Retrieval Flow

Embedding-backed retrieval should be an overlay, not a replacement.

1. Query normalization and FTS candidate generation run locally.
2. Lifecycle, authority, scope, labels, and policy eligibility remain local gates.
3. Embeddings run only on the query and the bounded candidate set, or against a local embedding index already keyed by memory/content hash.
4. Reranking runs only on the bounded post-embedding candidate set.
5. Context packing remains after policy authorization.
6. Receipt metadata records each rank transition and fallback.

Initial ranking chain:

```text
fts candidates
  -> local lifecycle/conflict annotations
  -> optional provider embedding score
  -> optional provider reranker score
  -> policy authorization
  -> context packing
  -> receipt/proof
```

Do not send quarantined, revoked, forgotten, expired, or policy-forbidden memory content to a hosted provider unless a future explicit audit mode is designed and receipted separately. Provider calls should only see content that the local gate would be willing to consider for ranking.

## Local Index Storage

Add a local embedding table only when provider embeddings are implemented.

Suggested table:

```sql
CREATE TABLE memory_embeddings (
  memory_id TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  provider_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  vector_id TEXT NOT NULL,
  vector_hash TEXT NOT NULL,
  dimensions INTEGER,
  normalized INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  vector BLOB NOT NULL,
  PRIMARY KEY (memory_id, content_hash, provider_id, model_id, config_hash)
);
```

Rules:

- `vector_id` should be a stable hash over provider id, model id, config hash, memory id, and content hash.
- `vector_hash` should hash the serialized vector bytes using a stable float format.
- Raw vectors may live in SQLite because the database is local state, but exports and receipts must include only ids/hashes.
- If a memory's content hash changes, the old embedding is stale and ignored.
- Add lazy backfill later through `zmem index embeddings`; do not require indexing during normal `remember`.

## Receipt And Proof Metadata

Extend existing retrieval metadata without raw vectors or secrets.

```json
{
  "embedding": {
    "enabled": true,
    "provider_id": "openai",
    "model_id": "text-embedding-3-small",
    "config_hash": "sha256:...",
    "config_redaction": "zerker.redacted_config.v1",
    "network": true,
    "query_vector_id": "vec_query_...",
    "query_vector_hash": "sha256:...",
    "candidate_vectors": [
      {
        "memory_id": "mem_...",
        "content_hash": "sha256:...",
        "vector_id": "vec_mem_...",
        "vector_hash": "sha256:...",
        "rank_before": 4,
        "rank_after": 2,
        "score": 0.8123
      }
    ],
    "fallback": null
  },
  "reranker": {
    "enabled": true,
    "provider_id": "cohere",
    "reranker_id": "rerank-v3.5",
    "config_hash": "sha256:...",
    "network": true,
    "rank_transitions": [
      {
        "memory_id": "mem_...",
        "rank_before": 2,
        "rank_after": 1,
        "score": 0.9421
      }
    ],
    "input_profile": {
      "candidate_count": 10,
      "candidate_text_hashes": ["sha256:..."],
      "query_hash": "sha256:..."
    },
    "fallback": null
  }
}
```

Allowed in receipts:

- provider id
- model id / reranker id
- normalized config hash
- endpoint profile id, not full URL if it may reveal private infrastructure
- query hash
- candidate text hashes
- vector ids and vector hashes
- rank transitions
- rounded scores or score hashes
- latency, retry count, token count when available
- fallback provider and fallback reason

Forbidden in receipts:

- raw API keys, bearer tokens, request headers, or signed URLs
- raw vectors
- raw provider request/response bodies
- hidden reasoning, chain-of-thought, or provider debug traces
- full endpoint URLs containing tenant identifiers unless the operator explicitly marks them public

Fallback metadata should be first-class:

```json
{
  "fallback": {
    "reason": "network_not_allowed",
    "from_provider_id": "openai",
    "to_provider_id": "local:pseudo",
    "to_model_id": "zmem-pseudo-embedding-v1",
    "deterministic": true
  }
}
```

## Benchmark Reproducibility

Benchmark runs must freeze and display retrieval config hashes.

Each run manifest/result should include:

- retrieval mode
- embedding provider id/model id
- reranker provider id/model id
- redacted retrieval config
- retrieval config hash
- network provider opt-in boolean
- fallback policy
- provider adapter version
- dependency versions for optional provider packages
- deterministic local fallback id

Comparison compatibility should warn when any of these differ:

- retrieval mode
- embedding provider id/model id
- reranker provider id/model id
- retrieval config hash
- embedding index config hash
- dataset hash or filtered dataset hash
- ZMem version
- provider adapter version
- network opt-in status
- fallback occurrence count

Hosted-provider benchmark runs should be marked separately from local deterministic runs:

- `scoring_status: provisional-local` remains for local scaffold scoring.
- Add `retrieval_reproducibility: deterministic-local` for FTS/pseudo modes.
- Add `retrieval_reproducibility: provider-observed` for hosted provider runs.
- `provider-observed` runs are auditable by receipts but not bit-for-bit reproducible unless the provider contract guarantees stable outputs.

For public or shared results:

- Include copy-ready rerun commands with `--config <path>`, `--retrieval-config-hash <hash>`, `--seed <seed>`, and explicit `--allow-network-providers` only when used.
- `bench verify` should validate hashes and artifact integrity locally, but should not call providers.
- `bench compare` should keep compatibility warnings visible in both JSON and Markdown reports.

## Dependency Choices

Start with no required new runtime dependencies.

Acceptable first slice:

- stdlib `urllib.request` or existing project HTTP style for one minimal hosted adapter only if needed.
- optional extra dependencies behind install extras, for example `zerker-memory[providers]`, only after the first manual adapter is too costly.
- provider SDKs only after a concrete adapter needs features that are hard or unsafe to reproduce with a small HTTP client.

Avoid until necessary:

- vector database dependencies
- ANN indexes such as FAISS or hnswlib
- heavyweight ML runtimes as required installs
- provider SDKs with broad transitive dependencies
- background workers or daemonized indexing
- automatic dataset downloads
- remote benchmark judges

Local vector search can start with exact cosine/dot-product over the bounded candidate set. Add an ANN index only after benchmark profiles show exact local scoring is too slow.

## Implementation Slices

### Slice 1: Config, Registry, And Redaction

Goal: load retrieval provider config, compute redacted config hashes, and expose disabled-by-default hosted provider readiness.

Likely files:

- `zerker_memory/retrieval_providers.py`
- `tests/test_retrieval_providers.py`
- optional docs update for config examples

Verification:

```bash
python3 -m unittest tests.test_retrieval_providers -q
python3 -m zerker_memory provider doctor
```

Acceptance:

- Hosted providers default disabled.
- Config hashes ignore secret values and include behavior-changing settings.
- Doctor reports readiness without leaking secrets.

### Slice 2: Local Provider Protocol Adapters

Goal: adapt existing deterministic pseudo-embedding and deterministic reranker plumbing to the new provider interfaces.

Likely files:

- `zerker_memory/retrieval_providers.py`
- focused tests around local adapter outputs and hashes

Verification:

```bash
python3 -m unittest tests.test_retrieval_providers tests.test_store tests.test_bench -q
python3 -m zerker_memory bench run synthetic --out /private/tmp/zmem-provider-plan-smoke --seed 0 --run-id local-pseudo --retrieval-mode pseudo-embedding-rerank
python3 -m zerker_memory bench verify /private/tmp/zmem-provider-plan-smoke/local-pseudo/benchmark-result.json
```

Acceptance:

- Existing pseudo modes keep their current receipt shape or only add backward-compatible provider fields.
- No network code is introduced.

### Slice 3: Embedding Index Table And Local Backfill

Goal: store local/provider vectors in SQLite by memory id, content hash, provider id, model id, and config hash.

Likely files:

- store migration code
- a small index command such as `zmem index embeddings`
- tests for stale content hash invalidation

Verification:

```bash
python3 -m unittest tests.test_store tests.test_cli_onboarding -q
python3 -m zerker_memory bench run synthetic --out /private/tmp/zmem-provider-index-smoke --seed 0 --run-id indexed-local --retrieval-mode pseudo-embedding
python3 -m zerker_memory bench verify /private/tmp/zmem-provider-index-smoke/indexed-local/benchmark-result.json
```

Acceptance:

- Raw vectors remain local-only.
- Receipts and benchmark outputs include vector ids/hashes, not raw vectors.
- Missing or stale vectors fall back deterministically.

### Slice 4: Hosted Embedding Adapter

Goal: add one hosted embedding adapter behind explicit config and `--allow-network-providers`.

Likely provider choice:

- Prefer the provider already used elsewhere by the project or operator.
- If no preference exists, add one small HTTP adapter first instead of a broad SDK dependency.

Verification without network:

```bash
python3 -m unittest tests.test_retrieval_providers tests.test_store tests.test_bench -q
python3 -m zerker_memory bench run synthetic --out /private/tmp/zmem-provider-no-network --seed 0 --run-id no-network-fallback --retrieval-mode pseudo-embedding
python3 -m zerker_memory bench verify /private/tmp/zmem-provider-no-network/no-network-fallback/benchmark-result.json
```

Optional live verification, run only by an operator who explicitly opts in:

```bash
python3 -m zerker_memory bench run synthetic --out /private/tmp/zmem-provider-live --seed 0 --run-id hosted-embedding --retrieval-mode provider-embedding --allow-network-providers
python3 -m zerker_memory bench verify /private/tmp/zmem-provider-live/hosted-embedding/benchmark-result.json
```

Acceptance:

- Absent flag causes local deterministic fallback.
- Missing key causes local deterministic fallback or a clear nonzero error depending on configured fallback policy.
- No secrets or raw vectors appear in artifacts.

### Slice 5: Hosted Reranker Adapter

Goal: add one hosted reranker adapter behind explicit config and `--allow-network-providers`.

Verification without network:

```bash
python3 -m unittest tests.test_retrieval_providers tests.test_store tests.test_bench -q
python3 -m zerker_memory bench compare /path/to/fts/benchmark-result.json /path/to/provider-rerank/benchmark-result.json
```

Optional live verification:

```bash
python3 -m zerker_memory bench run synthetic --out /private/tmp/zmem-provider-live --seed 0 --run-id hosted-rerank --retrieval-mode provider-embedding-rerank --allow-network-providers
python3 -m zerker_memory bench verify /private/tmp/zmem-provider-live/hosted-rerank/benchmark-result.json
```

Acceptance:

- Rank transitions are recorded.
- Provider latency/token metrics are recorded when available.
- Fallback to embedding/FTS order is receipted.

### Slice 6: Benchmark Compatibility Hardening

Goal: make provider-backed runs honest in report/verify/compare.

Likely files:

- benchmark manifest/result builders
- benchmark report rendering
- comparison compatibility logic

Verification:

```bash
python3 -m unittest tests.test_bench -q
python3 -m zerker_memory bench compare /path/to/fts/benchmark-result.json /path/to/provider/benchmark-result.json
```

Acceptance:

- Provider-backed runs display retrieval reproducibility class.
- Config hash mismatches create warnings.
- Verification never calls network providers.

## Risks

- Provider nondeterminism can make benchmark deltas noisy. Mitigation: label hosted runs `provider-observed`, store config hashes, and keep deterministic local fallback.
- Secret leakage can happen through logs, exceptions, or serialized config. Mitigation: central redaction helper, tests with fake secret sentinels, and artifact scans.
- Raw vectors may be privacy-sensitive. Mitigation: keep vectors local and exclude them from receipts, snapshots intended for sharing, and Treeship statements unless a future encrypted export exists.
- SDK dependency creep can bloat install and complicate release smoke. Mitigation: no required SDKs in the first hosted slice.
- Endpoint URLs may reveal private tenants. Mitigation: record endpoint profile ids by default, not raw URLs.
- Provider calls could send memory that local policy would later withhold. Mitigation: run local lifecycle/scope/policy eligibility gates before hosted calls.
- Multi-hop and provider reranking could fight over rank semantics. Mitigation: record each rank transition as a named stage and keep Erdos-owned multi-hop files untouched during provider work.

## Open Questions For User Decisions

- Should embedding/reranking provider config extend `.zerker/providers.json`, or should retrieval inference use a separate `.zerker/retrieval-providers.json`?
- Which hosted embedding provider should be first?
- Which hosted reranker should be first?
- Should missing hosted-provider keys fall back automatically in normal runs, or fail closed unless a `fallback: local` policy is configured?
- Are raw endpoint URLs acceptable in local-only receipts, or should receipts always use endpoint profile ids?
- Should shared benchmark reports strip provider latency details that might reveal private infrastructure?
- Should vector tables be included in normal snapshots, excluded by default, or exported only as hashes?

## Recommended Next Slice

Start with Slice 1: config, registry, and redaction. It has the highest leverage and lowest blast radius. It lets the team lock the secrets/config/hash contract before any live provider call exists, and it gives later implementation workers a safe foundation for adapter work.

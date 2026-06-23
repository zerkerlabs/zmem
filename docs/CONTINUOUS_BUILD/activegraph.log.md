# ActiveGraph Integration Lane Log

## 2026-06-23T04:41:53Z - public docs and site surface

- Scope: documented the source-level ActiveGraph integration on the public website and docs.
- Files touched: `site/src/pages/ActiveGraphPage.tsx`, `site/src/pages/ActiveGraphBlogPage.tsx`, `site/src/pages/ChangelogPage.tsx`, `site/src/App.tsx`, `site/src/components/Navigation.tsx`, `site/src/pages/DocsPage.tsx`, `site/src/pages/ProofPage.tsx`, `site/src/sections/ProofOfWorkSection.tsx`, `docs/content/docs/activegraph.mdx`, `docs/content/docs/benchmarks.mdx`, `docs/content/docs/meta.json`, `CHANGELOG.md`, coordinator docs, and this lane log.
- Documentation changed: ActiveGraph is now described as cross-run memory plus compact event-sourced benchmark traces, with the current source-pack boundary and pending loader smoke called out.
- Benchmark docs changed: official LoCoMo FTS baseline and exact next `fts-multihop` / `pseudo-embedding-rerank` commands are now visible to operators.
- Runtime changed: none in this slice.
- Verification: `pnpm --dir docs build` passed; `git diff --check` passed; `site/` production build hung silently in `tsc -b && vite build` until interrupted.

## 2026-06-23T04:18:41Z - pack and compact benchmark runner

- Scope: added the first ZMem ActiveGraph pack surface and compact event-sourced benchmark runner.
- Files touched: `pack/pack.yaml`, `pyproject.toml`, `setup.py`, `zerker_memory/bench.py`, `zerker_memory/bench/activegraph_runner.py`, `zerker_memory/integrations/__init__.py`, `zerker_memory/integrations/activegraph.py`, `zerker_memory/pack.py`, `zerker_memory/store.py`, `tests/test_activegraph_pack.py`, `docs/CURRENT_STATE.md`, `docs/SWARM_OPERATION_TRACKER.md`, `docs/BUILD_LOG.md`, and this lane log.
- Behavior changed: ActiveGraph `object.created`, `patch.applied`, `llm.responded`, `tool.responded`, `policy.created`, and `relation.created` events can persist cross-run ZMem memories under `ag:{session_id}` with `caused_by_event`; `llm.requested` can recall and prepend scoped memories using `ZMEM_RETRIEVAL_MODE`.
- Benchmark changed: `zmem-bench-locomo` and `zerker_memory.bench.activegraph_runner` write `activegraph.sqlite`, `memory.sqlite`, `trace.jsonl`, and `scored_receipt.json` instead of per-question receipt bundles.
- Tests: `python3 -m py_compile` under `PYTHONPYCACHEPREFIX=/private/tmp/zmem-pycache` passed; `python3 -m unittest tests.test_activegraph_pack -q` passed; targeted ActiveGraph plus write-receipt store tests passed; `python3 -m zerker_memory.bench.activegraph_runner --help` passed; `python3 -m zerker_memory eval` passed (`11/11`).
- Blockers: no real external `activegraph` package loader smoke was run in this restricted shell; Treeship emission remains opt-in and local command based.
- Next safe slice: run the pack through a real ActiveGraph install/loader and decide whether benchmark-level `--treeship` should emit one aggregate artifact.

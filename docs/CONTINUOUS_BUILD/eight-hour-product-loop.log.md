# Eight-Hour Product Loop

## 2026-08-19 - Run 0: publish the Rooms acceptance gate

- Priority: finish the releaseable ZMem-owned Rooms contract before starting more feature work.
- Landed: feature PR `#44`, release PR `#45`, exact tag `v0.1.17`, GitHub wheel/source assets, and production site/docs.
- Verified: all PR/main/tag CI jobs, clean-tag packaging, downloaded asset hashes, downloaded-wheel install, 20/20 concurrent requests, 14/14 isolation/fail-closed checks, and live release content.
- Prevented: a dirty-worktree package build attempted to include two unrelated untracked duplicate files. No contaminated artifact was published; release assets were rebuilt from a detached tag checkout and scanned.
- Open: Gateway immutable pin, cached dense-hybrid readiness, production load/timeouts, and one host-native two-agent Room flow.
- Newly observed: four fixable site build dependency advisories. Handle in an isolated PR before calling the public surface fully clean.
- Coordination: broad recurring swarms remain paused. The hourly heartbeat may take only one bounded slice at a time and must append its outcome here.

## 2026-08-19 - Run 1: clear the site build advisories

- Priority: close the only known public-surface security hygiene gap before adding more product behavior.
- Landed: dependency-only PR `#47`, updating the site lockfile to patched `brace-expansion`, `js-yaml`, `nanoid`, and `postcss` releases without changing application code or direct dependency ranges.
- Verified: local audit reports zero vulnerabilities, lint and production build pass, and the full PR matrix passes.
- Deployed: production site `dpl_42EpxEFRMyH847eqFsQ273rZNK7W` is ready and aliased to `https://www.zmem.sh`; Vercel's clean install reports zero vulnerabilities.
- Canaried: home and changelog return HTTP `200`, the release content is present, and the live JavaScript digest matches the local verified build.
- Next: batch multi-agent connection with one shared workspace and a separate agent-bound one-time invitation for each requested host.

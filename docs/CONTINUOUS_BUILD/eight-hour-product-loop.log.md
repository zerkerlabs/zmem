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

## 2026-08-19 - Run 2: connect several current agents in one command

- Priority: remove the repeated setup/invitation work between Codex, Claude Code, Hermes, and other supported hosts while preserving one explicit identity boundary per connector.
- Candidate: `zmem connect codex claude-code hermes --label release-work` initializes one workspace and prints one distinct agent-bound invitation plus verification command for each requested host.
- Failure behavior: host presets are deduplicated; all workspace bindings must pass before invitation creation; invitation inserts commit as one transaction or roll back together.
- Boundaries: Room ids remain context only, Gateway remains membership authority, MCP connection ids prove process provenance, and client session ids remain asserted unless the host verifies them.
- Verified: `243` focused tests, `1,459` full-suite tests with two expected skips, eval `11/11`, compilation, docs typecheck/build (`19` static pages), strict release smoke, and a real isolated three-host CLI run.
- Packaged: built from Git's staged tree in a clean source directory, installed the wheel into a fresh virtual environment, passed eval `11/11` and the three-host command, and confirmed neither protected duplicate filename entered the wheel or source distribution.
- Newly observed: the fallback setuptools build emits future license-metadata and direct-`setup.py` deprecation warnings. Treat modernizing the packaging frontend and SPDX metadata as separate maintenance, not part of this connection feature.
- Next: open one reviewable PR without merging or releasing it; the following loop should monitor that PR before selecting another product lane.

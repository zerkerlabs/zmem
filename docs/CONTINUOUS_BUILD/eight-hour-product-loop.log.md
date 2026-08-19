# Eight-Hour Product Loop

## 2026-08-19 - Run 0: publish the Rooms acceptance gate

- Priority: finish the releaseable ZMem-owned Rooms contract before starting more feature work.
- Landed: feature PR `#44`, release PR `#45`, exact tag `v0.1.17`, GitHub wheel/source assets, and production site/docs.
- Verified: all PR/main/tag CI jobs, clean-tag packaging, downloaded asset hashes, downloaded-wheel install, 20/20 concurrent requests, 14/14 isolation/fail-closed checks, and live release content.
- Prevented: a dirty-worktree package build attempted to include two unrelated untracked duplicate files. No contaminated artifact was published; release assets were rebuilt from a detached tag checkout and scanned.
- Open: Gateway immutable pin, cached dense-hybrid readiness, production load/timeouts, and one host-native two-agent Room flow.
- Newly observed: four fixable site build dependency advisories. Handle in an isolated PR before calling the public surface fully clean.
- Coordination: broad recurring swarms remain paused. The hourly heartbeat may take only one bounded slice at a time and must append its outcome here.

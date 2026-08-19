"""Seed a deterministic ZMem review-queue state for the Vigilis QA gate.

Creates a few agent-proposed (quarantined -> review queue) memories plus a couple
of human-authored (active) memories, all in a caller-provided SQLite DB, so the
review dashboard has real promote/reject targets in CI. Uses only the public
`zmem` CLI so it stays valid as the store internals evolve.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# Deterministic content -- labelled "seed" so tests/humans can spot CI fixtures.
# Several queued items so promote + reject specs (and CI retries) each have a
# fresh target without racing on shared dashboard state.
QUEUED = [
    "seed: agent observed the login button moved to the top-right nav",
    "seed: agent believes the checkout API base path changed to /v2",
    "seed: agent noted the pricing page now lists a team tier",
    "seed: agent saw the docs sidebar collapse on mobile",
]
ACTIVE = [
    "seed: release policy requires two reviewers for prod deploys",
]


def _zmem(db_path: str, *args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "zerker_memory", "--db", db_path, *args],
        check=True,
    )


def seed(db_path: str) -> dict[str, int]:
    for content in QUEUED:
        # agent source stays quarantined -> shows up in the review queue.
        _zmem(db_path, "propose", content, "--type", "semantic", "--source", "agent")
    for content in ACTIVE:
        # human source is active by default -> populates the proven/active view.
        _zmem(db_path, "remember", content, "--type", "policy", "--source", "human")
    return {"queued": len(QUEUED), "active": len(ACTIVE)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed ZMem review state for the Vigilis QA gate")
    parser.add_argument("--db", required=True, help="SQLite DB path (must match the dashboard --db)")
    args = parser.parse_args(argv)
    counts = seed(args.db)
    print(f"[seed] queued={counts['queued']} active={counts['active']} db={args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

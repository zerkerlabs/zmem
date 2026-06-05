# Zerker Memory Permanent Chat Brief

Use this file to bootstrap a fresh long-lived Zerker Memory chat without digging through automation threads.

This is an aggregated brief from:

- `docs/CURRENT_STATE.md`
- `docs/BUILD_LOG.md`
- `docs/PRODUCT_STATUS.md`
- `README.md`
- `QUICKSTART.md`
- `docs/DAY1_AGENT_SETUP.md`
- automation memory at `/Users/zzo/.codex/automations/zerker-memory-overnight-build-loop/memory.md`
- recurring automation instructions from `Zerker Memory Overnight Build Loop`

## Actual Project Location

- Actual project folder: `/Users/zzo/Documents/Codex/2026-05-25/files-mentioned-by-the-user-trusted`
- Package name: `zerker-memory`
- Python package: `zerker_memory`
- Intended public repo: `https://github.com/zerkerlabs/zerker-memory`
- Intended raw installer: `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`

Important repo caveat:

- This project folder is not currently its own `.git` repo.
- `git rev-parse --show-toplevel` resolves to `/Users/zzo`.
- `/Users/zzo` currently has unrelated remotes, including `https://github.com/rezker1/nextjs-with-supabase.git`.
- Before publishing, make this project folder its own clean repo for `zerkerlabs/zerker-memory`.

## Product Identity

- Product: Zerker Memory
- Positioning: local-first governed memory for AI agents
- Promise: agents can use memory with trust, authority, lineage, revocation, and proof
- Principle: neural recall, symbolic control
- Current status: functional local-first MVP

Zerker Memory is ready for:

- local developer dogfooding
- MCP-capable agent experiments
- demos to builders/startups
- early enterprise architecture conversations
- GitHub open-source release as an alpha, once external proof is captured

It is not yet:

- hosted SaaS
- production enterprise control plane
- fully signed public Treeship workflow
- full vector/graph memory replacement
- polished hosted review workflow

## Active Phase

- Current phase: `Phase 1 - Public Alpha Launch Gate`
- Top blocker: external proof of the live public repo and raw installer from a clean networked shell
- Second blocker: final screenshots/GIFs under `.zerker/launch-proof/assets/`

Do not start broad Phase 2+ work while Phase 1 remains open unless blocked by external access. If external access is unavailable, prefer local-adjacent Phase 1 work: docs audit, launch asset handoff polish, console proof polish, clean-shell checklist hardening, or verifier summary hardening.

## Automation Operating Rules

Every autonomous build run should:

- start with the gstack check
- read `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/PRODUCT_STATUS.md`, `README.md`, `QUICKSTART.md`, `docs/DAY1_AGENT_SETUP.md`, automation memory, and current tests/status
- pick exactly one highest-leverage next slice
- prefer finishing Phase 1 over starting new features
- keep changes scoped and shippable
- run focused tests after code changes
- run `python3 -m zerker_memory eval` after behavior changes
- update `docs/BUILD_LOG.md` with `Shipped`, `Verification`, `Blockers`, `Next`, and `Delegation/Handoff`
- update `docs/CURRENT_STATE.md`
- update automation memory
- keep README, QUICKSTART, docs, and `landing/index.html` aligned with user-facing claims
- avoid destructive git operations
- do not publish, deploy, commit, or push unless explicitly asked

## Phase Roadmap

Phase 1 - Public Alpha Launch Gate:

- create/publish `github.com/zerkerlabs/zerker-memory`
- verify live raw install command from a clean networked shell
- rerun `python3 scripts/release_smoke.py` in packaged-install mode without local-wrapper fallback
- run `zmem release-pack --summary-only`
- run strict `zmem prelaunch --summary-only`
- capture launch screenshots/GIFs from `zmem ui release-pack` plus handoff restore

Phase 2 - Day-1 Adoption Polish:

- improve first five minutes
- improve install wording, `zmem status`, agent pack, direct module smoke, MCP smoke, console walkthrough, examples
- support Codex, Claude Code, OpenClaw, Hermes, and generic MCP agents

Phase 3 - Verifiable Trust Expansion:

- signed/public Treeship publish and verify
- stronger proof bundle UX
- handoff verification improvements
- signed release packet docs
- receipt portability

Phase 4 - Provider And Framework Integrations:

- harden Mem0, Zep, Graphiti, and other provider adapters
- provider doctor/live smoke
- framework examples
- external recall quarantine flows

Phase 5 - Shared/Swarm Memory:

- team scopes
- shared handoff packs
- conflict policy
- multi-agent lineage
- permissions
- swarm receipts
- collective memory verification

Phase 6 - Enterprise/Hosted/BT Analytics:

- hosted/team review console
- roles, retention, SSO, VPC/on-prem guides
- policy packs
- BT/recovery analytics
- benchmark reporting

## What Is Shipped

Core memory:

- local SQLite store
- SQLite FTS plus fallback search
- typed memories: episodic, semantic, procedural, policy
- trust and authority as separate concepts
- quarantine, review queue, promote, reject, revoke
- lineage and revocation propagation
- symbolic policy gate before injection
- JSON policy configuration
- append-only event log
- Merkle roots
- action receipts
- `why`
- receipt bundles and verification
- stable JSON export
- full-state snapshots
- snapshot verify and restore

Interfaces:

- `zerker-memory`
- `zmem`
- compatibility command `zerker`
- `zerker-memory-mcp`
- Python package
- MCP server
- local review console via `zmem ui`

Agent setup:

- Codex config generation and install
- Claude Code config generation and install
- OpenClaw manual export, checklist, snippet, guide, smoke
- Hermes manual export, checklist, snippet, guide, smoke
- generic MCP export, checklist, snippet, guide, smoke
- manual-agent pack via `zmem agent pack --summary-only`
- direct `zmem agent smoke`
- real MCP stdio smoke via `zmem agent mcp-smoke`
- post-install doctor checks
- text-only manual install summaries

Day-1 bootstrap:

- `install.sh`
- curl-style installer path
- `examples/first_run.sh`
- bootstrap ends with `zmem status --summary-only`
- installer runs eval, doctor, manual-agent pack, agent smoke, and MCP smoke
- Python 3.10+ auto-reexec for direct module commands
- release smoke Python auto-reexec
- offline fallback from editable install to no-build-isolation, then `venv-pth`, then local wrappers

Proof and release:

- `zmem launch-proof`
- `zmem launch-proof --summary-only`
- `zmem release-pack --summary-only`
- `zmem prelaunch`
- strict publish gate
- launch-proof HTML report
- launch-proof manifest
- portable proof pack paths
- public verify checklist
- public verify command script
- public verify log capture
- public verify result receipt
- public verify run summary artifact
- public verify summary target pinning
- public verify verifier command
- launch asset checklist
- launch asset handoff
- launch asset verifier
- launch asset storyboard in CLI and UI
- outbound operator packet
- operator packet verifier
- operator packet preflight inside clean-shell script
- durable clean-shell runbook
- copy-ready clean-shell operator prompt
- return packet archive
- return packet finalize script
- receive-side return packet verifier
- release smoke summary preflight
- packaged-install requirement for final public proof

Console:

- local dashboard
- receipt actions
- proof inspector
- first-run guidance
- release-pack action
- launch-proof action
- handoff action
- handoff restore action
- launch-asset verification action
- return-packet verification action
- release panel with public-verify and launch-asset blocker visibility
- release panel storyboard cards for all eight assets

BT/provider work:

- behavior-tree trace ingest
- trace listing
- fallback explanation
- dependency-free `py_trees` adapter helpers
- BTPG transition adapter helpers
- BehaviorTree.CPP/Groot2 XML export with proof manifest
- Mem0 provider search/import scaffold
- Zep live smoke support
- provider config via `.zerker/providers.json`
- provider doctor
- live provider doctor
- external provider imports default to quarantine with provenance labels

Docs and launch surface:

- README
- QUICKSTART
- DAY1 agent setup
- product status
- public launch audit
- launch plan
- clean-shell public verify runbook
- clean-shell operator prompt
- static landing page
- landing page launch proof path

CI:

- GitHub Actions unit/eval matrix
- Python 3.10 first-run/release-smoke job
- release smoke exercises launch proof, operator packet, launch assets, return packet, release pack, and prelaunch

## Recent Automation Slices

The most recent automation and chat-management work shipped:

- `Launch Asset Storyboard Surfacing`: `zmem verify-launch-assets --summary-only` prints the full eight-shot storyboard inline
- `Outbound Handoff Triplet Surfacing`: release summaries repeat the exact three outbound artifacts to forward together
- `Public Verify Summary Target Pinning`: `public-verify-summary.md` restates public repo, raw installer, and packaged-install completion
- `Offline Packaged Smoke Unblock`: release smoke accepts `venv-pth` while still rejecting `local-wrappers` for packaged proof
- `Copy-Ready Clean-Shell Operator Prompt`: durable operator prompt exists in repo docs and generated launch-proof packet
- `Permanent Chat Brief`: this file exists as the permanent-thread bootstrap
- `Repo Location Clarification`: actual project folder is this workspace, but it is not its own Git repo yet

## Full Shipped Chronology By Build-Log Title

Recent Phase 1 launch gate hardening:

- 2026-06-02 - Compact Public Verify Summary Contract
- 2026-06-02 - Launch Asset Storyboard Surfacing
- 2026-06-02 - Outbound Handoff Triplet Surfacing
- 2026-06-02 - Public Verify Summary Target Pinning
- 2026-06-02 - Phase 1 Completion Contract Surfacing
- 2026-06-02 - Public Verify Start-Here Summary
- 2026-06-02 - Durable Operator Prompt Handoff
- 2026-06-02 - Operator Prompt Surface Completion
- 2026-06-02 - Operator Prompt Next-Step Surfacing
- 2026-06-02 - Offline Packaged Smoke Unblock
- 2026-06-02 - Release-Pack Target Pinning
- 2026-06-02 - Release Panel Storyboard Visibility
- 2026-06-02 - Copy-Ready Clean-Shell Operator Prompt
- 2026-06-02 - Operator Packet Script Preflight
- 2026-06-02 - Operator Prompt Contract Alignment
- 2026-06-02 - Launch Plan Contract Lock
- 2026-06-02 - Clean-Shell Stop-Rule Hardening
- 2026-06-02 - Pre-Release Surface Truthfulness

June 1 launch handoff and console hardening:

- 2026-06-01 - Landing Packet Restore Callout
- 2026-06-01 - Public Proof Target Pinning
- 2026-06-01 - Status Gate Ordering Alignment
- 2026-06-01 - Console Release Surface Hardening
- 2026-06-01 - Launch Proof Transcript Snapshot Refresh
- 2026-06-01 - Standalone Public Verify Gate
- 2026-06-01 - Operator Packet Open-First Runbook
- 2026-06-01 - Release Pack Packet Consistency Repair
- 2026-06-01 - Operator Packet Snapshot Gate
- 2026-06-01 - Installer Public Repo Alignment
- 2026-06-01 - Launch Asset Gate-Truth Fix
- 2026-06-01 - Clean-Shell Public Verify Runbook
- 2026-06-01 - Public Verify Summary Asset Contract
- 2026-06-01 - Release Smoke Summary Preflight
- 2026-06-01 - Operator Packet Contract Summary

May 31 public verify, packets, return handoff, and asset gates:

- 2026-05-31 - Public Verify Run Summary Artifact
- 2026-05-31 - Launch Packet Gate Snapshot Surfacing
- 2026-05-31 - Launch Proof Handoff Asset Count Alignment
- 2026-05-31 - Public Verify Attempt Receipt
- 2026-05-31 - Status Launch-Gate Focus
- 2026-05-31 - Console Launch Asset Verification
- 2026-05-31 - Release Smoke Operator Packet Gate
- 2026-05-31 - Launch Asset Contract Verifier
- 2026-05-31 - Public Verify Status Contract Repair
- 2026-05-31 - Release Guidance Operator Preflight
- 2026-05-31 - Strict Launch Asset Publish Gate
- 2026-05-31 - Outbound Operator Packet Verification
- 2026-05-31 - Return Packet Finalize Script
- 2026-05-31 - Receive-Side Return Packet Handoff
- 2026-05-31 - Public Verify Operator Packet
- 2026-05-31 - Self-Contained Launch Asset Handoff
- 2026-05-31 - Self-Contained Public Verify Handoff
- 2026-05-31 - Console Return Packet Verification
- 2026-05-31 - Public Verify Operator Handoff Artifact
- 2026-05-31 - Return Packet Receive-Side Verification

May 30 launch proof, public verify, and portable paths:

- 2026-05-30 - Status Proof Pack Handoff Surface
- 2026-05-30 - Return Packet Readiness Validation
- 2026-05-30 - Public Verify Return Packet Archive
- 2026-05-30 - Public Verify Return Packet Contract
- 2026-05-30 - Public Verify Result Receipt
- 2026-05-30 - Release Guidance Critical Path Ordering
- 2026-05-30 - Console Launch Gate Visibility
- 2026-05-30 - Public Verify Gate Truthfulness
- 2026-05-30 - Launch Asset Readiness Surface
- 2026-05-30 - Launch Asset Storyboard Contract
- 2026-05-30 - Portable CLI Public Verify Handoff
- 2026-05-30 - Public Verify Front-And-Center Proof Pack
- 2026-05-30 - Public Verify Manifest Contract
- 2026-05-30 - Portable Proof Pack Paths
- 2026-05-30 - Launch Proof Status Truthfulness
- 2026-05-30 - Launch Proof Manifest
- 2026-05-30 - Portable Public Verify Script
- 2026-05-30 - Public Verify Log Capture
- 2026-05-30 - Public Verify Script And Repo-Path Fix

May 29 release pack, handoff, prelaunch, and repo target:

- 2026-05-29 - Generated Public Verify Checklist
- 2026-05-29 - Generated Launch Asset Checklist
- 2026-05-29 - Strict Packaged Install Gate
- 2026-05-29 - Launch Proof Summary-Only Flow
- 2026-05-29 - Strict Publish Gate Release Smoke
- 2026-05-29 - Console Release Pack Action
- 2026-05-29 - Console Handoff Restore Action
- 2026-05-29 - Release Pack Operator Flow
- 2026-05-29 - Console Release Artifact Actions
- 2026-05-29 - Handoff Restore Manifest
- 2026-05-29 - Status Release Readiness View
- 2026-05-29 - Prelaunch Treeship Handoff Gate
- 2026-05-29 - Handoff Treeship Proof
- 2026-05-29 - Python Module Runtime Reexec
- 2026-05-29 - Handoff Release Gate
- 2026-05-29 - Zerker Labs Repo Target
- 2026-05-29 - Shared Handoff Pack
- 2026-05-29 - Launch Proof HTML Report
- 2026-05-29 - Prelaunch Release Gate
- 2026-05-29 - First-Class Launch Proof CLI
- 2026-05-29 - Agent-Aware Bootstrap Smoke

May 28 day-1 adoption, bootstrap, CI, release smoke, and manual agents:

- 2026-05-28 - Agent-Aware Status Next Steps
- 2026-05-28 - Launch Proof Capture Harness
- 2026-05-28 - Public Launch Audit
- 2026-05-28 - Doctor Recovery Guidance
- 2026-05-28 - First-Run Manual Pack Readiness
- 2026-05-28 - Bootstrap Readiness Summary
- 2026-05-28 - Terminal Readiness Status
- 2026-05-28 - Release Smoke Offline Fallback
- 2026-05-28 - Curl-Style Bootstrap
- 2026-05-28 - CI Launch Gate Hardening
- 2026-05-28 - End-User Day-1 Pack Polish
- 2026-05-28 - Manual Agent Pack Handoff
- 2026-05-28 - Release Smoke Python Auto-Reexec
- 2026-05-28 - Self-Contained Manual-Agent Checklist
- 2026-05-28 - Default Manual-Agent Guide Flow
- 2026-05-28 - Agent Install Post-Install Doctor
- 2026-05-28 - Text-Only Manual Install Summary
- 2026-05-28 - Manual Install Summary Flag
- 2026-05-28 - Inline Manual Install Preview
- 2026-05-28 - Manual Install Writes Checklist Artifact
- 2026-05-28 - Manual Agent Checklist Artifact
- 2026-05-28 - Generic MCP Install Path Proof
- 2026-05-28 - Default Manual Agent Export Paths
- 2026-05-28 - Single-Server Agent Snippet

May 27 core alpha, agent setup, BT, provider, and MCP:

- 2026-05-27 - Agent Guide Command
- 2026-05-27 - Manual Agent Config Doctor Verification
- 2026-05-27 - Agent Install Doctor Checks
- 2026-05-27 - Direct Agent Install
- 2026-05-27 - Verified First-Run Script
- 2026-05-27 - MCP Stdio Smoke
- 2026-05-27 - Agent Presets And Day-1 Smoke
- 2026-05-27 - BT Proof Export
- 2026-05-27 - BTPG Recovery Adapter
- 2026-05-27 - Launch Proof UX
- 2026-05-27 - Day-1 Agent Launch Path
- 2026-05-27 - Provider Live Smoke And Launch Readiness
- 2026-05-27 - Release-Ready Python Alpha

Initial alpha:

- 2026-05-26 - Functional Local-First Memory Alpha

## Current Verification Baseline

Last recorded verification:

```bash
python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q
python3 -m zerker_memory eval
python3 -m zerker_memory verify-launch-assets --summary-only
python3 scripts/release_smoke.py --summary-only
```

Expected current state:

- unit slice passes
- eval passes `11/11`
- `verify-launch-assets` exits non-zero until all eight assets exist
- `release_smoke.py --summary-only` passes repo-local preflight but reports strict publish blocked on external evidence and launch assets

## Exact Phase 1 Blockers

Public verify evidence:

- prove `https://github.com/zerkerlabs/zerker-memory`
- prove `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`
- run the clean-shell public verify script
- capture logs under `.zerker/launch-proof/public-verify-logs/`
- update `.zerker/launch-proof/public-verify-result.json`
- ensure observed install mode satisfies `packaged`

Required clean-shell logs:

- `curl-install.log`
- `first-run.log`
- `release-pack.log`
- `packaged-release-smoke.log`
- `prelaunch.log`

Required launch assets:

- `assets/install-status.png`
- `assets/first-run-status.png`
- `assets/release-pack-summary.png`
- `assets/proof-report-overview.png`
- `assets/transcript-proof.png`
- `assets/ui-release-pack.gif`
- `assets/handoff-restore-terminal.png`
- `assets/ui-handoff-restore.gif`

Completion condition:

- `zmem verify-public-verify --summary-only` reports ready
- `zmem verify-launch-assets --summary-only` reports `8/8 captured`
- `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` reruns
- `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready

## Critical Commands

```bash
python3 scripts/release_smoke.py --summary-only
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
zmem verify-public-verify --summary-only
zmem verify-launch-assets --summary-only
zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only
python3 -m zerker_memory eval
```

## Critical Handoff Artifacts

Forward together:

- `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`
- `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`
- `.zerker/launch-proof/public-verify-operator-packet.tar.gz`

Clean-shell operator opens first:

- `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`

Return packet:

- `.zerker/launch-proof/public-verify-return-packet.tar.gz`

Receive-side acceptance:

- `.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md`
- `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`

## Recommended Next Move

Finish Phase 1. The best next move is not more feature work. It is the external clean-shell public proof plus launch asset capture.

Run local preflight, forward the three outbound artifacts to a clean networked shell, execute `PUBLIC_VERIFY_COMMANDS.sh`, validate public verify, capture all eight assets, finalize the return packet, and accept it only after the receive-side verifier passes.

## Bootstrap Prompt For A Permanent Chat

```text
We are continuing Zerker Memory from /Users/zzo/Documents/Codex/2026-05-25/files-mentioned-by-the-user-trusted.

First run the repo gstack check. Then read docs/PERMANENT_CHAT_BRIEF.md, docs/CURRENT_STATE.md, docs/BUILD_LOG.md, docs/PRODUCT_STATUS.md, README.md, QUICKSTART.md, docs/DAY1_AGENT_SETUP.md, and the automation memory at /Users/zzo/.codex/automations/zerker-memory-overnight-build-loop/memory.md.

The current phase is Phase 1 - Public Alpha Launch Gate. Prioritize finishing external public proof and launch-asset capture over starting new features. Treat docs/CURRENT_STATE.md as the orchestration dashboard and docs/BUILD_LOG.md as the append-only shipped log. Keep changes scoped, run focused tests, run python3 -m zerker_memory eval after behavior changes, and update docs/BUILD_LOG.md, docs/CURRENT_STATE.md, and automation memory after each build run.

Important repo caveat: the project folder is not currently its own .git repo. The intended public repo is https://github.com/zerkerlabs/zerker-memory.
```

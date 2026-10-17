# Results tracker

Revision: 3. Date: 2026-10-17. Status: CODEX_ADAPTER_CONTRACT_TESTED.

## Goal and constraints

Generalize the supplied project-specific harness into an approachable GitHub project for tasks with executable acceptance checks. Favor a small working core, verifiable behavior, clear onboarding, and examples spanning code, data, and documents. Preserve source archives unchanged and exclude their private execution history from the release.

## Decisions

- New portable implementation, ProofLoop, rather than shipping domain policy and machine-specific code.
- Keep isolated worktrees, ratcheted acceptance, regression verification, protected paths, bounded retries, review, and evidence.
- Freeze checker paths from the start via configuration; use full verification instead of caching in v0.1.
- Provide a local process adapter; no unverified vendor-specific flags or claimed real-model integration.
- Strict reviewer failure rejects a candidate. No automatic weakening or bypass.

## Evidence and judgment

Claim: a task-independent local controller can reject bad candidates and preserve verified progress across these fixture families. Strongest limitation: passing synthetic fixtures does not establish usefulness or efficiency on real agent tasks.

Observed: 30 integration tests pass; code reject/accept demo and data/report recipes complete; a built wheel runs outside the source checkout. Evidence: tests/test_core.py, examples/, docs/validation.md. This supports the local engineering behavior. Real-model completion, efficiency, and generalization remain unresolved. Neither stars nor cost savings have been measured.

## Next decisive comparison

Use one tested CLI adapter and a frozen small task suite. Compare equal-budget one-shot execution against the harness using the same model and evaluator. Record completion, regressions, wall time, tokens, and cost with unknown usage marked explicitly. That comparison should determine whether feedback, review, or smaller stages improve practical value before adding routing, caching, or a trained discriminator.

## Delivery

Source, package metadata, MIT license, visual README, offline demos, task documentation, contribution templates, CI configuration, and launch copy are prepared. The public repository IreneXiaooo/proofloop was created with explicit user authorization. This commit prepares the release source for publication. Hosted CI status must be checked after publication.

## Codex upgrade

Authorized: add the previously proposed Codex roles/delegation/usage upgrade and publish to the existing public repository. Implemented version 0.2: managed Codex CLI adapter; explicit worker/planner/reviewer models; validated sequential task lists; native agent-tool disabling requested through CLI configuration; cumulative role-call budgets; bounded role prompts; persisted usage records and optional cost estimates; init-codex, doctor, and usage commands. Generic task configurations remain valid.

Observed: 57 local tests pass; old task fingerprints preserved; offline data/report recipes complete. No Codex executable is installed here, so the model-facing integration is tested through a CLI fixture. Live model access, actual sandbox behavior, pricing, token savings, and generalization remain unresolved. Evidence: tests/test_codex.py, tests/fake_codex.py, docs/codex.md, docs/validation.md.

Next decisive validation: run the generated mean task on an authenticated, version-recorded Codex installation using the requested model IDs; inspect role logs, usage completeness, fixed checks, and the resulting diff. Then compare direct versus delegated runs at equal call/time budgets on a frozen task suite.

Mixed-provider coverage: a Codex planner assigns a Codex worker and a generic command worker to the same candidate. Their combined output passes the frozen check; the generic worker is identified by its configured profile and its usage remains unknown. This test simulates the provider boundary and does not call Qwen.

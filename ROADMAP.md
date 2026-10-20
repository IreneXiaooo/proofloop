# Roadmap

v0.1 is a local alpha: a deterministic loop, frozen path policy, command checks, optional JSON review, resumable state, and three offline task examples.

Next candidates, in priority order:

1. **Live-model validation.** Version 0.2 adds a contract-tested Codex adapter with model roles, bounded delegation, and usage accounting. Next, pin an installed CLI version and publish real-model end-to-end runs.
2. **Evaluation across task families.** Freeze a small coding/data/document suite. Compare one-shot agent execution with this controller on the same tasks, models, budgets, and checks. Report completion, regressions, attempts, latency, tokens, cost, and unknown usage.
3. **Measured efficiency.** Use the new per-call ledger to compare fixed-budget direct and delegated runs. Add provider-backed reservations before proposing hard dollar or token caps. Only add verification caching after invalidation correctness is tested.
4. **Measured harness evolution.** Version 0.4 adds opt-in fixed-weight Proposer–Reflector search with matched evaluation, activation evidence, strategy crossover and an archive. Compare it with equal-budget direct editing on frozen development tasks, then evaluate the frozen champion on unseen tasks. Weight training and a trained discriminator remain research directions.
5. **Isolation and portability.** Container execution, filesystem restrictions, broader crash fault injection, Windows CI, and storage quotas. Version 0.3 adds isolated parallel worktrees and bounded text conflict resolution; distributed execution and direct inter-agent messaging remain outside scope.

No item above is a measured improvement yet. API publishing, external service actions, and unattended scientific claims are outside the initial scope.

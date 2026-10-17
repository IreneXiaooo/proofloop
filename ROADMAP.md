# Roadmap

v0.1 is a local alpha: a deterministic loop, frozen path policy, command checks, optional JSON review, resumable state, and three offline task examples.

Next candidates, in priority order:

1. **A tested real-agent adapter.** Select one installed CLI, pin its tested version, verify permissions and cancellation, and publish reproducible end-to-end runs.
2. **Evaluation across task families.** Freeze a small coding/data/document suite. Compare one-shot agent execution with this controller on the same tasks, models, budgets, and checks. Report completion, regressions, attempts, latency, tokens, cost, and unknown usage.
3. **Measured efficiency.** Add a versioned usage event protocol and fail-closed budget reservations before proposing dollar or token caps. Only add verification caching after invalidation correctness is tested.
4. **Better failure feedback.** Test whether structured rejection summaries improve completion per unit cost. Keep critique separate from execution and freeze the evaluator. A trained discriminator is a research direction, not a shipped feature.
5. **Isolation and portability.** Container execution, filesystem restrictions, crash fault injection, Windows CI, and storage quotas.

No item above is a measured improvement yet. API publishing, external service actions, and unattended scientific claims are outside the initial scope.

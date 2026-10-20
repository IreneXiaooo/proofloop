# Validation record — 2026-10-20

Local validation for the v0.1.0 source release, on Linux with Python 3.11. No paid model or remote provider was called.

| Check | Observed result |
| --- | --- |
| `python -m unittest discover -s tests -q` | 30 tests passed, most recent run 9.417 seconds. |
| Offline mean demo | Attempt 1 rejected; attempt 2 accepted; COMPLETE. Original checkout preserved. |
| `python examples/run_examples.py` | Data and report recipes each completed with one accepted attempt. |
| `python -m compileall -q proofloop` | Passed. |
| Wheel build with no build isolation or dependencies | Produced `proofloop-0.1.0-py3-none-any.whl`. |
| Install wheel to a separate target; run from outside source checkout | Offline demo completed with one rejection and one acceptance. |
| SVG hero | Rendered to PNG and visually inspected for layout. |

The integration suite uses actual temporary Git repositories and scripted workers. It checks baseline completion, rejection followed by acceptance, original checkout preservation, rerun without new worker calls, verify-only behavior, protected-file edits/deletions, disallowed new paths, no-change stalls, nonzero agent exits, regressions, reviewer approval/rejection/invalid JSON/modification, configuration drift, dirty checkouts, checked-out result branches, external branch changes, simulated compare-and-swap failures, write-ahead reconciliation, lock exclusivity, verifier modifications, process timeout, Unicode logs, missing executables, invalid configuration, interruption immediately before/after publication, cumulative attempt limits, and exhausted active-time budgets.

Limitations: no live LLM integration, external task benchmark, adversarial security evaluation, Windows or macOS run, full power-loss durability test, dollar/token accounting, or performance comparison. The CI workflow is provided but has not run on a hosted repository in this delivery. Two interruption fault-injection tests exercise the publication boundary; they do not simulate every possible operating-system crash.

## 0.2.0 upgrade validation

On 2026-10-17, the expanded suite passed 57 tests locally. New CLI-fixture coverage includes Codex argument construction, worker/reviewer models, read-only planning, two-worker model selection, oversized/unknown plans, planner/reviewer modifications, call limits before review and during delegation, explicit model-call errors, unknown usage, missing terminal/final messages, malformed reviews, timeouts, resume without double accounting, stage model overrides, price arithmetic, setup without inference, executable checks, interrupted call ledgers, legacy unattributed calls, and missing prices.

The fixture implements the documented Codex command interface and emits synthetic JSONL usage; it does not enforce an OS sandbox or call a model. The real `codex` executable is absent in this environment, and `proofloop doctor` correctly reports LAUNCH_ERROR. No live Astra/Sol/Luna execution, pricing, or efficiency benchmark is claimed. A 0.1 task's normalized fingerprint was checked against its original persisted state and remained unchanged. Generic offline data/report recipes still complete.

The earlier public 0.1 commit passed all six hosted Linux/macOS jobs on Python 3.11–3.13. The new upgrade's hosted CI is checked after source publication; its result is reported separately.

Installed 0.2 wheel smoke test from outside the source checkout: init-codex, doctor, run, and usage all succeeded against the CLI fixture. The run completed with three harness-issued roles (planner Astra, worker Sol, reviewer Astra), retained synthetic token counts per role, and correctly left dollar cost unknown without pricing. These are fixture outcomes, not live model measurements.

Mixed-provider coverage: a Codex planner assigns a Codex worker and a generic command worker to the same candidate. Their combined output passes the frozen check; the generic worker is identified by its configured profile and its usage remains unknown. This test simulates the provider boundary and does not call Qwen.

## 0.3.0 parallel upgrade validation

The expanded local suite passed **86 tests** (50.222 seconds in the recorded full run). Parallel tests run actual subprocesses against temporary Git repositories. A two-process rendezvous proves simultaneous execution in distinct worktrees; a three-worker case verifies a two-worker concurrency cap, unique atomic call IDs, and stable plan-order integration. Coverage includes clean/disjoint and same-file nonoverlapping merges, ordinary text/add-add conflicts, successful and bounded-retry resolution, unresolved markers, failed/bad/out-of-scope resolvers, frozen checks, regression rejection, binary/modify-delete/rename conflict rejection, worker failure and sibling cancellation, worker timeout, keyboard interruption and cleanup, worker/resolver call-budget exhaustion, merge errors, staged-diff review, setup validation, and the offline parallel demo.

The offline demo completes with four harness-issued calls (fixture planner, two generic workers, fixture resolver), combines a deliberate conflict, and leaves the original checkout unchanged. No model/provider is called. The 0.3 wheel builds, and source examples/documentation links validate. Hosted CI is checked after publication. Live Codex/Qwen model performance, cost savings, OS adversarial containment, Windows behavior, and distributed execution remain unvalidated.

## 0.4.0 Evo²-inspired harness evolution validation

On 2026-10-20, the full local suite passed **108 tests in 24.523 seconds**, including 22 new evolution tests. They exercise autonomous/directed proposals, keep/revise/crossover decisions and provenance, matched task/executor/seed requests across repeats, positive credit only with trusted activation evidence, per-task regression rejection, frozen evaluator protection even under broad writable globs, malformed role/evaluator output, missing result files, evaluator mutation, no-op/nonzero/startup failures, Reflector write rejection, unknown donors, bounded root/champion pools, call/evaluator/time limits, interruption cleanup, refusing reused run ids, schema/permission routing for Codex roles, and external result-branch movement. The suite runs actual subprocesses and temporary Git worktrees.

The no-key parser-harness evolution demo runs from an independently installed 0.4 wheel outside the source checkout. It makes three scripted role calls and five evaluator invocations, selects a directed child, preserves the original checkout and records its raw experience. Codex setup prepares a committed configuration without inference. These demonstrate controller behavior, not learned capability. All six hosted Linux/macOS Python 3.11–3.13 jobs passed for v0.3; v0.4 hosted CI is checked after publication.

No live paid model, weight training, EvoTIDE reproduction, held-out generalization, statistical significance, hard provider spend control, or comparative performance gain is claimed. Frozen executor identity is protocol-checked; actual remote version/settings enforcement belongs to the trusted evaluator.

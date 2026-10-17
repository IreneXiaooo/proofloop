# Architecture and provenance

ProofLoop is a new, smaller implementation generalized from the two user-supplied archives `harness.zip` and `harness_state.zip` dated 2026-10-17. The private source was a gene-evidence engineering harness tied to a specific CLI, repository layout, frozen biological policy, and machine setup.

The source review covered the active README, permanent contract, configuration structure, controller methods, final state summary, and representative accepted/rejected run decisions. The supplied final summary reported 20 iterations and engineering readiness, and explicitly withheld scientific validation. Those are source-reported results for another project, not ProofLoop benchmark results. The historical state archive is not a dependency and is not distributed.

| Source idea | Public implementation |
| --- | --- |
| Staged engineering tasks | Ordered configurable command stages with optional dependencies. |
| Candidate worktrees | Detached worktree per baseline/attempt. |
| Ratcheted acceptance | New passing stage, no prior-pass regression. |
| Protected files and locked tests | Frozen-from-start writable/protected policy over inventoried files. |
| Journal and compact feedback | Per-attempt evidence, recent decisions, bounded check tails. |
| Reviewer concerns | Optional strict JSON approval gate; no fail-open fallback. |
| Compare-and-swap integration | Result ref updated against expected parent; write-ahead recovery. |
| Repeated failure stop | Consecutive rejection cap plus total attempts/time. |

The source's domain policy, prompts, local paths, model IDs, raw logs, SQLite database, biological examples, and historical costs are excluded. Provider hooks, learned memory, model routing, test generation/locking, dependency-aware caching, revise passes, usage accounting, and advisor calls are not ported. They would add deployment assumptions or broaden the first release beyond what is demonstrated here.

## Components

`core.py` owns schema validation, process execution, worktrees, verification, path checks, acceptance, state, and publication. `cli.py` exposes run/verify/status/report/demo. `demo.py` creates an isolated synthetic task. The package uses Python's standard library and the Git executable.

Each check is evaluated independently. Previously passing checks are re-run on candidates. The agent cannot make its stdout count as a pass; the configured checker exit status determines it. The trust boundary still includes the host and all configured commands: file hashes are an after-the-fact guard, not an adversarial security system.

## Reused foundations

Git's [worktree interface](https://git-scm.com/docs/git-worktree) supplies linked checkouts, and [update-ref](https://git-scm.com/docs/git-update-ref) supplies compare-and-swap publication. Python's [subprocess interface](https://docs.python.org/3/library/subprocess.html) supplies argv-based process execution and timeout handling. Using those existing primitives keeps the core install small and inspectable.

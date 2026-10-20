# Runs, evidence, and recovery

State is local under the repository's Git common directory:

```text
proofloop/<task-id>/
  task.json
  state.json
  REPORT.md
  baseline/
    <stage>.log
    checks.json
  runs/0001/
    prompt.txt
    agent.log
    agent.json
    diff.patch
    decision.json
    verification/
      <stage>.log
      checks.json
    review-prompt.txt   (when review runs)
    review.log
    review.json
```

Use `git rev-parse --git-common-dir` to locate it. The files do not enter ordinary commits. Baseline logs show the latest baseline; candidate run evidence is retained per attempt. Raw logs and binary patches can grow large; v0.1 has no retention quota.

`proofloop status task.json` prints counters. `proofloop report task.json` prints a Markdown summary. Rejected worktrees are removed after recording their patches. Accepted changes live on `proofloop/<task-id>`; your initial branch and checkout are not updated by the controller.

## Exit codes and status

- `0`: COMPLETE (run) or VERIFIED (verify).
- `1`: checks fail or a run stops at its attempt, time, or stall budget.
- `2`: configuration/repository error.
- `130`: keyboard interruption.

`CHECKS_FAILED` is expected when verifying a task that still needs work. `STALLED` means too many consecutive rejections; `ATTEMPT_BUDGET` and `TIME_BUDGET` are cumulative limits. A run has no automatic review bypass or unbounded retries.

## Resume

Rerun the same `run` command. Every resume rechecks the accepted branch. Configuration changes or branch movement outside the controller stop the run. Successful tasks can be reverified without another worker call.

Ctrl+C kills the active process group on POSIX and attempts process-tree termination on Windows, saves state, and removes the active worktree. Attempts are charged before launch, so an interrupted invocation still counts. Rejected history may be missing for an abruptly interrupted attempt; inspect its directory and state before continuing. Final budgets require a reviewed new task ID to begin another bounded effort.

## Machine crash or forced termination

A repository-wide exclusive lock prevents concurrent ProofLoop writers. A crash can leave a `RUNNING.lock` or `worktree-*` directory. First verify no controller or child command is still running. Remove a stale worktree with `git worktree remove --force <exact-path>`, then remove that task's stale lock under the common directory's `proofloop/` folder. Never remove a lock belonging to a live run. Retry the original command.

Publication uses Git compare-and-swap and a write-ahead state entry. Resume reconciles an interrupted update when the result branch matches that pending commit. If a person moved the branch, the controller refuses to guess. Review those changes and start a new task ID from the desired committed baseline. There is no remote push or merge.

Git worktrees share object storage and Git administration. Protect the host with a restricted container/VM when commands are untrusted. File guards cannot undo external side effects.

## Model-call ledger (0.2)

`calls/000001.json` records reserved/completed/interrupted calls, roles, requested models, token usage, and optional cost estimates. `usage.json` is rebuilt on state saves; `proofloop usage task.json` computes it from the ledger. Codex role logs have adjacent `.final.txt` and, for structured roles, `.schema.json` files. An unfinished reservation remains an unknown-usage call. Legacy calls without records are explicitly counted as unattributed. `CALL_BUDGET` stops further role invocations when the cumulative cap is exhausted. A crash can consume time/usage not reported before termination; use provider limits for hard financial controls.

## Parallel batches (0.3)

Worker worktrees are named with the attempt and worker number. On ordinary cancellation the controller waits for all child executions before removing them. A forced crash may leave several worktrees; confirm no process is still using them before manual cleanup. `parallel.json`, `worker-N.patch`, and `merges/NN/` preserve the attempted integration and resolution evidence. Resume starts a new attempt from the accepted base, not from a partially merged candidate. See [parallel execution](parallel.md).

## Harness evolution (0.4)

`evolve` uses `proofloop/evolution/<id>/` under the Git common directory and a separate `proofloop-evolution/<id>` result branch. It retains candidate refs and raw role/evaluation evidence. Automatic evolution resume is unsupported: inspect the archive and start a new explicitly budgeted id. Errors/interruption retain root as the result; normal stopping publishes the best eligible candidate locally with a branch lease. See [evolution evidence and recovery](evolution.md#evidence-stopping-and-recovery).

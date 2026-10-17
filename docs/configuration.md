# Configuration reference

JSON, schema version 1. Unknown keys are rejected. Paths are relative to the target repository root. The config itself may be outside the repository; its normalized content is fingerprinted and saved before work starts. Keep an in-repository config protected.

| Field | Required | Meaning / default |
| --- | --- | --- |
| `version` | Yes | `1` |
| `id` | Yes | Unique task slug, `[a-z][a-z0-9_-]{0,47}`; result branch is `proofloop/<id>`. |
| `goal` | Yes | Nonempty task description; include constraints and any authorization for external actions. |
| `agent.command` | Yes | Nonempty argv array. Prompt goes to stdin; process cwd is the worktree. |
| `agent.timeout_s` | No | Positive timeout, default 600. |
| `reviewer` | No | Same command/timeout shape as agent. Exact JSON response required. |
| `writable` | Yes | Nonempty list of relative globs. Only matching changes may be committed. |
| `protected` | No | Relative globs, default `[]`; overrides writable. |
| `stages` | Yes | Nonempty ordered list of acceptance stages. |
| `context_chars` | No | Maximum assembled worker prompt context in characters, default 16000. Not a token limit. |
| `budget.max_attempts` | No | Total lifetime attempts for this task, default 8. |
| `budget.max_seconds` | No | Cumulative active wall time across runs, default 3600. Includes baseline checks and review. |
| `budget.stall_after` | No | Consecutive rejected attempts before stopping, default 3. |

A stage has `id`, `check` (argv), optional `goal`, `timeout_s` (default 120), and `depends_on` (list of earlier stage IDs). Exit zero means pass; a timeout, launch failure, or nonzero exit means fail. Every stage runs for the baseline and each eligible candidate. Dependencies only select the next worker target, not whether a check executes.

No shell is involved. Use a Python script or another explicit executable for pipes and complex commands. `{python}` is replaced only when it occupies an entire argv item. Commands must be available on PATH or explicitly located; installed tools and ignored virtual environments are not copied into worktrees.

Globs use Python `fnmatchcase` against POSIX-style paths. `src/**` includes paths below `src/`; `*` matches slashes. Avoid assuming shell glob semantics. Absolute paths, `..` segments, backslashes, and `.git` segments are rejected in path patterns. Protect checker scripts, fixtures, dependencies, test runners, configuration, and source data. Do not rely on patterns for ignored or external files: they are outside the file guard's inventory.

Config edits after initialization stop the run. Use a new task ID when changing goals, budgets, adapters, or acceptance criteria. This makes policy changes explicit. There is no hidden budget reset or automatic loosening of review.

The report counts invocations and active seconds. Dollar cost and token counts are unknown; no cost savings are claimed or enforced. Time caps are operational bounds, not provider billing guarantees. Cleanup and filesystem operations can exceed the remaining wall-time allowance slightly.

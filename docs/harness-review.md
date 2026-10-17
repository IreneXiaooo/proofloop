# Harness design review — 2026-10-17

This is a focused review of primary documentation for task delegation, context isolation, worktree isolation, and integration. It is not a benchmark or full code/security audit of the compared products. The goal is to choose mechanisms for ProofLoop's parallel upgrade.

| Reference | Documented mechanism | Adaptation in ProofLoop |
| --- | --- | --- |
| [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) | Parallel specialized agents, model/effort selection, and summarized results. Its guidance cautions about simultaneous code edits. | Keep named worker profiles and explicit limits. Schedule independent work; use stages for prerequisites. |
| [Claude Code worktrees](https://code.claude.com/docs/en/common-workflows#run-parallel-sessions-with-worktrees) | Separate Git checkouts support parallel sessions. | Give every worker a detached worktree at the same accepted commit. |
| [Deep Agents subagents](https://docs.langchain.com/oss/python/deepagents/subagents) | Focused subagents with distinct instructions/models and context quarantine. | Preserve the original goal and policy in each worker prompt; keep raw logs in per-worker evidence. |
| [Git merge-tree](https://git-scm.com/docs/git-merge-tree) | Three-way merge into a tree object without touching a checkout/index; exit status and conflict paths identify unsuccessful merges. | Reuse Git's merge engine, retain its evidence, and inspect conflicts before materializing a candidate. |

These are design inputs, not evidence that ProofLoop outperforms the referenced systems. No third-party harness code or new runtime dependency is imported.

## Chosen contract

One supervisor validates a bounded plan. Workers execute in independent worktrees. The controller records their patches, validates file boundaries, and integrates successful candidates in plan order. Worktree isolation prevents ordinary file/index collisions, while the host and Git object store remain shared.

A clean Git merge is only a structural success. Every acceptance check is rerun on the combined candidate. An optional reviewer sees `git diff HEAD`, including staged integration changes. Publication still requires a new passing stage without regressing earlier passes.

Text conflicts can receive a configured resolver with a separate call/time limit. Its editable scope is the explicit conflict-file set. Binary, symlink, mode, modify/delete, and complex rename conflicts stop when they cannot be handled by the supported text-resolution contract. There is no automatic preference for one worker's version.

## Deliberate tradeoffs

- Parallel tasks must be independent. Cross-worker prerequisites belong in earlier stages or sequential execution.
- A failed worker rejects the whole candidate; successful sibling patches remain available for diagnosis.
- Stable plan-order integration makes the merge sequence reproducible. Model outputs and completion order need not be reproducible.
- Generic providers use the same command contract; their usage is unknown until a dedicated parser is implemented.
- Separate worktrees are version isolation, not OS sandboxes or hard provider spend controls.
- No speed, accuracy, or cost advantage is claimed from these design choices alone. The fixture suite demonstrates overlap and decision behavior; real tasks are still needed for comparative evaluation.

## Smallest useful real comparison

Freeze several independent two-component tasks and several deliberately conflicting tasks. Run equal-model/call-budget sequential and parallel conditions; record acceptance, regressions, conflicts, resolver calls, known/unknown token usage, and wall time. Only adopt larger worker counts if measured completion/latency justify the extra integration and model overhead.

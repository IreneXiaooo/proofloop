# Evolve a harness, with a frozen evaluator

Version 0.4 adds an **opt-in development workflow** inspired by [Evo²: Evolving the Evolver through Weight-Harness Co-Evolution](https://arxiv.org/abs/2610.13025), particularly its fixed-weight Proposer–Reflector loop (§3.2 and §4.4). A Proposer edits a candidate harness. A read-only Reflector examines measured outcomes and chooses `keep`, `revise`, or strategy `crossover`. A directed edit is evaluated again. Both roles use the same frozen `evolver` specification.

This is an engineering adaptation, not a reproduction of the paper. It does not implement EvoTIDE, SFT, GRPO, model-weight updates, free-form edit extraction, or prefix continuation. The bounded pool and per-task non-regression gate are ProofLoop choices. Published benchmark numbers do not describe this implementation.

## Run the offline example

```bash
python -m proofloop evolution-demo
cat .proofloop-evolution-demo/.git/proofloop/evolution/json-harness/REPORT.md
git -C .proofloop-evolution-demo diff main..proofloop-evolution/json-harness
```

The deterministic fixture evolves a JSON-output parsing harness against three frozen response types. An autonomous edit handles fences; reflection requests a revision for surrounding prose. The evaluator uses actual Python call tracing to identify which parser functions executed. This tests controller behavior; it is not an LLM benchmark.

To prepare the same development task with a real, authenticated Codex CLI:

```bash
python examples/evolution/prepare.py --dir my-evolution --model YOUR_AVAILABLE_MODEL
proofloop evolve my-evolution/evolution.json --repo my-evolution
```

Preparation makes no inference calls. `evolve` runs the configured commands and may consume provider allowance. Codex permissions are `workspace-write` for Proposer and `read-only` for Reflector. CLI behavior is fixture-tested; live provider validation is still pending. Generic commands, including your Qwen wrapper, receive the same JSON prompts on stdin and must return the same role JSON on stdout. Generic commands receive no automatic OS sandbox, and their token usage remains unknown.

## Settings

Evolution uses a separate file, not additional keys in ordinary `task.json`:

```json
{
  "version": 1,
  "id": "parser-search",
  "goal": "Improve the agent harness without changing the fixed task executor or checks.",
  "evolver": {"adapter": "codex", "model": "YOUR_AVAILABLE_MODEL", "timeout_s": 300},
  "writable": ["harness/**", "prompts/**"],
  "protected": ["checks/**", "data/**", "evaluate.py", "evolution.json"],
  "evaluation": {
    "command": ["{python}", "evaluate.py"],
    "timeout_s": 300,
    "tasks": ["dev-a", "dev-b"],
    "executor": {"model": "FIXED_EXECUTOR", "revision": "PINNED_VERSION", "temperature": 0, "max_tokens": 4096},
    "repeats": 2
  },
  "budget": {"max_rounds": 3, "max_calls": 9, "max_evaluations": 26, "max_seconds": 3600},
  "search": {"pool_size": 8, "root_share": 0.25, "seed": 0},
  "context_chars": 24000
}
```

Adapt the evaluator and paths before use. `model` values are placeholders; no model availability is implied. Protected paths override writable globs. The configuration itself and existing repository files named directly in evaluator/evolver argv are additionally frozen. Protect imported checker dependencies, fixed data, executor wrappers, and any other acceptance authority explicitly. The controller does not discover Python import graphs or inspect the evaluator's remote provider calls.

The complete normalized configuration is snapshotted and hashed. It remains fixed throughout one search. A different task suite, model, decoding policy, or resource budget requires a new run id. The Proposer can change only declared candidate harness files, in a detached worktree; it cannot alter the live controller process. Your original checkout stays unchanged.

## Trusted evaluator contract

The evaluator runs in a **fresh checkout of each candidate commit**, receives one JSON request on stdin, and writes one JSON result to `request["output"]`. Raw stdout/stderr is retained as execution evidence. A request has this shape:

```json
{"tasks": ["dev-a", "dev-b"], "executor": {"model": "FIXED_EXECUTOR", "revision": "PINNED_VERSION", "temperature": 0, "max_tokens": 4096}, "seed": 0, "output": "/absolute/run/0.result.json"}
```

Example result:

```json
{
  "executor": {"model": "FIXED_EXECUTOR", "revision": "PINNED_VERSION", "temperature": 0, "max_tokens": 4096},
  "tasks": [
    {"id": "dev-a", "score": 1.0, "active_mechanisms": ["retry_policy"]},
    {"id": "dev-b", "score": 0.5, "active_mechanisms": []}
  ]
}
```

Require an externally defined normalized score in `[0, 1]`, with higher better. Exactly the registered task IDs must appear, once each. Boolean, non-finite, missing, duplicate, unknown, or out-of-range scores reject evaluation. The reported executor object must equal the frozen object. This checks protocol consistency, not the truth of a model identity assertion: the trusted evaluator must enforce the actual executor version, decoding settings and task budget.

The evaluator must execute task agents in its own temporary task environments and **must not modify the candidate harness checkout**. Do not return the candidate agent's self-assessed score. Derive `active_mechanisms` from trusted instrumentation, such as function-call or tool-dispatch traces, not from Proposer metadata or text printed by the candidate. Keep your test/held-out data outside search and evaluate the chosen branch separately after freezing it.

Before each edit, the controller reserves enough remaining evaluator capacity for a complete comparison. Parent and child run on the same task list, executor object and repeat seeds. Every invocation is charged before launch. There is no cached parent score in the paired delta. Repeats are averaged per task. This does not control nondeterministic provider drift or yield statistical confidence intervals; use a registered independent evaluation for scientific conclusions.

## Roles and decisions

The Proposer edits files, then returns:

```json
{"strategy": "Retry only after a parse failure", "mechanism": "retry_policy"}
```

`mechanism` is a lowercase slug matching a trusted activation trace label. The Reflector receives the candidate's measured outcomes, evidence directory and a bounded library of previously evaluated strategies. It returns exactly one of:

```json
{"action": "keep", "directive": "", "donor": ""}
```

```json
{"action": "revise", "directive": "The malformed-output task still fails; validate before retrying.", "donor": ""}
```

```json
{"action": "crossover", "directive": "Adapt the donor's retry mechanism to this parser; preserve the current API.", "donor": "0001-autonomous"}
```

An unknown donor, empty actionable directive, malformed response, or Reflector edit is rejected. Crossover uses an evaluated strategy and its commit as context for adaptation; it is **not automatic Git patch merging**. Existing parallel worker/conflict resolution remains available inside candidate harnesses, with its usual verification contract.

The archive records root, autonomous and directed nodes, recipient parents, donor IDs, diffs, role responses, paired scores, deltas and activation evidence. It includes executable regressions and weak candidates for later repair. Parent selection retains root and champion in a bounded pool, fills with depth representatives/recent nodes, then samples with a seeded policy. Root gets a fixed sampling share; other weights favor scores away from 0.5. This heuristic is configurable and is not a validated optimum.

A candidate can replace the champion only if its paired mean increases, **no registered task regresses against its freshly evaluated parent**, its declared mechanism actually executes, and its scores also dominate the current champion. Positive execution credit is zero without activation evidence. Directed Proposer credit compares the revision to the candidate it changed; the Reflector receives that measured intervention credit, not a prose-quality score. `keep` has zero intervention credit. Invalid evaluations receive no fabricated numeric reward.

## Evidence, stopping, and recovery

Artifacts live under the Git common directory at `proofloop/evolution/<id>/`; `REPORT.md`, `state.json`, `config.json`, `calls/`, and per-node evaluation directories are inspectable. Per-role prompts, complete available responses, diffs, process results, activation labels and matched requests support later offline data curation. They are **raw experience**, not an automatically approved SFT/GRPO dataset. Audit examples and selection biases before training. No hidden reasoning is requested or extracted.

Candidate commits are retained under `refs/proofloop-evolution/<id>/<node>` to prevent ordinary garbage collection. On normal completion or budget exhaustion, the best eligible candidate is published locally to `proofloop-evolution/<id>` using compare-and-swap. No main-branch update, remote push, or automatic merge occurs. `COMPLETE` means the configured rounds finished, not that a gain or generalization was demonstrated. Errors/interruption keep the result at root and retain the archive. Ordinary `run` keeps its existing resumable behavior.

Evolution intentionally refuses automatic resume or reuse of an existing id. After an interruption, inspect the archive and any worktree/lock before starting a new explicitly budgeted run. See [recovery](recovery.md) for stale lock/worktree cleanup. Do not delete live locks. Round, role-call, evaluator-invocation, context, per-process time and whole-run time limits are enforced; executor calls inside an evaluator must be bounded by that trusted evaluator. Provider cost limits are separate. Worktrees isolate versions, **not permissions**; ignored files and external side effects are outside path guards.

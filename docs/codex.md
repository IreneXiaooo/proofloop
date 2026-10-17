# Codex: Astra, Sol, and other models

ProofLoop 0.2 adds a built-in Codex CLI adapter. Choose the model for each role explicitly. The adapter runs your installed `codex exec` using its saved authentication; it does not read credentials or sign you in. Model names in these examples require access in your account/workspace.

The implementation follows OpenAI's [non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) and [configuration sample](https://learn.chatgpt.com/docs/config-file/config-sample). Automated tests use a deterministic CLI fixture. No live Astra/Sol task has run in the development environment: Codex is not installed there. Treat this as a contract-tested integration and validate it on your own installed CLI before unattended use.

## First run

Install ProofLoop from the source checkout, then install and authenticate the official Codex CLI using OpenAI's [CLI instructions](https://learn.chatgpt.com/docs/codex/cli). Do not commit authentication files or paste keys into a task config.

```bash
python -m pip install -e .

# Create a separate committed example project; this makes no model call.
proofloop init-codex --dir my-codex-demo \
  --worker-model gpt-6.1-sol --reviewer-model gpt-6-astra

# Check the executable and CLI version, without logging in or calling a model.
proofloop doctor my-codex-demo/task.json --repo my-codex-demo

# Run with your own Codex authentication. This can consume your model allowance.
proofloop run my-codex-demo/task.json --repo my-codex-demo
proofloop usage my-codex-demo/task.json --repo my-codex-demo
proofloop report my-codex-demo/task.json --repo my-codex-demo

git -C my-codex-demo diff main..proofloop/codex-mean
```

The example fixes a mean function against independent frozen checks. It uses Sol for editing and Astra for review. This is a proposed role assignment, not a measured optimal model policy. Change the model IDs before first run if your account exposes a different set.

## Add a planner and bounded delegation

```bash
proofloop init-codex --dir my-team-demo \
  --worker-model gpt-6.1-sol --planner-model gpt-6-astra \
  --reviewer-model gpt-6-astra
```

The planner runs read-only and returns a list of tasks selecting named, configured worker profiles. Workers can use either the built-in Codex adapter or a generic command wrapper for another provider, such as Qwen. The harness validates the entire plan before launching workers. Unknown workers, empty plans, and plans above `max_tasks` are rejected. The controller then invokes workers sequentially in the same candidate worktree. Workers see the original goal and constraints plus their assigned subtask. They do not receive another model's hidden reasoning.

All workers must finish successfully. Checks run on their combined candidate; review follows only if acceptance criteria improve without regressions. Any failure discards the whole candidate. Per-worker path guards stop boundary violations before the next worker. Planner and reviewer file changes are rejected.

This is **harness-managed delegation**, not an implementation of Codex's native subagent threads. Each role is a separate CLI invocation. The adapter requests `agents.enabled=false` and `features.multi_agent=false` so ordinary calls do not create native subagents. It also instructs roles not to launch nested agents. All assembled role prompts are capped by `context_chars`; an oversized prompt rejects the candidate before that call. The call cap bounds harness-issued invocations, not malicious subprocesses or external tool calls. Use an isolated host and provider-side spend controls where a hard spending boundary is necessary.

See [direct config](../examples/codex/task.json) and [delegated config](../examples/codex/delegated-task.json). These are templates: put them in your own committed project with a real `checks/acceptance.py` and allowed `src/` outputs. For mixed-provider operation, see [the mixed worker example](../examples/codex/mixed-task.json). The root `agent` is the direct worker; with delegation enabled the named worker map is used instead. A stage-level `agent` overrides the worker and bypasses planning for that stage.

## Adapter fields

```json
{
  "adapter": "codex",
  "model": "gpt-6.1-sol",
  "reasoning_effort": "medium",
  "timeout_s": 600
}
```

`model` is required. `reasoning_effort` is optional: `low`, `medium`, `high`, or `xhigh`; the selected model/CLI must support it. `ultra` is excluded to avoid requesting automatic delegation outside the controller's explicit plan. `command` optionally supplies an executable prefix such as `["/opt/bin/codex"]`; normally omit it to use `codex` on PATH. This is not a raw override of the managed arguments.

Worker calls request `workspace-write`. Planner and reviewer calls request `read-only`. The adapter does not set `--yolo`, disable approval review, or switch models after errors/refusals. Unsupported flags, unavailable models, failed authentication, and command failures reject the attempt and are logged. Your existing Codex configuration and repository instructions still apply, subject to the explicit command-line overrides.

## Structured results and diagnostics

The adapter uses stdin for the prompt, `--json` for event logs, and `--output-last-message` for the final response. Review and planning also use `--output-schema`. The final response is read separately, so CLI progress/diagnostics cannot contaminate JSON approval. Locally validate the plan and verdict even when the CLI claims schema compliance. Missing terminal events, missing/oversized final responses, and failed events reject the call.

Evidence is written under the Git common directory's `proofloop/<task-id>` folder. Candidate directories include prompts, raw logs, final response files, schemas, and per-role results. `calls/<number>.json` reserves and records each invocation before/after execution. Interrupted or crashed reservations remain visible with unknown usage. `usage.json` and `proofloop usage` aggregate known counts by requested role/model; model identity is reported as observed only when a CLI event actually supplies it.

## Tokens and cost estimates

Completed-turn events report input, cached-input, and output tokens. Cached input is a subset of input, not an extra token category. Missing or invalid telemetry is unknown. A failed/interrupted call may have consumed additional tokens after its last completed event; aggregates retain the known portion and mark incomplete coverage. Legacy calls with no ledger entries are also counted as unknown.

To estimate cost, optionally add a full `pricing` object to each Codex role. Supply current rates from your own provider/pricing arrangement:

```json
{"pricing": {"input_per_million": 2.0, "cached_input_per_million": 1.0, "output_per_million": 5.0}}
```

These numbers are an arithmetic example, **not model prices**. Estimated cost is `(uncached input × input rate + cached input × cached rate + output × output rate) / 1,000,000`. Subscription credits and actual billed charges may differ. A complete total estimate is null when any call lacks pricing or complete usage. Known partial estimates are shown separately. There is no automatic claim that delegation saves tokens or money.

`budget.max_calls` caps worker, planner, and reviewer invocations together across resumes. The default is `max_attempts × (max_tasks + 2)`, using one worker if delegation is disabled. Attempt and active-time limits still apply. These are execution bounds; no hard token or dollar ceiling is implemented.

## Mixed providers: Codex + Qwen

A Codex planner can select a generic command worker alongside Codex workers. For example:

```json
{
  "workers": {
    "sol": {"adapter": "codex", "model": "gpt-6.1-sol", "timeout_s": 600},
    "qwen": {"command": ["{python}", "qwen_wrapper.py"], "timeout_s": 600}
  }
}
```

This is the `workers` portion of a `delegation` object. Your Qwen wrapper must consume the task on stdin, run in the current worktree, edit only allowed files, and propagate a nonzero exit on failure. Configure it against your installed Qwen agent's actual interface. A Qwen API that only returns text needs an editing/tool adapter; merely returning proposed code does not update the worktree. No native Qwen installation or live mixed-model run is claimed. Generic worker usage remains unknown; the Codex JSONL parser is not applied to another provider's output.

Workers execute sequentially on one candidate; the configured plan is bounded by `max_tasks` and the total call budget. Parallel worktrees, automatic conflict resolution, and inter-agent messaging are not provided. A review can approve or reject the combined candidate, but the fixed acceptance checks still decide whether it made progress.

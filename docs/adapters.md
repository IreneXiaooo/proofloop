# Bring your agent

For the built-in Codex adapter, model roles, and bounded delegation, see [Codex integration](codex.md). The generic process contract below remains supported.

ProofLoop does not depend on a model vendor. Its adapter interface is a local process:

- Input: one UTF-8 task prompt on stdin. Includes goal, active stage, path policy, bounded check tails, and recent decisions.
- Working directory: a fresh detached Git worktree at the last accepted commit.
- Output: edits to allowed files, plus optional stdout/stderr. Logs are evidence, not proof of correctness.
- Success: exit code 0. Nonzero exits and timeouts reject the candidate, even if some checks would pass.
- Git: the controller owns staging, commits, and result-branch publication. The agent must not mutate Git state.

A wrapper can adapt a CLI that needs a flag rather than stdin:

```python
# agent_wrapper.py — customize against your installed CLI's documentation
import subprocess
import sys

prompt = sys.stdin.read()
# Replace both the executable and flags with your actual verified CLI interface.
result = subprocess.run(["your-agent-cli", "--prompt", prompt])
raise SystemExit(result.returncode)
```

This is an interface sketch, not a tested vendor adapter. Prefer a CLI's stdin or prompt-file interface for long prompts: command-line length limits differ by OS, and argv may be visible to other processes. The harness does not switch models after a refusal or bypass provider permissions. It treats an unsuccessful worker call as a rejected attempt.

Set `agent.command` to `["{python}", "agent_wrapper.py"]`. Put the wrapper outside writable paths, freeze its dependencies, and commit it with the task. A trusted absolute-path wrapper is also supported; it is not copied or guarded by the harness.

## Optional reviewer

The reviewer receives JSON on stdin with goal, check results, changed paths, and instructions to inspect the diff and new files. It can read files and use `git diff` but must not modify repository files. It must print only this JSON to stdout/stderr combined:

```json
{"verdict": "APPROVE", "reason": "The behavioral checks cover the requested edge cases."}
```

or:

```json
{"verdict": "REJECT", "reason": "The report omits an important limitation."}
```

A failed command, timeout, malformed response, or unapproved verdict rejects the candidate. A change to an inventoried file during review also rejects it. This is checked after review; the process is not made read-only by the operating system. Keep wrapper diagnostics out of the combined log if you expect JSON parsing to succeed.

Review is a supplemental gate. It does not replace acceptance checks, and calling the same model twice is not independent scientific validation. No discriminator is trained in this version.

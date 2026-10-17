# GitHub launch kit

Repository: [IreneXiaooo/proofloop](https://github.com/IreneXiaooo/proofloop).

**About:** A small, auditable harness for verifiable agent tasks. Your agent proposes. Your checks decide.

**Suggested topics:** `ai-agents`, `agent-harness`, `verification`, `developer-tools`, `automation`, `python`, `reproducibility`.

**First release title:** ProofLoop v0.1 — keep only verified progress.

**Release text:**

ProofLoop wraps your agent command in a bounded propose → verify → accept loop. Each attempt runs in a fresh Git worktree. A candidate reaches the result branch only when a new acceptance stage passes without regressing a previously passing stage, and an optional reviewer approves. Every attempt leaves an inspectable patch and decision.

Start with `python -m proofloop demo` from the checkout—no API key required. The scripted demo rejects a wrong fix before accepting a correct one. Additional recipes cover data cleaning and a local report.

This is an alpha for trusted local tasks. Worktrees are not security sandboxes. Live-model performance and cost savings have not been benchmarked. Contributions of reproducible tasks and tested adapters are welcome.

## Upload checklist

Create an empty GitHub repository, then upload the contents of this project folder, including `.github` and the license. Alternatively initialize Git locally, commit, add your repository URL as `origin`, and push `main`. This release archive contains no preconfigured remote or repository credentials.

Before announcing: confirm the name, let CI finish, run one real task through a tested adapter, and attach a short terminal recording of that run. Replace a scripted demonstration with real-agent evidence only when it has been measured. The README already makes the demo's limits explicit.

Stars are a discovery signal, not an acceptance metric. Focus the launch on a concrete working example and an easy first contribution.

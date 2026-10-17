# Contributing

Start with a reproducible task or controller failure. Please keep changes small enough to inspect.

```bash
python -m unittest discover -s tests -v
python examples/run_examples.py
python -m proofloop demo --dir /tmp/proofloop-contributor-demo
```

Choose a new demo path on each run. Tests create disposable Git repositories and do not call LLM APIs. For a controller change, add a meaningful behavioral test: a candidate that should be accepted/rejected, a recovery transition, or an observable budget limit. Do not weaken frozen checks to make a test pass.

Recipes should include a small synthetic input, fixed acceptance checks independent of the worker, and explicit limits on what the checks establish. Adapter contributions should state exact tested CLI versions, permissions, stdin/stdout behavior, cancellation, and how usage is reported. Do not commit credentials, real provider logs, private corpora, or historical state archives.

Promising first contributions: a new task recipe; a tested CLI adapter; crash-recovery coverage; Windows integration tests; report usability. Discuss changes to the acceptance rule or trust model before expanding the architecture.

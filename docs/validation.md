# Validation record — 2026-10-17

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

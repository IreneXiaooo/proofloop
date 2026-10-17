# Design a task that can finish

Use this harness when a deliverable can live in a Git repository and success can be tested by a command. Split a broad goal into stages that can each pass within one bounded agent call. This controller discards partial candidates that do not finish a new stage.

A useful acceptance check tests behavior against expectations written independently of the candidate. For code, use concrete examples, boundary cases, and a regression suite. For data, preserve records and identifiers, validate numeric transformations, and keep original inputs frozen. For documents, verify required content and references, then review readability and factual claims separately.

Exit codes can only enforce what the checker actually examines. An always-successful command, a skipped suite, or a checker that imports its expected answers from generated output is weak evidence. ProofLoop does not infer the quality of arbitrary validators or count test assertions. Keep the evaluator and every dependency outside writable paths; add a reviewer if the task needs judgment.

## Research and ML

Freeze evaluation data, splits, seeds, metric definitions, and scoring code. Keep training artifacts separate from acceptance fixtures. Require explicit missing-data and invalid-result states. Engineering completion means the pipeline satisfied its contract; it does not establish model generalization, mechanistic truth, or a publishable scientific conclusion.

Do not optimize against a held-out test set on every iteration and then call it held out. Use development checks in the loop and a separate final evaluation outside the loop. Run external data and expensive computations under an appropriate resource manager; v0.1 does not isolate datasets, enforce GPUs, or schedule HPC jobs.

## Poor fits

Open-ended research with no agreed evaluator, sending messages, irreversible account actions, autonomous deployment, or a long task that needs many partial commits before any stage can pass. This harness manages repository artifacts; it is not a universal app automation or scientific validation system.

## Smallest useful starting point

One goal, one writable output directory, frozen inputs and checks, one stage, three attempts. Run `verify` first and inspect its log. Use the offline recipes as interface examples. Broaden only after the smallest real task works.

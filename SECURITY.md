# Security and trust

ProofLoop executes trusted commands with the permissions and environment of the current user. Worktrees are not sandboxes. The agent and reviewer can reach shared Git administration and anything else their host account can reach. Use a restricted disposable container/VM for untrusted tasks; do not mount secrets or production data.

Path guards cover tracked files and nonignored new files. They do not cover ignored files, external files, network effects, Git administration, or provider retention. Prompts, logs, patches, reports and task goals may contain sensitive content. Inspect and sanitize before sharing.

To report a vulnerability, use GitHub private vulnerability reporting if enabled. Otherwise open a minimal issue asking for a private contact without including credentials, personal data, or an exploit against a live service. No security audit or adversarial containment guarantee is claimed.

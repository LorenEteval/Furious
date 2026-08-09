---
name: python-black-formatter
description: >-
  Format or verify Python source files with Black using the repository's
  configured environment and Black settings. Use when Codex writes or
  refactors Python, is asked to run Black or fix formatting, prepares Python
  changes for review, or investigates a Black check failure. Keep formatting
  scoped to the task and preserve unrelated, generated, and user-owned changes.
---

# Format Python with Black

Use Black as the formatting authority. Keep formatting separate from semantic
changes when practical, and never treat a successful Black run as a correctness
test.

## Workflow

1. Establish repository context.
   - Work from the repository root unless project documentation specifies
     another directory.
   - Inspect the worktree before formatting. Distinguish task-owned files from
     pre-existing user changes.
   - Read the repository's Black configuration, normally `[tool.black]` in
     `pyproject.toml`, and check for a documented task-runner command.

2. Select the existing Black installation.
   - Prefer the repository's documented formatter command.
   - Otherwise invoke Black through the active or project-managed Python
     environment: `<python> -m black`.
   - Use `uv run black` only when the repository already uses uv for this
     workflow and doing so will not unexpectedly install or update packages.
   - Do not install, upgrade, or reconfigure Black without user authorization.

3. Choose the narrowest correct target.
   - Honor paths explicitly named by the user first.
   - Otherwise format only Python files created or modified for the current
     task.
   - Format a package or the entire repository only when requested or required
     by an established repository workflow.
   - Exclude generated, vendored, or user-owned files unless the requested
     scope or repository configuration explicitly includes them.

4. Run the requested mode.

   Verify formatting without modifying files:

   ```text
   <python> -m black --check --diff <targets>
   ```

   Apply formatting:

   ```text
   <python> -m black <targets>
   ```

   Do not add command-line options that override repository configuration
   unless the user explicitly requests them. Operational options such as
   `--check`, `--diff`, and `--color` are safe when appropriate.

5. Review and verify.
   - Inspect the diff for every formatted target.
   - Confirm Black did not touch files outside the intended scope.
   - Re-run Black with `--check` on the same targets after formatting.
   - Run relevant tests or compilation separately when the surrounding code
     change requires them.
   - Report the target scope, whether files changed, and the final check result.

## Failure Handling

- If Black is unavailable, report the attempted command and environment. Do not
  silently install it or fall back to a different formatter.
- If Black reports invalid Python, diagnose the syntax or incompatible target
  version before formatting. Do not manually approximate Black's output.
- If Black's safety check cannot run under the selected Python version, prefer
  a repository-supported interpreter. Do not add `--fast` merely to suppress
  the check; use it only when repository policy or the user explicitly permits
  it.
- If formatting changes unrelated code, stop and narrow the target. Preserve
  all pre-existing worktree changes.

## Completion Criteria

Finish only when:

- the intended targets have been formatted or checked;
- apply mode ends with the same targets passing `black --check`;
- verify-only mode reports Black's pass or fail result without modifying files;
- the reviewed diff contains no unintended formatting changes; and
- the final response identifies any skipped files, warnings, or unavailable
  validation.

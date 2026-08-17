# Furious repository guidance

## Source of truth and change discipline

- Treat the checked-out tree as authoritative. Do not resurrect deleted experiments or infer current architecture from old commits or conversations.
- Preserve unrelated working-tree and staged changes. Keep edits scoped to the requested behavior.
- When `.codegraph/` exists, use `codegraph explore` before text search or broad file reading to locate symbols and understand call paths. Use `rg` for exact follow-up searches.
- Before running Python commands, inspect the repository root for an existing environment matching `.venv*` or `venv*`. Prefer its interpreter for project scripts, tests, formatters, generators, and dependency-backed tools whenever usable; do not create or modify an environment unless the task requires it.
- Keep the existing GPL header, `from __future__` placement, import grouping, and repository naming style in touched Python files.

## Architecture boundaries

- Keep models/configuration documents independent of presentation. Repositories own persistence, services own workflows, controllers own application state/orchestration, and widgets/actions are thin adapters.
- Prefer plugin capabilities and backend factories over protocol/core conditionals in shared application code.
- Treat persisted user configuration as input. Connection-time, test-time, routing, logging, and statistics preparation must operate on explicit runtime copies unless an API is documented as mutating persisted state.
- Application-wide controllers and repositories may be process-lifetime objects; transient UI and temporary process resources must not become accidental global state.
- Keep platform-specific host mutation behind the existing runtime/system abstractions. A feature must remain safe to import and test on unsupported platforms.

## Generated artifacts and translations

- `Furious/Frozenlib/AppResources.py` and `Furious/Externals/GenTranslation.py` are generated artifacts. Do not hand-maintain them as ordinary source.
- Add user-facing strings through the existing translation-aware widgets/actions and `_()` extraction conventions. Regenerate translations with `Translation.py` when translation source changes.
- Pass only static string literals to `_()`. Runtime-formatted translations such as `_(f'{arg} do something...')` and `_('{arg} do something...'.format(...))` are unsupported; translate static fragments and compose dynamic values outside `_()` instead.
- Curly braces in extracted strings are reserved for application-constant substitution: `Translation.py` resolves every `{name}` through `Furious.Frozenlib.Constants`. Do not use braces as ordinary runtime-format placeholders.

## Verification

- Run the narrowest relevant tests first, then the affected test tier documented in `tests/README.md`.
- Format only touched Python files with the repository Black configuration, then run Black check mode on the same files.
- For backend/process/platform changes, verify failure cleanup and bounded shutdown as well as the success path.
- For Qt ownership changes, follow `Furious/AGENTS.md`, use the `manage-qt-pyside6-lifetimes` skill, and run the relevant lifetime tests; do not use forced garbage collection as a production fix.

## Code review rules

- Flag UI code that becomes a second owner of controller/domain state.
- Flag mutation of persisted configuration during runtime preparation.
- Flag new protocol-specific branches in shared managers when a plugin capability can own the behavior.
- Flag edits to generated artifacts without the corresponding generator workflow.

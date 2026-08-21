# Furious repository guidance

## Working method

- Treat the checked-out tree as authoritative. Preserve unrelated staged and unstaged work; do not revive deleted
  experiments or infer architecture from old history.
- If `.codegraph/` exists, use `codegraph explore` before broad text search or file reading. Use `rg` for exact
  follow-up searches.
- Before Python work, inspect the repository root for `.venv*` or `venv*` and prefer its interpreter when usable. Do not
  create or modify an environment unless required.
- Keep edits focused. Preserve GPL headers, `from __future__` placement, import grouping, repository naming style, and
  public compatibility unless a deliberate migration is part of the task. Treat curated package `__init__` exports,
  plugin API dataclasses, persisted keys, and semantic exit codes as compatibility surfaces.

## Pythonic design

- Prefer the simplest design that makes ownership, state transitions, failure, and side effects explicit. Readability
  and one canonical path beat clever indirection or parallel implementations.
- Keep policy close to the layer that owns it: models describe data, repositories persist domain collections,
  `AppSettings` persists preferences, services own workflows and temporary resources, controllers own shared state
  machines/orchestration, plugins/backends own protocol-specific behavior, `Application` composes the process, and UI
  adapts those APIs.
- Make invalid states and boundary failures visible with specific return values, result objects, or exceptions. Catch
  broadly only at a genuine isolation boundary, log actionable context, and do not silently convert explicit user input
  into a different behavior.
- Bound external work where the workflow requires responsiveness: network requests, subprocess startup/shutdown,
  thread joins, and host commands need caller-chosen timeouts or a documented non-GUI execution context. Low-level
  wrappers such as `runExternalCommand()` intentionally do not invent a universal timeout. Cleanup must be idempotent,
  own exact resources, and never search by process name.
- Prefer immutable metadata, pure transformations, dependency injection, and explicit runtime copies. Avoid global
  mutable state, hidden mutation, duplicated caches, and UI-owned business state.

## Repository invariants

- Treat persisted user configuration as input. Connection, routing, testing, logging, TUN, and statistics preparation
  must not mutate it implicitly; use explicit runtime/derived state unless an API is documented as mutating storage.
- Prefer plugin capabilities/factories over protocol or core conditionals in shared managers. Registries may strongly
  own process-lifetime plugins, capability providers, factories, descriptors, and metadata; they must not retain
  transient UI or active runtime instances.
- A `ServerProfile` combines profile metadata with one persisted connection/configuration document. `CoreRuntime` means
  one managed proxy-core lifecycle regardless of whether its implementation uses a subprocess, multiprocessing, or an
  in-process binding. Reserve process terminology for actual operating-system processes and handles.
- Application-wide controllers and repositories may be process-lifetime. Transient UI, network replies, timers,
  callbacks, and temporary processes must not become accidental global state.
- Keep platform mutation behind `Frozenlib`/runtime abstractions so unsupported platforms remain safe to import and
  tests can fully mock host operations.
- Treat secrets, subscription payloads, paths, URLs, and plugin data as untrusted input. Do not log credentials or full
  sensitive configurations; validate before host or process use.

## Generated files and translations

- `Furious/Frozenlib/AppResources.py` and `Furious/Externals/GenTranslation.py` are generated. Change their source
  inputs and run the existing generator instead of hand-maintaining them.
- Add user-facing text through translation-aware controls and `_()` extraction conventions, then run `Translation.py`.
- `_()` normally receives a static string literal. The sole dynamic exception is an f-string made only from bare names
  in `Furious.Frozenlib.Constants`; the extractor resolves those constants. Runtime values, attributes, calls, format
  specifications, and `.format(...)` inside `_()` are unsupported.
- Curly braces in extracted strings are reserved for application-constant substitution, not ordinary runtime
  placeholders.
- Keep both source execution and the `Deploy.py`/Nuitka build viable. Plugin discovery and optional heavy imports must
  remain statically discoverable or explicitly included without introducing import-time application/UI construction.

## Verification and review

- Run the narrowest relevant tests first, then the affected tier in `tests/README.md`. Tests must not touch production
  settings, networking, routing, TUN, startup registration, or unrelated processes.
- Format only touched Python files with the repository Black configuration and run Black check mode on those files.
- For backend/process/platform work, verify error cleanup and bounded shutdown. For Qt ownership work, follow
  `Furious/AGENTS.md` and `Furious/Qt/AGENTS.md`, use the `manage-qt-pyside6-lifetimes` skill, and run the relevant
  lifetime tests.
- Review for duplicated state authorities, mutation of persisted configuration during runtime preparation, broad
  swallowed errors, unbounded waits/caches, generated-file edits without regeneration, and protocol branches that belong
  in a capability.

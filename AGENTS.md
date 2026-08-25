# Furious repository guidance

## Work from the current tree

- Treat the checked-out tree, including unstaged work, as authoritative. Preserve unrelated changes and do not revive
  deleted experiments from history.
- If `.codegraph/` exists, use it for structural questions before broad searches; use `rg` for exact follow-up.
- Before Python work, inspect `.venv*`/`venv*` at the repository root and prefer its interpreter when usable. Do not
  create or alter an environment without need.
- Keep edits focused. Preserve GPL headers, `from __future__` placement, import grouping, and established naming. Search
  consumers before changing curated package exports, plugin contracts, persisted keys, serialized values, IDs, aliases,
  migrations, or semantic exit codes.

## Design and boundaries

- Make each state authority, resource owner, mutation, and failure path explicit. Prefer one readable canonical path
  over parallel implementations or clever indirection.
- Put policy in its owning layer: models describe data; repositories persist domain collections; `AppSettings` persists
  preferences; services own workflows and temporary resources; controllers own shared state machines; plugins/backends
  own protocol variation; `Application` composes the process; UI adapts those APIs.
- Existing global accessors and live repository collections are compatibility mechanisms, not invitations to add hidden
  ownership. Prefer a narrow injected dependency or named operation for new code when practical.
- Treat persisted configuration as input. Build runtime, routing, testing, logging, TUN, and statistics state from
  explicit copies unless an API is documented as mutating storage.
- Prefer plugin capabilities/factories to protocol conditionals in shared orchestration. Registries may own
  process-lifetime plugins and metadata, never transient UI or active runtimes.
- Keep platform mutation behind `Frozenlib` and runtime boundaries. Own exact processes, threads, replies, timers, and
  handles; cleanup is bounded where responsiveness requires it, idempotent, and never based on process-name searches.

## Errors and external input

- Internal invariant failures remain visible. Validate user/plugin/network input and return a controlled failure with
  useful diagnostics. At OS/network/plugin boundaries, translate expected failures without discarding their cause.
- Cleanup may continue after one failure, but log the failed resource/stage. Narrow best-effort suppression is
  acceptable only when the caller cannot act and the primary outcome remains observable.
- Treat secrets, subscription payloads, paths, URLs, and plugin data as untrusted. Do not log credentials or complete
  secret-bearing configurations.

## Generated and packaged artifacts

- `Furious/Frozenlib/AppResources.py` and `Furious/Externals/GenTranslation.py` are generated. Modify their source inputs
  and run the existing generator; do not hand-edit generated output.
- `_()` normally receives a static literal. Its only dynamic exception is an f-string composed solely of bare names
  from `Furious.Frozenlib.Constants`; ordinary placeholders, attributes, calls, format specs, and `.format()` are not
  extractable. Curly braces are reserved for constant substitution.
- Keep both source execution and `Deploy.py`/Nuitka builds viable. Runtime data belongs under `Furious/Data`; plugin and
  optional imports must remain discoverable without constructing application or UI objects at import time.

## Verification

- Run the narrowest relevant tests, then the affected tier documented in `tests/README.md`. Tests never touch production
  settings, networking, routing, TUN, startup registration, unrelated processes, or external services.
- Format only touched Python files with the repository Black configuration and check those files afterward.
- Match verification to the boundary: round trips/migrations for models and persistence; transitions/signal counts for
  controllers; stale/cancel/cleanup paths for async services; partial startup and bounded cleanup for runtimes; repeated
  destruction for Qt lifetimes; fully mocked host operations for platform helpers.
- Review for duplicated state authorities, persisted-data mutation during preparation, swallowed diagnostics, unowned
  resources, unbounded external-input caches, and shared-manager branches that belong in a capability.

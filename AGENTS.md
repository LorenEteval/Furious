# Furious repository guidance

## Product and runtime map

- Furious is a cross-platform PySide6 desktop proxy client. Persisted server profiles and subscriptions are interpreted
  by protocol/plugin capabilities, then `ConnectionController` and `ConnectionManager` prepare an attempt-scoped
  configuration and own the selected proxy runtime, optional native or application TUN, system proxy, DNS, and routes.
- `Main.py`, `Furious-GUI.py`, and the installed `Furious` command enter `Furious.__main__`. `AppMainProcess` runs the Qt
  application in an exact child process so the parent can translate crashes and show a fallback report.
  `DesktopApplication` then performs singleton election, composes process-lifetime owners, restores the requested
  connection, runs the event loop, and unwinds acquired stages in reverse order.
- The main dependency direction is: models describe data; repositories persist domain collections; `AppSettings`
  registers QSettings-backed preferences/blobs; services own workflows and temporary resources; controllers own shared
  state machines; plugins/backends own protocol and runtime variation; `Application` composes the process; windows,
  widgets, and actions adapt those APIs for presentation.
- Official backends are Xray, Hysteria 1, Hysteria 2, and a structured external-core process. New backend variation
  belongs behind plugin capabilities, not core-name conditionals in shared orchestration.

## Work from the current tree

- Treat the checked-out tree, including unstaged work, as authoritative. Preserve unrelated changes and do not revive
  deleted experiments from history.
- If `.codegraph/` exists, use it for structural questions before broad searches; use `rg` for exact follow-up.
- Before Python work, inspect `.venv*`/`venv*` at the repository root and prefer its interpreter when usable. Do not
  create or alter an environment without need.
- Keep edits focused. Preserve GPL headers, `from __future__` placement, import grouping, and established naming. Search
  consumers before changing curated exports, plugin contracts, persisted keys, serialized values, IDs, aliases,
  migrations, or semantic exit codes.

## Engineering boundaries

- Make each state authority, resource owner, mutation, commit point, and failure path explicit. Prefer one readable
  canonical path over a compatibility shim plus a second implementation.
- Existing global accessors and live repository collections are compatibility mechanisms, not invitations to add hidden
  ownership. Prefer a narrow injected dependency or named operation for new code when practical, and migrate callers
  incrementally without creating a competing cache.
- Treat persisted configuration as input. Build runtime, routing, probing, logging, TUN, and statistics state from
  explicit copies unless an API is documented as mutating storage. A failed preparatory stage must not change the
  persisted profile; a post-commit side-effect failure must be reported without pretending the commit rolled back.
- Keep platform mutation behind `Frozenlib` and runtime boundaries. Own exact processes, threads, replies, timers, files,
  and handles; cleanup is bounded where responsiveness requires it, idempotent, and never based on process-name searches.
- Internal invariant failures remain visible. Validate user/plugin/network input and return controlled failures with
  useful context at boundaries. Cleanup may continue after one failure, but log the failed owner or stage.
- Treat secrets, subscription payloads, paths, URLs, plugin data, and complete core documents as untrusted. Do not log
  credentials or secret-bearing configurations.

## Generated, curated, and packaged artifacts

- `Furious/Frozenlib/AppResources.py` is generated from `Resources.qrc` and its icon inputs; never hand-edit it. Regenerate
  it with the compatible PySide6 resource compiler after changing the manifest or resources.
- `Furious/Externals/GenTranslation.py` is generator-managed but also retains curated language values and review flags.
  Follow `Furious/Externals/AGENTS.md`; do not treat it as an opaque disposable output.
- `_()` normally receives a static literal. Its only extractable dynamic form is an f-string composed solely of bare
  names from `Furious.Frozenlib.Constants`; ordinary placeholders, attributes, calls, conversions, format specs, and
  `.format()` are not extractable. Curly braces are reserved for constant substitution.
- Keep source execution, wheel/sdist installation, and `Deploy.py`/Nuitka builds viable. Runtime data belongs under
  `Furious/Data`; lazy/plugin/optional imports must remain discoverable without constructing application or UI objects
  at import time. The release workflow builds multiple OS/architecture artifacts, so host-local success is not proof of
  packaged correctness.

## Verification

- Run the narrowest relevant tests, then the affected tier documented in `tests/README.md`. Tests never touch production
  settings, networking, routing, TUN, startup registration, unrelated processes, or external services.
- Format only touched Python files with the repository Black configuration and check those files afterward.
- Match verification to the boundary: round trips/migrations for models and persistence; transitions/signal counts for
  controllers; stale/cancel/cleanup paths for async services; partial startup and bounded cleanup for runtimes; repeated
  destruction for Qt lifetimes; fully mocked host operations for platform helpers; source plus packaged checks for
  import/discovery/compiler-sensitive changes.
- Review for duplicated state authorities, persisted-data mutation during preparation, swallowed diagnostics, unowned
  resources, unbounded external-input caches, and shared-manager branches that belong in a capability.

## Keep this guidance useful

- `AGENTS.md` records durable intent, invariants, boundaries, pitfalls, and validation—not a frozen inventory of classes.
  When implementation and guidance diverge, investigate the current code and tests, then update the narrowest applicable
  guide in the same change when the architectural truth has moved.
- Let child guides specialize inherited rules instead of repeating them. Remove obsolete constraints, distinguish a
  compatibility path from the preferred direction, and avoid turning incidental implementation details into permanent
  policy. A new rule should help a future agent make a concrete engineering decision.

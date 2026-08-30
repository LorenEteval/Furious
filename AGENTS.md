# Furious repository guidance

## Learn before changing

- Treat the checked-out tree, tests, build configuration, and verified runtime behavior as the immediate source of truth.
  Existing guidance is a maintained model, not an authority that can make itself true.
- If `.codegraph/` exists, use CodeGraph before broad text searches for structural questions; use `rg` for exact
  follow-up. Inspect callers, tests, persisted formats, platform branches, and packaging consumers before changing a
  contract.
- For substantial work, use this loop: understand the intended owner and invariant; form a hypothesis; trace the real
  call/runtime path; implement at the owning boundary; test real behavior; then re-evaluate the architectural model.
- When guidance says A and code appears to do B, inspect the call path and tests. Decide whether B is intentional
  evolution, compatibility debt, or a bug; preserve the intended invariant and update either code or the narrowest
  applicable guidance. Do not encode speculation, experiments, or incidental class names as durable rules.

## Operating model

- Furious is a cross-platform PySide6 desktop client. Entrypoints reach `Furious.__main__`; a parent process translates
  child exit/crash results, while the Qt application performs singleton election, composes process-lifetime owners,
  runs the event loop, and unwinds acquired resources in reverse order.
- Read the packages as cooperating responsibilities rather than a strict stack: `Interface` and `Models` define
  dependency-light contracts/domain values; `Repository` persists them; `Plugins` defines backend/extension contracts;
  bundled `Backends` and `Extensions` implement those contracts; `Service` owns workflows and temporary resources;
  `Controllers` owns shared state transitions; `Qt`, `Widget`, `Window`, and `Actions` present them; `Application`
  composes the process; `Frozenlib` contains compatibility, settings, and host integration boundaries.
- Official proxy backends are Xray, Hysteria 1, Hysteria 2, and External Core. Shared orchestration asks plugin
  capabilities; backend-specific parsing, runtime preparation, routing, TUN, statistics, and exit interpretation stay
  behind those capabilities.

## Project-wide invariants

- Keep one authority for each state and one owner for each resource. Multiple UI surfaces observe shared
  controllers/models; they do not copy connection, routing, System Proxy, TUN, subscription, or test state.
- Treat persisted profiles and plugin documents as input. Prepare runtime, routing, probe, and TUN state on explicit
  copies unless an API deliberately mutates storage. A failed pre-commit stage leaves persistence unchanged; a failed
  post-commit side effect is reported without pretending the commit rolled back.
- Use stable domain identity, not table rows, proxy indexes, display text, or object position. Async results additionally
  prove that the target generation/fingerprint is still current before mutation.
- Startup and other staged workflows own every resource acquired before commit and roll back only that attempt on
  failure, cancellation, or supersession. Cleanup is bounded where responsiveness requires it, idempotent, and targets
  exact processes, threads, replies, timers, files, handles, routes, and callbacks—never process names.
- Keep GUI-thread work bounded. Blocking host/process/network work runs behind an owned worker or asynchronous Qt
  boundary; workers publish data back to the owning Qt thread and never mutate widgets or live repositories directly.
- Validate user, network, persisted, and plugin data at boundaries. Keep invariant failures visible, preserve useful
  diagnostics, and never log credentials, subscription payloads, full share links, environments, or complete core
  documents.
- Preserve source execution, wheel/sdist installation, and Nuitka/native distributions. Importing dependency-light
  layers must not construct the application, discover plugins, start runtimes, or create UI.

## Working in the tree

- Preserve unrelated and unstaged user changes. Do not revive deleted experiments from history or broaden a task to
  nearby technical debt.
- Before Python work, prefer an existing root `.venv*`/`venv*` interpreter. Do not create or mutate an environment
  without need. Format only touched Python files with the repository Black configuration and check them afterward.
- Preserve GPL headers, `from __future__` placement, import grouping, and established naming. Search consumers before
  changing public exports, plugin APIs, persisted keys/schemas, IDs, aliases, migrations, package data, or semantic exit
  codes.
- Generated and curated artifacts have separate sources of truth: never hand-edit
  `Furious/Frozenlib/AppResources.py`; update `Resources.qrc`/resource inputs and regenerate it. Follow
  `Furious/Externals/AGENTS.md` for the translation catalog and `Furious/Data/AGENTS.md` for bundled assets.
- Dependency, Python/Qt floor, entrypoint, package-data, version, or artifact changes may span `pyproject.toml`,
  `setup.py`, `requirements.txt`, `Deploy.py`, and the release workflow. Review every applicable surface rather than
  assuming one declaration is canonical. Networked `Deploy.py --download` and destructive build cleanup run only when
  explicitly in scope.

## Verification

- Run the narrowest relevant test first, then the affected tier documented in `tests/README.md`. Tests use isolated
  settings and mocked host/network boundaries; they never mutate a real proxy, TUN, routing table, startup registration,
  desktop, or unrelated process.
- Match evidence to the contract: round trips/migrations for models and repositories; exact transitions/signal counts
  for controllers; stale/cancel/rollback/cleanup paths for services; partial startup and resource reaping for runtimes;
  mocked OS branches for host helpers; import/discovery and packaged checks for compiler-sensitive changes.
- Use real Qt semantics when focus, selection, keyboard modifiers, proxy mapping, event delivery, queued callbacks,
  geometry, or QObject destruction matters. Prefer semantic state and destroyed/resource counts over pixel snapshots or
  arbitrary sleeps/RSS thresholds.
- Before handoff, review for duplicate authorities, persisted-data mutation during preparation, stale async write-back,
  swallowed diagnostics, unowned resources, unbounded external-input caches, plugin-specific branches in shared code,
  and source-only assumptions at packaging boundaries.

## Maintaining this guidance

- AGENTS files contain durable decision rules, not inventories or frozen recipes. Update guidance only when supported by
  current architecture, tests, verified runtime behavior, explicit design, or an intentional refactor completed in the
  same change.
- Put a rule at the narrowest scope where it helps future decisions; let child guides specialize rather than repeat
  parents. Remove obsolete rules and distinguish preferred architecture from compatibility paths.
- After significant architectural work, ask what durable fact was learned, whether guidance now misleads, and whether a
  future agent would choose the correct owner and test boundary. Do not update AGENTS for temporary implementation
  details.

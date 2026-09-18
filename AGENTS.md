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
  applicable guidance. Never resolve the contradiction by deleting the scoped guidance file. Do not encode speculation,
  experiments, or incidental class names as durable rules.

## Preserve the guidance hierarchy

- Every existing `AGENTS.md` and `AGENTS.override.md` path is an established documentation scope. During ordinary
  guidance maintenance, do not delete, rename, relocate, merge, consolidate, or change the kind of any existing file.
  Improve a seemingly redundant scope in place by making its inherited and local rules more precise.
- Add a new AGENTS file only when verified architecture has a durable uncovered scope that no existing file can
  represent. A new scope never makes an existing one disposable. Keep override files explicit about which inherited
  assumption they replace and why.
- Before a hierarchy-wide audit, inventory tracked, untracked, hidden, and ignored AGENTS paths, including
  overrides; record each scope and its nearest ancestor guide. At handoff compare exact path sets and Git
  status/diff: no original path may disappear or become a rename. Default to exact equality and improve redundant
  scopes in place.
- Inheritance follows directory ancestry. Name the nearest governing guide when clarifying a scope; a sibling guide
  identifies a contract to consult, not another parent. Verification and self-evolution here apply to every descendant
  scope without repeating the same maintenance checklist in each file.

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

- Keep one authority for each state and one responsible owner for each resource. UI surfaces observe shared
  controllers/models; presentation snapshots must not become competing connection, routing, System Proxy, TUN,
  subscription, or test authorities. State transitions, result freshness, and physical resource release are separate
  claims: prove each at its owning boundary.
- Treat persisted profiles and plugin documents as input. Prepare runtime, routing, probe, and TUN state on explicit
  copies unless an API deliberately mutates storage. A failed pre-commit stage leaves persistence unchanged; a failed
  post-commit side effect is reported without pretending the commit rolled back. Identify the unit of commit:
  cancellation of a batched operation may preserve completed batches rather than roll back the entire command.
- Use stable domain identity, not table rows, proxy indexes, display text, or object position. Async results additionally
  prove that the target generation/fingerprint is still current before mutation.
- Distinguish profile identity, subscription membership, remote synchronization ownership, and execution snapshots.
  Moving a profile into a group does not transfer remote ownership; a running core uses its prepared document even
  when the live profile later changes.
- Startup and other staged workflows own every resource acquired before commit and roll back only that attempt on
  failure, cancellation, or supersession. Cleanup is bounded where responsiveness requires it, idempotent, and targets
  exact processes, threads, replies, timers, files, handles, routes, and callbacks—never process names.
- Keep new GUI-thread work bounded through an owned worker or asynchronous Qt boundary; workers publish data back to
  the owning Qt thread and never mutate widgets or live repositories directly. Existing synchronous compatibility
  and host-operation paths require explicit responsiveness review: an async entry point alone does not prove
  non-blocking preparation, cancellation, or shutdown.
- Validate user, network, persisted, and plugin data at boundaries. Keep invariant failures visible, preserve useful
  diagnostics, and never log credentials, subscription payloads, full share links, environments, or complete core
  documents.
- Preserve source execution, wheel/sdist installation, and Nuitka/native distributions. Importing dependency-light
  layers must not construct the application, discover plugins, start runtimes, or create UI.

## Working in the tree

- Preserve unrelated and unstaged user changes. Do not revive deleted experiments from history or broaden a task to
  nearby technical debt.
- Before Python work, prefer an existing root `.venv*`/`venv*` interpreter. Do not create or mutate an environment
  without need. Format only touched Python files with `python -m black <files>`, then `python -m black --check
  <files>`; `pyproject.toml` preserves string quotes. Syntax/import checks supplement behavior tests.
  Documentation-only work does not require unrelated formatting or generated-file refreshes.
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
  Test a resource that refuses cleanup as well as one that exits normally. A terminal flag, cleared reference, or
  elapsed timeout is not evidence of native resource release; distinguish that observation from the intended guarantee.
- Report source inspection, executed tests, mocked platform evidence, and packaged validation separately. A passing
  source suite does not prove native distributions or every declared Python/Qt floor. Release import checks do not
  replace behavioral tests; record untested targets and compatibility gaps explicitly.
- Use real Qt semantics when focus, selection, keyboard modifiers, proxy mapping, event delivery, queued callbacks,
  geometry, or QObject destruction matters. Prefer semantic state and destroyed/resource counts; use targeted
  rendering assertions when pixels are the defect, without relying on whole-window snapshots or arbitrary sleeps.
- Before handoff, review for duplicate authorities, persisted-data mutation during preparation, stale async write-back,
  swallowed diagnostics, unowned resources, unbounded external-input caches, plugin-specific branches in shared code,
  and source-only assumptions at packaging boundaries.

## Maintaining this guidance

- AGENTS files are maintained architectural memory, not immutable truth. Update durable rules only when supported by
  current architecture, tests, verified runtime behavior, explicit design, or an intentional refactor completed in the
  same change.
- Put a rule at the narrowest scope where it helps future decisions; let child guides specialize rather than repeat
  parents. For each local rule, identify the decision it protects and the implementation or test that could disprove
  it. Anchor non-obvious rules to owning implementations and focused tests; label untested assumptions or known gaps
  rather than promoting them into guarantees. Remove obsolete content inside files, distinguish preferred architecture
  from compatibility paths, and preserve every established path. A guidance audit must not turn a defect into a design.
- After significant architectural work, re-read the applicable hierarchy as a fresh agent: can it identify the
  owner, invariant, failure boundary, and relevant tests without relying on conversation history? Challenge rules
  likely to become stale, circular references, and wording that freezes incidental structure.
- Distinguish observed behavior from design requirements and name tests/consumers that can challenge a local rule.
  A known limitation is not a desired invariant. During guidance-only work, report code defects separately instead
  of changing production code to satisfy the prose.

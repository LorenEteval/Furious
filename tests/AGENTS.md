# Furious test guidance

Inherit repository-wide rules from the root `AGENTS.md`. This scope specializes isolation, evidence, resource ownership,
and test-tier selection; test convenience never weakens a production invariant.

## Isolation is a product invariant

- Tests must not affect a running Furious instance, production settings/data, desktop windows, tray, system proxy, DNS,
  routing, TUN, startup registration, interfaces, unrelated processes, or external services. Use `tests/support.py`, an
  offscreen Qt platform set before Qt import, a temporary INI settings identity, temporary files, and fully mocked host
  and network boundaries.
- Own exact child processes, threads, timers, replies, sockets, and handles created by a test. All waits are bounded and
  cleanup targets only those resources. Normal suites require neither network access nor installed proxy cores.
- Tests may exercise real Qt event loops, subprocesses, and compiled probes when that boundary is the defect, but use a
  hermetic child, temporary settings, disabled singleton/tray/restoration, and mocked host mutation.
- Import order is part of isolation: select the offscreen Qt platform and temporary settings identity before importing
  modules that can create Qt/application globals. A late patch is not equivalent to preventing the side effect.
  A temporary QSettings namespace does not reset already-cached `Storage` collections: explicitly isolate and restore
  live repository fixtures as well as persisted settings, especially when exercising cleanup or partial startup.

## Test the contract

- Assert semantic behavior and architectural invariants, not private coordinates or incidental call order. Internal
  counters/registries are valid evidence when ownership, reclamation, or complexity is the contract; pair them with
  an observable result instead of treating every implementation detail as forbidden. Cover success, invalid input,
  timeout/cancel, stale/partial completion, rollback, cleanup, and compatible persisted input where applicable.
- For staged changes, fail immediately before commit and prove live plus persisted state is unchanged. Test a
  post-commit side-effect failure separately. Keep persisted-profile assertions distinct from runtime-copy output.
- Use stable profile/subscription identities in reconciliation and async tests. Exercise supersession, removal/reorder,
  duplicate endpoints, bounded scheduling, and unrelated-work preservation rather than relying on row positions.
- Qt behavior involving focus, selection, proxy mapping, shortcuts, queued delivery, geometry, animation, or destruction
  uses real widgets and `QTest`. Localized-text tests choose an explicit language inside `isolatedSettings()`.
  Rendering regressions may assert targeted pixel/alpha or geometry properties under explicit themes and scaling.
  Stylesheet selector counts are not rendering invariants: shared rules and component overrides can both be valid.
- Prefer exact state, signal counts, destroyed signals, weak references, registry/child counts, thread/process/handle
  ownership, and final exit status. A mock cleared from its owner does not prove termination: failure-to-reap tests
  must independently retain and inspect the fake process. For Qt API compatibility, a permissive Python fake cannot
  validate a real binding's accepted argument types; exercise a harmless real object at that boundary.
  RSS/handle trends and repeated lifecycle batches belong in stress tiers; `gc.collect()` is diagnostic at batch
  boundaries, never a production fix or per-cycle requirement.

## Tiers and maintenance

- Use `python -m unittest tests.<module> -v` from the root for focused work and `python -m unittest discover -s
  tests -v` for full source-suite discovery (opt-in tests still skip). The runner is unittest, not pytest. Run the
  narrow module first, then the affected tier documented in `tests/README.md`. The release-confidence tier is
  explicitly opt-in with `FURIOUS_VERY_HEAVY_TESTS=1`; packaged/manual smoke work uses disposable environments.
  The historical log comparison additionally requires `FURIOUS_LOG_MANAGER_BASELINE` naming a trusted, compatible
  local Git revision; it loads that revision's implementation. Report this opt-in and any skips separately rather
  than assuming the very-heavy switch alone executes every discovered case.
- Source-only tests and an offscreen platform do not prove a packaged Qt runtime. Compiler-sensitive changes need
  native lifecycle tests and the compiled fixture documented in `tests/README.md`, including accept/reject/close
  and owner-first teardown. An unavailable private Nuitka counter is unknown, not measured zero; combine toolchain
  inspection with native destruction, weak-wrapper and registry evidence. Record the interpreter, binding/compiler,
  target, and relevant build flags with results: diagnostic flags can change the failing behavior and are not a
  substitute for the ordinary release build. Report skipped/unavailable targets and distinguish commented test
  examples from discovered tests. Release artifact checks do not execute this source behavioral suite.
- Separate deterministic correctness/scale assertions from performance measurements. Opt-in stress tests may gate
  relative scaling or resource bounds; document the measured contract and environment rather than treating one
  machine's absolute timing as a portable product requirement.
- Update `tests/README.md` when coverage ownership, modules, commands, tiers, opt-ins, or environment requirements change.
  The final unittest status and process exit code are authoritative even when negative paths intentionally log errors.
- Review new tests for production-state mutation, live network dependence, process-name cleanup, unbounded waits,
  shared mutable fixtures, order dependence, timing-only assertions, and storage assertions where runtime output is
  the contract. For guidance-only changes, verify path preservation, changed-file scope, referenced commands/tests,
  and contradictory claims; run existing behavior tests only to resolve architecture uncertainty rather than adding
  tests of prose.

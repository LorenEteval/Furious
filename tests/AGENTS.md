# Furious test guidance

## Isolation

- Tests never affect a running Furious instance or production data. Set `QT_QPA_PLATFORM=offscreen` before Qt import,
  use `tests/support.py` for one deliberately small application and temporary INI-backed QSettings identity, and mock
  every external/network/host service.
- Never mutate real proxy, DNS, routing, TUN, startup registration, tray, interfaces, desktop windows, or host processes.
  Own exact test threads/children/replies/handles, give waits bounded timeouts, and clean only resources created by the test.
- Normal tests require neither network access nor installed proxy cores. Real Qt/process boundaries use hermetic child
  scripts; packaged/manual smoke procedures are explicit and run only in disposable profiles/environments.

## Contract design

- Test public behavior and architectural contracts, not private widget coordinates or incidental implementation. Cover
  success, invalid input, timeout/cancel, partial/stale completion, cleanup, and compatible persisted input where relevant.
- Tests that assert localized text set `Language` in an `isolatedSettings()` scope or request an explicit locale. Do not
  depend on the system-locale default or on whether another test happened to construct the shared `QApplication` first.
- For staged mutations, fail immediately before commit and assert live plus persisted state is unchanged. Test
  post-commit side-effect failure separately without claiming rollback.
- Keep persisted profile and runtime-copy assertions distinct. TUN preservation, generated native TUN, application
  fallback, malformed explicit TUN, and proxy-only stripping are separate cases and must not share a helper that erases
  their differences.
- Deterministic logic/UI belongs in normal tiers. Repeated object/handle/thread/process/RSS trends belong in stress tiers;
  the release-confidence tier requires `FURIOUS_VERY_HEAVY_TESTS=1`.
- Prefer exact state, signal, destroyed, weak-reference, registry, thread, handle, and child assertions over arbitrary
  timing/RSS thresholds. `gc.collect()` is diagnostic at batch boundaries, never a production fix or per-cycle crutch.

## Real lifecycle boundaries and maintenance

- Bugs involving native Qt event loops/callbacks, interpreter finalization, subprocess teardown, wrapper destruction, or
  Nuitka callback retention require the smallest real integration boundary that reproduces them. Isolate it in a child
  with temporary settings, singleton/tray/restoration disabled, and all host/network mutation mocked.
- Exercise public shutdown and repeat intermittent lifecycles. Automated tests cannot focus, flash, inspect, signal, or
  modify the desktop or a potentially running Furious process.
- Update `tests/README.md` whenever modules, coverage ownership, tiers, commands, opt-ins, or environment requirements
  change. Run the narrow module first, then its documented tier; the final unittest status/exit code is authoritative
  even when negative-path diagnostics are expected.
- Review for production state/host mutation, external network dependence, process-name cleanup, unbounded waits, shared
  mutable fixtures, hidden test-order dependence, and assertions against storage when runtime output is the true contract.

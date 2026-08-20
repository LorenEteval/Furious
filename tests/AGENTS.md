# Furious test guidance

## Isolation

- Tests must never affect a running Furious instance or production data. Set `QT_QPA_PLATFORM=offscreen` before Qt
  import and use `tests/support.py` for one small application and temporary INI-backed settings.
- Never mutate real proxy, DNS, routing, TUN, startup registration, tray, network interfaces, or external services.
  Patch host/network APIs and inject fake controllers, runtimes, repositories, clocks, and clients.
- Own exact subprocess handles/PIDs and threads. Use bounded waits and clean up only resources the test created; never
  discover or terminate by process name.
- Normal tests require no external network or installed proxy core. Keep packaged/manual smoke procedures explicit and
  disposable.

## Test design

- Test public behavior and architectural contracts, not implementation trivia. Cover success, validation failure,
  timeout, cancel, partial/stale result, cleanup, and backward-compatible persisted input.
- Use canonical `CoreRuntime` vocabulary in runtime factories, registry fixtures, and traffic-statistics providers.
- Separate persisted configuration from runtime-copy assertions. Normal connection, generated native TUN, preserved user
  TUN, and proxy-only stripping must not share a helper that erases their differences.
- Keep deterministic logic/UI behavior in the normal tier. Put repeated live-object, native-handle, thread, subprocess,
  and RSS trends in explicit stress tiers.
- Qt lifetime tests use real close/deferred-delete paths, weak references, destroyed signals, and live counts.
  `gc.collect()` is diagnostic at batch boundaries only; threshold increases or production collection are not leak
  fixes.
- Avoid timing-only assertions. Drive events deterministically and assert final ownership/state plus absence of
  duplicate connections/timers/replies.
- Update `tests/README.md` when modules, tiers, or environment requirements change. Documentation commands use the
  active `python` environment.

## Real lifecycle and process-boundary regressions

- Apply the highest-fidelity safe test boundary throughout the suite. Unit tests remain appropriate for deterministic
  logic, but bugs involving Qt event loops, native callbacks, interpreter finalization, subprocess teardown, or wrapper
  destruction need a focused integration test that exercises the real boundary that failed.
- For application-lifecycle regressions, start a clean child Python process, force `QT_QPA_PLATFORM=offscreen` before
  importing Qt, construct the smallest real `QApplication`/`DesktopApplication` and real Qt window needed, run the real
  event loop, request shutdown through the public path, and assert the child process exits normally. Repeat the cycle
  when the defect is intermittent.
- A lifecycle child must be hermetic: bypass single-instance discovery and IPC, use temporary settings and application
  identity where relevant, disable tray and startup restoration, mock all host/network integrations, and never attach
  to, signal, inspect, or change a potentially running Furious instance.
- Child-process tests own only the windows, threads, handles, and processes they create. Give every wait and child a
  bounded timeout, capture diagnostics, and terminate only that exact child on timeout. Never use process-name cleanup.
- Visible diagnostic windows are for an explicit manual smoke procedure only. Automated tests always use the offscreen
  platform so they cannot flash, steal focus, or interact with the desktop session.

## Code review rules

- Flag production settings/host mutation, broad process cleanup, unbounded waits, external network dependence, shared
  mutable fixtures, and tests that only check storage when runtime output is the contract.

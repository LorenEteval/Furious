# Furious test guidance

## Isolation

- Tests never affect a running Furious instance or production data. Set `QT_QPA_PLATFORM=offscreen` before Qt import,
  use `tests/support.py` for one small application and temporary INI-backed settings, and mock every external service.
- Never mutate real proxy, DNS, routing, TUN, startup registration, tray, interfaces, or host processes. Own exact test
  threads/children/handles, give waits bounded timeouts, and clean up only resources created by the test.
- Normal tests need no network or installed proxy core. Keep packaged/manual smoke procedures explicit and disposable.

## Test contracts

- Test public behavior and architecture contracts rather than private layout trivia. Cover success, invalid input,
  timeout/cancel, partial/stale completion, cleanup, and compatible persisted input where applicable.
- For staged mutations, fail immediately before commit and assert live plus persisted state is unchanged. Test
  post-commit side-effect failure separately without claiming rollback.
- Keep persisted configuration and runtime-copy assertions distinct. TUN preservation, generated TUN, fallback, and
  proxy-only stripping must not share a helper that erases their differences.
- Deterministic logic/UI belongs in normal tiers. Put repeated object/handle/thread/process/RSS trends in stress tiers;
  very heavy work requires `FURIOUS_VERY_HEAVY_TESTS=1`.
- Prefer exact ownership, destroyed-signal, registry, thread, handle, and child assertions over timing or arbitrary RSS
  thresholds. `gc.collect()` is diagnostic at batch boundaries, never a production fix or per-cycle requirement.

## Real lifecycle boundaries

- Bugs involving Qt event loops, native callbacks, interpreter finalization, subprocess teardown, or wrapper destruction
  require a focused integration test using the smallest real boundary that failed.
- Run lifecycle regressions in a clean child process with offscreen Qt, temporary identity/settings, singleton IPC and
  tray/restoration disabled, and all host/network integration mocked. Exercise the public shutdown path and repeat when
  intermittent.
- Automated tests cannot flash, focus, inspect, signal, or modify the desktop or a potentially running Furious process.
  Visible windows are limited to explicit manual smoke procedures.
- Update `tests/README.md` when modules, tiers, commands, or environment requirements change; examples use active
  `python`.

## Review

- Flag production state/host mutation, external network dependence, process-name cleanup, unbounded waits, shared
  mutable fixtures, and tests that assert storage when runtime output is the actual contract.

# Frozenlib guidance

## Foundation and compatibility

- `Frozenlib` is the low-level platform/compatibility foundation and a broad import surface. Keep imports cheap,
  cross-platform, and free of application/UI construction. Preserve exports unless all wildcard consumers migrate.
- `Constants`, enums, and pure helpers remain dependency-light. `Globals` exposes only deliberate application-lifetime
  owners and returns safely during partial startup/shutdown.
- `AppSettings` is the preference boundary. Preserve key/value/default/migration compatibility and write a requested
  state only after any required host side effect succeeds.

## Host and resource ownership

- Isolate proxy, DNS, routing, TUN, startup, session, and process mutation here so callers can mock it completely.
  Return/log actionable failure and never test against real host state.
- `runExternalCommand()` deliberately has no universal timeout; each caller supplies one when responsiveness requires
  it or documents a non-GUI execution context.
- Own exact threads/processes/handles, clear dead daemon references, and make cleanup bounded and repeatable. Externally
  keyed caches are bounded; finite metadata caches never capture QObject instances or bound methods.
- Context managers restore prior state when nested. Weak pools/callbacks must not have a parallel strong owner.
- `AppResources.py` is generated from resource inputs; update inputs and regenerate.

## Verification

- Use direct mocked helper tests plus affected controller/service tests. Review GUI blocking, persisted success after
  host failure, process-name cleanup, sensitive logs, stale daemon references, and unbounded external-input caches.

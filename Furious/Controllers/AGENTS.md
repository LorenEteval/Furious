# Controller guidance

- Controllers are process-lifetime state authorities. Expose observable state/transitions and orchestrate
  repositories/services; do not retain transient widgets or duplicate service resource ownership.
- `ConnectionController` owns the connection state machine and interaction gating. Stable and transitional states,
  failures, unexpected exits, reconnect preference, `runtimes` snapshots, and signal ordering must remain explicit.
  Runtime managers are injected for tests.
- `RoutingController` owns selected/active routing semantics. Distinguish repository selection from the routing actually
  applied to a live connection; derive runtime routing through backend capabilities.
- `SettingsController` validates, persists, and applies settings through service-level APIs where practical. Host
  registration or administrator-dependent changes persist only after success; UI pages should not implement settings
  policy.
- Controller signals carry state/results, not widget callbacks. Long work belongs in services/workers, and GUI-thread
  entry points must not perform unbounded waits.
- Treat partial startup/shutdown as normal: global dependencies may be absent and cleanup methods must be repeatable.

## Code review rules

- Flag direct ownership of dialogs/pages, duplicated connection/routing state, settings saved after failed side effects,
  and protocol branches that belong in a capability.
- Test success, validation failure, startup failure, unexpected exit, signal order, restoration, cancellation, and
  idempotent shutdown.

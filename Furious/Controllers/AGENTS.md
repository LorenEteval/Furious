# Controller guidance

## State authorities

- Controllers are process-lifetime authorities for shared application state and transitions. They orchestrate
  repositories/services and publish structured signals; they do not own transient widgets or duplicate service
  resources.
- `ConnectionController` is the sole connection state machine. Preserve atomic state/signal ordering, interaction gating,
  the exact active `ServerProfile`, runtime snapshots, persisted reconnect preference, and cleanup after validation,
  start, system-proxy, or unexpected-core-exit failure. Worker/core callbacks queue work back to its Qt thread.
- `RoutingController` owns displayed/persisted selection and capability-provided options. Distinguish the selected
  repository profile from the profile already owned by a live connection; changing routing may require a controlled
  reconnect rather than mutating the running document.
- `SettingsController` validates preferences and applies host/UI effects. When a host effect such as startup registration
  fails, do not persist the requested state as successful. Keep UI pages declarative and do not duplicate this policy.
- Protocol/core-specific behavior goes through plugin capabilities. Long work belongs in an owned service/worker, and
  global compatibility dependencies may be absent during partial startup, teardown, or isolated tests.

## Verification

- Test exact transitions and signal counts for success, invalid input, runtime/system-proxy failure, cancellation,
  unexpected exit, routing refresh/reconnect, startup restoration, failed settings effects, partial dependencies, and
  repeatable shutdown.

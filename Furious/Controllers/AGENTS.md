# Controller guidance

## Scope and ownership

- Controllers are process-lifetime authorities for shared state and transitions. They orchestrate repositories/services
  and publish results; they do not own transient widgets or duplicate service resources.
- `ConnectionController` owns connection state, interaction gating, active profile, failure/exit transitions, and signal
  ordering. `RoutingController` distinguishes repository selection from routing applied to a live connection.
- `SettingsController` validates, persists, and applies preferences. A setting whose host side effect fails must not be
  persisted as successful; UI pages do not reimplement that policy.
- Protocol-specific behavior goes through capabilities. Long work belongs in an owned service/worker, not an unbounded
  GUI-thread controller call. Global dependencies may be absent during partial startup and shutdown.

## Verification

- Test transitions and signal counts for success, validation/start failure, cancellation, unexpected exit, restoration,
  failed settings effects, and repeatable shutdown.

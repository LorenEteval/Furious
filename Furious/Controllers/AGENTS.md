# Controller guidance

Inherit `Furious/AGENTS.md` and its root ancestor. This scope preserves controllers as process-lifetime
authorities for shared transitions. Services own execution resources; existing prompts are presentation
compatibility paths.

## Shared state authorities

- Controllers own process-lifetime shared state and transition policy. They coordinate injected repositories/services
  and publish structured Qt signals. New behavior delegates presentation and execution resources to their owners;
  existing host-setting prompts do not justify moving network replies, core processes, or pools into controllers.
- `ConnectionController` is the sole connection state machine. A GUI start remains `Connecting` while one
  generation-checked `ConnectionManager` transaction acquires readiness/TUN resources. The selected live profile is
  exposed during `Connecting`; successful runtime commit precedes System Proxy setup and `Connected`. Failure resets
  the active profile. Disconnect/reconnect cancels the exact in-flight generation and ignores stale completion.
- Preserve state and signal ordering, interaction gating, the exact selected `ServerProfile`, runtime snapshots,
  reconnect preference, and rollback after validation, runtime, TUN, System Proxy exceptions, cancellation, or unexpected-exit
  failure. Worker/native callbacks cross to the controller’s Qt thread before transition. Signal listeners and queued
  actions can synchronously disconnect or replace a start. Required invariant: revalidate current state/operation
  after invoking them before acquiring a runtime, completing the connection, or applying further host effects.
  This includes the initial profile/state/progress notifications, before a start operation exists to cancel.
  Verify that a listener which disconnects during `Connecting` prevents subsequent launch admission, not merely
  that the final state label is Disconnected. A pre-emission check cannot establish freshness afterward.
- The active live profile is not the prepared document used by an already-started runtime. Resolve identity and
  generation before changing state or host effects, and preserve typed runtime failures; cancellation and supersession
  are not generic connection errors. Runtime commit, host-effect success, and visible connection state are distinct
  observations. Progress completion only ends the presentation interval; consumers and tests use connection state,
  structured errors/notifications, and host results to establish the outcome.
- `RoutingController` owns available capability options plus selected/persisted routing. Distinguish a newly
  selected repository profile from the active-profile reference and the independent runtime document; changes use
  controlled reconnect, not mutation of the running document. Capability refresh prefers the active profile and
  otherwise the repository's activated profile. Normalizing the displayed option does not itself persist a new
  preference; explicit selection or invalidation owns that mutation. Disabling the selected custom route persists
  its supported fallback without reconnecting by itself; re-enabling restores availability, not selection.
  If reconnect is declined, selected/persisted routing may differ from the running document. Menu checkmarks prove
  selection only; exercise fallback persistence separately from reconnect acceptance and runtime preparation.
  `RoutingControllerTest` in `tests/test_controllers.py` anchors explicit invalidation versus observational refresh.
  User-defined routing labels are not translatable UI literals.
- `SettingsController` is the shared policy path used by Home, Settings, tray, and platform integration. Startup
  registration persists only after host success; other preferences may apply immediately or on the next connection.
  Preserve each setting's actual application timing instead of imposing one transaction order on all preferences.
- System Proxy configuration is best effort. Its helper logs host failures; an explicit False return does not roll
  back an otherwise usable committed runtime or prevent Connected. Preserve exception-path recovery separately.
  Exercise actual helper results with mocked OS boundaries; Connected does not guarantee the OS proxy was applied.

## Verification and evolution

- Test exact states and signal counts for async success, invalid input, supersession, cancellation, partial
  acquisition, System Proxy failure, unexpected exit, routing refresh/reconnect, startup restoration, failed host
  settings, missing partial-startup dependencies, and repeated shutdown. Ownership changes must retire the former
  state authority rather than leave two controllers. Start with `tests/test_controllers.py`, `tests/test_connection_startup_async.py`, and the shared-state cases in
  `tests/test_qt_interactions.py`.

# Controller guidance

## Shared state authorities

- Controllers own process-lifetime shared state and transition policy. They coordinate injected repositories/services
  and publish structured Qt signals; they do not own transient widgets, network replies, core processes, or worker pools.
- `ConnectionController` is the sole connection state machine. A GUI start remains `Connecting` while one generation-
  checked `ConnectionManager` transaction acquires readiness/TUN resources; System Proxy and the active-profile commit
  occur only after success. Disconnect/reconnect cancels the exact in-flight generation and ignores stale completion.
- Preserve state and signal ordering, interaction gating, the exact selected `ServerProfile`, runtime snapshots,
  reconnect preference, and rollback after validation, runtime, TUN, System Proxy, cancellation, or unexpected-exit
  failure. Worker/native callbacks cross to the controller’s Qt thread before transition.
- `RoutingController` owns available capability options plus selected/persisted routing. Distinguish a newly selected
  repository profile from the profile snapshot already owned by a live connection; changes use controlled reconnect,
  not mutation of the running document. User-defined routing labels are semantic data, not translatable UI literals.
- `SettingsController` is the shared policy path used by Home, Settings, tray, and platform integration. Validate
  availability and complete host effects before persisting success; UI surfaces render its signals rather than keeping
  duplicate preference state.

## Verification and evolution

- Test exact states and signal counts for async success, invalid input, supersession, cancellation, partial acquisition,
  System Proxy failure, unexpected exit, routing refresh/reconnect, startup restoration, failed host settings, missing
  partial-startup dependencies, and repeated shutdown. If ownership moves deliberately, update this guide and the
  affected controller tests instead of keeping a compatibility controller as a second authority.

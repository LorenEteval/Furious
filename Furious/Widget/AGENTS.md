# Reusable widget guidance

- Widgets are reusable presentation components below full pages/windows. Prefer controller/service/repository
  dependencies passed explicitly; do not add new `AppMainWindow()` reach-through or duplicate application state.
- Subscription views delegate download, decoding, reconciliation, persistence effects, and recurring scheduling to
  `SubscriptionManager`; keep view code limited to user intent, presentation, and repository-backed table refresh.
- Models, delegates, menus, actions, spinners, animations, timers, and network-backed helpers need explicit owners.
  Persistent page widgets are constructed once; refresh/show cycles toggle state rather than recreate/connect
  indefinitely.
- Resolve table/list actions through the model mapping that is current after sort/filter. Use stable repository IDs for
  persisted or cross-refresh identity; preserve existing row-index compatibility only where the repository contract
  still requires it. Keep model begin/end notifications and repository ordering synchronized.
- Use `AppQ*` controls and responsive layouts. Preserve translated-text growth, shortcuts, focus, accessibility, theme
  changes, high-DPI rendering, and hidden-page lazy behavior.
- Expensive parsing, map/network work, metrics aggregation, and subscription synchronization must not freeze the GUI.
  Batch, defer, or offload work according to the Qt API involved; publish worker results through owned signals and
  reject stale completions where requests can be superseded.
- Transient editors/progress dialogs use managed `open()` lifetime; reusable top-level windows retain one explicit
  owner.

## Code review rules

- Flag direct global/window reach-through, duplicated persistence logic, row-index identity, repeated signal/timer
  creation, hidden-page rendering, and callbacks retaining closed widgets.
- Run relevant behavior plus Qt lifetime tests for repeated refresh/show/open/close cycles.

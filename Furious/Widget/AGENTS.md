# Reusable widget guidance

- Widgets are reusable presentation components below full pages/windows. Prefer controller/service/repository
  dependencies passed explicitly; do not add new `AppMainWindow()` reach-through or duplicate application state.
- Subscription views delegate download, decoding, reconciliation, persistence effects, and recurring scheduling to
  `SubscriptionManager`; keep view code limited to user intent, presentation, and repository-backed table refresh.
- Models, delegates, menus, actions, spinners, animations, timers, and network-backed helpers need explicit owners.
  Persistent page widgets are constructed once; refresh/show cycles toggle state rather than recreate/connect
  indefinitely.
- Table selection operates on stable repository IDs, not visual rows after sort/filter. Keep model begin/end
  notifications, timer collections, and repository order synchronized.
- Use `AppQ*` controls and responsive layouts. Preserve translated-text growth, shortcuts, focus, accessibility, theme
  changes, high-DPI rendering, and hidden-page lazy behavior.
- Expensive parsing, syntax highlighting, map/network work, metrics aggregation, and subscription synchronization must
  not freeze the GUI. Publish results through owned signals and reject stale generations.
- Transient editors/progress dialogs use managed `open()` lifetime; reusable top-level windows retain one explicit
  owner.

## Code review rules

- Flag direct global/window reach-through, duplicated persistence logic, row-index identity, repeated signal/timer
  creation, hidden-page rendering, and callbacks retaining closed widgets.
- Run relevant behavior plus Qt lifetime tests for repeated refresh/show/open/close cycles.

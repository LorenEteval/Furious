# Reusable widget guidance

- Widgets are presentation components below pages/windows. Prefer explicit controller/service/repository dependencies;
  do not add new `AppMainWindow()` reach-through or duplicate application state.
- Subscription views issue commands to `SubscriptionManager` and render repository-backed results; they do not own
  download, decode, reconciliation, persistence, or scheduling workflows.
- Models, delegates, menus, actions, spinners, animations, timers, and network helpers have explicit owners. Persistent
  widgets are constructed and connected once; refresh/show toggles state rather than accumulating objects.
- Resolve actions through the current model/proxy mapping after sort/filter. Use stable IDs across persistence/refresh
  and keep model begin/end notifications synchronized with live repository ordering.
- Reuse `AppQ*` controls and keep expensive parsing, aggregation, mapping, and synchronization off blocking GUI paths.
  Reject stale completions where work can be superseded.
- Verify behavior and repeated refresh/show/open/close lifetime, including sorted/filtered model actions and hidden-page
  rendering.

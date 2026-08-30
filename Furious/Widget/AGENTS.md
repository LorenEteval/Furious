# Reusable widget guidance

- Widgets are presentation components below pages/windows. Prefer explicit controller/service/repository dependencies;
  do not add new `AppMainWindow()` reach-through or duplicate application state. Existing reach-through is compatibility
  debt that may be migrated without preserving the coupling.
- Server/subscription views render the same live repositories and share the server table's `SubscriptionManager`.
  Subscription views issue commands to that service; they do not duplicate download, decode, reconcile, persist, or
  schedule workflows.
- Qt models must bracket live-collection mutations with matching begin/end notifications and keep stored row/index flags
  synchronized. After sort/filter, map an action from the current proxy index to the source object and use stable IDs;
  display text and row position are not identity.
- Models, delegates, headers, menus, actions, spinners, animations, timers, network helpers, and
  reusable editors each need an explicit owner. Persistent widgets construct/connect once; refresh/show changes state
  instead of accumulating objects.
- Keep expensive parsing, aggregation, mapping, screen/network/core work off blocking GUI paths or split it into bounded
  event-loop units. Reject superseded worker/reply results before mutating a live model.
- `ServerTableView` owns profile-test selection and repaint only. Submit live selected profiles to `ProfileTestManager`,
  forward repository/subscription mutation boundaries, and repaint the exact committed latency/speed cell; do not move
  workers, queues, networking, concurrency, port allocation, or result mutation back into the widget.
- Verify behavior plus repeated refresh/show/open/close lifetime, sorted/filtered actions, model notification ranges,
  cancellation/stale results, hidden-page rendering, and exact cleanup of worker/core/native resources.

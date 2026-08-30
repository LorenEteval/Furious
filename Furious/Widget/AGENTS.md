# Reusable widget guidance

## Presentation and identity

- Widgets present state below pages/windows. Prefer explicit controller/service/repository inputs and do not add new
  application-global reach-through or a duplicate state cache; existing global access is compatibility debt, not a
  template.
- Table/list models wrap live repository collections. Bracket mutations with correct begin/end or layout notifications,
  keep index/deleted compatibility fields synchronized, and map proxy indexes to source objects before acting. Stable
  profile/subscription IDs—not display text, object row, or current sort order—preserve selection, focus, activation, and
  async write-back.
- Sorting/filtering/reordering must retain logical selection and keyboard focus. Recursively scope table-owned menu
  shortcuts as `WidgetShortcut` so a focused editor or another surface keeps its own shortcut semantics.

## Workflow and lifetime boundaries

- The server and subscription views share one subscription workflow owner. Subscription UI issues commands and renders
  sync state; it does not duplicate download, decode, reconciliation, timer, persistence, or post-commit behavior.
- `ServerTableView` owns selection and cell repaint for profile tests, while `ProfileTestManager` owns scheduling,
  concurrency, temporary runtimes, cancellation, stable-target validation, and latency/speed mutation. Repository or
  subscription changes are forwarded as invalidation boundaries; stale results never write by row.
- Models, delegates, headers, menus, actions, animations, spinners, WebEngine/map objects, timers, workers, and replies
  each need one owner. Persistent widgets connect once and refresh state; visibility may pause rendering/animation, not
  application-level log draining, traffic collection, or other service ownership.
- Verify sorted/filtered commands, notification ranges, identity-preserving move/delete, real keyboard focus and nested
  shortcuts, subscription/test cancellation, hidden-page rendering, exact cell updates, optional WebEngine fallback,
  and repeated cleanup to baseline. Update this guide when ownership moves; never move service orchestration back into
  a widget just to preserve historical wording.

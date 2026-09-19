# Reusable widget guidance

Inherit `Furious/AGENTS.md` and its root ancestor; consult `Furious/Qt/AGENTS.md` for shared
lifetime/presentation contracts. This scope covers reusable controls and model/view adapters below page
composition. Persistent widgets currently host some service owners; that construction detail does not make every
view an independent workflow authority.

## Presentation and identity

- Widgets present state below pages/windows. Prefer explicit controller/service/repository inputs and do not add new
  application-global reach-through or a duplicate state cache; existing global access is compatibility debt, not a
  template.
- Table/list models wrap live repository collections. Bracket mutations with correct begin/end or layout notifications,
  keep index/deleted compatibility fields synchronized, and map proxy indexes to source objects before acting. Stable
  profile/subscription IDs—not display text, object row, or current sort order—preserve selection, focus, activation, and
  async write-back.
- Sorting/filtering/reordering must retain logical selection and keyboard focus. Capture domain IDs before yielding
  to a dialog or event-loop turn; an ordinary QModelIndex/source row may become invalid or refer to another item.
  Resolve a multi-target confirmation independently for each captured ID: targets may move or disappear while it is
  open, and later selection must not change the command. Map resolved objects back through the proxy when restoring
  focus. Recursively scope table-owned menu shortcuts as `WidgetShortcut` so focused editors and other surfaces
  keep their own shortcut semantics. Selection identity, current keyboard index, and selection painting are separate:
  keeping targets highlighted while a command button/menu has focus must not change selection or steal editor focus.
  Exercise the button-focus interval before popup display as well as the open menu to catch highlight flicker.

## Workflow and lifetime boundaries

- The server and subscription views share one subscription workflow owner. Subscription UI issues commands and renders
  sync state; it does not duplicate download, decode, reconciliation, timer, persistence, or post-commit behavior.
- `ServerTableView` owns selection and cell repaint for profile tests, while `ProfileTestManager` owns scheduling,
  concurrency, temporary runtimes, cancellation, stable-target validation, and latency/speed mutation. Repository or
  subscription changes are forwarded as invalidation boundaries; stale results never write by row.
- Models, delegates, headers, menus, actions, animations, spinners, WebEngine/map objects, timers, workers, and replies
  each need one owner. Persistent widgets connect once and refresh state; visibility may pause rendering/animation, not
  application-level log draining, traffic collection, or other service ownership.
- A pending confirmation whose callback mutates a view belongs to that exact view on every platform. A shared
  window parent can outlive the view, and an unparented prompt can outlive both. Native view destruction must end
  the prompt without running its mutation; `test_qt_lifetime.py` exercises this with the containing window still alive.
- Model notifications describe the real source mutation. Structural replacement may legitimately use a model reset;
  metadata-only test results should update the exact cell. A persistent model index is valid only within its model
  and can be invalidated by removal/reset; use domain IDs across collection/model replacement. Do not use resets or
  full repaints to mask broken mapping. Test selected identities and the current keyboard index independently.
- Bulk profile mutations validate/prepare a batch before beginning structural notifications. Resolve captured IDs
  again after confirmation and between deferred batches, report actual source ranges, and preserve activation before
  observers see completed removal. Forward bulk insert/delete operations through the model instead of replaying a
  single-item notification/reconciliation path for every profile. Small direct operations and deferred large ones
  share these identity rules; batch yields and throttled progress updates serve different responsiveness purposes.
- Endpoint lookup belongs to `EndpointInfoService`; the map renders validated results and has a no-WebEngine
  fallback. Optional WebEngine import failure must not prevent importing the widget/package, and hidden presentation
  must not retarget a queued lookup.
- Verify sorted/filtered commands, notification ranges, identity-preserving move/delete, real keyboard focus and
  nested shortcuts, subscription/test cancellation, hidden-page rendering, exact cell updates, optional WebEngine
  fallback, and repeated cleanup to baseline. Update this guide when ownership moves; never move service
  orchestration back into a widget just to preserve historical wording. Start with `tests/test_qt_interactions.py`,
  `tests/test_profile_test_jobs.py`, and `tests/test_endpoint_info.py`.

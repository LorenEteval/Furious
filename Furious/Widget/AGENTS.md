# Reusable widget guidance

Inherit the [nearest parent guide](../AGENTS.md). Widgets own controls and model/view adapters, not
independent workflows. Domain identity survives sorting and deferred commands; indexes remain model-specific.
Read `Furious/Widget/ServerTableView.py` with `tests/test_qt_interactions.py`; paths are relative to this
source tree's root.

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
  An action shared with a page button still resolves the table's selected domain targets when triggered; moving its
  presentation must not introduce another test scheduler or a second selection model.

## Workflow and lifetime boundaries

- The server and subscription views share one subscription workflow owner. Subscription UI issues commands and renders
  sync state; it does not duplicate download, decode, reconciliation, timer, persistence, or post-commit behavior.
- `ServerTableView` owns selection and cell repaint for profile tests, while `ProfileTestManager` owns scheduling,
  concurrency, temporary runtimes, cancellation, stable-target validation, and latency/speed mutation. Repository or
  subscription changes are forwarded as invalidation boundaries; stale results never write by row.
- Persistent widgets reuse their model, delegates and signal paths during refresh; replacement needs explicit
  retirement of the former owned tree. Visibility may pause rendering/animation, not application-level log draining,
  traffic collection, or other service ownership.
  A view may borrow a model, delegate, or controller; installing one is not a transfer of QObject ownership.
  Parent newly created presentation objects to their intended owner and retire replacements at the creating
  boundary, while preserving explicitly shared owners. Test native owner-first teardown with wrappers retained.
- A pending confirmation whose callback mutates a view belongs to that exact view on every platform. A shared
  window parent can outlive the view, and an unparented prompt can outlive both. Native view destruction must end
  the prompt without running its mutation; `test_qt_lifetime.py` exercises this with the containing window still alive.
- Model notifications describe the real source mutation. Structural replacement may legitimately use a model reset;
  metadata-only test results should update the exact cell. Observers may run synchronously at notification boundaries:
  expose consistent source contents, activation, and index/deleted fields before publishing completion. A persistent
  model index is valid only within its model and can be invalidated by removal/reset; use domain IDs across
  collection/model replacement. For a non-reset update, preserve the model's persistent-index mapping as well as
  the view's selected IDs. Do not use resets or full repaints to mask broken mapping. Test selected identities and
  the current keyboard index independently.
- Bulk profile mutations validate/prepare a batch before beginning structural notifications. Resolve captured IDs
  again after confirmation and between deferred batches, report actual source ranges, and preserve activation before
  observers see completed removal. Forward bulk insert/delete operations through the model instead of replaying a
  single-item notification/reconciliation path for every profile. Small direct operations and deferred large ones
  share these identity rules; batch yields and throttled progress updates serve different responsiveness purposes.
  Duplication captures selected IDs, resolves surviving sources at each batch, and uses independent manual copies;
  cancellation preserves completed batches, and explicit table cleanup stops pending copies before service shutdown.
  Favorite commands use the repository's local metadata mutation and
  keep connection/remote ownership intact. Favorites, search, and subscription filters intersect in the existing
  proxy model; a favorite mark is persisted metadata, while the filter is presentation state. The profile mutation
  and Home workflow cases in `tests/test_qt_interactions.py` cover these boundaries.
  Favorite SVG decoration follows the remark's foreground and selected-text roles, including privilege-dependent
  connection colors. Use the shared color authority and view palette rather than a dark/light test; keep selected
  icon and text behavior aligned. The selected-rendering cases in `tests/test_qt_interactions.py` are the pixel anchor.
- Endpoint lookup belongs to `EndpointInfoService`; the map renders validated results and has a no-WebEngine
  fallback. Optional WebEngine import failure must not prevent importing the widget/package, and hidden presentation
  must not retarget a queued lookup.
- Verify sorted/filtered commands, notification ranges, identity-preserving move/delete, real keyboard focus and
  nested shortcuts, subscription/test cancellation, hidden-page rendering, exact cell updates, optional WebEngine
  fallback, and repeated cleanup to baseline. Update this guide when ownership moves; never move service
  orchestration back into a widget just to preserve historical wording. Start with `tests/test_qt_interactions.py`,
  `tests/test_profile_test_jobs.py`, and `tests/test_endpoint_info.py`. When an event-filter callback destroys its
  watched target or owner, exercise actual native event delivery in an isolated child; calling the Python
  filter method directly cannot establish safe Qt delivery. Navigation cases live in
  `tests/test_isolation_and_navigation.py`.
  Outside-click navigation collapse leaves surviving targets' clicks deliverable, but consumes the event if a
  synchronous observer deletes its target or containing view. Native child probes cover both destruction cases.

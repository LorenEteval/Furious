# Window and page guidance

Inherit the [nearest parent guide](../AGENTS.md).
Windows and pages compose presentation around shared owners. Persistent, reusable and transient surfaces
have different close semantics; visibility does not transfer workflow ownership.
Read `Furious/Window/MainWindow.py` with `tests/test_ui_behavior.py`; paths are relative to this source tree's root.

## Composition and shared state

- `MainWindow` owns the persistent built-in page tree and navigation; plugin pages enter through the plugin navigation
  service. Pages adapt shared controllers/services/repositories and must not become competing state authorities.
  Plugin page factories transfer widgets to the navigation owner; the registry's lifetime does not keep a page valid.
  Verify failed construction/registration cleanup as well as successful one-time registration through
  `PluginNavigationManager` and `tests/test_service_runtime.py`.
  Preserve application-facing forwarding APIs until their consumers migrate deliberately. Bulk profile forwarding
  must retain the bulk mutation boundary through Home and its model, without expanding into per-profile refreshes.
- Home, Settings, tray actions, and reusable dialogs render the same connection, routing, and settings controllers.
  Apply availability and interaction gating to both a control and its associated label, on initial composition and
  later state changes. Disabling presentation does not clear a stored preference or authorize a duplicate host side
  effect; preserve the controller's platform/capability policy.
  Application-engine customization is independent of proxy-core native TUN. The sing-tun dialog edits a copied
  option projection; Models validates its closed native schema and Repository commits it. Advanced JSON is not a
  full core document or permission to override application-owned routing/DNS. Present effective defaults without
  silently normalizing storage, importing tun2socks preferences, or launching a native engine just to open settings.
  The application JSON editor is another view of that same candidate, not a second configuration authority.
  Validate the merged candidate at acceptance; editor syntax checking does not replace model validation.
  Translate semantic application validation categories here, preserving technical diagnostics and user JSON keys.
  Do not classify failures by matching exact English exception text.
- The current page composition shares one subscription workflow between server and subscription presentation, records
  traffic into one history, and derives metrics/endpoint presentation from owned services. These exact locations may
  evolve, but a refactor retains one durable owner, one scheduler/request path, and one signal path.
- Home remains the initial page and navigation expansion/selection is session-local unless a product decision adds a
  persisted migration. Plugin ordering and bottom settings placement remain declarative navigation concerns.

## Visibility, lifetime, and geometry

- Long-lived pages construct persistent controls, models, timers, services, and connections once. Page visibility may
  coalesce log/graph painting or deliberately gate a lazy endpoint lookup, but it never owns log collection/draining,
  traffic sampling, subscription schedules, or an already-started request.
- A page that creates a service must make its process-lifetime or page-lifetime ownership explicit and expose one
  cleanup path through the containing window/application. Moving a service between pages must not duplicate schedules,
  histories, requests, or controller connections during the transition.
  Status/layout publication may destroy the page, badge and service synchronously. Check the surviving owner before
  later child-widget or timer work; Home's badge and connectivity cases in `tests/test_ui_behavior.py` and
  `tests/test_service_runtime.py` cover both direct and Qt-dispatched delivery.
- One-shot editors/prompts use managed transient dialogs and weak compiled-safe continuations. Reusable text/editor
  windows and retained settings dialogs need an explicit owner and reopen policy. Classify a plugin-created page or
  dialog by the lifetime transferred to its caller, not by the registry's process lifetime. A settings label or Qt
  parent does not determine lifetime: inspect the base class and close/accept/reject path before changing deletion policy.
- Empty-state presentation distinguishes an empty repository from a filtered view with no matches. Recovery changes
  view filters only; reuse existing import/edit/test actions instead of creating page-specific workflow owners.
- Use normal layouts and `AppQ*` controls. Restore top-level geometry only after persistent composition and through the
  canonical first-show path; never-shown Qt fallback geometry must not overwrite a prior user decision.
- QR export captures capped independent profile snapshots before deferred work. Incremental generation is owned by
  the result window and stops on close; a malformed item cannot retarget or invalidate completed tabs. Attempted
  items and successful tabs are separate counts: failures still advance the batch, and an all-failed export closes
  its empty window. Cancellation preserves already generated tabs while releasing pending snapshots. Resizing
  scales the cached module image at integer factors with its quiet zone, rather than regenerating or smoothing
  secret-bearing QR content. Reuse plugin export semantics and never log the encoded URI.
- Search debounce belongs to the persistent page: clear/submit cancels pending work, hide stops it, and show applies
  only the current query. Find shortcuts are page-scoped; document editing shortcuts stay with their document widget.
  Settings search matches section headings and card titles/descriptions, including plugin metadata and English/current
  locale text. It filters presentation only: never search control values, apply preferences, enable disabled cards, or
  reveal platform-unavailable sections. The search control owns debounce and its Find action; the page supplies its
  existing cards/sections. Refilter after all translated labels update. The Settings organization cases
  in `tests/test_ui_behavior.py` cover these boundaries with real input and navigation.
- Log freezing is currently commented out. Its restoration notes and commented cases in
  `tests/test_ui_behavior.py` are design references, not executed coverage. If restored, keep freezing a
  presentation policy and verify filtering/catch-up after clear, eviction, and navigation against the live
  bounded collector. Do not infer active features or coverage from preserved restoration code.
- Log views keep per-filter cursors and catch up on visibility; metrics pages derive series from shared raw history.
  Switching pages, ranges, or filters must not reset collection or create a second history. Metric buckets use the
  shared monotonic timeline: moving the visible range must not regroup unchanged historical samples. Preserve missing
  samples separately from zero measurements and usage-history clearing separately from speed history.

## Verification and evolution

- Verify initial/plugin navigation, shared Home/Settings/tray state, service ownership, lazy rendering versus
  continuous collection, async continuation cleanup, unsaved-close behavior, translation/theme changes, geometry
  migration, and repeated open/show/hide/destroy stability with real Qt input where semantics depend on it.
  Anchors include `tests/test_ui_behavior.py`, `tests/test_qr_export_scalability.py`, `tests/test_metrics_behavior.py`,
  and `tests/test_main_window_geometry.py`.

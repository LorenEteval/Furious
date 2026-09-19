# Window and page guidance

Inherit the root and package guides. Consult Qt/Widget for presentation and Controllers/Service for shared owners.
This scope owns persistent page composition and top-level presentation, not shared domain state.

## Composition and shared state

- `MainWindow` owns the persistent built-in page tree and navigation; plugin pages enter through the plugin navigation
  service. Pages adapt shared controllers/services/repositories and must not become competing state authorities.
  Preserve application-facing forwarding APIs until their consumers migrate deliberately. Bulk profile forwarding
  must retain the bulk mutation boundary through Home and its model, without expanding into per-profile refreshes.
- Home, Settings, tray actions, and reusable dialogs render the same connection, routing, and settings controllers.
  Apply availability and interaction gating to both a control and its associated label, on initial composition and
  later state changes. Disabling presentation does not clear a stored preference or authorize a duplicate host side
  effect; preserve the controller's platform/capability policy.
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
- One-shot editors/prompts use managed transient dialogs and weak compiled-safe continuations. Reusable text/editor
  windows and retained settings dialogs need an explicit owner and reopen policy. A settings label or Qt parent does
  not determine lifetime: check the actual base class and close/accept/reject path before changing deletion policy.
- Empty-state presentation distinguishes an empty repository from a filtered view with no matches. Recovery changes
  view filters only; reuse existing import/edit/test actions instead of creating page-specific workflow owners.
- Use normal layouts and `AppQ*` controls. Restore top-level geometry only after persistent composition and through the
  canonical first-show path; never-shown Qt fallback geometry must not overwrite a prior user decision.
- QR export captures capped independent profile snapshots before deferred work. Incremental generation is owned by
  the result window and stops on close; a malformed item cannot retarget or invalidate completed tabs. Resizing
  scales the cached module image at integer factors with its quiet zone, rather than regenerating or smoothing
  secret-bearing QR content. Reuse plugin export semantics and never log the encoded URI.
- Search debounce belongs to the persistent page: clear/submit cancels pending work, hide stops it, and show applies
  only the current query. Find shortcuts are page-scoped; document editing shortcuts stay with their document widget.
- LogPage's optional Pause/Resume Updates control and logic are currently commented out. Its restoration notes and
  the two retained pause tests in `tests/test_ui_behavior.py` describe the intended contract if re-enabled: freeze
  presentation/filters only, keep collection bounded, and resume from retained entries after clear/eviction/navigation.
- Log views keep per-filter cursors and catch up on visibility; metrics pages derive series from shared raw history.
  Switching pages, ranges, or filters must not reset collection or create a second history. Metric buckets use the
  shared monotonic timeline: moving the visible range must not regroup unchanged historical samples. Preserve missing
  samples separately from zero measurements and usage-history clearing separately from speed history.

## Verification and evolution

- Verify initial/plugin navigation, shared Home/Settings/tray state, service ownership, lazy rendering versus
  continuous collection, async continuation cleanup, unsaved-close behavior, translation/theme changes, geometry
  migration, and repeated open/show/hide/destroy stability with real Qt input where semantics depend on it. Anchors include `tests/test_ui_behavior.py`,
  `tests/test_qr_export_scalability.py`, `tests/test_metrics_behavior.py`, and `tests/test_main_window_geometry.py`.

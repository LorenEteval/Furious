# Window and page guidance

## Composition and shared state

- `MainWindow` owns the persistent built-in page tree and navigation; plugin pages enter through the plugin navigation
  service. Pages adapt shared controllers/services/repositories and must not become competing state authorities.
  Preserve application-facing forwarding APIs until their consumers migrate deliberately.
- Home, Settings, tray actions, and reusable dialogs render the same connection, routing, and settings controllers.
  Platform/capability availability affects presentation but does not authorize an unsupported persisted value or a
  duplicate host side effect.
- The current page composition shares one subscription workflow between server and subscription presentation, records
  traffic into one history, and derives metrics/endpoint presentation from owned services. These exact locations may
  evolve, but a refactor retains one durable owner, one scheduler/request path, and one signal path.
- Home remains the initial page and navigation expansion/selection is session-local unless a product decision adds a
  persisted migration. Plugin ordering and bottom settings placement remain declarative navigation concerns.

## Visibility, lifetime, and geometry

- Long-lived pages construct persistent controls, models, timers, services, and connections once. Page visibility may
  coalesce log/graph painting or deliberately gate a lazy endpoint lookup, but it never owns log collection/draining,
  traffic sampling, subscription schedules, or an already-started request.
- One-shot editors/prompts use managed transient dialogs and weak compiled-safe continuations. Reusable windows such as
  the text editor and parent-owned settings dialogs retain one explicit owner, reset on reopen, and use normal close
  semantics; do not convert every top-level surface to delete-on-close or global retention.
- Use normal layouts and `AppQ*` controls. Restore top-level geometry only after persistent composition and through the
  canonical first-show path; never-shown Qt fallback geometry must not overwrite a prior user decision.

## Verification and evolution

- Verify initial/plugin navigation, shared Home/Settings/tray state, service ownership, lazy rendering versus continuous
  collection, async continuation cleanup, unsaved-close behavior, translation/theme changes, geometry migration, and
  repeated open/show/hide/destroy stability with real Qt input where semantics depend on it. Keep this guide as current
  architectural memory: change it with intentional page ownership, not after forcing new code through stale structure.

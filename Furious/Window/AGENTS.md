# Window and page guidance

- `MainWindow` owns built-in pages, navigation, and the persistent Qt tree. Plugin pages enter through
  `PluginNavigationManager`; pages adapt owning controllers/services/repositories rather than becoming competing state
  authorities. Preserve public forwarding attributes/methods until their consumers migrate.
- The current composition has one shared subscription workflow owned by the server table and reused by
  `SubscriptionPage`; Home owns update/connectivity/traffic services; Metrics owns endpoint inspection and derived
  rendering. Those locations may evolve, but a refactor must retain one durable owner, one scheduler, and one signal path.
- Home is the initial page. Page selection and navigation expansion are session-local and initially collapsed; do not
  persist them without an explicit product decision and migration.
- Long-lived pages create controls, models, timers, services, and signal connections once. Visibility may pause or defer
  rendering, but never application-level collection, log draining, subscription scheduling, or request ownership.
- One-shot editors/prompts use managed transient dialogs. `TextEditorWindow` is intentionally reusable and needs one
  durable owner; normal close/`closeEvent` remains the authority for unsaved confirmation, hiding, and final owner cleanup.
- Use normal layouts and `AppQ*` controls. File/network/core work leaves or cooperatively yields the GUI thread, and
  results return through owned signals without exposing secret documents in diagnostics.
- Top-level windows use `AppQMainWindow` first-show preparation and declarative default sizes. Restore saved geometry only
  after persistent children/layout exist; a valid saved geometry wins, otherwise use the canonical default/centering path.
- Verify navigation defaults/plugin placement, lazy rendering versus continuous collection, shared-service ownership,
  async continuations, unsaved-close behavior, geometry migration/restore, and repeated open/show/hide/destroy stability.

# Window and page guidance

- `MainWindow` owns built-in pages/navigation and their persistent Qt tree. Plugin pages are registered through
  `PluginNavigationManager`; pages adapt owning controllers/services/repositories rather than becoming state authorities.
- Home is the initial page. Page selection and navigation expansion are session-local, with navigation initially
  collapsed; do not persist either state.
- Long-lived pages create controls, timers, services, and connections once. Visibility controls lazy presentation, not
  application-level collection or scheduler lifecycles.
- One-shot editors/prompts use managed transient dialogs. `TextEditorWindow` is reusable and needs a deliberate durable
  owner. Close buttons call the normal `close()`/`closeEvent` path so confirmation and cleanup remain canonical.
- Use normal layouts and `AppQ*` controls. Blocking file/network/core work leaves the GUI thread, and worker results
  return through owned signals without exposing secrets.
- Top-level windows use `AppQMainWindow` first-show preparation and `DEFAULT_WINDOW_SIZE`. Restore saved geometry only
  after the persistent child layout exists; a successful `restoreGeometry()` is authoritative, otherwise use the
  canonical default/centering path.
- Verify navigation defaults, page lazy behavior, async continuations, unsaved-close flow, geometry restore, and
  repeated open/show/hide/destroy stability.

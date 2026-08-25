# Window and page guidance

- `MainWindow` owns long-lived built-in pages, navigation, page-level managers, and compatibility aliases. Pages remain
  stable for the window lifetime; plugin pages are owned by navigation plus `PluginNavigationManager`.
- Main-window page selection and navigation expansion are session-local. Register Home first as the canonical initial
  page and keep new navigation views collapsed; never persist or restore either state from a previous process.
- Pages and dialogs adapt controllers/services/repositories to user interaction. Do not create a competing state
  authority; prefer controller/service APIs over new cross-page reach-through.
- Long-lived pages create controls, timers, and signal connections once. Show/hide activates lazy rendering or refresh
  intent without multiplying objects or background work.
- One-shot editors/prompts inherit `AppQTransientDialog`/`AppQMessageBox`, connect `finished` before `open()`, and are
  not retained afterward. Reusable `TextEditorWindow` keeps an explicit owner, survives normal close/show, and is
  destroyed only by that owner.
- Close buttons route through the normal `close()`/`closeEvent` path so save/discard/cancel and cleanup remain
  canonical. Base event handlers are called unless intentionally documented.
- Keep file/network/core work bounded and off the GUI thread when it can block. Present structured failures without
  swallowing them or exposing secrets.
- Use Fluent `AppQ*` controls, normal layouts, translation-aware construction, and theme callbacks. Preserve shortcuts,
  default/escape actions, focus, resizing, navigation overlay behavior, and light/dark presentation.
- `AppQMainWindow` owns platform-neutral first-show preparation, centering, and shown-wrapper retention. Subclasses
  declare stable defaults through `DEFAULT_WINDOW_SIZE`; persistent windows override `prepareInitialGeometry()` only
  for product-owned restoration/migration and call `restoreInitialGeometry()` so a valid saved position suppresses
  centering. Never call overridable geometry hooks during construction or manipulate private first-show flags.
- Restore composed top-level window geometry only after its persistent child layout exists. Treat Qt's explicit
  `restoreGeometry()` result as authoritative; missing or invalid data uses the canonical application default and must
  not be inferred from magic window dimensions. Repeated show/hide cycles preserve the live window geometry.

## Code review rules

- Flag local top-level windows shown without a durable owner, transient dialogs cached by pages/controllers, repeated
  show-time connections, direct worker-thread UI mutation, and manual translation already handled by controls.
- Test navigation/page restoration, async dialog continuations, unsaved-close flow, hidden-page behavior, and repeated
  lifecycle stability.

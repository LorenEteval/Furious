# Application composition guidance

- `DesktopApplication` is the composition root. It durably owns process-lifetime controllers, logging, the main window,
  tray, thread pool, singleton IPC endpoint, cleanup stack, and plugin-registry lifecycle. `MainWindow` owns the built-in
  page/widget tree and page-level managers through normal Qt parentage; do not duplicate those owners in the application.
- Keep bootstrap order explicit: environment/plugins and storage before consumers, controllers/services before UI, and
  restoration only after all dependencies exist. Accessors must tolerate partial startup and cleanup.
- Each successful startup stage registers its exact cleanup immediately. Partial startup and final shutdown use the
  same reverse-order, failure-isolating cleanup stack, and cleanup is idempotent without relying on destructor timing.
- Keep graceful shutdown distinct from the final base-Qt event-loop exit. Delayed forced-exit callbacks must never
  recursively re-enter application cleanup.
- The tray owns its long-lived actions/menus and reflects controller state. Dynamic submenu rebuilds must not retain
  stale actions or menus.
- Application code may import higher layers to compose them; lower layers must not import `DesktopApplication` to obtain
  dependencies when injection or a narrow global accessor suffices.
- Keep blocking startup checks bounded and event-loop safe. A startup failure must leave enough runtime available to
  report the error and still clean up.

## Verification

- Test partial initialization, repeated cleanup, singleton IPC commands, tray menu rebuilding, startup restoration, and
  failure before the main window exists.
- Do not start the production singleton/host mutation in ordinary tests; compose fakes through the established
  boundaries.

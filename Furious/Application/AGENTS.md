# Application composition guidance

## Ownership and lifecycle

- `DesktopApplication` is the composition root. It owns process-lifetime controllers, plugin-registry lifecycle,
  storage, singleton IPC, logging, platform integration, the main window/tray, and the cleanup stack. `MainWindow` owns
  the persistent page tree through Qt parentage.
- Keep startup order explicit: settings/storage and plugins before consumers; controllers/services before UI;
  restoration after dependencies exist. Register exact cleanup immediately after each successful acquisition.
- Partial startup and normal exit use the same reverse-order, failure-isolating, idempotent cleanup path. Keep graceful
  resource cleanup separate from final Qt event-loop exit.
- Single-instance election is an atomic host operation: serialize stale-endpoint recovery and do not delete an endpoint
  that another launch may have claimed.
- The tray owns its long-lived actions/menus. Dynamic rebuilds release obsolete objects, and absence of a system tray is
  a supported desktop condition rather than an OS-support verdict.

## Verification

- Test partial initialization, singleton commands/races, tray rebuilding, restoration, and repeated cleanup with host
  integration mocked.

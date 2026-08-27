# Application composition guidance

## Composition and lifecycle

- `Furious.__main__` and `AppMainProcess` own the outer process/crash boundary; `DesktopApplication` is the inner Qt
  composition root. It owns singleton IPC, the plugin-registry lifecycle, repository owners, controllers, logging,
  theme/system integration, the main window/tray, the thread pool, and the cleanup stack.
- Keep startup dependencies explicit: win singleton election; configure plugins/environment; restore repository owners;
  construct controllers; configure logging/theme/system integration; build UI; then restore the requested connection.
  Register cleanup immediately after each acquisition that succeeded.
- Partial startup, normal exit, and event-loop failure converge on the same reverse-order, failure-isolating, idempotent
  cleanup stack. `exit()` requests termination; `aboutToQuit`/`finally` perform cleanup. Keep graceful cleanup separate
  from the final Qt exit-code decision. Window, tray, session, and action handlers request `exit()`; they do not run the
  cleanup stack themselves.
- `ConnectionController.shutdown()` preserves the reconnect-on-next-start preference while releasing the live runtime.
  Repository cleanup persists live collections only after successful restoration or explicit replacement.

## Desktop integration and UI ownership

- Single-instance election is an atomic host operation. Serialize candidates, re-probe after waiting, recover only a
  confirmed stale endpoint, and fail closed when ownership remains uncertain—especially during `RunAs` handoff.
- Native Windows session callbacks are not Qt-thread callbacks; queue shutdown into the GUI thread. System proxy daemon,
  dock visibility, tray availability, and Flatpak/AppImage behavior are platform capabilities, not assumptions inferred
  from the OS name alone.
- `MainWindow` owns the persistent page tree through Qt parentage. The application owns top-level window/tray wrappers;
  the tray owns its long-lived actions and menus. Dynamic rebuilds dispose obsolete objects, and an unavailable tray
  falls back to showing the main window and explicitly confirms a main-window exit. Qt automatic last-window quitting
  remains disabled so every accepted shutdown uses the normal application exit path.

## Verification

- Test success and failure at every acquisition boundary, reverse cleanup, repeated cleanup/exit, singleton races and
  commands, queued session shutdown, tray-present/absent behavior, startup restoration, and worker-pool bounds with all
  host integration mocked. Process-wrapper behavior belongs to `tests/test_application_process.py`.

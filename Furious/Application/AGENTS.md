# Application composition guidance

- `Furious.__main__` and `AppMainProcess` own the outer process/crash boundary; `DesktopApplication` owns the inner Qt
  composition. Keep those responsibilities separate and preserve semantic exit codes and original failure context.
- Startup acquires singleton ownership before composing process-lifetime repositories, plugins, controllers, logging,
  host integration, UI, and optional restored connection. Register cleanup as each acquisition succeeds.
- Partial startup, normal exit, signals, and event-loop failure converge on one reverse-order, failure-isolating,
  idempotent cleanup path. `exit()` requests Qt termination; action/window/session handlers do not run cleanup directly.
- Singleton election is atomic: serialize candidates, re-probe after waiting, recover only a confirmed stale endpoint,
  and fail closed when ownership is uncertain, including privilege handoff.
- Native session callbacks cross to the GUI thread before touching Qt-owned state. Tray, dock, System Proxy daemon,
  Flatpak/AppImage, and no-tray behavior are explicit platform capabilities.
- The application owns the top-level window/tray wrappers; `MainWindow` owns the persistent page tree. Do not let dynamic
  menus, sockets, theme snapshots, workers, or partial startup owners outlive their registered cleanup stage.
- Verify each acquisition failure, reverse/repeated cleanup, singleton races/commands, queued session shutdown,
  tray-present/absent close policy, restored connection, and exact child/thread-pool ownership with host effects mocked.

# Application composition guidance

Inherit `Furious/AGENTS.md` and its root ancestor. This scope owns process-lifetime Qt composition and the
boundary between the outer child-process supervisor and the inner application event loop.

- `Furious.__main__` and `AppMainProcess` own the outer process/crash boundary; `DesktopApplication` owns the inner Qt
  composition. Keep those responsibilities separate and preserve semantic exit codes and original failure context.
- Plugin, storage, and UI initialization follows singleton election; the Qt application and its initial resource
  owners already exist during election. Plugins are available before repository restoration interprets persisted
  profiles. Register cleanup as each acquisition succeeds, including election-failure paths, and preserve these
  dependencies when changing stage order.
- Partial startup, normal exit, signals, and event-loop failure converge on one reverse-order cleanup path.
  `aboutToQuit` and the event-loop `finally` may both reach it; repeated entry must not repeat registered stages.
  One callback failure does not skip later stages, but the stack consumes that callback and does not retry it.
  Its successful `close()` return means this invocation ran the stack, not that every resource was released.
  Service-level retry/retention obligations must be satisfied before the owner disappears. `exit()` requests Qt
  termination; action/window/session handlers do not run cleanup directly.
- A stage that fails before its cleanup callback is registered must release its own partial acquisitions. The outer
  cleanup stack releases completed stages; it cannot discover half-built controllers, UI, logging handlers, or
  native listeners. Restore logging configuration as well as closing handlers. Run service shutdown while its
  owners remain valid; scheduling `deleteLater()` is not evidence that workers or native resources have finished.
  Review cooperative pool drains separately from the cleanup stack's ordering guarantees. The application pool's
  timed wait logs unfinished work, whereas subscription preparation waits synchronously after its diagnostic timeout.
  Neither policy can be inferred from reverse cleanup order or from the name of a shutdown method.
- Singleton election serializes cooperating candidates, re-probes after waiting, recovers only a confirmed stale
  endpoint, and fails closed when ownership is uncertain, including privilege handoff. A successful Windows
  local-server listen alone does not establish exclusivity; command delivery and endpoint ownership are separate
  observations.
- Native session callbacks cross to the GUI thread before touching Qt-owned state. Tray, dock, System Proxy daemon,
  Flatpak/AppImage, and no-tray behavior are explicit platform capabilities.
- The application owns the top-level window/tray wrappers; `MainWindow` owns the persistent page tree. Cleanup order
  follows dependencies: consumers stop while the plugins, repositories, and Qt objects they need are still valid.
  A registered cleanup callback establishes responsibility, not proof that its menus, sockets, snapshots, or workers
  were released. Verify partial composition as well as a fully constructed application.
- Verify each acquisition failure, reverse/repeated cleanup, singleton races/commands, queued session shutdown,
  tray-present/absent close policy, restored connection, and exact child/thread-pool ownership with host effects
  mocked. Start with `tests/test_architecture_refactors.py`, `tests/test_application_process.py`, and
  `tests/test_main_window_geometry.py`; use their partial-startup cases to challenge this guide when composition
  changes.

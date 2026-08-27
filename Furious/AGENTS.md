# Furious package guidance

## Package architecture

- `Application` is the composition root. Elsewhere depend on the narrowest owning model, repository, service,
  controller, or plugin capability; do not create a second authority merely to avoid an existing boundary.
- Keep lower layers importable without application construction. `Interface` and `Models` cannot depend on UI,
  controllers, services, repositories, or concrete backends. Backend imports remain lazy enough that importing
  `Furious` does not initialize Qt resources, plugins, runtimes, or windows.
- Package `__init__.py` files are curated public/import surfaces, not convenience mirrors of every module. Before adding
  an export, check import direction, source installation, tests, and Nuitka discovery. Several settings are deliberately
  registered as modules import, so moving imports can change which `AppSettings` keys exist during partial startup or
  isolated tests.
- Process-lifetime accessors in `Frozenlib.Globals` expose compatibility paths to deliberate application owners only.
  They may be unavailable during tests, partial startup, or shutdown; new code should prefer explicit dependencies and
  callers using globals must tolerate that boundary rather than installing fallback owners.
- The current UI tree deliberately shares a few owners: `MainWindow` owns persistent pages, the server table owns the
  subscription workflow used by both server and subscription views, and page-owned services live with their page.
  Refactors may move those owners, but must leave exactly one durable owner and one state path.
- Keep GUI-thread work short. Workers publish result data through the established Qt boundary and never mutate widgets
  or live repositories directly from a worker thread.

## Qt ownership and presentation

- Classify Qt objects as process/application-lifetime, reusable, or transient. Give each a durable Python owner,
  compatible QObject parent, and explicit reuse or destruction path; audit every signal, timer, filter, cache, action,
  model, delegate, reply, and callback that can extend that path.
- Use the canonical `Furious.Qt` `AppQ*` controls. One-shot dialogs use `AppQTransientDialog` or `AppQMessageBox`;
  reusable windows retain one explicit owner. For lifetime-sensitive changes, follow `Furious/Qt/AGENTS.md` and the
  `manage-qt-pyside6-lifetimes` skill.
- Reuse translation/theme-aware construction and layout behavior rather than parallel registries or call-site styling.
  Preserve focus, keyboard, shortcut, accessibility, resize, high-DPI, and light/dark behavior.
- UI presents failures at the interaction boundary; owning services/controllers expose structured, testable outcomes.
- Route a change by authority: domain shape and identity to `Models`; persistence and migration to `Repository`;
  temporary work and external resources to `Service`; shared transitions to `Controllers`; backend variation to plugin
  contracts/implementations; host mutation to `Frozenlib`; and presentation to `Qt`, `Widget`, `Window`, or `Actions`.
  If a change crosses these boundaries, keep one commit point and document which owner coordinates it.

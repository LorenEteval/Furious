# Furious package guidance

## Architecture

- `Application` is the broad composition root. Elsewhere, depend on the narrowest owning model, repository, service,
  controller, or plugin capability. Do not create a second authority merely to avoid an existing boundary.
- Process-lifetime accessors in `Frozenlib.Globals` must tolerate partial startup and shutdown. They may expose deliberate
  application authorities, never transient dialogs, replies, workers, editors, or runtimes.
- Compatibility code still reaches global accessors and live collections. Do not extend that coupling when a narrow
  API can be added without a competing cache or state path.
- Keep GUI-thread work short. Workers publish result data through the established Qt boundary and never mutate widgets
  directly.

## Qt ownership

- Classify Qt objects as application-lifetime, reusable, or transient. Give each one a durable Python owner, compatible
  QObject parent, and explicit reuse or destruction path.
- Use the canonical `AppQ*` controls. One-shot dialogs use `AppQTransientDialog` or `AppQMessageBox`; managed `open()` is
  safe for local variables, while `exec()` is reserved for genuinely synchronous flow. Reusable windows retain one
  explicit owner.
- Parent or explicitly dispose timers, models, delegates, replies, event filters, menus, and actions. Never cache a
  transient QObject or an instance method in a global/unbounded cache.
- For lifetime-sensitive changes, follow `Furious/Qt/AGENTS.md` and the `manage-qt-pyside6-lifetimes` skill, then run the
  relevant native and packaged lifecycle checks.

## Presentation

- Reuse translation/theme-aware construction instead of parallel manual retranslation or one-off styling. Preserve
  focus, keyboard, shortcut, accessibility, resize, high-DPI, and light/dark behavior.
- UI presents failures at the interaction boundary; owning services/controllers provide structured, testable results.

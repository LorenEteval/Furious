# Furious package guidance

## Layering and state

- `Models` and `Interface` define core-neutral data and contracts. `Repository` owns persisted domain collections,
  `AppSettings` owns preferences, `Service` owns workflows/resources, `Controllers` own shared runtime state,
  `Plugins`/`Backends` own protocol behavior, and `Application` composes them. `Qt`, `Widget`, and `Window` present that
  state.
- Existing UI code has compatibility paths that reach repositories or application globals. Do not extend that coupling
  when a controller/service API can be introduced cleanly; migrate incrementally rather than creating a second state
  authority.
- Long-lived objects may be exposed through `Frozenlib.Globals`, but accessors must tolerate partial startup and
  shutdown. Never place transient dialogs, replies, workers, or editor instances in application globals.
- Keep GUI-thread work short. Worker callbacks publish immutable/result data to the GUI thread; they do not mutate
  widgets directly.

## Qt/PySide6 lifetime invariants

Classify every dynamic Qt object before choosing ownership:

- **Application-lifetime:** main window, navigation pages, shared controllers/managers. Give them one durable
  application owner and idempotent cleanup.
- **Reusable:** intentionally hidden and shown again. Retain one explicit Python owner and release it deliberately at
  final shutdown.
- **Transient:** editors, prompts, progress windows, and one-shot dialogs. Use a suitable parent plus normal
  close/deferred deletion; do not retain them after completion.

Use `AppQTransientDialog` for one-shot dialogs. `AppQDialog.open()` and `AppQMessageBox.open()` retain asynchronous
dialogs until completion, so local variables are safe; connect `finished` before `open()`. Use `exec()` only where
synchronous control flow is required. Do not add `WA_DeleteOnClose` universally or use `gc.collect()` as a production
fix.

QObject parent ownership and Python references are separate concerns. Parent timers/models/delegates where appropriate,
stop/disconnect owned resources on teardown when auto-disconnection is insufficient, remove event filters when lifetimes
differ, and clear references after `destroyed`. Never cache a transient QObject instance or an instance method with
unbounded `lru_cache`.

## UI and translation

- Reuse `AppQ*` Fluent/theme/translation-aware primitives. Prefer layout composition over fixed geometry and preserve
  keyboard, focus, shortcut, accessibility, and theme behavior.
- Pass source text at construction when an `AppQ*` control already retranslates it; avoid parallel manual
  `retranslate()` logic.
- UI shows errors at the interaction boundary, while services/controllers provide structured, testable failures. Do not
  broadly catch and hide deleted-wrapper or worker failures.

## Verification

- For changed transient/reusable UI, test open/close/show cycles, weak-reference clearing or deliberate retention,
  signal/timer stability, and asynchronous completion.
- Use offscreen Qt and the isolated settings helpers documented in `tests/README.md`. Distinguish allocator high-water
  behavior from linear live-object/resource growth.

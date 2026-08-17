# Furious application guidance

These rules apply to all application code below `Furious/` and refine the repository-wide guidance.

## State and layering

- `ConnectionController`, `RoutingController`, and `SettingsController` are the application state authorities. UI consumers observe/delegate; they do not maintain parallel state machines.
- Services and controllers may depend on models, repositories, plugin capabilities, and runtime abstractions. They must not strongly own transient dialogs, editors, message boxes, or page-local widgets.
- Keep blocking I/O, subprocess waits, DNS/network work, and heavy aggregation off the GUI thread. Marshal presentation updates back through Qt signals/slots.
- Cleanup/shutdown methods must be safe on partial startup and repeated calls. Release callbacks, timers, threads, child processes, and native handles owned by the component.

## Qt/PySide6 lifetime

Every `QObject` has an intentional Python owner, Qt parent, lifetime category, and destruction path.

Use the repository `manage-qt-pyside6-lifetimes` skill for any change or audit involving Qt object creation, ownership, signals, timers, filters, caches, windows/dialogs, memory growth, premature collection, or stale wrappers. Read its detailed lifetime reference completely before acting.

- Long-lived pages/controllers are application owned and created once.
- Reusable windows retain one explicit strong owner and reset state when shown again.
- Transient dialogs/windows retain a strong owner only while visible, use the normal close/accept/reject path, and are released after destruction. Use `WA_DeleteOnClose` only for genuinely transient objects.
- A local variable followed by `.show()`/`.open()` is not sufficient ownership for an asynchronous top-level window. Conversely, parenting a closed transient dialog to an application-lifetime widget does not make its destruction correct.
- Parent timers, animations, actions, menus, models, delegates, and event filters according to their intended owner. Stop/remove them when Qt automatic teardown is not sufficient.
- Prefer QObject-bound slots. Review lambdas, closures, partials, callbacks, and long-lived senders for captures of transient UI.
- Never place transient `QObject` instances or bound instance methods in unbounded caches. Static caches may contain immutable metadata, strings, classes/factories, or application-lifetime icons.
- Weak registries must not have a parallel strong owner, callbacks that capture the target, or dead entries that accumulate. Check wrapper validity before invoking weakly registered QObjects.
- Custom `closeEvent`, `accept`, `reject`, and `done` implementations must preserve the corresponding Qt lifecycle unless intentionally documented.
- Do not update widgets from worker threads. Do not mask ownership bugs with routine `gc.collect()`, global window retention, or swallowed deleted-wrapper exceptions.

## UI and translation

- Reuse the application Fluent widgets, action rows, menus, design tokens, and translation-aware controls before creating one-off styling or manual retranslation code.
- Keep page/window presentation thin: existing `QAction` or controller/service logic should remain the behavior source when controls are rearranged.
- When replacing a dialog/menu/window implementation, preserve shortcuts, default/escape results, enabled/checkable state, translations, and explicit transient/reusable lifetime semantics.

## Required verification

- For transient UI changes, exercise repeated create/open/close cycles and verify `destroyed`, weak-reference clearing, and stable live-object counts.
- For reusable windows, verify normal close/show reuse and explicit owner destruction without duplicated actions or signals.
- Run `tests.test_qt_lifetime` for ownership changes and the relevant UI behavior tests; use the explicit stress tier only when the change warrants it.

## Code review rules

- Flag controllers/services/registries retaining transient widgets or widget-bound callbacks.
- Flag asynchronous top-level windows without a durable Python owner.
- Flag parentless active timers, stale event filters, instance-method caches on transient UI, or close handlers that only hide a transient object.
- Flag direct widget mutation from non-GUI threads.

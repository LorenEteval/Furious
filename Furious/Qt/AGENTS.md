# Qt foundation guidance

Use the `manage-qt-pyside6-lifetimes` skill for QObject ownership, transient/reusable UI, signal retention, or packaged
PySide6 lifetime work.

## Canonical presentation

- Reuse `Furious.Qt` `AppQ*` controls, `AppStyleSheet`, translation/theme mixins, and shared dialog/window infrastructure.
  Do not create parallel style, theme-transition, translation, or lifetime registries.
- Controls that retranslate retain source text; semantic/user-defined values stay untranslated. Preserve keyboard focus,
  shortcut scope, accessibility, translated-text growth, responsive layout, high-DPI behavior, and both themes.
- Application-owned theme transitions commit destination state immediately; snapshots are non-interactive presentation
  objects that are interrupted/disposed on replacement, geometry change, window destruction, or application cleanup.

## Ownership and destruction

- Classify each Qt object as application-lifetime, reusable, or transient. Record its Python owner, QObject parent,
  close/hide/destroy path, and every timer, model, delegate, action, menu, animation, effect, event filter, reply, worker,
  callback, cache, and signal edge that may extend the lifetime.
- Reusable windows retain one explicit owner and reset on reopen. One-shot dialogs use `AppQTransientDialog` or
  `AppQMessageBox`; async presentation retains them through native destruction, not merely `finished`.
- `AppQDialog`/`AppQMainWindow` registries bridge asynchronous presentation/visibility; they are not substitute
  application owners. Registry cleanup captures opaque tokens, never the object being released.
- A Qt parent alone does not prove the Python wrapper or logical feature lifetime. Conversely, `.show()` does not retain
  an unparented top-level wrapper. Do not solve ambiguity by global retention, indiscriminate delete-on-close, routine
  `gc.collect()`, or broad deleted-wrapper suppression.

## Signals, threads, and async Qt work

- Only the GUI thread mutates widgets/live GUI models. Slots do not sleep or perform unbounded file, host, process, or
  network work; split work into bounded event-loop units or an owned worker and reject stale results on return.
- Native and Nuitka PySide6 can retain Python callbacks differently. A transient/repeated receiver must not be connected
  through a compiled bound method or a closure/partial that strongly captures it. Use `connectWeakly()` with a static
  method name and `sender=` when the sender is independent/longer-lived; use `forwardSender=True` instead of relying on
  `QObject.sender()` and `singleShotWeakly()` for deferred named-method delivery.
- Direct bound-method connections are acceptable only for deliberately long-lived receivers when retention is
  intentional. `AppQAction.callback` is strong by design, so the action owner cannot outlive the captured receiver.
- Every `QNetworkReply` has one manager/context owner, one freshness rule, and one terminal deletion path. Do not attach
  ad-hoc attributes to third-party Qt objects or multiply timers/connections across show/hide cycles.

## Geometry and verification

- Top-level windows use canonical first-show preparation. Save geometry/state only after a native presentation; a
  never-shown Qt fallback must not overwrite persisted user geometry. Do not call overridable geometry hooks from
  constructors or manipulate private first-show state.
- When behavior depends on focus, selection, proxy mapping, modifiers, shortcuts, queued delivery, animation, geometry,
  or destruction, construct real widgets and use `QTest` plus the real event loop. Test semantic state and lifecycle,
  not private coordinates or pixel-perfect screenshots.
- For lifetime-sensitive changes, repeat open/close/accept/reject paths and assert destroyed signals, weak wrappers,
  registries, timers, callbacks, replies, threads, handles, and child counts return to baseline. Run a representative
  Nuitka probe when compiled callback retention or packaged-only behavior is part of the defect.

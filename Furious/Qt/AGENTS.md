# Qt foundation guidance

Use the `manage-qt-pyside6-lifetimes` skill for QObject ownership, transient/reusable UI, signal retention, or packaged
PySide6 lifetime work.

Inherit the root and package guides. This scope owns reusable Qt presentation, translation/theme behavior, and lifetime
primitives; pages and services consume them without creating parallel registries.

## Canonical presentation

- Reuse `Furious.Qt` `AppQ*` controls, `AppStyleSheet`, translation/theme mixins, and shared dialog/window infrastructure.
  Do not create parallel style, theme-transition, translation, or lifetime registries. Shared control styling belongs
  in the application stylesheets; component-specific overrides are valid parts of stylesheet composition. Check
  selector specificity for disabled, hover, and selected states: a general disabled-label rule may lose to an
  object-name rule even when the widget's enabled state is correct.
- Controls that retranslate retain source text; semantic/user-defined values stay untranslated. Preserve keyboard focus,
  shortcut scope, accessibility, translated-text growth, responsive layout, high-DPI behavior, and both themes.
- Application-owned theme transitions commit destination state immediately; snapshots are non-interactive presentation
  objects that are interrupted/disposed on replacement, geometry change, window destruction, or application cleanup.

## Ownership and destruction

- Classify each Qt object as application-lifetime, reusable, or transient. Record its Python owner, QObject parent,
  close/hide/destroy path, and every timer, model, delegate, action, menu, animation, effect, event filter, reply, worker,
  callback, cache, and signal edge that may extend the lifetime.
- Reusable windows retain one explicit owner and reset on reopen. One-shot dialogs use `AppQTransientDialog` or
  `AppQMessageBox`; `open()` registers their strong async owner through native destruction and releases the token on
  the next event-loop turn. Plain dialog `show()` does not enter that registry and needs another durable owner.
  `finished` ends interaction, not native lifetime; operation context may be released then only if later callbacks
  do not need it.
- `AppQDialog`/`AppQMainWindow` registries bridge asynchronous presentation/visibility; they are not substitute
  application owners. Cleanup captures a unique lifetime token, never the object being released or a reusable
  numeric object ID. A delayed destruction callback must not evict a newer wrapper from the registry. A queued
  finish must also match the presentation generation so reopening the same reusable dialog cannot lose its owner.
- A Qt parent alone does not prove the Python wrapper or logical feature lifetime. Bare Qt `.show()` does not retain
  an unparented wrapper; `AppQMainWindow.show()` adds its own visible-window retention until accepted close. Do not
  solve ambiguity by global retention, indiscriminate delete-on-close, routine `gc.collect()`, or broad
  deleted-wrapper suppression.

## Signals, threads, and async Qt work

- Only the GUI thread mutates widgets/live GUI models. Slots do not sleep or perform unbounded file, host, process, or
  network work; split work into bounded event-loop units or an owned worker and reject stale results on return.
- Native and Nuitka PySide6 can retain Python callbacks differently. A transient/repeated receiver must not be connected
  through a compiled bound method or a closure/partial that strongly captures it. Use `connectWeakly()` with a static
  method name and `sender=` when the sender is independent/longer-lived; use `forwardSender=True` instead of relying on
  `QObject.sender()` and `singleShotWeakly()` for deferred named-method delivery.
- Direct connections are appropriate for deliberately shared persistent lifetimes; syntax alone does not prove a
  leak. Recheck the selected Nuitka/PySide6 callback protection when the toolchain changes. Static weak method names
  are runtime contracts, so renames must update registrations and tests. Weak dispatch itself does not marshal
  arbitrary worker calls to the GUI thread; choose an explicit queued owner-thread delivery boundary.
- `AppQAction.callback` is strong by design, so the action owner cannot outlive the captured receiver.
- Every `QNetworkReply` has one manager/context owner, one freshness rule, and one terminal deletion path. Do not attach
  ad-hoc attributes to third-party Qt objects or multiply timers/connections across show/hide cycles.
- Queued delivery never transfers ownership implicitly. The sender may finish before delivery, so callbacks resolve a
  still-valid receiver and current generation in the receiver's Qt thread before touching widgets, models, or wrappers.

## Geometry and verification

- Top-level windows use canonical first-show preparation. Save geometry/state only after a native presentation; a
  never-shown Qt fallback must not overwrite persisted user geometry. Do not call overridable geometry hooks from
  constructors or manipulate private first-show state.
- A stylesheet border radius paints a rounded frame but does not clip child viewports or table headers. Padding
  can protect the corners while introducing a visible inset; assess both effects before changing shared view styles.
  Popup native-window transparency is a separate boundary from in-window child painting.
- When behavior depends on focus, selection, proxy mapping, modifiers, shortcuts, queued delivery, animation, geometry,
  or destruction, use real widgets, `QTest`, and the event loop. Prefer semantic assertions; for rendering defects,
  test the affected border/background/alpha behavior under explicit themes and scale factors instead of relying on
  selector counts or whole-window pixel equality.
- For lifetime-sensitive changes, repeat open/close/accept/reject paths and assert destroyed signals, weak wrappers,
  registries, timers, callbacks, replies, threads, handles, and child counts return to baseline. Run a
  representative Nuitka probe when compiled callback retention or packaged-only behavior is part of the defect.
  Start with `tests/test_qt_lifetime.py`, `tests/test_dialog_geometry.py`, and `tests/test_main_window_geometry.py`;
  use the `tests/fixtures/editor_lifetime_probe.py` fixture for compiled investigation. Treat unrun packaged probes
  as unverified, and update these rules when measured ownership or the toolchain changes.

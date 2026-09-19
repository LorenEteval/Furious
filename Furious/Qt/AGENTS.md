# Qt foundation guidance

Use the `manage-qt-pyside6-lifetimes` skill for QObject ownership, transient/reusable UI, signal retention, or packaged
PySide6 lifetime work.

Inherit `Furious/AGENTS.md` and its root ancestor. This scope owns reusable Qt presentation, translation/theme
behavior, and lifetime primitives; pages and services consume them without creating parallel registries.

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
- Native and Nuitka PySide6 can retain Python callbacks differently. Avoid protected compiled bound methods for
  transient/repeated receivers. Use `connectWeakly()` with a static method name and `sender=` for a sender outside
  the receiver's QObject subtree; use `forwardSender=True` instead of relying on `QObject.sender()` and
  `singleShotWeakly()` for deferred named-method delivery. A closure/partial that captures the receiver does not
  substitute for weak dispatch. Bounded dialog-completion closures may intentionally capture context; verify their
  native destruction/disconnection boundary and both owner-first and sender-first teardown.
- Detaching a child ends the shared QObject-tree lifetime assumption. Disconnect the registrations owned by that
  feature before reparenting, preserve unrelated listeners, and remove default/escape/selection references when the
  child dies. Signal delivery is also a reentrancy boundary: a listener may delete the sender or its owner before
  the emitting method resumes. Recheck validity before later native calls. `AppQMessageBox` button reuse and
  native-destruction regressions exercise both boundaries.
- Direct connections are appropriate for deliberately shared persistent lifetimes; syntax alone does not prove a
  leak. Recheck the selected Nuitka/PySide6 callback protection when the toolchain changes. Static weak method names
  are runtime contracts, so renames must update registrations and tests. Weak dispatch itself does not marshal
  arbitrary worker calls to the GUI thread; choose an explicit queued owner-thread delivery boundary. A surviving
  Python wrapper can already be natively invalid, so callback freshness and `shiboken6.isValid()` address different
  failure modes. Weak dispatch neither cancels execution nor checks workflow generations; those remain with the
  workflow owner. None of these checks replaces the strong owner required while asynchronous UI remains active. For independent
  sender/receiver trees, test both destruction orders: receiver cleanup must disconnect its edge, and sender cleanup
  must retire receiver-side tracking without keeping a signal wrapper or sender alive.
- `AppQAction.callback` is strong by design, so its owner must not outlive the captured receiver; construction alone
  does not enforce that requirement. An action also owns a submenu supplied without a QWidget parent and schedules
  its native deletion when the action dies;
  `QAction.setMenu()` alone does not establish parent ownership. Explicitly parented menus retain their chosen owner.
- Every `QNetworkReply` has one manager/context owner, one freshness rule, and one terminal deletion path. Request
  context must also be released when native destruction skips `finished`, including manager-first teardown with
  retained Python wrappers. Use the shared network-manager tracking boundary; cleanup must not capture a reply
  strongly. User hooks and signal delivery can synchronously destroy the reply or manager; recheck native validity
  before subsequent hooks or Qt cleanup. `test_service_runtime.py` covers completion and abort reentrancy.
  Do not attach ad-hoc attributes to third-party Qt objects or multiply timers/connections across show/hide cycles.
- Queued delivery never transfers ownership implicitly. The sender may finish before delivery, so callbacks resolve a
  still-valid receiver and current generation in the receiver's Qt thread before touching widgets, models, or wrappers.
  A zero-delay timer yields work but does not establish ordering against an unrelated Qt event. Express required
  ordering through an owned continuation or semantic completion signal and test that boundary rather than one
  platform's incidental event order.

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
  Retained Python wrappers may already be invalid: count native destruction independently, including owner-first
  teardown. A pass under diagnostic compiler flags does not establish behavior under ordinary release flags.
  Start with `tests/test_qt_lifetime.py`, `tests/test_dialog_geometry.py`, and `tests/test_main_window_geometry.py`;
  use the `tests/fixtures/editor_lifetime_probe.py` fixture for compiled investigation. Treat unrun packaged probes
  as unverified, and update these rules when measured ownership or the toolchain changes.

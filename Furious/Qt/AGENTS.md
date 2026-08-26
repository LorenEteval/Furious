# Qt foundation guidance

Use the `manage-qt-pyside6-lifetimes` skill for Qt ownership or lifecycle work.

## Canonical UI surface

- Extend/reuse `Furious.Qt` `AppQ*` controls for Fluent styling, themes, translation, dialogs, menus/actions, inputs,
  tables/lists, and top-level windows. Do not create call-site styling or parallel lifetime registries.
- Pass source text at construction when a control retains it for retranslation. Preserve focus, keyboard, shortcuts,
  accessibility, translated-text growth, high-DPI, responsive layout, and both themes.
- `AppQMessageBox.windowTitle` is native metadata. Visible hierarchy is `heading`, `text`, then `informativeText`.
  `AppQMessageBox.open()` delegates asynchronous ownership to `AppQDialog.open()`; do not add a parallel message-box
  registry or release a transient box before native destruction completes.
- `AppStyleSheet` is the public style authority. `StyleSheets` contains internal QSS fragments that consume the semantic
  palette; application code does not import fragments directly.

## Lifetime and threading

- Application-lifetime Qt objects have one durable owner; reusable windows retain one deliberate owner; transient
  dialogs use `AppQTransientDialog`/`AppQMessageBox` and remain retained through deferred native destruction.
- Direct compiled bound-method signal connections can retain transient receivers in Nuitka builds. Use
  `connectWeakly(signal, receiver, 'methodName', sender=...)` when the sender is independent/longer-lived; never replace
  it with a closure or partial capturing the receiver.
- `AppQAction.callback` is a strong reference. Its owner cannot outlive the callback receiver. Parent or explicitly
  dispose timers, models, delegates, replies, event filters, menus, animations, and effects.
- Only the GUI thread mutates widgets. Slots do not sleep or perform unbounded host/network/process work. Coalescing
  timers are created once and do not multiply across show/hide cycles.
- Each `QNetworkReply` has one manager/context owner, one terminal cleanup, and a freshness rule when superseded.
  Schedule deletion on every terminal path; do not attach ad-hoc application attributes to third-party Qt objects.

## Presentation and verification

- Top-level subclasses use the canonical first-show geometry hooks and centering/retention behavior; do not call
  overridable geometry hooks from constructors or alter private first-show state.
- Persistent top-level subclasses save geometry/state only after `hasPreparedInitialGeometry()` confirms first-show
  preparation; never replace saved user geometry with a never-shown widget's native default.
- Use `exec()` only when synchronous control flow is required; otherwise connect completion before managed `open()`.
- Run focused behavior tests plus repeated native lifecycle cycles. For compiled-signal or transient-dialog changes,
  also run the Nuitka probe and verify destroyed signals, weak references, registries, callbacks, timers, replies, and
  native resources return to baseline.

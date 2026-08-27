# Qt foundation guidance

Use the `manage-qt-pyside6-lifetimes` skill for Qt ownership or lifecycle work.

## Canonical UI surface

- Extend/reuse `Furious.Qt` `AppQ*` controls for Fluent styling, semantic themes, translation, dialogs, menus/actions,
  inputs, views, and top-level windows. `AppStyleSheet` is the public style authority; application code does not import
  internal `StyleSheets` fragments or create parallel style/lifetime registries.
- Pass source text at construction when a control retains it for retranslation. Preserve focus, keyboard, shortcuts,
  accessibility, translated-text growth, high-DPI, responsive layout, and both themes.
- `AppQMessageBox.windowTitle` is native metadata; its visible hierarchy is heading, text, then informative text. Keep
  message-box presentation on the shared `AppQDialog` lifecycle instead of adding a second async owner.

## Ownership, destruction, and signals

- Classify every object as application-lifetime, reusable, or transient. Application owners construct long-lived objects
  once; reusable windows retain one explicit strong owner; transient dialogs use `AppQTransientDialog`/`AppQMessageBox`
  and are deleted after the interaction.
- `AppQDialog.open()` retains a reusable dialog through `finished`; delete-on-close transients remain retained through
  deferred native destruction and release after `destroyed`. Registry cleanup captures only the opaque lifetime token,
  never the dialog. `exec()` is for genuinely synchronous control flow.
- `AppQMainWindow._openWindows` is a visibility-lifetime bridge for shown top-level windows, not a second application
  owner: accepted close or destruction must remove the entry. A reusable window still needs a deliberate owner that can
  show it again; a transient top-level must not remain in this registry after closing.
- Native PySide and Nuitka can retain callbacks differently. Never pass a transient/repeated receiver's bound method to
  `Signal.connect()` or `QTimer.singleShot()`, and do not hide that capture in a lambda/partial. Use
  `connectWeakly(signal, receiver, 'methodName', sender=...)` when the sender is independent/longer-lived; use
  `forwardSender=True` when the slot needs it, and use `singleShotWeakly()` for deferred named-method dispatch. Direct
  bound methods are reserved for deliberately process-lifetime receivers whose retention is intentional and documented.
- `AppQAction.callback` is deliberately strong; its owner cannot outlive the receiver it captures. Parent or explicitly
  dispose timers, models, delegates, replies, event filters, menus, actions, shortcuts, watchers, animations, and effects.
- Only the GUI thread mutates widgets. Slots do not sleep or perform unbounded host/network/process work. Create
  coalescing/render timers once and do not multiply them across show/hide cycles.
- Each `QNetworkReply` has one manager/context owner, one freshness rule, and one terminal deletion path. Shared slots use
  `sender()`/stored context rather than per-reply closures; do not attach ad-hoc attributes to third-party Qt objects.

## Geometry and verification

- Top-level subclasses use the canonical first-show preparation and centering/retention hooks. Do not call overridable
  geometry hooks from constructors or modify private first-show state.
- Persistent windows save geometry/state only after `hasPreparedInitialGeometry()` proves a native presentation occurred;
  never overwrite saved user geometry with Qt's never-shown fallback. A valid `restoreGeometry()` is authoritative.
- Run focused behavior tests plus repeated native lifetime cycles. For transient signal/dialog infrastructure or a
  packaged-only failure, run the Nuitka probe and verify destroyed counts, weak wrappers, dialog/context registries,
  callbacks, timers, replies, and native resources return to baseline without per-cycle garbage collection.

# Qt foundation guidance

Use the `manage-qt-pyside6-lifetimes` skill for any Qt ownership or lifecycle change.

## Public UI primitives

- `Furious.Qt` is the canonical Fluent/theme/translation-aware UI surface. Extend/reuse `AppQ*` controls instead of
  styling raw Qt controls at call sites.
- Construction-time source text should be retained by the control for retranslation. Do not duplicate manual
  `retranslate()` code where an `AppQ*` widget/action/menu already supports it.
- Preserve public exports and wildcard-import compatibility carefully; keep optional/heavy facilities lazily imported
  where practical.
- `AppStyleSheet` remains the sole public stylesheet authority. Internal `StyleSheets` modules are data-oriented QSS
  fragments that consume the centralized semantic palette; application consumers must not import fragments directly.

## Ownership and destruction

- `AppQDialog` provides an asynchronous open-dialog registry. `AppQMessageBox` has an additional registry cleanup layer;
  it is redundant but harmless. Keep both registries balanced if either implementation changes.
- `AppQTransientDialog` is delete-on-close. Connect completion before `open()` and never access it after destruction.
  Reusable dialogs/windows instead need a durable owner and must not be delete-on-close.
- `AppQAction.callback` is a deliberate strong reference; owner scope must be no longer than the callback receiver.
  Application-lifetime actions cannot capture transient bound methods.
- Parent child widgets/models/delegates/timers where their lifetimes match. Explicitly stop/disconnect timers, remove
  mismatched event filters, abort/delete network replies, and clear references when wrappers can outlive C++ objects.
- Do not cache QObject instances or instance-bound methods in global/unbounded caches. Weak callbacks must not close
  over their target.

## Threading and event loops

- Only the GUI thread mutates widgets. Workers return immutable/result data through queued signals or established
  managers.
- Never sleep or perform unbounded host/network/process work in a slot. Timers and debounce/coalescing must have one
  owner and must not multiply across show/hide cycles.
- `exec()` is reserved for genuinely synchronous control flow; prefer managed `open()` when continuation logic can live
  in `finished` callbacks.

## Network replies and presentation

- Give each reply one manager/context owner, reject stale generations, handle success/error/abort exactly once, and call
  `deleteLater()` on every terminal path. Do not attach ad-hoc application attributes to third-party Qt objects when a
  manager mapping suffices.
- Preserve keyboard, focus, shortcuts, accessibility, light/dark theme, layout responsiveness, and translated-text
  growth.

## Verification

- Run focused UI behavior and lifetime tests. Repeated open/close/show/refresh cycles must stabilize object, signal,
  timer, reply, handle, and callback counts.

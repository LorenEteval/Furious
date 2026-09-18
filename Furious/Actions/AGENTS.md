# Action guidance

Inherit the root and `Furious/AGENTS.md`; this scope adds rules for translating user gestures into owned commands and
presentation without becoming a workflow authority.

## Command boundary

- Actions adapt one user command to presentation. Resolve live controller/repository state when triggered, delegate the
  operation to its owner, and render the result; an action is not a second connection, routing, subscription, or
  persistence authority.
- Share a `QAction` across menus/buttons when command target, owner lifetime, and shortcut scope are the same.
  Distinct window/tray contexts may need separate actions that observe the same controller; do not force one global
  action across incompatible lifetimes. Keep checked/enabled state and translation consistent, and do not make menu
  shortcuts application-wide when focused editors or other controls own the same keys.
- Routing and connection actions render the shared controllers. Rebuilding a dynamic menu releases the old actions,
  action group, and callbacks before publishing the new snapshot; user-defined labels remain untranslated.
- Existing import actions still combine capture/file/clipboard presentation with incremental repository insertion. Treat
  that as a compatibility path, not a service template. Reuse plugin protocol parsing, construct a complete valid result
  before each mutation, and keep batched GUI work cancellable and bounded per event-loop turn.

## Lifetime, input, and verification

- `AppQAction.callback` is a deliberate strong reference. The action owner must not outlive a captured receiver, and a
  transient/repeated receiver uses the weak named-method facilities required by `Furious/Qt/AGENTS.md`.
- Clipboard text, files, QR images, share links, and plugin results are untrusted and may contain credentials. Bound
  diagnostic excerpts and never log or echo a complete secret-bearing payload merely to explain a parse failure.
- Screen capture and QR decoding currently run synchronously; batching the resulting imports does not make capture
  interruptible. If moved to workers, transfer data through an owned GUI-thread continuation without retaining
  transient windows. Each screen-capture action owns a separate native capture handle, including separate tray/page
  instances; type-deduplicated cleanup must not leave one open. QR export generation belongs to its result window,
  not a parallel action-owned exporter.
- Small profile imports use the direct bulk path; large imports yield between bounded batches. Preserve captured
  input and one operation context until completion/cancellation, reject deferred calls after teardown, and retain
  already committed batches when cancellation stops later work. A parser call itself is not preempted by a batch.
- Batch limits bound work between event-loop yields; the minimum progress interval throttles status refreshes at
  those boundaries. It is not an independent paint timer. Keep terminal feedback accurate and choose scale policies
  from measured responsiveness rather than freezing a batch count into the command contract.
- Resolve the live target when a command is triggered, then capture intended identities/input before yielding. On
  confirmation, resolve those captured targets again rather than adopting a later selection. Progress reports actual
  completed work; rejecting a progress dialog stops later batches and does not undo already inserted profiles.
- Verify command state and delegation, cancellation/error presentation, shortcut scope in the real focused widget,
  menu rebuild cleanup, and repeated dialog/capture/action lifetimes. Use
  `tests/test_qt_interactions.py`, `tests/test_ui_behavior.py`, and `tests/test_qt_lifetime.py` for focused
  command/retention evidence.

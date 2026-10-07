# Action guidance

Inherit the [nearest parent guide](../AGENTS.md).
Actions delegate to workflow owners. Capture command targets before yielding; resolve live navigation
separately from captured input or diagnostics.
Read `Furious/Actions/Import.py` with `tests/test_qt_interactions.py`; paths are relative to this source tree's root.

## Command boundary

- Actions adapt one user command to presentation. Resolve live controller/repository state when triggered, delegate the
  operation to its owner, and render the result; an action is not a second connection, routing, subscription, or
  persistence authority.
- Share a `QAction` across menus/buttons when command target, owner lifetime, and shortcut scope are the same.
  Distinct window/tray contexts may need separate actions that observe the same controller; do not force one global
  action across incompatible lifetimes. Keep checked/enabled state and translation consistent, and do not make menu
  shortcuts application-wide when focused editors or other controls own the same keys.
- Routing and connection actions render the shared controllers. Rebuilding a dynamic menu retires its old actions
  and action group; deferred deletion completes only when Qt processes it. Verify native destruction after repeated
  rebuilds rather than treating an emptied Python list as release. Refreshing options is observational, not a user
  selection or reconnect command; user-defined labels remain untranslated.
- Existing import actions still combine capture/file/clipboard presentation with incremental repository insertion. Treat
  that as a compatibility path, not a service template. Reuse plugin protocol parsing, construct a complete valid result
  before each mutation, and keep batched GUI work cancellable and bounded per event-loop turn.

## Lifetime, input, and verification

- `AppQAction.callback` is a deliberate strong reference. The action owner must not outlive a captured receiver, and a
  transient/repeated receiver uses the weak named-method facilities required by `Furious/Qt/AGENTS.md`.
- Clipboard text, files, QR images, share links, and plugin results may contain credentials. A character limit is
  not redaction: never log rejected payloads. Clipboard import-error dialogs retain their existing length-limited
  preview by explicit product choice; do not change that preview policy without a request. Inspect other error
  presentation independently from parser diagnostics.
  Connection-error diagnostics retain only the displayed failure text for explicit copying; copying leaves the dialog
  open. Open Logs resolves the current application window and rechecks native validity after dialog completion and
  navigation. It opens the existing log page without retrying a stale connection or acquiring another workflow owner.
  Recovery actions keep the displayed failure snapshot and resolve their live navigation target when triggered;
  a later connection or settings change must not retarget the captured text. Render diagnostic text plainly.
  `DialogBehaviorTest` in `tests/test_ui_behavior.py` and the compiled lifetime fixture verify these actions.
- Screen capture and QR decoding currently run synchronously; batching the resulting imports does not make capture
  interruptible. If moved to workers, transfer data through an owned GUI-thread continuation without retaining
  transient windows. Each screen-capture action owns a separate native capture handle, including separate tray/page
  instances; type-deduplicated cleanup must not leave one open. QR export generation belongs to its result window,
  not a parallel action-owned exporter.
- Native action destruction also releases its screen-capture handle through the same idempotent cleanup path as
  application shutdown. Destruction callbacks retain plain resource state, not the action. Failed close is diagnosed
  and retains the handle while that state has a surviving owner; native destruction does not provide a retry scheduler.
  A top-level progress widget borrowed by an action needs explicit native deletion when that action dies.
  Verify native teardown while intentionally retaining action wrappers/bound methods.
- Small profile imports use the direct bulk path; large imports yield between bounded batches. One operation owns
  captured input and its continuation through completion/cancellation; teardown rejects deferred calls. A parser call
  itself is not preempted by a batch. Keep preparation and insertion distinct so a failed batch cannot publish a
  partially validated result.
- Batch limits bound work between event-loop yields; the minimum progress interval throttles status refreshes at
  those boundaries. It is not an independent paint timer. Keep terminal feedback accurate and choose scale policies
  from measured responsiveness rather than freezing a batch count into the command contract.
- Capture intended identities/input before yielding. Selection commands retain target IDs and re-resolve live
  objects at confirmation; export commands may instead need immutable payload snapshots. Choose that policy at
  command start so later selection or edits cannot retarget deferred work. Progress reports actual completed work;
  rejecting a progress dialog stops later batches without undoing inserted profiles.
- Verify command state and delegation, cancellation/error presentation, shortcut scope in the real focused widget,
  menu rebuild cleanup, and repeated dialog/capture/action lifetimes. Use
  `tests/test_qt_interactions.py`, `tests/test_ui_behavior.py`, and `tests/test_qt_lifetime.py` for focused
  command/retention evidence.

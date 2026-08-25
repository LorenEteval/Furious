# Action guidance

## Scope and contracts

- Actions are thin presentation commands. Resolve current state when triggered, call its owning controller/service, and
  present the result; do not own connection, routing, import, or persistence state.
- Share one `QAction` command between menus/buttons so callback, enabled/check state, shortcut, and translation cannot
  diverge. `AppQAction.callback` is a strong reference, so its QObject owner must not outlive a captured receiver.
- Import through `profileFromAny` and plugin capabilities. Treat clipboard, file, URI, QR, and subscription content as
  untrusted and avoid logging secret-bearing payloads.
- Managed asynchronous dialogs connect completion before `open()`. Long or batched work must yield or use one owned
  worker/progress dialog; never sleep the GUI thread.

## Verification

- Verify command state and results plus repeated triggering: dialogs, dynamic menus, callbacks, and workers must return
  to baseline.

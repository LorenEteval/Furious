# Action guidance

## Role and boundaries

- Actions are presentation commands: resolve current state when triggered, invoke its owning controller/service, and
  present the outcome. They do not become authorities for connection, routing, subscription, or persistence state.
- Some existing import actions still perform parsing, repository insertion, screen capture, and a cooperative batch
  dialog directly. Treat that as a compatibility path, not a template: new reusable or fallible workflows belong in an
  injected service/controller and may be migrated there without preserving action-local orchestration. Its timer-driven
  dialog yields through weak named-method scheduling; preserve that packaged-lifetime boundary per `Furious/Qt/AGENTS.md`.
- Share one `QAction` command between menus/buttons when they represent the same operation so callback, enabled/check
  state, shortcut, and translation cannot diverge. `AppQAction.callback` is a strong reference; the action owner must not
  outlive a captured receiver, and dynamic menus must release obsolete actions and callbacks.
- Import through `profileFromAny` and plugin capabilities. Clipboard, file, URI, QR, and subscription content is
  untrusted and may contain secrets; bound diagnostics and never log the complete payload.

## Asynchronous UI and verification

- Connect dialog completion before managed `open()`. Long or batched work must yield between bounded units or use one
  owned worker/progress dialog; do not sleep or perform unbounded capture/file/network work on the GUI thread.
- Verify command state, result/error presentation, cancellation, and repeated triggering. Dialogs, dynamic menus,
  callbacks, native capture handles, and workers must return to their intended baseline.

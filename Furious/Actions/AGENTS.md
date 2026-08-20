# Actions guidance

- Actions are thin presentation adapters: resolve current controller/service state at trigger time, invoke the owning
  API, and present the result. Do not make an action a second owner of connection, routing, repository, or import state.
- Reuse shared `QAction` command logic for menus/buttons. Keep shortcuts, check state, enabled state, translation, and
  callback semantics synchronized from one source.
- `AppQAction.callback` is intentionally a strong reference. Scope actions to a suitable QObject owner; an
  application-lifetime action must not retain a transient bound method or closure.
- Import through `profileFromAny`/plugin capabilities. Treat clipboard, file, URI, QR, and subscription text as
  untrusted; report per-item failures without logging credentials or whole secret-bearing payloads.
- Long or batched work must yield safely or use an owned worker/progress dialog. Do not sleep the GUI thread.
- Asynchronous prompts/editors use managed `open()` lifetime and connect completion before opening. Rebuilt dynamic
  menus must release obsolete `QMenu`/`QAction` objects rather than accumulating them.

## Code review rules

- Flag duplicated controller logic, captured transient widgets, unsanitized sensitive logging, and action-local
  persistence changes.
- Verify repeated triggering does not multiply dialogs, callbacks, menus, or workers.

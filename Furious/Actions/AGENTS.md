# Action guidance

## Command boundary

- Actions adapt one user command to presentation. Resolve live controller/repository state when triggered, delegate the
  operation to its owner, and render the result; an action is not a second connection, routing, subscription, or
  persistence authority.
- Prefer one shared `QAction` for one semantic command across menus and buttons so checked/enabled state, shortcut,
  callback, and translation cannot diverge. A host widget may narrow shortcut context; do not make menu shortcuts
  application-wide when focused editors or other controls own the same keys.
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
- Verify command state and delegation, cancellation/error presentation, shortcut scope in the real focused widget, menu
  rebuild cleanup, and repeated dialog/capture/action lifetimes. When this command boundary changes intentionally, update
  this guide and remove superseded compatibility wording in the same change.

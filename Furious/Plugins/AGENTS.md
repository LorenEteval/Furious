# Plugin guidance

Inherit `Furious/AGENTS.md` and its root ancestor; consult Interface guidance for runtime/storage contracts.
This scope owns capability definitions, atomic registration, dispatch, and plugin lifecycle; backend policy
remains in each implementation.

## Contracts and registry

- `Plugins.API` defines independently composable capabilities for protocols/editors, subscription decoding, runtime
  factories, routing/TUN/probes, statistics, settings, actions, and navigation. Extend the owning capability instead of
  adding backend-name branches or a parallel registry.
- The registry normalizes and validates a plugin's complete contribution before changing indexes. Initialization
  runs with the contribution indexed; if it fails, shutdown is attempted and those indexes are removed. This is
  rollback of registry publication, not a transaction over arbitrary plugin side effects. Plugins must clean their
  own partial acquisitions even when initialization fails. Duplicate IDs/schemes and invalid versions/descriptors
  must leave existing providers intact.
- Host plugin types register before external entry-point discovery. Bundled registrations are explicit for source,
  wheel, and Nuitka inclusion. External entries currently follow metadata enumeration order; do not promise sorted
  discovery or rely on it for precedence. Registration is atomic per plugin, not across a multi-plugin entry point.
- Failure policy belongs to the dispatch operation. Automatic subscription detection tries decoders by priority; an
  explicitly selected decoder restricts candidates. URI dispatch selects the registered scheme owner rather than
  probing unrelated handlers after failure. Keep required-operation failures observable without secret payloads.

## Ownership and compatibility

- Registries own plugin/capability instances and descriptors; created editors and runtimes transfer to their
  callers. Capabilities may retain explicitly owned reusable services with shutdown obligations. Do not cache
  created transient UI in the registry or treat the registry as the connection/repository authority.
- Once a runtime factory returns a valid launch, the caller acquires that exact runtime even if start raises, so partial
  resources can be stopped/disposed. Return no runtime only when none was acquired.
- Plugin/model data is untrusted at the boundary even though installed code is trusted to execute. Validate types,
  ownership, required fields, and QObject validity before publishing results.
- API and model layers never import concrete plugins. Bundled backends/extensions obey the public lifecycle; their
  existing host-global integrations must not become prerequisites for external plugins.
- Evolve contracts additively when practical. Before a breaking change, inspect external discovery, compatibility
  exports, every bundled implementation, tests, and compiled inclusion; do not infer compatibility from built-ins alone.
- A capability contract is generic only when an external plugin can satisfy it without importing private application
  state. Backend-specific defaults, settings keys, document branches, and host assumptions stay behind the provider.
  Capability presence advertises an operation, not a configured target or successful execution; callers must handle
  absence, unavailable configuration, and operation failure separately (notably statistics, export, and probes).
- API-version-3 runtime factories return `PreparedRuntime` directly. The runtime is fully prepared before return,
  starts with zero arguments, raises typed startup failures, and exposes readiness separately. An alternate result
  shape requires an explicit contract/version migration, not an implicit adapter inferred from built-in factories.
  The registry's existing synchronous `startCoreRuntime()` wrapper separately returns runtime/success for
  compatibility; preserve ownership on start failure.
- `TUNPreparationError` is the explicit terminal native-TUN failure contract. Other provider exceptions currently
  log and return an unhandled result; required TUN rejection must use the typed error rather than assume all
  exceptions stop fallback. Optional capabilities may be absent; an External Core need not implement statistics or
  download probes.
- Frozen result envelopes are not recursively immutable: embedded configuration/metadata mappings still require copy
  isolation before mutation or worker handoff.
- Capability instances default to GUI-thread-only for background subscription preparation. A decoder or protocol
  handler opts into worker execution only after its parsing, validation, caches, globals, and Qt usage are audited as
  safe for concurrent copied inputs; keep unclassified third-party capability execution on the GUI thread.

## Verification

- Cover discovery/order, API version and duplicate rejection, each changed dispatch path, registration rollback,
  reverse idempotent shutdown, provider failure isolation, invalid factory results, repeated transient creations
  without registry retention, and packaged discovery/import. `tests/test_plugin_architecture.py` and
  `tests/test_public_api.py` anchor compatibility.

# Plugin guidance

## Contracts and registry

- `Plugins.API` defines independently composable capabilities for protocols/editors, subscription decoding, runtime
  factories, routing/TUN/probes, statistics, settings, actions, and navigation. Extend the owning capability instead of
  adding backend-name branches or a parallel registry.
- The registry normalizes and validates a plugin's complete contribution before committing indexes. Duplicate IDs or
  schemes, incompatible API versions, invalid descriptors, and initialization failure leave existing providers intact.
- Host plugin types register before external entry-point discovery. Discovery and bundled registrations remain
  deterministic, side-effect-light, and literal enough for source, wheel, and Nuitka inclusion.
- Optional provider failure is isolated when another candidate can continue; required-operation failure remains
  observable with plugin/capability identity and without secret configuration data.

## Ownership and compatibility

- Registries own process-lifetime plugin instances, capabilities, factories, descriptors, and immutable metadata. They
  never own created editors/dialogs, active runtimes, replies, repository collections, or controller state. Factories
  return a fresh owned result per request.
- Once a runtime factory returns a valid launch, the caller acquires that exact runtime even if start raises, so partial
  resources can be stopped/disposed. Return no runtime only when none was acquired.
- Plugin/model data is untrusted at the boundary even though installed code is trusted to execute. Validate types,
  ownership, required fields, and QObject validity before publishing results.
- API and model layers never import concrete plugins. Bundled backends and extensions obey the same public lifecycle as
  entry-point plugins; do not give bundled code hidden repository/UI side channels.
- Evolve contracts additively when practical. Before a breaking change, inspect external discovery, compatibility
  exports, every bundled implementation, tests, and compiled inclusion; do not infer compatibility from built-ins alone.

## Verification

- Cover discovery/order, API version and duplicate rejection, each changed dispatch path, registration rollback,
  reverse idempotent shutdown, provider failure isolation, invalid factory results, repeated transient creations without
  registry retention, and packaged discovery/import.

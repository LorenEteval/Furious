# Plugin guidance

## API, registry, and discovery

- `Plugins.API` defines capability contracts; `Registry` owns normalization, validation, deterministic indexing and
  selection, initialization rollback, failure isolation, and reverse-order idempotent shutdown.
- The process-wide manager registers host plugin types before trusted entry-point discovery, publishes a registry only
  after successful construction, and may reconcile additional host types idempotently. Keep discovery literal,
  deterministic, and side-effect-light for source, wheel, and Nuitka builds.
- Use current `CoreRuntimeFactory`, `CoreRuntimeRequest`, and `CoreRuntimeLaunch` vocabulary. Protocols, editors,
  subscription decoders, runtimes, traffic statistics, settings, actions, and navigation are independently indexed
  capability kinds. Routing, native-TUN/application-tun2socks policy, probes, environment, core versions, log patterns,
  and exit interpretation are hooks on the owning runtime factory. Extend the correct contract instead of adding
  central `coreName()` branches or inventing a parallel registry.
- Registration validates the complete plugin/capability contribution before committing indexes. Duplicate IDs/schemes,
  incompatible API versions, invalid descriptors, and initialization failures cannot corrupt existing providers; log
  plugin and capability identity without leaking configuration secrets.

## Ownership and trust boundaries

- Registries strongly own process-lifetime plugin instances, capabilities/factories, descriptors, and immutable metadata.
  They do not own factory-created widgets, active runtimes, replies, or controller state. Factories return a fresh object
  per request; invalid QObject results are explicitly destroyed.
- Once a runtime factory returns a valid launch, startup transfers that exact runtime to the calling connection attempt
  even when `start()` raises, so the attempt can stop and dispose partial resources. A controlled failure returns `None`
  only when no valid runtime was acquired.
- External entry points and plugin-returned data are a boundary even when plugins are trusted for execution. Validate
  types and required fields, isolate optional provider failure where the operation can continue, and keep the primary
  failure observable when it cannot.
- API/model layers never import concrete plugins. Bundled backends/extensions implement the same contracts and must not
  rely on registration-time application or UI objects.

## Verification

- Test discovery/order, API-version and duplicate rejection, every changed dispatch path, staged rollback, reverse
  shutdown, provider failure isolation, compiled inclusion, and factories returning invalid or repeatedly created
  objects without registry retention.

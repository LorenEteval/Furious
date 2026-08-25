# Plugin guidance

## Registry and extension contract

- `Plugins.API` defines capability contracts; `Registry` owns validation, deterministic registration/selection,
  initialization rollback, and reverse-order idempotent shutdown.
- Use current `CoreRuntimeFactory`, `CoreRuntimeRequest`, and `CoreRuntimeLaunch` vocabulary. Add protocol, runtime,
  routing/TUN, statistics, subscription, or navigation variation through its capability family rather than central
  conditionals.
- Registries strongly own process-lifetime plugins, providers, factories, descriptors, and immutable metadata. They do
  not own factory-created UI, active runtimes, or controller state; rejected QObject results are destroyed explicitly.
- Registration validates before committing index changes. A failed plugin is isolated with useful plugin/capability
  context and cannot corrupt existing providers. Partial initialization is rolled back.
- Discovery imports stay literal, deterministic, and side-effect-light for source and Nuitka builds. API/model layers
  never import concrete plugins.

## Verification

- Test discovery/order, duplicates and invalid capabilities, dispatch, rollback/shutdown, compiled inclusion, and
  factories returning invalid objects.

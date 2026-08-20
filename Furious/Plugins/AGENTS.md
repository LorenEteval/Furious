# Plugin architecture guidance

- `Plugins.API` defines stable capability contracts; `Registry` owns registration, selection, materialization,
  initialization, rollback, and reverse-order shutdown.
- Use `CoreRuntimeFactory`, `CoreRuntimeRequest`, and `CoreRuntimeLaunch` consistently across capabilities, registry
  dispatch, statistics providers, and tests.
- Plugins contribute factories, handlers, descriptors, immutable metadata, and service providers—not live transient
  widgets, active core instances, or controller state.
- Protocol parse/export/editor, backend runtime, routing/TUN, statistics, subscription decoding, and navigation behavior
  belongs behind capabilities. Shared code must not add core-name conditionals when capability dispatch can express the
  policy.
- Registration is deterministic and validates every capability family through focused validators before committing
  any index changes. A plugin failure is isolated, logged with plugin/capability context, and does not corrupt already
  registered providers.
- Initialization is transactional: partially initialized plugins are rolled back; shutdown is reverse-order and
  idempotent.
- Keep discovery imports literal and side-effect-light for source and Nuitka builds. Avoid circular dependencies from
  API/model layers into concrete plugins.
- UI factories create fresh owned widgets. Invalid QObject results are explicitly destroyed; registries never retain
  rejected objects.

## Verification

- Test order, duplicate/invalid registration, dynamic dispatch, rollback, shutdown, compiled discovery, and factories
  returning invalid objects.

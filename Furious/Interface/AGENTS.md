# Interface guidance

- This package defines small contracts shared by lower layers. Keep it cheap to import and independent of UI,
  controllers, services, repositories, and concrete backends.
- Contracts state observable lifecycle, ownership, mutation, and failure semantics; implementations may strengthen but
  not weaken them.
- `CoreRuntime` is mechanism-neutral. Preserve semantic exit codes, `startError()`, callback order, serialization, and
  bounded stop expectations; use process terminology only for actual OS processes.
- Storage contracts intentionally expose live mutable collections. Editor bindings translate widget/configuration
  values but do not own runtime policy.
- Shared encoders support `CoreConfiguration` and compatible mappings; serialization failures retain useful context.
- Verify import independence and representative implementations for lifecycle/error, serialization, and live-storage
  semantics.

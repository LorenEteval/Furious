# Interface contract guidance

- This package defines small, low-level contracts shared across layers. Keep imports cheap and avoid depending on UI,
  controllers, services, repositories, or concrete backends.
- Abstract methods state observable behavior, ownership, mutation, and failure contracts; concrete implementations may
  add detail but must not weaken them.
- `CoreRuntime` is the canonical mechanism-neutral lifecycle contract. Preserve its semantic exit codes, `startError()`,
  callback order, serialization behavior, and bounded stop expectations.
- Do not introduce mechanism-specific aliases for `CoreRuntime` or mistake the semantic runtime contract for an
  operating-system process.
- Serialization uses the shared `Furious.Models` encoders. Preserve supported dict subclasses such as
  `CoreConfiguration`; return/raise behavior must be documented and failures must retain useful diagnostics.
- Storage contracts intentionally expose live mutable collections. State that explicitly—do not label them copies—and
  keep persistence/ordering semantics in concrete repositories.
- Editor bindings translate between widgets and configuration but do not decide process/runtime policy.

## Verification

- Contract tests cover representative implementations, serialization failures, lifecycle/error behavior, mutable-storage
  semantics, and import independence.

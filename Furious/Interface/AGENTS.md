# Interface guidance

- This package defines small contracts shared across architectural layers. Keep it cheap to import and independent of
  UI, controllers, services, repositories, and concrete backends; dependency-light models/constants used by a contract
  are acceptable when they do not pull in application construction.
- Contracts state observable lifecycle, ownership, mutation, serialization, and failure semantics. Implementations may
  strengthen those guarantees but cannot silently weaken them; search representative implementations and tests before
  changing a base contract or semantic exit code.
- `CoreRuntime` is mechanism-neutral: an implementation may use multiprocessing, `subprocess`, or an in-process binding.
  Preserve `startError()`, callback/exit semantics, serialization diagnostics, and an idempotent bounded stop policy;
  use child-process terminology only for implementations that actually own one.
- `StorageBackend.data()` intentionally exposes a live mutable collection for compatibility. Do not reinterpret it as a
  snapshot or add a second cache. Editor bindings map widget values to configuration but do not own runtime policy.
- Shared encoders support `CoreConfiguration` and compatible mappings. Constructors may record diagnostics instead of
  raising; callers at import/runtime boundaries must preserve useful context rather than treating every empty result as
  equivalent.
- Verify import independence and representative implementations for lifecycle/error, serialization, live-storage, and
  editor-binding semantics.

# Interface guidance

- This package defines dependency-light contracts shared across layers. It does not import Qt presentation,
  controllers, services, repositories, plugins, or concrete backends; a contract may depend on a small model/constant
  only when that does not trigger application construction or registration.
- Contracts specify observable ownership, lifecycle, mutation, serialization, callback, and failure semantics. Search
  every representative implementation and contract test before changing one; an implementation may strengthen a
  guarantee but cannot silently weaken it.
- `CoreRuntime` is mechanism-neutral: embedded multiprocessing, direct `subprocess`, or an in-process binding can satisfy
  it. Preserve actionable `startError()`, callback/exit behavior, runtime identity, serialization diagnostics, and a
  bounded idempotent stop/dispose path. Process/child terminology belongs only to implementations that own one.
- `StorageBackend.data()` deliberately exposes a live mutable collection for compatibility. Do not reinterpret it as a
  snapshot or introduce a second authoritative cache. Editor bindings map input to configuration and back; they do not
  decide runtime, persistence, or host policy.
- `ApplicationRunner.ExitCode` is a process-boundary protocol. Shared encoders and non-throwing configuration
  construction preserve their distinct diagnostics so callers do not collapse every empty result into the same error.
- Verify cheap/import-independent contracts plus representative runtime, storage, editor, application-exit, encoding,
  and configuration implementations. Update this guide when a contract intentionally changes, together with all
  implementers and compatibility tests.

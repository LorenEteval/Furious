# Interface guidance

Inherit `Furious/AGENTS.md` and its root ancestor. This file preserves dependency-light contracts that multiple
implementations can satisfy without importing application composition or concrete backends.

- This package defines dependency-light contracts shared across layers. It does not import Qt presentation,
  controllers, services, repositories, plugins, or concrete backends; a contract may depend on a small model/constant
  only when that does not trigger application construction or registration.
- Contracts specify observable ownership, lifecycle, mutation, serialization, callback, and failure semantics. Search
  every representative implementation and contract test before changing one; an implementation may strengthen a
  guarantee but cannot silently weaken it.
- Interface contracts and the separately versioned plugin API are different compatibility surfaces. Reject
  unsupported shapes at their owning boundary and update implementations/exports together; do not invent a version
  gate for every Python interface or remove an established adapter without tracing its callers.
- `CoreRuntime` is mechanism-neutral: embedded multiprocessing, direct `subprocess`, or an in-process binding can satisfy
  it. It owns execution only: zero-argument start, passive liveness, typed terminal events, and bounded idempotent
  stop/dispose. Preparation, serialization, readiness, and startup transactions belong outside this contract. Bind its
  event sink once before start; the callback may originate on a worker thread, so the receiving owner supplies explicit
  thread-safe delivery. Concrete runtimes own once-only terminal publication; the base publisher forwards events and
  does not deduplicate them. Process/child terminology belongs only to implementations that own one.
- `StorageBackend.data()` deliberately exposes a live mutable collection for compatibility. Do not reinterpret it as a
  snapshot or introduce a second authoritative cache. Editor bindings map input to configuration and back; they do not
  decide runtime, persistence, or host policy.
- `ApplicationRunner.ExitCode` is the outer application process protocol; it is not interchangeable with a core's
  raw exit code or `RuntimeExitReason`. Preserve the meaning at each boundary instead of translating every nonzero
  value into one generic failure.
- Model encoders may raise, while configuration construction deliberately captures diagnostics. Callers must inspect
  the contract they consume; successful construction alone proves neither serialization nor backend acceptance.
- Runtime liveness is observational: querying it must not consume an exit, transfer ownership, or dispatch
  callbacks. A zero process exit can still be an unexpected connection failure; requested stop and raw exit success
  are different facts. Preserve both in terminal events so orchestration can interpret the exit in its current
  attempt/connection context without making the runtime own controller policy. Keep semantic startup errors separate
  from process codes and readiness timeouts. Define cleanup-failure semantics without assuming every runtime owns a subprocess. Bounded stop/dispose is a contract to
  verify, not a guarantee supplied by the base class: third-party work may be non-cooperative. Report known violations
  at their implementation/owner boundary rather than weakening the interface to bless an unreleased resource.
- Verify cheap/import-independent contracts plus representative runtime, storage, editor, application-exit,
  encoding, and configuration implementations. Update this guide when a contract intentionally changes, together
  with all implementers and compatibility tests. Start with `tests/test_interface.py` and
  `tests/test_runtime_lifecycle.py`; include `tests/test_public_api.py` when imports or exports change.

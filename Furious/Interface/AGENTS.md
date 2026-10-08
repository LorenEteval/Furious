# Interface guidance

Inherit the [nearest parent guide](../AGENTS.md).
This scope owns dependency-light, mechanism-neutral contracts. Implementers supply resource guarantees;
interfaces do not supply execution or readiness.
Read `Furious/Interface/Runtime.py` with `tests/test_interface.py`; paths are relative to this source tree's root.

- This package defines dependency-light contracts shared across layers. It does not import Qt presentation,
  controllers, services, repositories, plugins, or concrete backends; a contract may depend on a small model/constant
  only when transitive imports preserve that boundary. Test the cold import, not just a local import list.
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
  does not deduplicate them. Process/child terminology belongs only to implementations that own one. A weak
  callback reference does not supply thread affinity, cancellation, or an execution owner; consumers establish
  those independently of the runtime's event envelope.
- `StorageBackend.data()` deliberately exposes a live mutable collection for compatibility. Do not reinterpret it as a
  snapshot or introduce a second authoritative cache. Editor bindings map input to configuration and back; they do not
  decide runtime, persistence, or host policy.
  The interface supplies no atomic disk-flush or malformed-input recovery guarantee. Those belong to the concrete
  repository and must be established through its restore/commit failure paths.
- `ApplicationRunner.ExitCode` is the outer application process protocol; it is not interchangeable with a core's
  raw exit code or `RuntimeExitReason`. Preserve the meaning at each boundary instead of translating every nonzero
  value into one generic failure.
  Declaring the exit enum does not route exceptions into it. Verify the concrete process boundary separately from
  an exception hook's mapping; bootstrap interception can bypass that hook.
- Model encoders may raise, while configuration construction deliberately captures diagnostics. Callers must inspect
  the contract they consume; successful construction alone proves neither serialization nor backend acceptance.
  Preserve `RuntimeStartError`'s reason/code/details and `RuntimeExit`'s typed meaning across adapters; exception text
  and a raw process code are diagnostics, not replacement protocols or evidence that readiness was reached.
- Runtime liveness is observational: querying it must not consume an exit, transfer ownership, or dispatch
  callbacks. A zero process exit can still be an unexpected connection failure; requested stop and raw exit success
  are different facts. Preserve both in terminal events so orchestration can interpret the exit in its current
  attempt/connection context without making the runtime own controller policy. Keep semantic startup errors separate
  from process codes and readiness timeouts. Bounded stop/dispose is a requirement to verify at each implementation,
  not a guarantee supplied by the base class. `Disposed` describes terminal API state; prove release using the
  implementation's actual resources, without assuming every runtime owns a subprocess. Define how incomplete
  cleanup remains observable to its owner and report violations separately from the required contract. Do not
  impose a Boolean release convention on `CoreRuntime.stop()` or `dispose()` merely because the service lease
  returns a Boolean: the lease combines exceptions and passive liveness into its own release outcome.
- Verify cheap/import-independent contracts plus representative runtime, storage, editor, application-exit,
  encoding, and configuration implementations. Update this guide when a contract intentionally changes, together
  with all implementers and compatibility tests. Start with `tests/test_interface.py` and
  `tests/test_runtime_lifecycle.py`; include `tests/test_public_api.py` when imports or exports change.

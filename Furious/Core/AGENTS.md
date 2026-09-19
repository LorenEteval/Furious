# Embedded runtime guidance

Inherit `Furious/AGENTS.md` and its root ancestor. Consult Interface for runtime contracts and Service for
connection ownership. This scope owns reusable embedded execution machinery and application tun2socks;
connection policy remains outside it.

- `Core` supplies shared multiprocessing runtime machinery, bounded output transport, and application tun2socks. External
  Core owns its separate direct `subprocess.Popen`; neither layer owns controller, repository, UI, or protocol policy.
- A launch spec describes prepared child construction, never semantic connection readiness. Serialization and launch
  arguments are prepared before execution starts; constructors may create owned timers/queues that still need
  disposal if execution never starts. Failed launch-factory construction must dispose resources already acquired
  before propagating the failure, because no service has received ownership yet. The service observes
  endpoints/process survival and commits later.
- `CoreRuntime` execution state, typed terminal exit, and readiness are separate contracts. A process becoming alive is
  not proof that its proxy/TUN endpoint is ready, while a readiness timeout must not overwrite an already observed typed
  exit.
- Required cleanup covers the exact child, process handle, monitor/drain timers, queues, callbacks, and feeder
  resources. Stop must bound waits, escalate only the owned child, and remain safe after partial start or repetition.
  Execution exit, terminal-event delivery, and monitor/transport disposal need separate assertions; success at one
  boundary must not hide a leak at another. A join timeout or failed handle close is not a successful reap. Verify
  actual child liveness before describing a terminal execution state as complete resource release; include failed
  escalation in ownership tests.
  `MultiprocessingRuntime._closeProcess()` currently discards its process reference even when handle close fails.
  This is a cleanup-contract gap, not a permissible ownership transfer: a fix must preserve observability of the
  outstanding child/handle and agree with the service lease's cleanup-failure semantics.
- Process-backed runtimes own exit monitoring and interpretation: publish one typed terminal event per execution,
  preserving the raw exit and whether stop was requested. `isRunning()` is a passive liveness query and must not
  consume or dispatch lifecycle events.
- Child targets never touch Qt widgets. Output transport is non-blocking and bounded in message size, pending volume, and
  per-turn drain work; draining continues independently of Log-page visibility and backs off only when idle. Diagnostic
  output may be truncated or dropped under pressure, so it cannot be the authoritative terminal-event channel. Preserve
  typed exit delivery independently of log transport and rendering. The output callback runs at the GUI drain
  boundary, so bounding queue admission alone is insufficient: preserve bounded drain batches and a bounded consumer
  such as the shared log model. Test producer pressure and hidden-page draining independently.
- Parentless timers are acceptable only with a durable runtime owner and explicit disposal. Leaving the manager pool
  must not leave timers, callbacks, queues, or process handles alive. Stopping execution is not QObject destruction:
  disposal must also release monitors and output infrastructure, including for a runtime that was never started.
- Verify invalid target/serialization, failed spawn, early exit, readiness compatibility, burst output
  bounds/backoff, normal and forced stop, repeated disposal, and absence of residual children, handles, timers,
  queues, or callbacks. Start with `tests/test_runtime_lifecycle.py` and `tests/test_connection_startup_async.py`;
  output/process stress lives in the tiers documented by `tests/README.md`. Review output admission and draining
  together when changing backpressure.

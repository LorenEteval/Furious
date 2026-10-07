# Embedded runtime guidance

Inherit the [nearest parent guide](../AGENTS.md). This scope owns embedded execution, output transport and
separate application TUN engines. Launch, readiness, terminal publication and disposal are distinct
boundaries. Read `Furious/Core/MultiprocessingRuntime.py` with `tests/test_runtime_lifecycle.py`; paths are
relative to this source tree's root.

- `Core` supplies shared multiprocessing runtime machinery, bounded output transport, and independent application
  tun2socks/sing-tun engines. External Core owns its separate direct `subprocess.Popen`; neither layer owns controller,
  repository, UI, or protocol policy.
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
  Keep an independently observable outstanding child/handle when release fails; forgetting it cannot satisfy
  this contract. Review `MultiprocessingRuntime._closeProcess()` together with service lease release when changing
  failure reporting or retry ownership. A stopped child can still have an unclosed process handle; retry must
  finish that release without restarting execution or publishing a second exit. Exercise failed escalation and
  failed handle close as separate cases.
- Process-backed runtimes own exit monitoring and interpretation: publish one typed terminal event per execution,
  preserving the raw exit and whether stop was requested. `isRunning()` is a passive liveness query and must not
  consume or dispatch lifecycle events.
- Child targets never touch Qt widgets. Output transport is non-blocking and bounded in message size, pending volume, and
  per-turn drain work; draining continues independently of Log-page visibility and backs off only when idle. Diagnostic
  output may be truncated or dropped under pressure, so it cannot be the authoritative terminal-event channel. Preserve
  typed exit delivery independently of log transport and rendering. The output callback runs at the GUI drain
  boundary, so bounding queue admission alone is insufficient: preserve bounded drain batches and a bounded consumer
  such as the shared log model. Test producer pressure and hidden-page draining independently.
  Consumer callbacks may synchronously dispose the output transport. End that drain turn before another queue read,
  callback or timer adjustment; the reentrant-disposal case in `tests/test_architecture_refactors.py` covers this path.
- Parentless timers are acceptable only with a durable runtime owner and explicit disposal. Leaving the manager pool
  must not leave timers, callbacks, queues, or process handles alive. Stopping execution is not QObject destruction:
  disposal must also release monitors and output infrastructure, including for a runtime that was never started.
  These timers belong to their constructing Qt thread even though the runtime owner is a Python object;
  child execution and process-watch threads must publish through the owned delivery boundary.
- Verify invalid target/serialization, failed spawn, early exit, readiness compatibility, burst output
  bounds/backoff, normal and forced stop, repeated disposal, and absence of residual children, handles, timers,
  queues, or callbacks. Start with `tests/test_runtime_lifecycle.py` and `tests/test_connection_startup_async.py`;
  output/process stress lives in the tiers documented by `tests/README.md`. Review output admission and draining
  together when changing backpressure.
- `SingTUN` imports the Go binding only in a spawned child. Its bounded status pipe establishes native readiness
  and the actual device name independently of diagnostic output and process liveness. Cooperative stop is followed
  by exact-child reap and attempt-local host recovery; retain the lease when either fails. Never infer Go cleanup
  from forced termination. Its `SingTUNHostPlan` remains attached through host-worker drain and restoration; tests
  in `tests/test_sing_tun.py` cover startup cancellation, validated status with binding-provided failure reasons,
  and cleanup refusal/retry. Privileged platform smoke tests remain separate from harmless source/compiled
  lifetime checks.
  Binding-provided failure text is diagnostic input, not a stable enumerated protocol: preserve useful reasons rather
  than accepting only exact known strings. Changing binding versions requires coordinated model validation,
  distribution metadata/native-library inclusion, and workflow API checks; a successful import does not exercise TUN.

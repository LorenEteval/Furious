# Service guidance

Inherit the [nearest parent guide](../AGENTS.md). Services own workflow generations, temporary resources and
commits. Publication cancellation does not establish physical termination or release cleanup ownership. Read
`Furious/Service/ConnectionManager.py` with `tests/test_runtime_lifecycle.py`; paths are relative to this
source tree's root.

## Workflow ownership

- Services own workflows and temporary resources; controllers own shared state, repositories own durable
  collections, and UI owns presentation. Prefer outcome signals/callbacks for new service APIs. `UpdateManager`
  still creates update dialogs as a compatibility path; preserve its public behavior until presentation is
  deliberately moved to a UI owner.
- A workflow keeps its execution resources and callback context owned until their users finish. Cancellation may
  suppress publication while execution continues; distinguish bounded teardown from cooperative drains and keep
  cancelled work inside admission/resource limits. Construct Qt services only after an application exists.
- Native owner destruction requires a final cleanup attempt for Python-owned resources; it does not terminate
  running Python work. At `destroyed`, the owner's wrapper is invalid
  but its QObject children have not yet been deleted; a plain weak-reference callback may release Python state
  and shut down still-valid child schedulers without calling the destroyed owner's Qt API. Statistics executors,
  profile-test runtime leases and DNS-operation replies exercise this boundary in `test_service_runtime.py` and
  `test_profile_test_jobs.py`. This final attempt does not guarantee release of a resource that refuses cleanup:
  explicit shutdown must retain retry ownership before native deletion. Cancellation of a running provider remains
  cooperative, and executor admission closure is distinct from actual worker termination.
- Inject repositories/providers/clients/runtime factories where practical. Stage results, prove freshness, and commit
  through the owning repository/controller rather than creating a parallel authoritative collection.
- Every async workflow defines supersession and one terminal publication path. Generation/version or exact target
  identity rejects stale completion. Successful release is idempotent; failed drains may require retry while their
  owner remains alive, without publishing another terminal result. Delete replies/Qt objects in their owning thread
  and release contexts only when execution no longer needs them. Late delivery must not revive a shut-down manager
  or mutate live state. A terminal result ends an operation's publication contract, not necessarily its execution:
  a replacement may be admitted only under the scheduler's resource bounds while cancelled work still occupies a slot.
  External provider callbacks, reply aborts and signal publication can be reentrancy boundaries. Trace the specific
  callback/observer contract before adding continuation guards; pure preparation is not a destruction boundary.
  Recheck native ownership and the captured generation before continuing a stage, restarting a timer, admitting
  another request, or publishing the next result; a check at callback entry alone cannot establish freshness afterward.

## Connection and network workflows

- GUI connection startup is a generation-checked transaction over a runtime copy: prepare TUN policy, launch and
  observe the primary runtime, acquire optional application TUN/DNS resources, and mutate host networking in platform
  order before commit. The tun2socks path preserves Windows runtime-before-device, Linux device-before-runtime, and macOS
  survival-before-DNS ordering. Failure/cancellation releases attempt-owned runtimes and registered host cleanup.
  The synchronous start path remains a compatibility boundary. Review GUI responsiveness at each stage, including
  factory preparation, host commands, and reverse cleanup: a scheduled start only defers the first call. Readiness
  timers and asynchronous DNS cannot preempt synchronous work. Keep cancellation checks at reentrant stage boundaries
  before acquiring the next resource, and audit shared route bookkeeping separately from attempt-local leases.
- Native proxy-core TUN policy precedes application-engine selection. The legacy plugin opt-in
  `usesApplicationTun2socks` still means application-TUN eligibility; it must not force the selected engine.
  Snapshot the engine and relevant customization once per attempt; bind each backend's named settings callers to
  that snapshot, preserving proxy-only and explicit native TUN behavior.
  Committed application-TUN usage is derived from the runtime leases marked at acquisition, not from mutable profile
  documents or next-start settings. Settings presentation must not run TUN preparation to decide whether to reconnect.
- Each application engine reads only its own persisted document: sing-tun's `host_options` belong to
  `CustomSingTUNSettings`, while tun2socks uses `CustomTUNSettings`; edits and missing defaults must never import
  preferences from the other engine. Their repository/host policies remain independent while orchestration,
  leases and general utilities may be reused.
- For sing-tun, resolve automatic and manual remote exclusions before native auto-routing, then require
  native readiness and checked DNS application before commit. `SingTUNHostPlan` owns only its assigned identifiers
  and DNS snapshots, independently of legacy `SystemRoutingTable.managedRoutes`; refuse ambiguous recovery and
  retain ownership for retry. Host preparation/DNS commands run in its owned worker, while synchronous compatibility
  startup and bounded cleanup joins remain explicit responsiveness limits. Consult `tests/test_sing_tun.py` and
  `tests/test_native_tun_semantics.py`; mocked host tests do not establish privileged OS behavior.
- Construct a runtime event router before asking a plugin to create its runtime. One lease owns the runtime/router from
  acquisition through attempt ownership, commit, and reverse-order release; commit changes logical delivery without
  replacing the runtime callback. Worker-thread exits are queued to the router's Qt thread, delivered at most once, and
  suppressed after release. Execution liveness and endpoint/TUN readiness remain separate observations. A readiness
  timeout never replaces a typed exit after execution has already stopped, even when that exit is still queued.
  Failed stop/dispose keeps the lease in Releasing with terminal delivery suppressed. The manager retains it for
  retry and refuses new startup while release remains incomplete. A failed attempt transfers unreleased leases
  back to that durable owner; deleting the attempt must not abandon them. Independent DNS cleanup still runs.
  Verify runtime liveness and actual handle/thread release separately from the lease's logical state.
  Native startup-operation destruction cancels child observers and rolls back an uncommitted attempt before child
  deletion. Terminal observers may destroy the operation synchronously; retire manager ownership without a later
  call into the dead QObject. Failed release still transfers to the manager, and a committed lease remains its
  responsibility. Test native destruction during stages/results as well as ordinary cancellation.
- `HttpGetManager` owns reply/error/timeout cleanup. DNS recursion and external-input caches are bounded. Update,
  connectivity, endpoint, subscription, and asset requests own their exact reply and reject stale generations.
  Workflow-specific reply indexes must also release on native destruction without `finished`. Abort hooks can
  synchronously destroy the manager, remaining replies, and child pools; recheck validity before using captured Qt
  resources during cancellation/shutdown. `tests/test_service_runtime.py` exercises those failure boundaries.
  Update result callbacks may destroy the manager or the requested dialog parent. Presentation requires both still
  to be valid after notification; do not substitute an unparented dialog for an expired parent. The update-response
  cases in `tests/test_service_runtime.py` verify completion without stale dialog creation.
- Subscription stages remain separate: decoders return neutral items; import constructs profiles/metadata;
  synchronization prepares one group reconciliation; the manager owns request/schedule generations and commits it.
  Worker-safe payload import and reconciliation preparation run in the manager's bounded pool over copied data;
  unclassified plugin parsers stay on the GUI compatibility path. The manager's synchronous shutdown closes
  admission, cancels work, and retains the pool/relay until workers finish. A slow-shutdown warning is diagnostic,
  not a deadline that permits destroying running workers; a non-returning plugin can still block shutdown.
  Subscription preparation workers never read live repositories or Qt models. The GUI thread verifies the full source
  signature and group revision, commits while preserving live profile identity/local metadata, then publishes
  coalesced status/structure.
  Post-commit reconnect/test invalidation failure is reported without undoing committed profiles. This is live
  reconciliation; repository flush and status persistence are separate boundaries, not one disk transaction.
- User-requested subscription stop invalidates pending generations and marks unfinished groups cancelled. Publish
  old group cancellation state before aborting replies: abort can synchronously finish a batch whose observers start
  another update. Finish only captured old operation contexts, never overwrite a newer generation's status. Keep
  completed commits/results and automatic schedules; future updates remain admissible. Logical batch completion
  does not release a still-running preparation worker or its relay.
- Provider-reported subscription usage/expiry metadata is untrusted advisory input. Parse it with strict bounds at the
  network boundary and commit or clear it only alongside a successful current synchronization; failed synchronization
  preserves the last successful metadata.
- Log transport, traffic collection, and metric history remain bounded and independent of page visibility. Endpoint
  inspection is different: visibility may initiate its lazy proxy-only lookup, while disabling inspection or changing
  the connection invalidates the cache and request generation. Hiding the page does not transfer request ownership
  to presentation or authorize direct-network fallback.
- Logging accepts concurrent producers through one globally ordered model with count, total-character, and per-entry
  limits. Batch input conversions are validated before mutation; compatibility per-entry signals observe the fully
  committed batch. Presenters consume coalesced changes/cursors rather than replaying those signals as a second log.
  Whole-stream clearing swaps generations; retired entries are reclaimed in bounded batches under retention budgets.
  Selective category clearing can cost O(k); do not claim every clear is constant-time.
- Log cursors are opaque and filter-specific. A generation change requires a reset; retention-only eviction supplies
  a new first-retained sequence so presenters can prune their prefix without rebuilding history. Capture entries and
  the next cursor atomically, and coalesce notifications without losing producer updates.
- Application TUN logs share an engine-neutral runtime category. Bind each producer's source to the connection
  attempt's captured engine selection rather than a later preference read; proxy-core native TUN output stays with
  the Core category. Preserve batching, export/rendering labels, and runtime clearing together. Tests in
  `test_sing_tun.py`, `test_log_manager_generation.py`, and `test_ui_behavior.py` cover these boundaries.
- Metrics sampling owns its worker/future generation and rejects results after disconnect, disablement, replacement,
  or shutdown. Normalize cumulative-counter resets before history aggregation; clearing usage must not erase speed
  history.
  Statistics preparation/publication and endpoint lookup use the workflow reentrancy rules above; exercise them
  through `tests/test_service_runtime.py` and `tests/test_endpoint_info.py` rather than inferring safety from entry checks.
  History contains finite values for registered metrics on a monotonic timeline. A missing metric sample is not a
  measured zero; preserve that distinction when adding providers or aggregating sparse series. Closing executor
  admission or cancelling a future does not terminate a query already inside plugin code; test stale-result suppression
  separately from worker completion. Monitor contracts must bound blocking work; report non-returning providers as a
  shutdown limitation, not successful cancellation.

## Profile testing

- `ProfileTestManager` is the sole result write-back boundary. A job captures stable profile ID, connection
  fingerprint, snapshot, ownership, and explicit options; workers return values and the manager resolves the current
  target before mutating latency/speed. Freshness currently resolves ID plus connection fingerprint; subscription
  ownership drives explicit group invalidation, not an implicit row or metadata equality test.
- User-requested test cancellation preserves received results, suppresses late cancelled results, and leaves the
  manager available for new work. Shutdown separately closes admission and releases owned execution resources.
- Repository changes reconcile queued/running jobs. A successful subscription commit cancels that group's pending and
  active tests, stale-marks non-cancellable calls, clears only that group's current results, and leaves manual/other-group
  work untouched.
- Blocking Ping uses a private bounded pool. TCPing owns sockets/deadlines in one dedicated Qt networking thread,
  deduplicates equal endpoint/policy requests, adapts within a fixed bound, and fans results into bounded GUI batches.
- A QObject owner must stop and join its running TCPing thread before native child deletion. The parent's `destroyed`
  boundary still permits that child cleanup; the thread's `run()` finalizer releases its engine/sockets on the
  networking thread. Explicit shutdown and owner-first destruction share the bounded stop/join path. Verify actual
  thread exit and engine destruction affinity in `tests/test_profile_test_jobs.py`, including held wrappers.
- Download jobs own a temporary proxy-only runtime, readiness timer, port, network reply, and cancellation path. Serial
  and concurrent admission share scheduler semantics; startup never blocks admission on a grace wait. Reentrant
  cancellation defers terminal deletion until the active start frame unwinds.
  Failed runtime release transfers its lease from the terminal worker to the scheduler before worker deletion.
  Keep the port and concurrency slot reserved until a later drain/cancel/shutdown retries cleanup successfully;
  final shutdown reports remaining leases and preserves retry ownership. Publish completion only after that
  transfer: a result listener may synchronously submit another job, cancel work, or shut down the manager. Those
  listeners must see the still-reserved resources. Completion is not proof of resource release.

## Verification

- Cover success plus invalid, stale, superseded, timeout, cancellation, partial acquisition, hidden-page, reentrant, and
  repeated-shutdown paths. Assert current identity at write-back and exact cleanup of pools, threads, sockets, replies,
  timers, ports, runtimes, callbacks, and host mutations. A failed worker drain must still attempt independent resource
  cleanup; closing admission is not evidence of completed shutdown and must not prevent retrying retained resources.
- Test pre-commit failure with unchanged live/persisted state separately from post-commit side-effect failure. Never
  use a broad rollback assertion to conceal which boundary actually committed. Use `tests/README.md` for
  workflow-specific modules; `test_log_manager_generation.py`, `test_profile_test_jobs.py`,
  `test_subscription_sync.py`, and `test_connection_startup_async.py` challenge the high-risk contracts above.
  Update this scope with verified changes to commit, cancellation, or ownership boundaries.

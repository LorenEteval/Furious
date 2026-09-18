# Service guidance

Inherit the root and package guides. Consult Models/Repository for data contracts, Plugins/Core for execution, and Qt
for lifetime primitives. This scope owns multi-stage workflows and temporary resources.

## Workflow ownership

- Services own workflows and temporary resources; controllers own shared state, repositories own durable
  collections, and UI owns presentation. Prefer outcome signals/callbacks for new service APIs. `UpdateManager`
  still creates update dialogs as a compatibility path; preserve its public behavior until presentation is
  deliberately moved to a UI owner.
- Give each QObject service, worker, reply, timer, pool, thread, runtime, process, cache, and callback context one durable
  owner and explicit idempotent cleanup. Cancellation can suppress a result without stopping the underlying work;
  distinguish deadline-bounded teardown from cooperative drains, and retain resources until their users finish.
  Construct Qt services only after an application exists.
- Inject repositories/providers/clients/runtime factories where practical. Stage results, prove freshness, and commit
  through the owning repository/controller rather than creating a parallel authoritative collection.
- Every async workflow defines supersession and one terminal path. Generation/version or exact target identity rejects
  stale completion. Terminal cleanup runs once and deletes replies/Qt objects in their owning thread. Release callback
  contexts when execution no longer needs them; late delivery must not revive a shut-down manager or mutate live state.

## Connection and network workflows

- GUI connection startup is a generation-checked transaction over a runtime copy: prepare TUN policy, launch and
  observe the primary runtime, acquire optional tun2socks/DNS resources, and mutate host networking in platform
  order before commit. Preserve Windows runtime-before-device, Linux device-before-runtime, and macOS
  survival-before-DNS ordering. Failure/cancellation releases attempt-owned runtimes and registered host cleanup.
  The synchronous start path is a compatibility boundary, not the default GUI mechanism. Timed readiness/DNS
  continuations do not make synchronous platform commands or backend preparation interruptible; audit those calls
  and shared route bookkeeping separately.
- Construct a runtime event router before asking a plugin to create its runtime. One lease owns the runtime/router from
  acquisition through attempt ownership, commit, and reverse-order release; commit changes logical delivery without
  replacing the runtime callback. Worker-thread exits are queued to the router's Qt thread, delivered at most once, and
  suppressed after release. Execution liveness and endpoint/TUN readiness remain separate observations. A readiness
  timeout never replaces a typed exit after execution has already stopped, even when that exit is still queued.
  Lease release currently logs stop/dispose errors and completes logical callback release; this is not evidence that
  the underlying resource was reaped. Changes to cleanup-failure reporting must cover both runtime and lease owners.
- `HttpGetManager` owns reply/error/timeout cleanup. DNS recursion and external-input caches are bounded. Update,
  connectivity, endpoint, subscription, and asset requests own their exact reply and reject stale generations.
- Subscription stages remain separate: decoders return neutral items; import constructs profiles/metadata;
  synchronization prepares one group reconciliation; the manager owns request/schedule generations and commits it.
  Worker-safe payload import and reconciliation preparation run in the manager's bounded pool over copied data;
  unclassified plugin parsers stay on the GUI compatibility path. The manager's synchronous shutdown closes
  admission, cancels work, and retains the pool/relay until workers finish. A slow-shutdown warning is diagnostic,
  not a deadline that permits destroying running workers; a non-returning plugin can still block shutdown.
  Workers never read live repositories or Qt models. The GUI thread verifies the full source signature and group
  revision, commits while preserving live profile identity/local metadata, then publishes coalesced status/structure.
  Post-commit reconnect/test invalidation
  failure is reported without undoing the committed profiles. Here commit means live reconciliation; repository
  flush and status persistence are separate boundaries, not one disk transaction.
- Provider-reported subscription usage/expiry metadata is untrusted advisory input. Parse it with strict bounds at the
  network boundary and commit or clear it only alongside a successful current synchronization; failed synchronization
  preserves the last successful metadata.
- Log transport, traffic collection, and metric history remain bounded and independent of page visibility. Rendering may
  be lazy; collection/draining ownership is not.
- Logging accepts concurrent producers through one globally ordered model with count, total-character, and per-entry
  limits. Batch input conversions are validated before mutation; compatibility per-entry signals observe the fully
  committed batch. Presenters consume coalesced changes/cursors rather than replaying those signals as a second log.
  Whole-stream clearing swaps generations; retired entries are reclaimed in bounded batches under retention budgets.
  Selective category clearing can cost O(k); do not claim every clear is constant-time.
- Log cursors are opaque and filter-specific. A generation change requires a reset; retention-only eviction supplies
  a new first-retained sequence so presenters can prune their prefix without rebuilding history. Capture entries and
  the next cursor atomically, and coalesce notifications without losing producer updates.
- Metrics sampling owns its worker/future generation and rejects results after disconnect, disablement, replacement,
  or shutdown. Cancellation cannot stop an already-running plugin query: monitor contracts must bound blocking work.
  Normalize cumulative-counter resets before history aggregation; clearing usage must not erase speed history.
  History contains finite values for registered metrics on a monotonic timeline. A missing metric sample is not a
  measured zero; preserve that distinction when adding providers or aggregating sparse series.

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
- Download jobs own a temporary proxy-only runtime, readiness timer, port, network reply, and cancellation path. Serial
  and concurrent admission share scheduler semantics; startup never blocks admission on a grace wait. Reentrant
  cancellation defers terminal deletion until the active start frame unwinds.

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

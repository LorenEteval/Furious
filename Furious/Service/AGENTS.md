# Service guidance

## Workflow ownership

- Services own workflows and temporary resources; controllers own shared state, repositories own durable collections,
  and UI owns presentation. Services may use Qt signals/networking but do not create pages or message boxes.
- Give each QObject service, worker, reply, timer, pool, thread, runtime, process, cache, and callback context one durable
  owner and bounded idempotent cleanup. Construct Qt services only after an application exists.
- Inject repositories/providers/clients/runtime factories where practical. Stage results, prove freshness, and commit
  through the owning repository/controller rather than creating a parallel authoritative collection.
- Every async workflow defines supersession and one terminal path. Generation/version or exact target identity rejects
  stale completion; terminal cleanup aborts/finishes once, deletes replies/Qt objects in their owning thread, and cannot
  retain a shut-down manager.

## Connection and network workflows

- GUI connection startup is a generation-checked transaction over a runtime copy: prepare TUN policy, launch and observe
  the primary runtime, resolve DNS, acquire optional tun2socks, mutate host networking in platform order, then commit.
  Failure/cancellation rolls back only attempt-owned runtimes and host changes. The synchronous start path is a
  compatibility boundary, not the default GUI mechanism.
- `HttpGetManager` owns reply/error/timeout cleanup. DNS recursion and external-input caches are bounded. Update,
  connectivity, endpoint, subscription, and asset requests own their exact reply and reject stale generations.
- Subscription stages remain separate: decoders return neutral items; import constructs profiles/metadata;
  synchronization prepares one group reconciliation; the manager owns request/schedule generations and commits it.
  Large payload import and reconciliation preparation run in the manager's bounded pool over copied payload/profile
  data. Workers never read live repositories or Qt models; the GUI thread verifies the full source signature and group
  revision, commits while preserving live profile identity/local metadata, then publishes coalesced status/structure.
  Post-commit reconnect/test invalidation failure is reported without undoing the committed profiles.
- Log transport, traffic collection, and metric history remain bounded and independent of page visibility. Rendering may
  be lazy; collection/draining ownership is not.

## Profile testing

- `ProfileTestManager` is the sole result write-back boundary. A job captures stable profile ID, connection fingerprint,
  snapshot, ownership, and explicit options; workers return values and the manager resolves the current target before
  mutating latency/speed.
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
  timers, ports, runtimes, callbacks, and host mutations.

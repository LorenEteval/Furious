# Service guidance

## Scope and ownership

- Services own workflows and temporary resources; controllers own shared application state. A service may use Qt for
  async I/O/signals but does not own pages or presentation policy.
- Construct QObject services only after the application exists. Give each worker, reply, timer, executor, runtime,
  process, and cache one explicit service/application owner with bounded, idempotent cleanup.
- Inject repositories, providers, clients, clocks, and runtime factories where practical. Services stage results and
  commit through the owning repository/controller rather than creating a parallel state cache.

## Runtime and asynchronous work

- `ConnectionManager` consumes runtime copies, coordinates capabilities and exact runtime ownership, and rolls back
  only resources acquired by the failed staged attempt. It respects the backend TUN decision before any tun2socks
  fallback.
- Every async workflow defines supersession: generation/version checks when stale completion is possible, or exact
  object ownership when requests are independent. Terminal paths remove context, abort/finish once, and schedule Qt
  replies for deletion once.
- Bound network/DNS/process/worker operations where their API permits it. Callbacks must not retain a shut-down manager;
  GUI effects cross through signals.
- Collection continues independently of page visibility. Log/process transports and metric history remain bounded;
  hidden pages may defer rendering but never draining. Raw metric samples remain immutable and display buckets derived.
- `SubscriptionManager` owns download, decode/filter/reconcile/persist, stale-request rejection, and stable-ID schedules.
  Reconciliation commits current data before optional reconnect effects; one subscription failure does not cancel other
  current results. Reapplying unchanged schedule policy does not restart timers or duplicate connections.
- Endpoint inspection enforces the active proxy, rejects stale connection results, uses neutral request metadata, and
  discloses actual providers without profile secrets.

## Verification

- Test success plus partial, stale, timeout, cancel, failure, hidden-page, and repeated-cleanup paths with fake
  providers/host operations. Review retained callbacks, widgets owned by services, unbounded transports, and
  persistence performed before final freshness checks.

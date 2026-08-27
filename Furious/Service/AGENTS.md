# Service guidance

## Workflow and ownership boundaries

- Services own workflows and temporary resources; controllers own shared application state and UI owns presentation.
  A service may use Qt for signals/networking, but it does not own pages or create message boxes.
- Construct QObject services only after a Qt application exists. Give every worker, reply, timer, executor, runtime,
  process, cache, and callback context one durable service/application owner with bounded, idempotent cleanup.
- Inject repositories, providers, clocks, clients, and runtime factories where practical. Stage data and commit through
  the owning repository/controller; do not create a parallel authoritative collection.

## Runtime and asynchronous invariants

- `ConnectionManager` consumes an attempt-scoped copy, asks the selected factory for native-TUN/application-tun2socks
  policy, and owns exact runtimes only after commit. On failure it rolls back only resources acquired by that attempt and
  restores host routing/DNS state through those owners.
- Every async workflow defines supersession: generation/version checks for stale completion or exact-object identity for
  independent requests. Terminal paths release context, finish/abort once, and schedule each Qt reply for deletion.
  Callbacks cannot retain a shut-down manager; worker results cross into the manager's Qt thread before mutation.
- `HttpGetManager` supplies common reply ownership and transfer timeouts. DNS recursion is depth/time bounded; update and
  connectivity requests own their active reply and cancellation. Never use page visibility as request or scheduler
  ownership.
- Log/process transport and metric history stay bounded and continue collecting/draining independently of rendering.
  Raw traffic samples are immutable; speed/usage baselines and graph buckets are derived state. Generation changes reject
  stale statistics futures.
- `SubscriptionManager` owns download, decode/filter, group-scoped reconciliation, persistence metadata, stable-ID
  schedules, cancellation, and reconnect/disconnect follow-up. Freshness is checked before commit; one group failure does
  not cancel current peers; post-commit side-effect failure does not roll back reconciliation; unchanged scheduling
  policy does not restart timers or duplicate connections.
- Keep the subscription stages distinct: decoders emit neutral `SubscriptionItem` values;
  `SubscriptionImportService` constructs profiles and metadata; `SubscriptionSynchronizer` prepares group-scoped
  reconciliation; `SubscriptionManager` owns request/schedule generations and commits the prepared result. Do not move
  repository or UI mutation into a decoder merely to shorten this path.
- Endpoint inspection uses only the active proxy, neutral request metadata, bounded caches, and connection generations.
  Reject stale results and disclose actual providers without exposing profile credentials or complete destinations.

## Verification

- Test success plus invalid, partial, stale, timeout, cancel, failure, hidden-page, and repeated-cleanup paths with fake
  providers/host operations. Review retained callbacks/replies, widgets owned by services, unbounded transports/caches,
  repository mutation before final freshness checks, and commits incorrectly described as rolled back.

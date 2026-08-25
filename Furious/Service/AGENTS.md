# Service guidance

- Services own workflows and temporary resources; controllers own shared application state. Services may use Qt for
  asynchronous I/O/signals but must not own pages or encode presentation policy.
- Never instantiate `QObject` services such as network-access managers at module import time. Acquire them after the
  application exists, give them one explicit service/application owner, and release them during that owner's cleanup.
- Inject repositories, runtimes, clients, clocks, and callbacks where practical. One service owns each worker, reply,
  timer, executor, process, and cache; cleanup is bounded and idempotent.

## Connection and configuration

- `ConnectionManager` coordinates plugin capabilities, core runtimes, proxy/TUN/routing, and rollback. Its `runtimes`
  collection contains semantic runtime owners, not necessarily operating-system processes. It consumes runtime copies
  and never mutates persisted profiles.
- Preserve the backend native-TUN decision reported by capabilities. Start application tun2socks only when no native TUN
  is handled; proxy-only operations strip TUN explicitly.
- Connection startup is one private staged attempt over a runtime configuration copy. Track each exact runtime as soon
  as it is acquired; failures roll back only that attempt in reverse order, and commit transfers ownership to the
  manager's normal lifecycle.
- Startup either reaches a valid running state or rolls back every process/host mutation with an actionable error.
  Shutdown and unexpected-exit paths are bounded and safe to repeat.

## Async, network, and background work

- Each asynchronous workflow defines one explicit ownership and supersession policy: a generation/version where stale
  completion is possible, or exact reply/future ownership where requests are independent. Partial results may publish
  independently; terminal reply paths abort or finish once and schedule deletion once.
- Bound network, DNS, process, host, and worker work where the provider permits it. Executor callbacks use weak or
  otherwise bounded ownership and must not retain a manager forever after shutdown; GUI updates cross via signals.
- Log storage has independent count, total-character, and per-entry hard bounds even when automatic clearing is
  disabled. High-rate producers must coalesce GUI notifications; hiding a page may defer rendering but must never defer
  draining a process pipe or bounded transport queue.
- Metric history has both a time horizon and a defensive sample-count ceiling. Derive graph buckets on demand rather
  than retaining a second ever-growing history.
- Every network reply has a finite transfer timeout unless a documented caller supplies a stricter one. Track replies
  by exact object identity, remove every context on the terminal path, and schedule the reply for deletion exactly once.
- Per-subscription versions exist only while the persisted subscription, its timer, or an active reply needs them;
  repeated create/delete cycles must not grow bookkeeping dictionaries.
- Logging and metrics collect while pages are hidden but avoid hidden-page rendering. Raw time-series samples are
  immutable; stable timestamp buckets are derived display data.
- Log retention is owned by `LogManager`, not a text document. Category pruning/reset notifications must keep lazy UI
  sequence state valid.
- Endpoint inspection must enforce the active proxy path, reject stale connection results, use neutral request metadata,
  and disclose actual external providers without sending profile secrets.
- `SubscriptionManager` owns download, decoding, filtering, reconciliation, persistence effects, stale-request
  rejection, and stable-ID auto-update timers. Subscription views invoke commands and render semantic results; they do
  not own this workflow. Remote data is untrusted.
- Long-lived service timers are created and connected once, then reconciled idempotently. Reapplying unchanged policy
  must not restart a periodic countdown, reconnect its timeout, or emit a lifecycle transition log.
- Page visibility and presentation refreshes must not control application-level background scheduler lifecycles.
  Reconcile schedules at service startup and when the corresponding persisted scheduling policy changes.
- Subscription reply callbacks stage decoded results only. Persist group status and reconcile profiles after the final
  request-version check; one group's failure must not abort other current groups in the same completion batch.
- Treat reconnect/disconnect after subscription reconciliation as a post-commit effect. Failure there must be logged
  without reporting the already-committed repository update as rolled back.

## Code review rules

- Flag widgets retained by services, unbounded executor/network/process work, callbacks that capture service owners
  after shutdown, UI-only cache invalidation, and swallowed provider failures.
- Test success, partial/stale/timeout/cancel/failure, hidden-page behavior, repeated cleanup, and worker/reply lifetime
  with fakes—never real host mutation.

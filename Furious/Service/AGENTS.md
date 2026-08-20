# Service guidance

- Services own workflows and temporary resources; controllers own shared application state. Services may use Qt for
  asynchronous I/O/signals but must not own pages or encode presentation policy.
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
- Logging and metrics collect while pages are hidden but avoid hidden-page rendering. Raw time-series samples are
  immutable; stable timestamp buckets are derived display data.
- Log retention is owned by `LogManager`, not a text document. Category pruning/reset notifications must keep lazy UI
  sequence state valid.
- Endpoint inspection must enforce the active proxy path, reject stale connection results, use neutral request metadata,
  and disclose actual external providers without sending profile secrets.
- `SubscriptionManager` owns download, decoding, filtering, reconciliation, persistence effects, stale-request
  rejection, and stable-ID auto-update timers. Subscription views invoke commands and render semantic results; they do
  not own this workflow. Remote data is untrusted.

## Code review rules

- Flag widgets retained by services, unbounded executor/network/process work, callbacks that capture service owners
  after shutdown, UI-only cache invalidation, and swallowed provider failures.
- Test success, partial/stale/timeout/cancel/failure, hidden-page behavior, repeated cleanup, and worker/reply lifetime
  with fakes—never real host mutation.

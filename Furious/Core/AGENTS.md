# Process-backed runtime guidance

## Scope and ownership

- This package supplies low-level process-backed `CoreRuntime`, output transport, and tun2socks primitives. It does not
  own controller, repository, page, or backend protocol policy.
- Own and reap exact child/handle objects. Startup validates launch/readiness; shutdown performs bounded
  terminate/join/kill escalation, stops queues/timers, clears callbacks, and is idempotent.
- Preserve semantic exit codes and actionable startup diagnostics. Child targets never touch GUI objects; callbacks
  cross through the established Qt timer/signal boundary.
- Bound producer queues/messages and drain independently of page visibility. Presentation may be lazy; process pipes
  cannot be. Parentless timers require a durable Python owner and explicit `dispose()` path.

## Verification

- Test invalid launch, failed spawn, early exit, burst output bounds, normal stop, forced escalation, repeated disposal,
  and absence of residual children, timers, queues, or handles.

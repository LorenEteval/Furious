# Process-backed core-runtime guidance

- This package provides low-level process-backed `CoreRuntime`, queue, output-redirection, and tun2socks primitives. It
  must not own controller, repository, page, or protocol policy.
- Own exact child `Process`/handle objects. Startup validates launch specs and readiness; shutdown uses bounded
  terminate/join/kill escalation, reaps the child, stops timers/queues, clears callbacks, and is idempotent.
- Preserve platform exit codes and expose actionable startup errors. Do not convert serialization/start failures to an
  unexplained success or “Unknown error” when context exists.
- Child-output transports are bounded and non-blocking for producers. Drain them in bounded batches regardless of page
  visibility: use a short interval while messages flow and back off to a finite maximum interval while idle. Truncate
  oversized messages and drop excess burst output at the documented queue boundary rather than retaining it
  indefinitely. Presentation may remain lazy after collection.
- Process targets do not touch GUI objects. Queue/monitor callbacks cross to the owning Qt thread through the
  established timer/signal boundary.
- A timer without a QObject parent requires an explicit durable Python owner and `dispose()` path. Never rely on wrapper
  finalization for process or timer cleanup.
- Temporary output files/streams close on every success and error path; avoid unbounded queues and blocking reads.

## Verification

- Test invalid specs, failed spawn, early exit, normal output, bounded stop escalation, repeated dispose, exact-child
  cleanup, and no residual timers/threads/handles.

# Embedded runtime guidance

- `Core` supplies shared multiprocessing runtime machinery, bounded output transport, and application tun2socks. External
  Core owns its separate direct `subprocess.Popen`; neither layer owns controller, repository, UI, or protocol policy.
- A launch spec is the validated spawn boundary, not semantic connection readiness. The asynchronous connection
  transaction observes endpoints/process survival and commits later; retain synchronous waiting only as a compatibility
  path where callers explicitly require it.
- A runtime owns and reaps its exact child, process handle, monitor/drain timers, queues, callbacks, and feeder resources.
  Stop is bounded, escalates only that child when needed, closes handles, and is safe after partial start or repetition.
- Child targets never touch Qt widgets. Output transport is non-blocking and bounded in message size, pending volume, and
  per-turn drain work; draining continues independently of Log-page visibility and backs off only when idle.
- Parentless timers are acceptable only with a durable runtime owner and explicit disposal. Leaving the manager pool
  must not leave timers, callbacks, queues, or process handles alive.
- Verify invalid target/serialization, failed spawn, early exit, readiness compatibility, burst output bounds/backoff,
  normal and forced stop, repeated disposal, and absence of residual children, handles, timers, queues, or callbacks.

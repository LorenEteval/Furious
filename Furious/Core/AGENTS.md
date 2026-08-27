# Embedded process-runtime guidance

## Scope and ownership

- This package supplies the shared `CoreRuntime` machinery for embedded-core multiprocessing workers, bounded log
  transport, and application tun2socks. The separate External Core backend owns its direct `subprocess.Popen`; neither
  package owns controller, repository, page, or protocol-preparation policy.
- `CoreLaunchSpec` is the launch transaction boundary. Validate target and serialization before spawn, distinguish
  starting/running/stopping/failed/exited states, preserve shared semantic exit codes, and keep an actionable
  `startError()` when launch cannot proceed.
- Own and reap the exact multiprocessing child/handle. Shutdown stops monitoring/draining, terminates and joins with a
  bound, escalates to kill and joins again, closes the handle, clears callbacks, and remains safe when repeated or when
  startup only partially succeeded.
- Child targets never touch GUI objects. Output crosses the bounded non-blocking `MsgQueue`; truncate oversized messages,
  cap pending work and per-tick draining, and keep draining independently of page visibility. Do not delay a core launch
  merely to wait for an output reader.
- Parentless queue/monitor timers are intentional only because their runtime owns a durable Python reference and an
  explicit `dispose()` path. Preserve that ownership or replace it with equally clear Qt parentage; never leave a timer,
  queue feeder, callback, or process handle after the runtime leaves the manager pool.

## Verification

- Test invalid serialization/target, failed spawn, early exit, burst output bounds/truncation/backoff, normal stop,
  forced escalation, repeated disposal, and absence of residual children, timers, queues, callbacks, or handles.

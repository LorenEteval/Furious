# Utility process guidance

- This package owns the outer application-process wrapper and exit-code translation; it is not a miscellaneous helper
  namespace and does not own application business/UI policy.
- `AppMainProcess` owns its exact child/runner, signal handlers, auxiliary manager resources, and best-effort crash-log
  attempt. Signal and exception paths tolerate partial startup, preserve the original failure, avoid sensitive logs, and
  perform bounded exact-resource cleanup.
- Verify normal/exception/signal exits, crash-log failure, pre/post application signals, cross-platform spawn, and no
  orphaned child or manager resources.

# Utility process guidance

- This package contains the outer application-process wrapper, not general miscellaneous helpers. Keep its surface small
  and avoid adding business/UI policy that belongs in application, controller, or service layers.
- `AppMainProcess` owns its exact child/application runner, signal handlers, exit-code translation, and crash-log
  attempt. Signal/exception paths must tolerate partial application startup.
- Crash reporting is best effort but must not hide the original exception; avoid logging secrets from application
  history and bound all cleanup before exit.
- Do not introduce process-name cleanup or unmanaged `multiprocessing.Manager`/thread resources. Explicitly shut down
  auxiliary process resources when no longer needed.
- Preserve semantic `ApplicationRunner.ExitCode` values and cross-platform spawn behavior.

## Verification

- Test normal exit, assertion/unknown exception mapping, crash-log write failure, signals before/after app creation, and
  no orphaned manager/child resources.

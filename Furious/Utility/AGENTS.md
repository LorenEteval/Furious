# Outer process guidance

- This package owns the parent-side application process wrapper and crash/exit translation; it is not a miscellaneous
  helper namespace and does not own application business, repository, runtime, or UI policy.
- `AppMainProcess` owns one exact Qt child process plus a small synchronized crash-log result. Do not introduce a
  `multiprocessing.Manager` or another auxiliary child merely to communicate status.
- Install signal and exception handling so it works before and after application construction. Preserve semantic
  `ApplicationRunner.ExitCode` values, the original exception/traceback, and best-effort crash logging; a crash-log write
  failure cannot replace the primary failure.
- The parent joins only its child, then creates the fallback Qt application/message box only for a nonzero result. Keep
  source and platform spawn behavior viable and do not search for or terminate processes by name.
- Verify normal, exception, assertion, signal, and crash-log-failure paths; pre/post application signals; command-line
  dispatch; cross-platform spawn; exact child joining; and absence of manager servers or orphaned resources.

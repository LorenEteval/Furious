# Outer process guidance

- `Utility` owns the child-side wrapper used by the outer application process and crash/exit translation. It is not a
  miscellaneous helper namespace and does not own application composition, repositories, runtimes, or UI policy.
- `AppMainProcess` owns one exact Qt application child and one small synchronized crash-log result. Do not add a
  `multiprocessing.Manager` or auxiliary child merely to communicate status, and preserve the platform’s explicit spawn
  behavior.
- Exception and signal handling must work before and after application construction. Preserve semantic
  `ApplicationRunner.ExitCode` values, original exception/traceback context, and best-effort crash logging; a log-write
  failure never replaces the primary failure.
- The parent entry point joins only the child it created and shows the fallback Qt report only for a nonzero result.
  Never discover or terminate processes by name, and keep normal/source/packaged command-line entry points equivalent.
- Verify normal return, exception, assertion, signal, pre-application failure, crash-log failure, command dispatch,
  cross-platform spawn, exact child joining, and absence of manager servers or orphaned resources. If this process
  topology changes intentionally, rewrite this guide rather than layering another supervisor over the old one.

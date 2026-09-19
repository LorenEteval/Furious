# Outer process guidance

Inherit `Furious/AGENTS.md` and its root ancestor. This scope preserves the exact outer child-process/crash
protocol and is not a general-purpose utility bucket.

- `Utility` owns the child-side wrapper used by the outer application process and crash/exit translation. It is not a
  miscellaneous helper namespace and does not own application composition, repositories, runtimes, or UI policy.
- `AppMainProcess` owns one exact Qt application child and one small synchronized crash-log result. Do not add a
  `multiprocessing.Manager` or auxiliary child merely to communicate status, and preserve the platform’s explicit spawn
  behavior.
- Exception reporting must work before and after application construction. The child runs the supplied application
  factory; the parent must not construct a Qt application to pass across the process boundary. Signal handlers are
  installed only after the factory returns, so pre-construction signals are outside this wrapper's handler coverage.
  Preserve semantic exit codes and original exception/traceback context; crash-log failure is secondary.
- The parent entry point joins only the child it created and shows the fallback Qt report only for a nonzero result.
  Never discover or terminate processes by name, and keep normal/source/packaged command-line entry points equivalent.
- Shared crash status is a synchronized Boolean plus the child's semantic exit result; set the flag only after the
  diagnostic file is written successfully. Text may include retained logs plus a traceback, so the Boolean channel
  does not bound the crash file's size or sanitize its contents. Keep crash-write failure separate from the primary
  exit result: the flag proves only that a file write completed, not that the child succeeded or the report can be
  parsed as an exit protocol. Test reporting both with and without a constructed application/log manager.
- Fallback presentation runs in the parent after a nonzero child result. It constructs a Qt application for the
  report but does not call the ordinary application `run()` initialization. Do not assume plugin, storage, controller,
  or main-window initialization occurred merely because the fallback has a Qt application. Keep its constructor
  dependencies in failure-path tests and preserve the original result when evolving reporting failures.
- Verify normal return, exception, assertion, signal, pre-application failure, crash-log failure, command dispatch,
  cross-platform spawn, exact child joining, and absence of manager servers or orphaned resources. If this process
  topology changes intentionally, rewrite this guide rather than layering another supervisor over the old one.
  `tests/test_application_process.py` and `tests/test_interface.py` are the contract anchors.

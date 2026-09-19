# External Core guidance

Inherit `Furious/Backends/AGENTS.md` and its ancestors; consult Plugins for capability contracts. This file
preserves the intentionally different direct-subprocess scope for user-selected executables.

## Structured executable boundary

- External Core represents one user-selected local executable, not an embedded protocol binding. Keep executable path,
  optional working directory, argument vector, environment overrides, HTTP/SOCKS endpoints, shutdown timeout, remote
  TUN address, and application-tun2socks opt-in distinct while preserving unknown top-level fields.
- Loading is observational: do not silently absolutize or rewrite relative paths. Validation before spawn owns path
  existence/type, argument and environment types/NULs, endpoint requirements, and a finite bounded shutdown timeout.
- Execute an argument vector with `shell=False`. Never concatenate a shell command, search or kill by process name, or
  log arguments/environment values that may contain credentials.

## Runtime and TUN ownership

- One runtime owns its exact `Popen`, stdout/stderr pipes and readers, watcher, partial-line buffer, exit callback, and
  reaping path. Shutdown terminates that process, uses only platform-specific escalation for its PID when necessary,
  kills as a last resort, joins readers, and remains bounded and idempotent after partial startup. Register each
  successfully started reader immediately; a later reader/watcher startup failure unwinds the child and every pipe,
  including pipes with no reader. Disposal is terminal and must reject new process acquisition.
- Keep execution liveness, configured proxy endpoints, and semantic readiness distinct. An immediate or later exit is
  interpreted once at this runtime boundary and retains actionable code/reason context for the shared startup workflow.
- Application tun2socks is an explicit profile capability. It requires a usable SOCKS endpoint and a separate remote
  server address for bypass routing; an executable path is never a network destination, and this backend never invents
  native core TUN support. Subscription decoding must continue to reject executable profiles.
- This is a mapping-only protocol: its explicit type discriminator selects local executable configuration, it
  declares no URI schemes, and portable URI/QR export may return no result. Shared import/export UI must preserve
  that capability absence. Endpoint readiness checks the configured proxy; it does not validate an arbitrary
  executable's remote service. Endpoint metadata does not configure the executable or cause it to open a listener;
  users remain responsible for matching that metadata to the executable's own configuration.
- Verify unknown-field and editor round trips, path/argument/environment validation, paths with spaces,
  immediate-exit failure, complete and partial output, exact callback/reader/watcher cleanup, repeated stop/dispose,
  TUN opt-in and remote-address handling, subscription rejection, and transient editor destruction. Start with
  `tests/test_external_core.py` and `tests/test_backend_editor_contract.py`. Exercise a child that remains alive
  after escalation and readers/watchers that outlast their joins. A failed final reap is a cleanup failure to report;
  clearing the runtime's process/thread references must not be used as evidence that those resources exited.
  Retain an independent reference in failure tests so an empty runtime field cannot make the test pass. Direct-child
  exit also does not prove that descendants closed inherited pipes. `Process.py` currently clears references after
  unsuccessful waits; this is a cleanup-contract gap. A repair must retain observable outstanding resources and
  coordinate failure semantics with `Furious/Service/RuntimeLease.py`, without broad process-name cleanup.

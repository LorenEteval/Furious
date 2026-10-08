# External Core guidance

Inherit the [nearest parent guide](../AGENTS.md). This backend owns structured executable input and direct
subprocess execution. Configured endpoints describe readiness targets without configuring the executable. Read
`Furious/Backends/ExternalCore/Process.py` with `tests/test_external_core.py`; paths are relative to this
source tree's root.

## Structured executable boundary

- External Core represents one user-selected local executable, not an embedded protocol binding. Keep executable path,
  optional working directory, argument vector, environment overrides, HTTP/SOCKS endpoints, shutdown timeout, remote
  TUN address, and application-TUN opt-in distinct while preserving unknown top-level fields.
- Loading is observational: do not silently absolutize or rewrite relative paths. An explicitly chosen file may
  be resolved by the editor, while opening a stored document must preserve its path text. The chooser's nested
  event loop also requires a surviving native field tree before write-back. Validation before spawn owns path
  existence/type, argument and environment types/NULs, endpoint requirements, and a finite bounded shutdown timeout.
  Reject NaN, infinities, Booleans, and integer-to-float overflow before process wait APIs. Preserve the accepted
  finite interval and prove rejection behavior directly; equivalent-looking comparisons are not a substitute
  for non-finite and overflow regression cases. Check `shutdownTimeout()` and the launch boundary
  with `tests/test_external_core.py`; serializability does not prove a value is a usable timeout.
- Execute an argument vector with `shell=False`. Environment overrides apply to a copy of the inherited process
  environment; preparation must not mutate the host's `os.environ`. Never concatenate a shell command, search or
  kill by process name, or log arguments/environment values that may contain credentials.

## Runtime and TUN ownership

- One runtime owns its exact `Popen`, stdout/stderr pipes and readers, watcher, partial-line buffer, exit callback, and
  reaping path. Shutdown terminates that process, uses only platform-specific escalation for its PID when necessary,
  kills as a last resort, joins readers, and remains bounded and idempotent after partial startup. Register each
  successfully started reader immediately; a later reader/watcher startup failure unwinds the child and every pipe,
  including pipes with no reader. Disposal is terminal and must reject new process acquisition.
- Keep execution liveness, configured proxy endpoints, and semantic readiness distinct. An immediate or later exit is
  interpreted once at this runtime boundary and retains actionable code/reason context for the shared startup workflow.
- Application TUN is an explicit profile capability. It requires a usable SOCKS endpoint and a separate remote
  server address for bypass routing; an executable path is never a network destination, and this backend never invents
  native core TUN support. Subscription decoding must continue to reject executable profiles.
  The stored/API opt-in retains its tun2socks name for compatibility, but the application preference chooses the
  engine. Validate its SOCKS transit specification for either engine without importing the executable's private schema.
  Changing its presentation label must not rename the stored opt-in, infer native TUN, or select an application engine.
- The embedded backends' JSON serialization helper is not this launch boundary: External Core passes a structured
  executable/argument/environment specification to `Popen`. Validate through `validateProcess()` and the launch path,
  including non-finite timeout rejection, rather than assuming a serializable mapping is safe or executable.
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
  exit also does not prove that descendants closed inherited pipes. Review `Process.py` and
  `Furious/Service/RuntimeLease.py` together: incomplete shutdown must preserve observable outstanding resources
  and an owner able to finish cleanup, without broad process-name cleanup.

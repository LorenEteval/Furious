# External Core guidance

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
  kills as a last resort, joins readers, and remains bounded and idempotent after partial startup.
- Application tun2socks is an explicit profile capability. It requires a usable SOCKS endpoint and a separate remote
  server address for bypass routing; an executable path is never a network destination, and this backend never invents
  native core TUN support. Subscription decoding must continue to reject executable profiles.
- Verify unknown-field and editor round trips, path/argument/environment validation, paths with spaces, immediate-exit
  failure, complete and partial output, exact callback/reader/watcher cleanup, repeated stop/dispose, TUN opt-in and
  remote-address handling, subscription rejection, and transient editor destruction. Update this guide when the process
  contract evolves rather than preserving today’s implementation mechanically.

# External Core guidance

- This backend models a user-selected local executable, not a protocol-specific embedded binding. Keep executable path,
  optional working directory, argument vector, environment overrides, HTTP/SOCKS endpoints, shutdown timeout,
  TUN remote address, and application-tun2socks opt-in as distinct fields while preserving unknown top-level fields.
- Path normalization is an explicit editor/user operation; loading a document does not silently rewrite relative paths.
  Validate absolute executable/working-directory paths, argument/environment types and NULs, endpoint requirements, and
  the bounded shutdown timeout before spawn.
- Execute an argument vector with `shell=False`. The runtime owns one exact `Popen`, stdout/stderr readers, watcher, and
  line buffer; terminate, platform-escalate when required, kill, join readers, and reap within the configured shutdown
  contract. Never concatenate a shell command, search by process name, or log the inherited/overridden environment.
- Application tun2socks is an explicit profile capability requiring a valid SOCKS endpoint and remote address for bypass
  routing. This backend never invents a native core TUN. Subscription decoders must not import executable profiles.
- Verify unknown-field/mapping round trips, path/argument/environment validation, spaces in paths, mocked spawn and
  immediate-exit failure, complete plus partial-line output, bounded termination escalation, unexpected exit callbacks,
  exact reader/watcher cleanup, TUN validation/resolution, subscription rejection, and repeated editor/dialog destruction.

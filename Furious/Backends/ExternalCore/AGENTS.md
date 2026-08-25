# External Core guidance

- This backend is protocol-agnostic. Keep executable, working directory, argument vector, environment, proxy endpoints,
  shutdown timeout, and application-tun2socks choice as distinct fields; preserve unknown top-level fields.
- Execute with `shell=False`, own the exact `Popen` plus readers/watchers, and terminate/kill/reap it within the configured
  shutdown contract. Never concatenate a shell command or log environment secrets.
- Application tun2socks is explicit and requires a valid remote address; this backend never invents a native core TUN.
- Verify mapping/unknown-field round trips, mocked spawn/start/stop failures, output-reader cleanup, TUN validation, and
  repeated editor/validation-dialog destruction.

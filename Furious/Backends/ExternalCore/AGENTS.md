# External Core backend guidance

## Configuration contract

- External Core is protocol-agnostic. Keep executable path, working directory, argument vector, environment mapping,
  proxy endpoints, shutdown timeout, and application-tun2socks choice as distinct fields.
- The editor projects these known fields but must preserve unknown top-level fields. Loading is observational and an
  untouched save must not normalize paths, arguments, environment variables, or future fields.
- Execute with `shell=False`. Never concatenate arguments into a shell command or log credentials/environment secrets.

## Runtime and TUN ownership

- Own the exact `Popen` instance and its reader/watcher resources. Startup failure and shutdown must close callbacks,
  terminate, kill if necessary, and reap the exact child within configured bounds.
- Application tun2socks is explicit and requires a valid remote address. This backend does not inject a native core TUN
  block or infer protocol-specific behavior.
- Validation dialogs are transient asynchronous UI: use the established `open()` ownership path and release them on
  destruction without retaining them in backend or plugin registries.

## Code review and verification

- Flag shell execution, ambiguous string arguments, inherited transient callbacks, unknown-field loss, and unbounded
  child-process cleanup.
- Use fully mocked subprocess and host-network operations. Test mapping round trips, unknown-field preservation,
  validation failures, output-reader shutdown, tun2socks validation, and repeated editor/dialog destruction.

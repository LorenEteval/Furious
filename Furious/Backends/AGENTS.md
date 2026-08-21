# Backend and core-integration guidance

- A backend owns protocol parsing/export, editor factories, runtime materialization, process integration, statistics,
  validation, and native-TUN capability for its core. Register these through plugin capabilities instead of adding
  shared-manager conditionals.
- The JSON/document submitted to a core is the runtime authority. Build it from a deep/runtime copy; never mutate the
  persisted profile while preparing connection, routing, logging, testing, or TUN state.
- Preserve full user-authored core documents and unknown supported fields. Report a lossless-compatibility failure
  instead of silently compiling or deleting unsupported configuration.

## Structured editor contract

- `factoryToInput()` is normally observational: loading an editor must not add defaults or otherwise mutate the
  configuration document unless that backend has a documented compatibility normalization, such as Xray transport
  aliases.
- `inputToFactory()` writes only fields represented by the editor and returns whether it actually changed the
  document. Do not materialize an absent effective default merely because the editor displays it.
- Display unknown future string values exactly and preserve them on an untouched load/save round trip. Editing one
  known leaf must preserve unknown fields and unknown siblings elsewhere in the same object.
- A deliberate user switch to a supported tagged variant may replace the incompatible active variant. Keep unrelated
  extension fields, and do not treat a fallback page used for display as a user selection.

## Native TUN policy

For a normal connection:

- If the Furious native-TUN option is enabled, replace any runtime native TUN with the generated TUN; mark TUN handled
  and do not start application tun2socks.
- If the option is disabled and the user document contains native TUN, preserve it unchanged; mark TUN handled and do
  not start tun2socks.
- If neither exists, do not inject native TUN; global TUN mode may use tun2socks.
- Proxy-only operations such as speed/latency tests explicitly strip native TUN from their own temporary copy.

Never remove an explicit user TUN merely because an application toggle is off, and never run native TUN plus application
tun2socks together.

## Runtime and UI

- Core runtimes expose actionable `startError()`, exact resource ownership, bounded startup/shutdown, and deterministic
  cleanup. Process-backed runtimes additionally own and reap their exact child process. Keep platform exit codes
  semantically intact.
- Keep runtime modules importable without constructing editor widgets. Use literal, discoverable lazy
  imports/registrations so Nuitka includes every editor family without per-editor command changes.
- Backend editors follow `Furious/Qt/AGENTS.md`; factories create fresh transient editors and registries retain
  factories/classes, not editor instances.

## Verification

- Test URI/mapping round trips, malformed input, runtime document equality, original-document immutability, all
  native-TUN matrix cases, proxy-only stripping, failed core startup, and cleanup.

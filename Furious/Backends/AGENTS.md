# Backend guidance

## Responsibility and extension

- A backend plugin owns the protocol/document types, parsing/export, structured editor factories, runtime factory,
  validation, and any supported routing, native-TUN, statistics, settings, actions, or assets. Shared orchestration asks
  capabilities; it does not branch on `coreName()`.
- `Backends.Configuration` and URI codec modules contain compatibility-era shared document implementations. They may be
  refactored, but protocol behavior must remain owned and dispatched by capabilities, with model/API layers free of
  concrete backend imports.
- The full core document is the runtime authority. Prepare routing, logging, probes, local endpoints, and TUN on an
  explicit copy and preserve the persisted profile plus unknown supported fields. Fail visibly when a lossless mapping
  or valid runtime document cannot be produced.
- Keep runtime/configuration modules importable without constructing Qt editors. Official plugin type imports remain
  lazy, registrations literal enough for Nuitka discovery, and every editor/runtime factory returns a fresh object that
  the registry does not retain.

## Structured editor contract

- Loading is observational except for a narrowly documented compatibility migration. Saving changes only represented
  fields the user changed, preserves unknown siblings/top-level data, and does not materialize absent effective defaults.
- Unknown future enum/tag/string values remain visible and survive an untouched round trip. An explicit switch to a
  known tagged variant may replace only the incompatible variant data owned by that control.
- Validation separates malformed external/persisted input from internal invariant failure and retains backend/core
  context without logging credentials or full configuration documents.

## TUN and runtime ownership

- Global TUN mode first asks the selected factory to prepare native TUN on the runtime copy. When managed native TUN is
  enabled it replaces runtime native-TUN configuration; when disabled, any explicit user native TUN is preserved. Either
  native case suppresses application tun2socks. Only a configuration with no native TUN may opt into the fallback.
- Treat presence of malformed explicit native TUN as authoritative so the core reports it; never silently change the
  networking mode or run two TUN implementations. Proxy/download probes explicitly strip TUN from their own copy.
- A `CoreRuntime` owns exact resources, publishes an actionable `startError()`, and has bounded idempotent cleanup after
  success or partial failure. Process-backed implementations additionally terminate/kill/reap only their exact child.

## Verification

- Test document/mapping/URI round trips, legacy/malformed/unknown input, untouched editor observation, persisted
  immutability, exact runtime document, the complete TUN matrix and probe stripping, start failure/rollback/cleanup,
  import/discovery, and repeated editor/dialog destruction.

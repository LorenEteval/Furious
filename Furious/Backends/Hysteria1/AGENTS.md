# Hysteria1 backend guidance

## Compatibility boundary

- Hysteria1 is an independent legacy backend with its own flat client schema and `hysteria://` share-link behavior.
  Do not import Hysteria2 nested configuration, obfuscation, or native-TUN assumptions into it.
- Its structured editor follows the shared observational-load/minimal-write contract. Unknown future string values in
  combo-backed fields remain visible and survive an untouched round trip.
- Preserve existing tolerant handling of malformed legacy field types unless a deliberate compatibility migration is
  part of the task; do not silently rewrite valid user values while loading.

## Runtime and assets

- Runtime setup owns Hysteria1-specific MMDB, geosite, and rule assets. Keep asset preparation and failure cleanup in
  this backend rather than shared connection managers.
- Proxy-only tests operate on a copy, set their temporary proxy listener, and must not alter the stored profile.

## Code review and verification

- Flag accidental reuse of Hysteria2 keys, loss of unknown flat fields, or editor factories retained as live widgets.
- Test URI and mapping compatibility, unknown combo values, runtime document immutability, asset failures, process
  cleanup, and transient editor destruction.

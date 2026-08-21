# Xray backend guidance

## Documents and editors

- The full Xray JSON document is authoritative. Structured editors project only the selected `proxy` outbound,
  transport, and TLS fields; preserve every unrelated inbound, outbound, routing field, and extension.
- Transport and security loading preserves unknown `network` or `security` strings so they remain visible and survive
  an untouched round trip.
- `http`, `gun`, and `mkcp` are legacy transport aliases that the editor intentionally normalizes to `h2`, `grpc`, and
  `kcp` while loading. Keep this compatibility rewrite explicit and covered by tests.
- Selecting a different known transport or security mode may replace incompatible represented settings. Preserve
  unknown sibling settings that the selected editor does not own.

## Runtime, routing, and TUN

- Prepare routing, logging, tests, and native TUN only on runtime copies. Keep the selected profile document intact.
- With Xray native TUN enabled, replace runtime TUN inbounds with the generated inbound. With it disabled, preserve and
  recognize user TUN inbounds. Proxy-only tests explicitly strip TUN.
- Xray API statistics, routing assets, and transient asset/routing windows belong to this backend. Keep window owners
  explicit and never register live editor or dialog instances globally.

## Code review and verification

- Flag editor loading that mutates configuration outside the documented transport-alias normalization or materializes
  unrelated defaults.
- Test URI/mapping round trips, unknown transport/security preservation, routing and TUN runtime-copy behavior, asset
  failure cleanup, and transient editor/window destruction.

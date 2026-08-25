# Xray guidance

- The full Xray JSON document is authoritative. Editors project selected outbound/transport/TLS fields and preserve
  unrelated inbounds, outbounds, routing, extensions, and unknown transport/security values.
- Loading may intentionally normalize legacy transport aliases `http`, `gun`, and `mkcp` to `h2`, `grpc`, and `kcp`;
  keep this sole compatibility mutation explicit and tested.
- Routing, logging, testing, and native TUN are prepared on copies. Native-TUN replacement/preservation and proxy-only
  stripping follow the parent backend contract, including multiple user TUN inbounds.
- This backend owns API statistics, routing assets, and its transient asset/routing UI; retain owners explicitly and
  never register live windows/editors globally.
- Verify document/URI round trips, unknown and alias behavior, routing/TUN copies, asset failures, process cleanup, and
  transient window destruction.

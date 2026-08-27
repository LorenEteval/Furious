# Bundled extension guidance

- `Extensions` contains host-shipped plugins that are not proxy backends. They implement the same public plugin API and
  lifecycle as entry-point plugins; do not give them privileged side channels into repositories, controllers, or UI.
- `StandardSubscriptionPlugin` owns standard subscription decoding only. Decoders convert untrusted bytes into neutral
  `SubscriptionResult` items; `SubscriptionImportService` owns profile construction/metadata and
  `SubscriptionManager` owns reconciliation and persistence.
- Decoder probing is ordered and failure-isolated. Return `None` when a format does not match, validate sizes/types and
  bound nesting/work for matched input, preserve useful names/upstream IDs, and never log complete payloads or links.
- Keep bundled extension imports deterministic, side-effect-light, and discoverable by source and Nuitka builds. Test
  format selection/fallback, malformed and secret-bearing payloads, stable duplicate identity inputs, plugin rollback,
  and absence of repository/UI mutation during decoding.

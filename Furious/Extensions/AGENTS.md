# Bundled extension guidance

- `Extensions` contains host-shipped plugins that are not proxy runtimes. They register through the same public API and
  lifecycle as entry-point plugins and receive no private repository, controller, or UI side channel.
- `StandardSubscriptionPlugin` owns format recognition and decoding only. A decoder returns an immutable neutral
  `SubscriptionResult`; profile construction/metadata belongs to `SubscriptionImportService`, and group reconciliation,
  request generations, timers, persistence, and post-commit effects belong to the subscription service/repository path.
- Decoder probing is priority-ordered and failure-isolated. Return `None` when a format does not match, validate the
  declared result shape, preserve useful names/upstream IDs, and never log a complete payload or link. Current standard
  formats are linear plain/Base64 share-link envelopes; introduce explicit size/depth/work limits before adding richer
  recursive or nested formats.
- Keep bundled registration deterministic, side-effect-light, and discoverable in source, wheel, and Nuitka builds.
  Test format selection/fallback, malformed and secret-bearing input, duplicate occurrence identity, unsupported
  subscription protocols, registration rollback, and absence of repository/UI mutation during decoding. Evolve this
  guide with the decoder contract rather than giving bundled formats permanent special treatment.

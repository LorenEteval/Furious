# Bundled extension guidance

Inherit `Furious/AGENTS.md` and its root ancestor; consult Plugins for capability and registration contracts.
This scope covers host-shipped non-runtime plugins and must not gain private authority merely because the code
is bundled.

- `Extensions` contains host-shipped plugins that are not proxy runtimes. They register through the same public API
  and lifecycle as entry-point plugins. New extension contracts must be usable without private
  repository/controller/UI access; bundled location is not permission to bypass the public boundary.
- `StandardSubscriptionPlugin` owns format recognition and decoding only. A decoder returns an immutable neutral
  `SubscriptionResult` envelope; nested mappings are not necessarily deeply immutable. Profile construction/metadata
  belongs to `SubscriptionImportService`, and group reconciliation, request generations, timers, persistence, and
  post-commit effects belong to the subscription service/repository path.
- Automatic detection probes decoders by priority. An explicit decoder ID restricts dispatch to that decoder;
  an unknown ID or a mismatch must not silently resume automatic detection. Return `None` for a mismatch. Recognizing
  a share-link envelope does not validate its URI schemes or protocols; the importer owns that decision. Preserve useful names/upstream IDs and never log a complete payload or link. Current
  standard formats are plain/Base64 share-link envelopes; linear parsing is not an input-size bound. Introduce
  explicit size/depth/work limits before adding richer recursive or nested formats.
- Worker safety is a property of the whole preparation path. Standard decoders opt in, but the selected protocol
  handlers must also opt in after their shared state, caches, and Qt use are audited. Preserve the GUI compatibility
  fallback for unclassified capabilities; a safe envelope decoder cannot authorize an unsafe downstream parser.
- Decoder output is descriptive, not a repository transaction. Supplied names and upstream IDs are input to profile
  construction, not permission to overwrite local identity or grant remote ownership. It cannot mutate a group,
  cancel tests, reconnect, or publish UI state; those decisions remain at the import/manager commit boundaries.
  Test recognized-empty, wholly unsupported, and mixed-validity payloads separately so decoder matching is not
  confused with successful profile import or authorization to clear an existing group. The standard share-link
  decoder treats blank/comment-only content as a mismatch; an empty result from a different decoder needs its own
  import/reconciliation policy, not an assumption borrowed from this format.
- Keep bundled registration deterministic, side-effect-light, and discoverable in source, wheel, and Nuitka builds.
  Test format selection/fallback, malformed and secret-bearing input, duplicate occurrence identity, unsupported
  subscription protocols, registration rollback, and absence of repository/UI mutation during decoding. Evolve this
  guide with the decoder contract rather than giving bundled formats permanent special treatment. Use
  `tests/test_plugin_architecture.py` and `tests/test_subscription_scalability.py`; decoder success is not
  authorization to import a protocol whose descriptor excludes subscriptions, such as local executables.

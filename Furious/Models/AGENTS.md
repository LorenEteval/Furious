# Model guidance

- Models are core-neutral Python data and transformations. Do not import Qt, globals, controllers, repositories,
  services, plugins, or concrete backends into this layer.
- `CoreConfiguration` is a dict-like connection document whose construction is deliberately non-throwing; unsupported
  or malformed input is represented by an empty object plus `constructionError()`. Keep serialization failure context
  separate in `serializationError()`.
- `ServerProfile` composes an independent connection copy with `ProfileMetadata`. Keep metadata and connection documents
  distinct through load/save/copy: display labels, subscription ownership, latency/speed, and annotations are not core
  configuration fields.
- Preserve unknown metadata and legacy aliases across migrations. A manual independent copy receives a new `profileId`
  and loses subscription ownership; a runtime `deepcopy()` preserves identity metadata because it is not a new domain
  profile.
- `ensureProfile()` is normalization, not cloning: when given an existing `ServerProfile`, metadata arguments update
  that same object. Use `independentCopy()` when caller intent is to create a new stored profile, and a
  deep runtime copy when identity must be preserved without mutating persistence.
- `profileId`, subscription source, `subscriptionProfileKey`, connection fingerprint, row position, and display text are
  separate identities. Fingerprints are deterministic only for supported JSON-compatible documents and failures remain
  explicit.
- Protocol construction/export dispatch belongs to plugin capabilities. Model/backend compatibility shims may remain
  while callers migrate, but do not add new protocol branches to the model layer.
- Verify malformed plus legacy/current/unknown-field round trips, copy and identity semantics, deterministic
  fingerprints, metadata/connection separation, serialization diagnostics, and capability-based construction/export.

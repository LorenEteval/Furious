# Model guidance

## Domain shape and identity

- Models are core-neutral Python data and transformations. Do not import Qt, globals, repositories, services,
  controllers, plugin registries, or concrete backends into this layer.
- `CoreConfiguration` is a dict-like connection document whose construction is deliberately non-throwing: unsupported
  or malformed input becomes an empty object with `constructionError()`. Keep construction and serialization errors
  distinct and preserve useful context through callers.
- `ServerProfile` composes an independent connection document with `ProfileMetadata`. Display name, stable profile ID,
  subscription ownership/key, latency, speed, annotations, and local flags never become core-configuration fields.
- Preserve unknown metadata and legacy aliases across load/save. `independentCopy()` creates a manual profile with a new
  ID and no subscription owner; a runtime `deepcopy()` preserves identity while isolating mutable preparation.
- `ensureProfile()` normalizes rather than clones: metadata arguments update an existing profile. Use an independent
  copy for a new stored item and a runtime copy when logical identity must survive without mutating persistence.
- Profile ID, object identity, subscription source/key, connection fingerprint, display text, and row position answer
  different questions. Fingerprints require deterministic JSON-compatible connection data and fail explicitly.

## Compatibility and verification

- Protocol construction/export belongs to plugin capabilities. Compatibility shims may remain while callers migrate,
  but new protocol-name branches do not belong in core models.
- Verify malformed/current/legacy/unknown-field round trips, metadata/connection separation, copy/identity semantics,
  deterministic fingerprints, construction/serialization diagnostics, and capability-based import/export. Revise this
  guide with intentional domain changes; do not preserve a legacy identity rule after migration replaces it.

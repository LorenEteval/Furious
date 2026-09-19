# Model guidance

Inherit `Furious/AGENTS.md` and its root ancestor. This scope owns dependency-light domain shape and identity,
never live persistence, Qt presentation, plugin discovery, or workflow execution.

## Domain shape and identity

- Models are core-neutral Python data and transformations. Do not import Qt, globals, repositories, services,
  controllers, plugin registries, or concrete backends into this layer.
- `CoreConfiguration` is a dict-like connection document whose construction is deliberately non-throwing: unsupported
  or malformed input becomes an empty object with `constructionError()`. Keep construction and serialization errors
  distinct and preserve useful context through callers. Successful generic mapping construction is not protocol
  validation: backend acceptance belongs to the selected capability, and serializability is a separate check.
- `ServerProfile` separates connection data from `ProfileMetadata`. `fromConfiguration()` copies a bare configuration
  but returns an already-supplied profile unchanged; the direct dataclass constructor does not imply copying. A type
  conversion is therefore not an isolation boundary. Choose explicit copy semantics before independent editing or
  worker handoff. Display name, profile ID, subscription ownership/key, latency, speed, annotations, and local flags
  never become core fields.
- Preserve unknown metadata and legacy aliases across load/save. `independentCopy()` creates a manual profile with a new
  ID and no subscription owner; a runtime `deepcopy()` preserves identity while isolating mutable preparation.
- Treat serialized and plugin-provided mappings as untrusted values. Normalize only documented compatibility aliases,
  retain unknown forward-compatible fields, and keep construction diagnostics available without mutating repositories
  or invoking a backend runtime.
- `ensureProfile()` normalizes rather than clones: metadata arguments update an existing profile. Use an independent
  copy for a new stored item and a runtime copy when logical identity must survive without mutating persistence.
- Profile ID, object identity, subscription source/key, connection fingerprint, display text, and row position
  answer different questions. Fingerprints cover only the connection document, not user metadata; they require
  deterministic JSON-compatible values and reject non-finite numbers. A metadata edit need not invalidate connection
  testing. Equal fingerprints do not imply equal profile IDs: independently stored profiles may describe identical
  connections. A fingerprint also cannot distinguish an old request from a newer request for the same document;
  workflow generation/cancellation remains the caller's responsibility. Do not merge metadata, ownership, or
  selection merely to deduplicate execution work.
- Subscription membership (`subscriptionSource`) and remote ownership (`subscriptionManaged` plus its matching key)
  are separate. Legacy migration may infer ownership where the flag was absent; current locally grouped profiles
  must remain local. Preserve that distinction through copies, moves, and metadata aliases.

## Compatibility and verification

- Protocol construction/export belongs to plugin capabilities. Profile mapping access and `toJSONString()` expose
  the connection document, not a complete profile record; persistence must encode metadata explicitly through its
  repository contract. A URI is the selected codec's projection. Compatibility shims may remain while callers
  migrate, but new protocol-name branches do not belong in core models.
- Verify malformed/current/legacy/unknown-field round trips, metadata/connection separation, copy/identity
  semantics, deterministic fingerprints, construction/serialization diagnostics, and capability-based import/export.
  Revise this guide with intentional domain changes; do not preserve a legacy identity rule after migration replaces
  it. `tests/test_models_and_services.py`, `tests/test_repository_contracts.py`, and
  `tests/test_profile_test_jobs.py` exercise these values across persistence and asynchronous consumers.

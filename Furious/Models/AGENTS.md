# Model guidance

- Models are core-neutral Python data and transformations. Do not import Qt, application globals, controllers,
  repositories, services, or concrete backend plugins.
- Preserve meaningful user configuration and unknown metadata fields across load/save/copy. Promote legacy fields
  through explicit, backward-compatible migrations without ambiguous duplicates.
- `ServerProfile` separates connection data from metadata. Stable profile IDs, subscription ownership/key fields,
  display metadata, and connection fingerprints each have distinct semantics; do not substitute row position or display
  text for identity.
- Fingerprints must be deterministic for supported JSON-compatible connection documents. If compatibility requires a
  fallback, make its stability/diagnostics explicit rather than silently changing identity across runs.
- Encoders are the canonical JSON/ujson boundary. Preserve supported mappings/dict subclasses and surface useful failure
  context at the caller boundary.
- `toURI()` dispatch belongs to plugin protocol capabilities; model methods may remain compatibility shims but must not
  grow new protocol-specific branches.

## Verification

- Test legacy/current mappings, unknown-field round trips, copies, deterministic identity, subscription migration,
  malformed serialization, and plugin-based export.

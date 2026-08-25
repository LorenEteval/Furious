# Model guidance

- Models are core-neutral Python data and transformations. Do not import Qt, globals, controllers, repositories,
  services, or concrete backends.
- Preserve user connection data, unknown metadata, and legacy migrations across load/save/copy without duplicate
  meanings. `ServerProfile` keeps metadata and connection documents distinct.
- Stable profile IDs, subscription ownership/profile keys, display data, and connection fingerprints have separate
  semantics; row position and display text are not identity.
- Fingerprints are deterministic for supported JSON-compatible documents. Export dispatch belongs to plugin protocol
  capabilities; model methods may be compatibility shims but gain no new protocol branches.
- Use the shared JSON/ujson encoders and surface serialization context at the caller boundary.
- Verify legacy/current/unknown-field round trips, copy identity, subscription migration, deterministic fingerprints,
  malformed serialization, and capability-based export.

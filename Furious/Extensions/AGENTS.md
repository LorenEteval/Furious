# Bundled extension guidance

- Extensions are bundled plugins, not exceptions to the plugin contract. Declare stable metadata and contribute
  capability objects through `Furious.Plugins` APIs.
- Store factories, handlers, descriptors, and immutable metadata; never retain transient UI or active runtime instances.
- Subscription decoders recognize and normalize one representation. Treat remote payloads as untrusted, return “not
  matched” distinctly from “matched but invalid,” and leave profile materialization/import policy to the shared
  pipeline.
- Imports must stay lightweight and deterministic so plugin discovery and Nuitka inclusion work without side effects.
- Initialization/shutdown must support registry rollback and repeated process cleanup.

## Verification

- Test discovery order, malformed/ambiguous payloads, capability registration, rollback, and shutdown without network or
  production state.

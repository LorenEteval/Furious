# Plugin architecture guidance

These rules apply to plugin APIs, registries, discovery, and capability dispatch.

## Capability model

- Plugins declare metadata and stable capability objects. Registries index protocol handlers, editor providers, kernel factories, traffic providers, settings/page providers, and subscription decoders by stable IDs.
- Register classes/factories/descriptors and immutable metadata, not transient editors, dialogs, menus, or pages. A provider may create UI on demand, with ownership left to the UI caller.
- Put protocol/core behavior behind the closest capability. Shared UI/services query the registry rather than branching on protocol names or importing official backend internals.
- Keep headless discovery free of eager Qt editor/window imports. Use literal lazy imports in editor factories so static packagers still see every dependency.

## Registry lifecycle and compatibility

- Validate all IDs, schemes, configuration types, kernel types, and duplicates before committing registration. A failed registration must roll back every index and initialized resource.
- The registry owns plugin initialization and shuts plugins down once in reverse registration order. Plugin shutdown must tolerate partial initialization.
- Avoid package-level import cycles: API/model layers stay lower-level; UI-specific imports occur only when a presentation capability is invoked.
- Subscription decoders return data/configuration, never executable or live UI/runtime objects. Keep untrusted subscription payloads outside executable-core capabilities.

## Code review rules

- Flag live transient `QObject` instances stored in a plugin/capability registry.
- Flag new global protocol conditionals or direct official-plugin imports from shared services/UI.
- Flag dynamic string imports that Nuitka cannot discover when literal lazy factories are practical.
- Flag partially registered plugins after validation/initialization failure or non-idempotent shutdown.

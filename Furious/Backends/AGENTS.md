# Backend guidance

## Common backend contract

- A backend plugin owns its configuration/document types, parsing/export, validation, editor factories, runtime factory,
  and supported routing, TUN, statistics, settings, actions, or assets. Shared code asks capabilities and never branches
  on core names.
- The complete persisted core document is authoritative. Prepare logging, routing, endpoints, probes, and TUN on an
  independent runtime copy; failed preparation must not mutate the stored profile.
- Structured editors are partial projections. Loading is observational except for a narrow documented migration;
  untouched save preserves unknown fields/values and absent defaults. Editing one represented leaf preserves unknown
  siblings and unrelated branches.
- Malformed external input returns controlled validation with backend context. Do not create a plausible but different
  profile, and do not log credentials, complete URIs, or documents.
- Configuration/runtime modules stay importable without constructing Qt editors. Plugin registration remains literal
  enough for compiled discovery; editor/runtime factories return fresh objects that the registry does not retain.

## TUN and runtime policy

- Global TUN first asks the selected runtime factory to prepare native TUN on the copy. Managed native TUN replaces the
  backend's runtime TUN; disabled management preserves any explicit user TUN—even malformed, so the core can reject it.
  Either native case suppresses application tun2socks; only absence may permit the fallback.
- Proxy/download-test copies explicitly remove native TUN. A managed-native-TUN preparation failure is terminal rather
  than permission to silently switch implementations.
- A runtime owns its exact process/thread/readers/monitors and publishes an actionable start error. Stop/dispose is
  bounded, idempotent, and correct after partial acquisition.

## Backend-specific invariants

- **Xray:** preserve the full JSON document, including unrelated inbounds/outbounds, routing, logging, extensions, and
  unknown transport/security data. Tagged protocol/transport/TLS editors and URI codecs alter only their projection.
  Compatibility transport-alias migration must be explicit. Xray also owns routing/assets/API statistics and its asset
  environment contract; asset replacement is digest-verified and atomic.
- **Hysteria 1:** retain its legacy flat schema/share-link semantics and tolerated upstream values. Do not import
  Hysteria 2 nested documents, obfuscation, statistics, or native-TUN policy. It uses application tun2socks when needed
  and owns the MMDB/ACL assets consumed by its runtime.
- **Hysteria 2:** preserve the native nested client document, unknown future values, optional-group absence, and tagged
  obfuscation siblings. Its runtime factory owns native-TUN privilege/address/route-exclusion policy and statistics
  capabilities; registries retain descriptors/providers, not request-lifetime monitors/dialogs.
- **External Core:** model a user-selected executable, not a protocol binding. Validate absolute executable/working
  directory, argument/environment types and NULs, endpoints, bounded shutdown timeout, and optional application-TUN
  metadata before spawn. Execute an argument vector with `shell=False`; never log environment/arguments or search by
  process name. The runtime owns one exact `Popen`, readers, watcher, buffering, termination escalation, and reaping.

## Verification

- Test mapping/document/URI round trips; malformed, legacy, and unknown input; untouched-editor preservation; persisted
  immutability; exact runtime/probe documents; every native/application-TUN case; startup/rollback/cleanup; assets and
  statistics where applicable; plugin discovery; and repeated editor/dialog destruction.

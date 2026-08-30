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

## Backend scopes

- Read the selected backend's nested guide before changing its configuration, editor, protocol codec, runtime, TUN,
  routing, asset, statistics, or process behavior. Those child guides own backend-specific compatibility details; keep
  this parent focused on rules that every backend must satisfy.
- A shared backend-contract change must be checked against Xray, Hysteria 1, Hysteria 2, and External Core rather than
  making the most feature-rich backend the implicit default for the others.

## Verification

- Test mapping/document/URI round trips; malformed, legacy, and unknown input; untouched-editor preservation; persisted
  immutability; exact runtime/probe documents; every native/application-TUN case; startup/rollback/cleanup; assets and
  statistics where applicable; plugin discovery; and repeated editor/dialog destruction.

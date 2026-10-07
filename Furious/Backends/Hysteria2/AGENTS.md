# Hysteria 2 guidance

Inherit the [nearest parent guide](../AGENTS.md). This backend owns the nested document, native TUN and server
statistics target. Editing, readiness, TUN and statistics have separate validation boundaries. Read
`Furious/Backends/Hysteria2/Plugin.py` with `tests/test_hysteria2_compatibility.py`; paths are relative to
this source tree's root.

## Native document and editor projection

- The persisted Hysteria 2 client document is authoritative and is submitted to the embedded runtime. The GUI is a
  partial projection. Sharing editor controls does not import Xray configuration rules or make represented
  fields a complete upstream schema.
- Preserve upstream names, optional-group absence, unknown siblings, and future string values. Effective defaults such
  as `realm.ipMode` are presented without materializing them during an untouched save; editing one leaf changes only
  that leaf.
- `obfs.type` selects tagged subtype data. Unknown types remain visible and survive untouched. An explicit switch to a
  known type may remove incompatible subtype branches, but never unrelated document branches.

## TUN, statistics, and lifecycle

- Managed native TUN replaces only the runtime copy’s `tun`. Disabled management preserves any explicit `tun`,
  including malformed data for the core to reject; only absence permits the selected application TUN engine.
  Linux native TUN requires the backend's privilege and server-route-exclusion guarantees. The application's Linux
  privilege-helper path does not grant an embedded native-TUN core the same privileges. Test availability separately.
  Failure to establish required managed server-route exclusions is terminal: use `TUNPreparationError` so registry
  dispatch cannot interpret it as permission to fall back to another TUN path. Probe/download copies always remove
  native TUN. Managed preparation currently resolves server addresses synchronously; asynchronous readiness does not
  make that preparation interruptible. Test resolved addresses and explicit route exclusions as separate inputs to
  the exclusion guarantee; a resolution failure alone does not prove that valid manual exclusions are absent.
  DNS failure and insufficient Linux privilege are independent preparation failures. Manual exclusions can satisfy
  the former route-input requirement but do not grant the latter privilege or prove remote connectivity.
- The statistics provider is a process-lifetime capability; the runtime captures a configured server-API target and
  sampling owns its monitor/query lifetime. API URL, client ID, and authorization secret are distinct from client
  connection credentials. Keep requests bounded, validate counters, and never log the secret or infer statistics
  from merely having a running Hysteria2 process. The configured server statistics target is separate from the
  client's local readiness endpoint; capability availability does not imply a usable target was configured. Queries
  consume cumulative counters without requesting server-side clearing; query failure is distinct from a valid
  response with no entry for the selected client, which currently represents zero counters.
- Capability presence is independent: native TUN, statistics, actions, settings, routing, and protocol editing must
  continue to work or fail through their own declared contracts rather than being inferred from the runtime type.
  This factory does not publish Xray's named/custom routing options. Preserve the no-options case through shared
  routing presentation and runtime preparation; a stored routing preference is not evidence of backend support.
- Verify nested sibling/default preservation, known and unknown values, obfuscation switching, URI/document
  projection preservation, every native/application-TUN and resolution case, probe stripping, readiness/exit cleanup,
  statistics cancellation, and repeated transient editor/settings-dialog destruction. Check the configured
  statistics target independently from the HTTP proxy readiness endpoint: the former queries the server API,
  while the latter only observes the local client listener. A monitor target is captured execution data;
  current UI credentials or an edited profile must not silently replace a running connection's statistics target.
  Keep this guide synchronized with verified upstream schema changes rather than treating current field lists as
  permanent. Start with
  `tests/test_hysteria2_compatibility.py`, `tests/test_native_tun_semantics.py`, and
  `tests/test_backend_editor_contract.py`.

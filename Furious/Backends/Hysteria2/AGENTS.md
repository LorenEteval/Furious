# Hysteria 2 guidance

- The persisted native Hysteria 2 client document is submitted to the embedded core. The GUI is a partial projection,
  not an Xray-shaped compiler or a general upstream-schema normalizer.
- Preserve upstream names and values. `realm.ipMode` currently uses `dual`, `v4`, or `v6`; absent effective defaults and
  unknown future strings remain absent/visible and survive untouched. Optional controls update only their leaf and keep
  unknown siblings.
- `obfs.type` selects tagged subtype data. Display an unknown subtype without rewriting it; an explicit switch to a
  known subtype may replace only incompatible obfuscation data, not unrelated document branches.
- Managed native TUN replaces the runtime copy's `tun`; disabled management preserves any explicit `tun`, including a
  malformed block so the core can reject it, and only absence permits application tun2socks. Native Linux TUN requires
  the privilege and route-exclusion invariants enforced by the factory. Probe/download copies omit `tun`.
- Statistics target/settings/actions are plugin capabilities with process-lifetime descriptors/providers and
  request-lifetime monitors/dialogs. Do not store live monitors, runtimes, or TUN dialogs in the registry.
- Verify nested sibling/default preservation, known/unknown strings, subtype switching, runtime document equality, every
  TUN/privilege/resolution case, probe stripping, statistics cleanup, and transient editor/settings-dialog destruction.

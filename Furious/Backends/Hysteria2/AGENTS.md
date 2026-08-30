# Hysteria 2 guidance

## Native document and editor projection

- The persisted Hysteria 2 client document is authoritative and is submitted to the embedded runtime. The GUI is a
  partial projection, not an Xray-shaped compiler or a general upstream-schema normalizer.
- Preserve upstream names, optional-group absence, unknown siblings, and future string values. Effective defaults such
  as `realm.ipMode` are presented without materializing them during an untouched save; editing one leaf changes only
  that leaf.
- `obfs.type` selects tagged subtype data. Unknown types remain visible and survive untouched. An explicit switch to a
  known type may remove incompatible subtype branches, but never unrelated document branches.

## TUN, statistics, and lifecycle

- Managed native TUN replaces only the runtime copy’s `tun`. Disabled management preserves any explicit `tun`, including
  malformed data for the core to reject; only absence permits application tun2socks. Linux native TUN requires the
  backend’s privilege and server-route-exclusion guarantees. Probe/download copies always remove native TUN.
- Traffic-statistics targets, setting descriptors, and action providers are process-lifetime plugin capabilities;
  monitors, replies, dialogs, and runtimes created from them are request/transient objects and are never registry-owned.
- Verify nested sibling/default preservation, known and unknown values, obfuscation switching, URI/document equality,
  every native/application-TUN and resolution case, probe stripping, readiness/exit cleanup, statistics cancellation,
  and repeated transient editor/settings-dialog destruction. Keep this guide synchronized with verified upstream schema
  changes rather than treating current field lists as permanent.

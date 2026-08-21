# Hysteria2 backend guidance

## Native document and structured editor

- The persisted Hysteria2 client document is the configuration submitted to the embedded core. The compact editor is
  a partial projection, not a compiler or schema normalizer.
- Keep upstream field names and values exact. In particular, `realm.ipMode` uses the native values `dual`, `v4`, and
  `v6`; an absent value has the effective dual-stack default. Unknown future strings remain visible and untouched.
- Optional nested controls edit only their leaf. Preserve unknown siblings, and do not create optional groups or
  effective Gecko packet defaults until the user actually changes the represented value.
- `obfs.type` selects a tagged subtype object. An unknown type must remain visible and preserve its subtype on an
  untouched round trip. An explicit user switch to a known type may remove the previously active incompatible subtype,
  while retaining unrelated extension data.

## Runtime, statistics, and TUN

- Runtime materialization passes a derived full Hysteria2 document to `startFromJSON`; do not translate it through an
  Xray-shaped intermediate representation.
- With native TUN enabled, replace the runtime `tun` block with the generated block. With it disabled, preserve and
  recognize a user `tun` block. Download/probe configurations explicitly omit TUN.
- Keep management/statistics requests bounded and separate from GUI objects. Runtime and worker ownership follows the
  parent backend and Qt lifetime guidance.

## Code review and verification

- Flag `_modified` shadow state, dynamic combo-item accumulation, fallback pages mistaken for user selections, and
  nested writes that replace an entire user object.
- Test known and unknown values, nested sibling preservation, obfs subtype switching, absent-default preservation,
  native-TUN matrices, proxy-only stripping, and editor destruction.

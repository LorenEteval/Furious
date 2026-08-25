# Hysteria2 guidance

- The persisted native client document is submitted to the embedded core; the GUI editor is a partial projection, not
  an Xray-shaped compiler or schema normalizer.
- Preserve upstream names/values. `realm.ipMode` uses `dual`, `v4`, or `v6`; absent effective defaults and unknown future
  strings survive untouched. Optional controls update only their leaf and preserve unknown siblings.
- `obfs.type` selects a tagged subtype. Display an unknown subtype without rewriting it; an explicit switch to a known
  type may replace only the incompatible subtype data.
- Runtime preparation and native-TUN behavior follow the parent backend contract; probe/download copies omit TUN.
- Verify nested sibling/default preservation, known/unknown values, subtype switching, runtime document equality, TUN
  matrices, statistics cleanup, and transient editor destruction.

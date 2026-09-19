# Xray guidance

Inherit `Furious/Backends/AGENTS.md` and its ancestors; consult Plugins for capability contracts. This scope
owns Xray's full JSON preservation, routing/assets/statistics, and protocol/transport/TLS projections.

## Full-document preservation

- The complete Xray JSON document is authoritative. Protocol, transport, TLS, local-endpoint, logging, routing, and TUN
  editors are partial projections; preserve unrelated inbounds/outbounds, extensions, unknown security/transport data,
  and unrepresented siblings.
- Loading is observational except for narrow tested compatibility migrations. Legacy transport aliases such as `http`,
  `gun`, and `mkcp` may map to their supported current representation, but do not expand this into general normalization
  of unknown future values.
- URI codecs round-trip only their supported projection without erasing the source document. Keep Shadowsocks plugin
  metadata and SOCKS/VMess/VLESS/Trojan semantics distinct; malformed input returns controlled validation rather than a
  plausible different profile.

## Runtime-specific capabilities

- Logging paths, selected routing, statistics API, local test endpoints, and TUN are prepared on an independent
  runtime copy. Managed native TUN replaces runtime TUN inbounds; disabled management preserves explicit valid or
  malformed TUN and suppresses tun2socks. Proxy/download preparation replaces inbounds with its test surface. Verify
  the prepared document rather than assuming `proxyModeOnly` alone removes user TUN from every factory input.
- Xray owns routing profiles/options, geo assets, API statistics, and the `XRAY_LOCATION_ASSET` environment contract.
  Action providers retain reusable routing/asset windows through the created action owner and create transient
  settings dialogs per request; the capability registry does not become a transient-window owner.
- Runtime asset updates stage bytes and digest verification before atomic replacement. Failure preserves the prior
  usable file. Network reply and checksum worker have separate lifetimes: cancellation/shutdown must suppress late
  hash publication as well as abort requests. The plugin capability owns its lazy updater through shutdown.
  `Deploy.py --download` has a separate integrity contract; shared filenames do not make the mechanisms equivalent.
- Routing selection IDs, user routing documents, and translated built-in labels are different contracts. Preserve
  custom document content and named-profile identity while composing runtime routing/API statistics. Trace the
  selected repository routing document separately from the connection's own routing branch; neither may be mutated
  as a side effect of preparing a launch.
- Routing-rule row moves mutate the live profile's rule list in matching order, with Qt move notifications preserving
  selection. Internal drag-and-drop, the Move menu, and list-scoped Ctrl+Up/Ctrl+Down shortcuts use this same model
  mutation and preserve selected-row order. Pending rule editors/confirmations use persistent model indexes so moving or deleting
  a rule cannot retarget their completion. Verify this through `tests/test_ui_behavior.py` and repository/runtime order
  round trips. Rule-editing confirmations share the transient rules dialog as their Qt owner on every platform,
  so owner destruction also ends pending confirmation callbacks.
- Statistics preparation is optional and may leave a valid runtime without a statistics target. Preserve that
  distinction from connection failure; later sampling uses the target captured for this runtime, not newly edited
  settings or an assumption based solely on the backend name. `configureXrayStats()` merges the required API service
  and counter policy into the runtime copy, preserving unrelated valid API/policy fields. Do not replace a user's
  entire API or policy branch merely to enable counters; test both the merged launch and unchanged stored document.
- Verify full-document and URI preservation, aliases and unknown values, runtime-copy isolation for
  routing/log/TUN/tests, multiple TUN inbounds, asset integrity/failure, statistics and process cleanup,
  compiled-safe UI callbacks, and repeated editor/window destruction. Use `tests/test_xray_asset_download.py`,
  `tests/test_native_tun_semantics.py`, and `tests/test_backend_editor_contract.py`.

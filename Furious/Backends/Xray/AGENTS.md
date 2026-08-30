# Xray guidance

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

- Logging paths, selected routing, statistics API, local test endpoints, and TUN are prepared on an independent runtime
  copy. Managed native TUN replaces runtime TUN inbounds; disabled management preserves explicit valid or malformed TUN
  and suppresses tun2socks. Proxy/download tests replace inbounds with their proxy-only test surface.
- Xray owns routing profiles/options, geo assets, API statistics, and the `XRAY_LOCATION_ASSET` environment contract.
  Asset replacement remains digest-verified and atomic; action providers retain reusable routing/asset windows only
  through the created action owner and create transient settings dialogs per request.
- Verify full-document and URI preservation, aliases and unknown values, runtime-copy isolation for routing/log/TUN/tests,
  multiple TUN inbounds, asset integrity/failure, statistics and process cleanup, compiled-safe UI callbacks, and
  repeated editor/window destruction. Update this scope when an upstream or plugin capability changes intentionally.

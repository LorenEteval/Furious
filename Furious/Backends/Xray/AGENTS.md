# Xray guidance

- The full Xray JSON object is authoritative. Editors are partial projections of the tagged proxy outbound,
  transport/TLS, and local endpoint fields; preserve unrelated inbounds/outbounds, routing, logging, extensions, and
  unknown transport/security data.
- Loading may intentionally migrate legacy transport aliases `http`, `gun`, and `mkcp` to `h2`, `grpc`, and `kcp`.
  Keep compatibility mutations few, explicit, backend-owned, and covered by a test that distinguishes them from normal
  observational loading.
- Protocol URI codecs must round-trip the supported Xray projection without erasing the source document. Preserve
  Shadowsocks plugin metadata and SOCKS/VMess/VLESS/Trojan field semantics; malformed input returns controlled validation
  rather than a plausible but different profile.
- Routing, logging, testing, local proxy endpoints, and native TUN are prepared on copies. Managed native TUN replaces
  all runtime TUN inbounds; disabled management preserves existing valid or malformed TUN inbounds and suppresses
  tun2socks. Proxy/download tests remove all TUN inbounds from their own copy.
- Xray owns API traffic statistics, routing/asset behavior, the `XRAY_LOCATION_ASSET` environment contract, and transient
  asset/routing UI. Retain active windows/tasks only through their intended owner and never register live instances.
- Verify document/URI preservation, alias and unknown-value behavior, routing/log/TUN copy isolation, multiple TUN
  inbounds, asset integrity/download failure, statistics/process cleanup, and transient editor/window destruction.

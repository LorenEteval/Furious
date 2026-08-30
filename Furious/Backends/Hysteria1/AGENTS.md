# Hysteria 1 guidance

- Hysteria 1 is the legacy flat client schema and `hysteria://` share-link backend. Do not import Hysteria 2 nested
  documents, obfuscation, statistics, realm, or native-TUN semantics merely because the upstream names are related.
- Preserve tolerated legacy types, upstream field names, absent defaults, and unknown combo values. Loading and an
  untouched editor/URI/mapping round trip are observational; explicit user edits may normalize only the represented
  field.
- Subscription import is allowed only through supported Hysteria 1 protocol handlers. Subscription identity and test
  metadata stay in `ServerProfile`, and validation diagnostics never disclose passwords or complete links.
- Runtime and download-test preparation use independent configuration copies. This backend uses application tun2socks
  when global TUN requires it and owns the MMDB/ACL inputs used by its routing launch; it does not gain native TUN by
  falling through another backend’s policy.
- Verify legacy/current URI and mapping compatibility, unknown/tolerated values, stored-copy isolation, MMDB/ACL
  absence or malformed paths, asynchronous readiness and rollback, core-exit translation, application-TUN policy, and
  repeated editor/runtime cleanup. Revise this guide with an intentional schema evolution instead of freezing quirks.

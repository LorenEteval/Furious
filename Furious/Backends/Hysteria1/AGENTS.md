# Hysteria 1 guidance

- Hysteria 1 is a legacy backend with its own flat client schema and `hysteria://` share links. Do not import Hysteria 2
  nested-document, obfuscation, statistics, or native-TUN semantics merely because the core names are related.
- Preserve tolerated legacy types, upstream field names, and unknown combo values. Loading is observational and an
  untouched editor/URI/mapping round trip does not normalize otherwise accepted user data.
- Subscription import is permitted for supported Hysteria 1 links; metadata still belongs in `ServerProfile`, not the
  flat core document. Validation failure must not expose credentials in logs.
- This backend uses application tun2socks when global TUN mode requires it and owns the MMDB/ACL assets consumed by its
  runtime. Proxy/download preparation alters only an independent copy.
- Verify legacy URI and mapping compatibility, unknown/tolerated values, persisted-copy isolation, missing/malformed
  assets, startup and rollback cleanup, core exit translation, and repeated editor destruction.

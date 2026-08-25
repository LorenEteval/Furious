# Hysteria1 guidance

- Hysteria1 is a distinct legacy flat schema with `hysteria://` links. Do not import Hysteria2 nested fields,
  obfuscation rules, or native-TUN assumptions into it.
- Loading preserves tolerated legacy types and unknown combo values; an untouched editor round trip does not normalize
  valid user data.
- This backend owns its MMDB, geosite, and rule assets. Proxy-only tests alter a copy and never the stored profile.
- Verify legacy URI/mapping compatibility, unknown values, asset/startup failure cleanup, and editor destruction.

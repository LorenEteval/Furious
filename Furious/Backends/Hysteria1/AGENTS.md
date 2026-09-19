# Hysteria 1 guidance

Inherit `Furious/Backends/AGENTS.md` and its ancestors; consult Plugins for capability contracts. This scope
exists to preserve Hysteria 1's legacy flat schema and lifecycle without importing assumptions from Hysteria 2.

- Hysteria 1 is the legacy flat client schema and `hysteria://` share-link backend. Do not import Hysteria 2 nested
  documents, obfuscation, statistics, realm, or native-TUN semantics merely because the upstream names are related.
- Preserve tolerated legacy types, upstream field names, absent defaults, and unknown combo values through mapping
  and untouched-editor round trips. URI round trips cover supported share-link fields only. Explicit user edits may
  normalize the represented field; runtime validation may reject values that observational loading must preserve.
- Preserve the distinction between Hysteria 1's ACL/MMDB launch inputs and its flat connection mapping. A routing
  change must be checked through both the serialized document and the extra prepared launch inputs; a JSON-only
  assertion cannot establish which routing the child received. URI parsing remains in this backend's handler.
- This backend participates in application tun2socks through the shared startup workflow; its factory does not own
  host routing or connection commit. Keep the factory's unsupported routing/TUN combination rejection before
  execution acquisition; do not silently substitute Global routing or borrow native TUN from Hysteria 2.
  Keep MMDB/ACL launch preparation here and application-TUN acquisition/rollback with that workflow. The existing
  rejection prompt is a compatibility path, not a requirement that runtime factories own UI.
- Routing ACL/MMDB launch inputs remain distinct from the stored connection JSON. Optional files are read into
  launch data before the child starts; a missing/unreadable file is logged and falls back to empty input. Preserve
  that observable fallback unless deliberately changing the contract, and include this synchronous file work in
  preparation responsiveness review. The child receives prepared ACL/MMDB inputs; editing an asset or stored
  routing preference does not reconfigure an existing execution. A prepared runtime advertises its local HTTP
  readiness endpoint separately from child liveness.
- Capability absence is deliberate: this factory supplies neither native TUN nor a statistics provider. Shared UI
  must not infer either from Hysteria 2 support. Download preparation replaces the HTTP listener and removes SOCKS
  on a copy; test traffic must use its owned endpoint without applying ordinary connection host effects.
- Verify legacy/current URI and mapping compatibility, unknown/tolerated values, stored-copy isolation, MMDB/ACL
  absence or malformed paths, asynchronous readiness and rollback, core-exit translation, application-TUN policy,
  and repeated editor/runtime cleanup. Use `tests/test_hysteria1_protocol.py`,
  `tests/test_backend_editor_contract.py`, and `tests/test_connection_startup_async.py`. Revise this guide with
  intentional schema evolution instead of freezing tolerated historical input into a universal backend rule.

# Repository guidance

- Repositories restore and persist server profiles, subscription definitions, routings, and TUN settings. They currently
  encode collections into registered `AppSettings`/QSettings values and synchronize at application cleanup; they do not
  own network workflows, controller state, or presentation.
- `Storage` caches exactly one application-lifetime repository owner per collection and publicly exposes its live mutable
  data for compatibility. Never create a competing cached copy. Prefer named repository mutations for new behavior so
  validation and commit boundaries can move behind the repository over time.
- Preserve stable profile/subscription IDs, ordering, unknown fields, legacy schemas, and explicit subscription
  ownership. Display names and active row indexes are derived/compatibility state, not domain identity.
- Restore failure is observable and an empty fallback must not overwrite unreadable persisted bytes during automatic
  cleanup. An explicit successful mutation may intentionally replace that fallback. Prepare every fallible decode,
  migration, or reconciliation before deterministic assignments to the live collection.
- Subscription reconciliation may change only profiles explicitly owned by that group and stable profile key. Preserve
  local metadata and object/profile identity for matched profiles; mark removed profiles and reindex only at commit.
- Verify old/current/unknown-field round trips, ordering/identity, subscription isolation, malformed persisted roots,
  failed pre-commit transforms, explicit replacement after restore failure, and temporary QSettings isolation.

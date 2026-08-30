# Repository guidance

- Repositories restore, migrate, order, and persist profiles, subscriptions, routings, and TUN settings. They do not own
  network workflows, controller state, test schedulers, or presentation.
- `Storage` owns one application-lifetime backend per collection and exposes live mutable collections for compatibility.
  Do not add a second cache/snapshot authority. Prefer named repository mutations so validation and commit boundaries
  can move behind the repository over time.
- Preserve stable profile/subscription IDs, subscription ownership/key, ordering, unknown fields, and legacy schemas.
  Active row/index and display text are compatibility/presentation state, not identity.
- A restore failure remains observable. Automatic cleanup must not replace unreadable persisted bytes with an empty
  fallback; only an explicit successful replacement may do so.
- Stage fallible decode, migration, or reconciliation before deterministic mutation of the live collection. A
  subscription commit changes only that group: matched managed profiles retain stable object/profile identity and local
  metadata, removed profiles are marked stale, and indexes/order update atomically.
- Moving a profile between subscription displays does not automatically make it remotely managed; preserve the explicit
  distinction between local membership and synchronization ownership.
- Verify legacy/current/unknown-field round trips, malformed roots, restore-failure preservation, ordering/stable
  identity, group isolation, reconciliation commit behavior, and persistence in temporary QSettings namespaces.

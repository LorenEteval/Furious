# Repository guidance

Inherit `Furious/AGENTS.md` and its root ancestor. Consult the Interface and Models guides when changing their
contracts. This scope owns restoration, migration, ordering, and persistence; workflows and presentation remain
outside it.

- Repositories restore, migrate, order, and persist profiles, subscriptions, routings, and TUN settings. They do not own
  network workflows, controller state, test schedulers, or presentation. A repository method name does not imply
  serialization: trace its mutation and `sync()`/cleanup calls to locate the actual persistence boundary.
- `Storage` owns one application-lifetime backend per collection and exposes live mutable collections for compatibility.
  Do not add a second cache/snapshot authority. Prefer named repository mutations so validation and commit boundaries
  can move behind the repository over time.
- Preserve stable profile/subscription IDs, subscription ownership/key, ordering, unknown fields, and legacy schemas.
  Active row/index and display text are compatibility/presentation state, not identity. Record-shape dispatch and
  metadata precedence are migration behavior: legacy `UserServer` aliases override nested metadata, and explicit
  top-level current fields then override those aliases. Preserve this order and unknown extras unless a tested
  migration deliberately changes it; do not treat every duplicate key as interchangeable.
- A restore failure remains observable. Automatic cleanup must not replace unreadable persisted bytes with an empty
  fallback; only an explicit successful replacement may do so. Root decoding, individual-record hydration, and later
  serialization are separate failure boundaries. Test malformed records inside a valid root as well as malformed
  roots. Profile and subscription hydration publishes only a complete collection; an invalid record must not
  expose a partially restored prefix that cleanup can serialize over the original document. The restore-failure
  guard protects automatic cleanup, not an arbitrary explicit `sync()` call. Do not flush an empty fallback merely
  to inspect or acknowledge a load failure; test the original persisted bytes through the cleanup path.
- Stage fallible decode/migration before live mutation. Subscription reconciliation currently belongs to
  `Furious/Service/SubscriptionSync.py` and commits through the compatibility live collection: matched managed profiles
  retain object/profile identity and local metadata, removed profiles become stale, and unrelated groups remain
  intact. Do not add a second reconciliation algorithm here merely because persistence belongs to this scope.
- Distinguish a live-collection commit from serialization/flush and subsequent controller effects. The compatibility
  collection can change before it is flushed; a successful in-memory synchronization is not proof of an atomic disk
  transaction. Preserve explicit flush/cleanup behavior and report failures at the boundary that actually failed.
  Batched UI commands may commit several live mutations; cancellation prevents later batches without restoring
  already committed ones. Do not impose whole-command atomicity without changing callers and failure semantics.
- Moving a profile to another subscription makes it a local member and clears its remote matching key; unchanged
  membership does not demote an already-managed profile. Removing a group definition alone does not delete profiles,
  cancel requests, or stop timers. Callers coordinate those effects through existing workflow boundaries; do not hide
  cascades inside a low-level repository operation.
- Verify legacy/current/unknown-field round trips, malformed roots, restore-failure preservation, ordering/stable
  identity, group isolation, reconciliation commit behavior, and persistence in temporary QSettings namespaces. Use
  `tests/test_repository_contracts.py` and `tests/test_subscription_sync.py` to revalidate this scope. Reordering a
  filtered view must preserve hidden slots, selected relative order, and unrelated profiles, then relocate activation
  by profile ID. Test the complete repository order as well as the visible projection; a correctly painted view can
  conceal a wrong persisted ordering.

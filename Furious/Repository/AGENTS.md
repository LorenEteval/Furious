# Repository guidance

- Repositories persist profiles, subscriptions, routings, and TUN settings. They do not own Qt presentation, network
  workflows, or controller state; application preferences remain in `AppSettings` at their owning boundary.
- Preserve stable IDs, ordering, unknown fields, legacy schemas, and subscription ownership. Display names and row
  indexes are not domain identity.
- Public access currently returns application-owned live mutable collections for compatibility. Do not create a second
  cached copy; prefer named repository mutations for new behavior when practical.
- Decode failures remain observable and must not be overwritten with an empty fallback during automatic shutdown.
  Prepare fallible transformations before committing deterministic assignments to live collections.
- Subscription reconciliation can change only profiles explicitly owned by that subscription and stable profile key.
- Verify old/current/unknown-field round trips, ordering/identity, subscription isolation, malformed persisted bytes,
  failed pre-commit transforms, and temporary-settings isolation.

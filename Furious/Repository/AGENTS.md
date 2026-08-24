# Repository guidance

- Repositories are the persistence authority for domain collections and documents such as profiles, subscriptions,
  routing configurations, and TUN settings. Application preferences and current selections may use `AppSettings` at
  their owning controller/application boundary. Keep Qt/UI/workflow concerns out of repository implementations.
- Preserve stable IDs, ordering, unknown compatible fields, legacy migrations, and subscription ownership. Display names
  and row indexes are not identities.
- Subscription synchronization may update only profiles explicitly managed by that subscription and identified by stable
  profile keys. Never delete user-created or another subscription's data.
- Public collection access currently returns live mutable application-owned collections for compatibility. Document this
  honestly and avoid introducing a second cached copy; new mutations should flow through named repository operations
  when practical.
- Load failures retain recoverable data where possible and log actionable context. Never silently replace malformed
  explicit configuration with unrelated defaults when doing so loses user intent.
- If persisted data cannot be decoded, automatic shutdown cleanup must not overwrite the unreadable value with an empty
  fallback. A deliberate non-empty repository mutation or explicit sync may replace it as a recovery action.
- Prepare fallible reconciliation work—identity calculation, metadata normalization, and the final collection—before
  mutating live repository objects. The commit phase should contain only deterministic assignments.
- Singleton repository caches are application-lifetime finite objects and must be reset/sandboxed in tests.

## Verification

- Test old/current schemas, unknown fields, ordering, stable identity, subscription isolation, malformed persisted data,
  round trips, and isolated temporary settings.

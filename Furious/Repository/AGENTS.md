# Repository and persistence guidance

These rules apply to storage adapters and persisted application data.

## Persistence contracts

- Repository objects are the persistence boundary. UI/controllers/services use repository APIs rather than writing their own `QSettings` keys for domain records.
- Preserve stable identities: profile IDs identify profiles, subscription group IDs identify sources, and subscription profile keys link upstream members to their owner. Do not match ownership by display name, URL, or table position.
- Subscription synchronization is group scoped. Updating/removing one group must not affect manual profiles or profiles owned by another group; retained profiles keep local metadata and stable IDs.
- Migrations must be conservative and non-destructive. Keep legacy keys registered/read when required, normalize incompatible metadata safely, and preserve unrelated/unknown data where the current format supports it.
- Copies intended as manual profiles receive a new identity and clear subscription ownership. Routine edits must not accidentally detach or reassign ownership.
- Application-lifetime cached repositories are intentional; do not place transient UI or short-lived runtime resources in them.

## Required verification

- Run repository/model tests with the isolated temporary `QSettings` namespace.
- Add migration tests for legacy input and round-trip tests for current data before changing serialized shapes.
- For subscription changes, test add/update/remove, stable order/identity, other-group isolation, and manual-profile preservation.

## Code review rules

- Flag persistence writes outside the repository/settings abstraction for domain data.
- Flag subscription reconciliation based only on names, URLs, or row indices.
- Flag migrations that delete unrelated data or overwrite a legacy value before successful conversion.

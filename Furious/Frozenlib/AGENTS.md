# Frozenlib guidance

## Foundation and compatibility

- `Frozenlib` is the low-level platform/compatibility foundation and a broad wildcard import surface. Keep imports cheap,
  cross-platform, and free of application/UI construction. Preserve curated exports until all consumers migrate.
- `Constants`, enums, and pure helpers remain dependency-light. `Globals` exposes only deliberate application-lifetime
  owners; its accessors are compatibility shims and may yield `None` or raise attribute/runtime errors during isolated
  tests, partial startup, and teardown. Callers at those boundaries must tolerate absence without inventing new globals.
- `AppSettings` registers QSettings keys at import time and validates values. Keys back both preferences and encoded
  repository blobs, so preserve names, string/binary encodings, defaults, migrations, and registration order where it
  affects imports. Perform a requested host side effect before persisting its successful preference state.

## Host and resource ownership

- Isolate proxy, DNS, routing, TUN, startup registration, session callbacks, external commands, and process mutation
  here or behind the runtime boundary so tests can mock them completely. Preserve the OS-specific Windows/macOS/Linux
  and Flatpak/AppImage semantics instead of forcing one platform path onto another.
- `runExternalCommand()` deliberately has no universal timeout; each caller supplies a bound when responsiveness or
  cleanup requires it, or documents a non-GUI build/setup context. Avoid shell strings when an argument vector works.
- Own exact threads/processes/handles, clear dead daemon references, and make cleanup bounded and repeatable. Externally
  keyed caches are bounded; finite metadata caches never capture QObject instances or bound methods.
- `Mixins.CleanupOnExit` and the translation/theme/connection pools are weak registries, not object owners. A real
  application/page/service owner must retain each live object. Cleanup's legacy `uniqueCleanup` default de-duplicates by
  type; resource-owning instances that each need cleanup must opt out or use a clearer explicit owner/cleanup stage.
  Preserve failure isolation and clear/prune invalid wrappers after a sweep.
- Context managers restore the previous state when nested. Weak callbacks must not accidentally gain another strong
  owner, and weak pools must prune invalid PySide wrappers.
- `AppResources.py` is generated from `Resources.qrc` and its resource files. Update those inputs and regenerate with the
  compatible PySide6 toolchain; do not edit the generated module.

## Verification

- Use direct mocked helper tests plus affected controller/service tests. Cover every supported platform branch where
  practical and review GUI blocking, persisted success after host failure, process-name cleanup, sensitive logs, stale
  daemon references, import-time construction, and unbounded external-input caches.

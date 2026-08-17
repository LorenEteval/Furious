# Furious test guidance

These rules apply to the isolated `unittest` suite and refine repository guidance.

## Isolation

- Tests must never affect an already-running Furious instance or production user data. Set `QT_QPA_PLATFORM=offscreen` before importing Qt and use helpers in `tests/support.py`.
- Route `QSettings` to the temporary INI sandbox. Never read/write the production organization/application namespace.
- Do not change the real system proxy, routing table, TUN devices, startup registration, tray, or network interfaces. Patch host-mutation APIs and inject fake controllers/managers.
- Do not discover, signal, terminate, or clean up processes by name. Own exact subprocess handles/PIDs and threads, use bounded waits, and reap only resources the test created.
- Tests must not require external network access or installed proxy-core executables unless explicitly marked/documented as an optional smoke procedure.

## Test design

- Keep deterministic logic/behavior tests in the normal tier. Put repeated live-object/native-handle/RSS checks in the explicit stress tier.
- Test persisted input and runtime copies separately for configuration preparation. A helper must not make normal connection and proxy-only behavior accidentally identical.
- Qt lifetime tests use real close/deferred-delete paths, weak references, and live-object counts. `gc.collect()` is allowed only at diagnostic batch boundaries, never as production behavior or once-per-operation masking.
- Threshold increases are not a leak fix. Investigate linear object/handle growth and distinguish it from allocator/native high-water caching.
- Update `tests/README.md` when adding a test module or changing tiers/required environment setup. Commands in documentation use the active `python` environment.

## Code review rules

- Flag any test that can touch production `QSettings` or host networking.
- Flag broad process cleanup, unbounded waits, timing-only assertions, or dependence on an existing GUI session.
- Flag tests that assert only stored configuration when the bug concerns the runtime document submitted to a core.

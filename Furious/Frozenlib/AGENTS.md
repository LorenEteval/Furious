# Platform and compatibility guidance

Inherit `Furious/AGENTS.md` and its root ancestor. This scope contains compatibility and host-integration
boundaries, not a license for unrelated application orchestration to accumulate in a broad helper namespace.

- `Frozenlib` is the low-level settings, platform, compatibility, and broad export surface. Keep imports cheap,
  cross-platform, and free of application/UI construction; preserve curated wildcard exports until consumers and
  public-import tests migrate together.
- `Globals` exposes only deliberate application-lifetime owners. Accessors may be absent during partial startup,
  isolated tests, or teardown; do not add fallback global owners that create competing lifecycles.
- `AppSettings` keys include preferences and encoded repository blobs. Preserve names, defaults, string/binary
  encodings, migrations, and import-time registration. Distinguish desired preferences, helper-reported success,
  and independently observed host state; a Boolean success is not an OS read-back guarantee. Startup-registration
  success is persisted only after its helper reports success. Settings storage and cached
  repository objects are distinct lifetimes: changing a QSettings identity does not reconstruct `Storage` backends.
  Tests that replace settings must isolate both boundaries before exercising cleanup or restoration.
- Keep proxy, DNS, routing, TUN, startup registration, session callbacks, external commands, and platform detection here
  or behind a runtime boundary so tests can replace them completely. Windows, macOS, Linux, Flatpak, AppImage, and older
  platform paths are distinct capabilities; never generalize from the current host.
- Check each helper's real result contract. System Proxy set/off/pac return True for reported host success, False for
  failure, and None when policy deliberately leaves host settings unchanged. Startup registration and some routing
  helpers return Booleans; script-mode startup registration intentionally does nothing. Preserve these distinctions
  at callers instead of treating absence of an exception as confirmed host state. A skipped (`None`) operation must
  not be presented as either a failed mutation or verified host configuration. Check every native command result,
  including each enabled macOS network service, and bound host-command waits at this boundary. A per-command timeout
  is not a deadline for a loop over services or routes. Multi-step host mutation may be partial when a later command
  fails; a False result does not establish that earlier effects were rolled back.
- Prefer argument vectors over shell strings. Require host helpers to bound individual external calls; workflow callers
  also account for the number of calls, retries, privilege interactions, and rollback. A helper timeout and a total
  operation deadline answer different questions; build-time commands and GUI-time mutation have different budgets.
- Windows proxy calls, Linux desktop settings/host bridging, and macOS network-service operations are distinct
  paths. Application tun2socks host routing differs from backend-native TUN; preserve privilege, DNS restoration,
  and managed route cleanup for the selected path. Some helpers block synchronously and need caller-level
  responsiveness review.
- Own exact native threads/processes/handles and clear stale daemon references. Externally keyed caches are bounded and
  no cache/weak pool captures QObject instances or bound methods accidentally.
- `CleanupOnExit` and translation/theme/connection pools are weak registries, not owners. Native destruction must
  remove membership even while another Python reference retains an invalid wrapper. Cleanup normally de-duplicates
  by type; repeated instances with separate resources require per-instance registration or a containing cleanup
  stage. Membership neither keeps active objects alive nor proves every instance drained. When a callback keeps
  resources after failure, inspect the containing shutdown caller as well as the registry; registry iteration is
  not an automatic retry scheduler.
- `AppResources.py` is generated from `Resources.qrc` and referenced assets. Change the manifest/input files and
  regenerate with the compatible PySide6 resource compiler; never hand-edit generated resource code.
- Verify every affected OS branch with mocked host calls, plus persistence-on-failure, bounded cleanup, import-time
  side effects, sensitive logging, stale handles/daemons, and cache growth. Use `tests/test_frozenlib.py` and the
  mocked platform cases in `tests/test_connection_startup_async.py`.

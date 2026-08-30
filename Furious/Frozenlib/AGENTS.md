# Platform and compatibility guidance

- `Frozenlib` is the low-level settings, platform, compatibility, and broad export surface. Keep imports cheap,
  cross-platform, and free of application/UI construction; preserve curated wildcard exports until consumers and
  public-import tests migrate together.
- `Globals` exposes only deliberate application-lifetime owners. Accessors may be absent during partial startup,
  isolated tests, or teardown; do not add fallback global owners that create competing lifecycles.
- `AppSettings` keys include preferences and encoded repository blobs. Preserve names, defaults, string/binary
  encodings, migrations, and import-time registration. When a preference represents a host side effect, persist success
  only after the host operation succeeds.
- Keep proxy, DNS, routing, TUN, startup registration, session callbacks, external commands, and platform detection here
  or behind a runtime boundary so tests can replace them completely. Windows, macOS, Linux, Flatpak, AppImage, and older
  platform paths are distinct capabilities; never generalize from the current host.
- Prefer argument vectors over shell strings. Each caller owns any responsiveness/cleanup timeout appropriate to its
  context; build-time commands and GUI-time host mutation do not share one universal timeout policy.
- Own exact native threads/processes/handles and clear stale daemon references. Externally keyed caches are bounded and
  no cache/weak pool captures QObject instances or bound methods accidentally.
- `CleanupOnExit` and translation/theme/connection pools are registries, not owners. Their legacy de-duplication behavior
  is a compatibility constraint; resource-owning repeated instances need an explicit owner/cleanup stage.
- `AppResources.py` is generated from `Resources.qrc` and referenced assets. Change the manifest/input files and
  regenerate with the compatible PySide6 resource compiler; never hand-edit generated resource code.
- Verify every affected OS branch with mocked host calls, plus persistence-on-failure, bounded cleanup, import-time side
  effects, sensitive logging, stale handles/daemons, and cache growth.

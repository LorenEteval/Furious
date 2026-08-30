# Bundled runtime data guidance

## Boundary and provenance

- This directory ships application assets, not user state: Xray GeoIP/geosite data, Hysteria MMDB/ACL data, the local
  MapLibre endpoint map, and the bundled font. Settings, subscriptions, caches, and temporary downloads belong elsewhere.
- Preserve upstream licenses, provenance, binary/text formats, filenames, and paths consumed by constants, backends,
  tests, setuptools package data, and Nuitka. Do not incidentally reformat generated ACLs or replace binary assets.
- `Deploy.py --download` performs a networked refresh and may rewrite large, time-varying assets. Run it only when that
  mutation is explicitly in scope; review source, checksums, exact changed files, and existing user modifications.

## Local endpoint map

- The MapLibre document is an offline/privacy boundary. Keep executable code, style, glyphs, sprites, and required data
  local and package-resolvable; do not add trackers or runtime CDN dependencies. Missing optional map detail must degrade
  visibly but must not crash the WebEngine renderer or the application.
- Linux Essentials-only builds deliberately operate without WebEngine; map consumers must retain their non-WebEngine
  fallback. macOS/Windows packaged paths may include WebEngine and must resolve all local resources from the bundle.

## Verification

- Verify the real consuming backend/widget, source and packaged path resolution, package-data/Nuitka inclusion, integrity
  and failure behavior, and license presence. Tests use fixtures or mocked downloads, never live asset refreshes.

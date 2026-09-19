# Bundled runtime data guidance

Inherit `Furious/AGENTS.md` and its root ancestor. This scope exists for shipped runtime assets and their
provenance; it is not an application-data or settings directory.

## Boundary and provenance

- This directory ships Xray GeoIP/geosite data, Hysteria MMDB/ACL data, the local MapLibre endpoint map, and the
  bundled font. It is not a home for settings, subscriptions, or general caches. The Xray updater currently replaces
  assets at the package-resolved data paths, so these files are not necessarily immutable at runtime. Review source,
  installed, and packaged write permissions separately; an application refresh may appear as a source-tree change.
- Preserve upstream licenses, provenance, binary/text formats, filenames, and paths consumed by constants, backends,
  tests, setuptools package data, and Nuitka. Do not incidentally reformat generated ACLs or replace binary assets.
- Markdown files in this directory are repository metadata, not runtime data. Keep top-level and nested Markdown files
  excluded consistently from setuptools package data and Nuitka inclusion while preserving them in the source tree.
- `Deploy.py --download` performs a networked refresh and may rewrite large, time-varying assets. Run it only when that
  mutation is explicitly in scope; inspect its actual integrity checks, provenance, exact changed files, and existing
  user modifications. A backend's digest-verified runtime updater does not establish this build downloader's guarantees.

## Local endpoint map

- Keep vendored `maplibre-gl.js`/CSS and their license distinct from the application-owned `EndpointMap.js`/HTML
  bridge. Change host behavior in the bridge and its Python consumer; a vendor replacement needs separate provenance
  and compatibility review. The style requests vector tiles and glyphs from
  `tiles.openfreemap.org`. This is not an offline map. Keep executable code local, preserve attribution, and review
  the HTML content-security policy and the widget's attribution-link validation when changing network resources or
  links. Missing tiles/network detail must degrade without crashing the renderer or the application.
- Linux Essentials-only builds deliberately operate without WebEngine; map consumers must retain their non-WebEngine
  fallback. macOS/Windows packaged paths may include WebEngine and must resolve all local resources from the bundle.
  Audit map assets together with `Furious/Widget/EndpointInfoWidget.py`: local loading, the WebChannel bridge, remote
  tile permissions, and external attribution navigation form one boundary. Validate both the renderer payload and
  host-side acceptance when that bridge changes; editing bundled JavaScript alone cannot establish host behavior.
  A CSP change alone does not establish that arbitrary navigation or remote executable code is allowed by the host.

## Verification

- Verify the real consuming backend/widget, source and packaged path resolution, package-data/Nuitka inclusion,
  integrity and failure behavior, and license presence. Tests use fixtures or mocked downloads, never live asset
  refreshes. `tests/test_endpoint_info.py` and `tests/test_public_api.py` cover map/resource consumers; release
  artifacts require their own inclusion checks. Check actual artifact contents, including nested Markdown exclusions,
  rather than only the presence of package-data patterns. Successful inclusion does not prove runtime write access or
  optional WebEngine availability. Revalidate provenance/network claims when an asset provider or loader changes.

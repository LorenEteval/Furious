# Bundled runtime data guidance

- This directory contains shipped runtime assets, not application state: Xray GeoIP/geosite databases, Hysteria
  MMDB/ACL rules, the vendored MapLibre endpoint map, and the bundled font. Keep user settings and downloaded temporary
  files outside this tree.
- Preserve upstream licenses, provenance, binary/text format, filenames, and paths referenced by constants, backends,
  tests, `package_data`, and Nuitka packaging. Do not reformat large generated ACLs or replace binary assets incidentally.
- `Deploy.py --download` refreshes Xray data and generated Hysteria assets from network sources. Such updates may be large
  and nondeterministic over time: make them only when explicitly in scope, review checksums/provenance and the exact diff,
  and never overwrite unrelated user changes already present in these files.
- MapLibre HTML/JS/CSS is a local privacy and offline boundary for endpoint presentation. Keep runtime requests neutral,
  local paths/package inclusion intact, and the vendored license alongside it. Avoid adding remote scripts or trackers.
- Verify the consuming backend/widget, package-data inclusion, source and packaged path resolution, asset integrity/error
  handling, licensing, and that tests use fixtures/mocks rather than live downloads.

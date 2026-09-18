# Icon source guidance

Inherit repository-wide rules from the root `AGENTS.md`. This top-level scope governs icon source/provenance and the
resource-manifest contract; it does not govern general UI layout.

- Reuse an existing semantic icon before introducing a new asset. SVG sources stay compact vectors without scripts,
  remote resources, embedded rasters, editor metadata, or hard-coded page backgrounds.
- Use the shared icon helpers and the bundled monochrome/default and white variants as appropriate. An SVG's
  `currentColor` alone does not establish Qt theme behavior; verify how `Furious/Qt/QtGui.py` resolves and masks the
  chosen asset. Reuse that path instead of adding control-specific recoloring, and do not rely on color alone.
- Preserve license/provenance and the `Resources.qrc` alias contract. Any add, removal, rename, or alias change
  updates all consumers and the manifest, then regenerates `Furious/Frozenlib/AppResources.py` with the selected
  environment's `pyside6-rcc Resources.qrc -o Furious/Frozenlib/AppResources.py`. Never hand-edit generated resource
  code; inspect compiler-version churn separately from the intended alias/asset change.
- Treat the alias as the application-facing identity and the source path as an implementation detail. Search both before
  replacement so an apparently unused file is not removed while still generated or consumed through an alias. Selecting
  an already bundled Bootstrap icon normally changes its consumer only; it does not require regeneration or another
  SVG copy. Compare the glyph's visible bounds at the actual control size, not only its nominal SVG canvas.
- Verify alias uniqueness and source/package resolution, then inspect the actual control or tray use under both
  themes, high DPI, relevant sizes, disabled/selected states, and platform packaging where applicable. Deployment
  icons also have direct filesystem consumers in `Deploy.py`; a resource alias search alone cannot prove a PNG is
  unused. Keep direct installer/application icons in verification alongside Qt aliases: a successful `pyside6-rcc`
  invocation proves resource generation, not deployment-icon inclusion or correct themed rendering.

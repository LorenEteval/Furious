# Icon source guidance

- Reuse an existing semantic icon before adding another. Source SVGs remain compact vectors without scripts, remote
  resources, embedded rasters, editor metadata, or hard-coded backgrounds.
- Follow the established monochrome/tint convention; add a theme-specific variant only when semantic tinting cannot
  express the design. Preserve accessible meaning rather than relying on color alone.
- Preserve upstream licensing and the `Resources.qrc` alias contract. Add/remove/rename updates the manifest and every
  consumer, then regenerates `Furious/Frozenlib/AppResources.py` with the compatible PySide6 resource compiler; never
  edit generated resource code.
- Verify manifest uniqueness, both themes, high-DPI rendering, and size/alignment in the actual `AppQ*` control and, when
  relevant, tray/platform packaging.

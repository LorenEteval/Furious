# Icon source guidance

- Reuse an existing semantic icon before adding another. Source SVGs remain compact vectors without scripts, remote
  resources, embedded rasters, editor metadata, or hard-coded backgrounds.
- Follow the established monochrome/tint convention; add theme variants only when tinting cannot express the design.
- Preserve resource paths and licensing. A rename/add/remove updates every consumer and regenerates
  `Furious/Frozenlib/AppResources.py`; never hand-edit that generated module.
- Verify both themes, high-DPI rendering, and icon size/alignment in the actual Fluent control.

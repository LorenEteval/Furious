# Icon asset guidance

- This tree contains source assets consumed by the Qt resource workflow. Reuse an existing semantic icon before adding a
  near-duplicate.
- Keep SVGs vector, compact, theme-compatible, and free of embedded raster data, scripts, remote resources, editor
  metadata, or hard-coded backgrounds.
- Follow the established monochrome/current-color convention for UI icons; add explicit light/dark variants only when
  the design cannot be expressed through tinting.
- Preserve upstream license/attribution requirements and stable resource paths. Renaming/removing an asset requires
  updating all references and regenerating `Furious/Frozenlib/AppResources.py` through the existing workflow.
- Do not hand-edit the generated resource module.

## Verification

- Search all references, regenerate resources, test light/dark and high-DPI rendering, and visually check icon
  size/alignment in the target Fluent control.

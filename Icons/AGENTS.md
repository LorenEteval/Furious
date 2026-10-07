# Icon source guidance

Inherit the [nearest parent guide](../AGENTS.md).
This scope owns icon provenance and resource identity. Compiled aliases, themed rendering and installer
inclusion require separate checks; commands remain with consumers.
Read `Resources.qrc` with `tests/test_public_api.py`; paths are relative to this source tree's root.

- Reuse an existing semantic icon before introducing a new asset. SVG sources stay compact vectors without scripts,
  remote resources, embedded rasters, editor metadata, or hard-coded page backgrounds.
- Use the shared icon helpers and the bundled monochrome/default and white variants as appropriate. An SVG's
  `currentColor` alone does not establish Qt theme behavior; verify how `Furious/Qt/QtGui.py` resolves and masks the
  chosen asset. Reuse that path instead of adding control-specific recoloring, and do not rely on color alone.
  Mask/opacity helpers cache shared icon values: keep cache size bounded and keys independent of widgets, and avoid
  mutating a cached icon as if it belonged to one control.
- Preserve license/provenance and the `Resources.qrc` alias contract. Any add, removal, rename, or alias change
  updates all consumers and the manifest, then regenerates `Furious/Frozenlib/AppResources.py` with the selected
  environment's `pyside6-rcc Resources.qrc -o Furious/Frozenlib/AppResources.py`. Never hand-edit generated resource
  code. Editing the bytes of an existing manifest input also requires regeneration even if its path and alias stay
  unchanged. Inspect compiler-version churn separately from the intended asset change.
- Treat the alias as the application-facing identity and the source path as an implementation detail. Search both before
  replacement so an apparently unused file is not removed while still generated or consumed through an alias. Selecting
  an already bundled Bootstrap icon normally changes its consumer only; it does not require regeneration or another
  SVG copy. Compare the glyph's visible bounds at the actual control size, not only its nominal SVG canvas.
  An icon substitution preserves the command's accessible text, shortcut, checked state, selection target, and
  popup-focus behavior. Verify those semantics at the consumer rather than imposing a new action-construction pattern.
- Resource identity is prefix plus alias: default and white collections intentionally repeat aliases under
  different prefixes. Check duplicate full paths and missing inputs, then exercise a compiled-resource consumer;
  a source file on disk and successful `pyside6-rcc` execution do not prove the expected alias resolves.
- Deployment icons have direct filesystem consumers in `Deploy.py` outside the Qt resource namespace. Check those
  installer/application inputs separately from aliases before removing a PNG. Verify control/tray rendering under
  both themes, high DPI, relevant sizes, and disabled/selected states; resource generation does not prove themed
  rendering or inclusion in an installer. Resource generation validates the manifest's input relationship, while
  consumer rendering validates meaning and visibility; neither proves the other. Keep asset-only checks separate
  from changes to the action's lifetime or command target.

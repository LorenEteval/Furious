# Translation catalog guidance

## Source and generation contract

- `Furious/Externals/GenTranslation.py` is generator-managed, but its language values and `isReviewed` flags are curated
  data. Repository-root `Translation.py` owns source extraction and catalog structure; neither file is disposable.
- Run `Translation.py --target <language>` with the repository interpreter after changing translatable source or curated
  wording. It rebuilds source membership, drops stale keys, preserves reviewed target text, initializes unresolved text,
  detects target collisions, and writes deterministic key order.
- Entry key order is `source`, language keys retained by the generator, then `isReviewed`. `source` contains
  deduplicated fully qualified modules; do not curate that list manually because extraction rebuilds it.
- Inspect the full diff. Preserve deliberate translations/review flags, HTML/newline semantics, and natural RU/ZH
  meaning; mark an entry reviewed only after a human has verified it. Do not hand-maintain the generated `source` module
  list.

## Extractable source text

- `_()` normally receives one static literal. The only supported dynamic form is an f-string composed solely of bare
  names imported from `Furious.Frozenlib.Constants`; ordinary placeholders, attributes, calls, conversions, format
  specifications, concatenation helpers, and `.format()` are not extractable.
- Keep runtime interpolation outside the translatable expression. Translate UI language, not identifiers, protocol
  values, user-defined names, persisted values, paths, or diagnostic payloads.
- When a control stores source text for later retranslation, update that source instead of manually translating one
  rendered instance. State-driven controls may deliberately reapply semantic state rather than call a generic base
  retranslator; preserve user-defined values in either path.

## Verification

- Run extraction for every affected language, review collisions/stale removal/order and the catalog diff, then run it a
  second time to prove stability. Exercise runtime lookup and affected UI retranslation under explicit locales.

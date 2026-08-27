# Translation catalog guidance

- `GenTranslation.py` is a generator-managed catalog written by repository-root `Translation.py`, but it is also the
  current source of curated language values and `isReviewed` state. Do not discard or blindly regenerate those values;
  intentional translation/review edits may be made in the catalog before running the generator.
- `Translation.py --target <language>` re-extracts source membership, removes stale keys, preserves reviewed target text,
  initializes missing/unreviewed target text, checks target collisions, and rewrites the catalog deterministically.
  Run it with the repository environment and inspect the complete catalog diff.
- Entry key order is `source`, language keys retained by the generator, then `isReviewed`. `source` contains deduplicated
  fully qualified modules; do not curate that list manually because extraction rebuilds it.
- Extraction accepts direct static `_()`/`gettext()` literals and the root-documented constants-only f-string form.
  Keep runtime interpolation outside the translatable expression.
- Preserve HTML/newline semantics and natural RU/ZH meaning. Mark new or changed wording reviewed only after a human has
  verified it. Verify collision output, stale-key removal, ordering, runtime lookup, and a stable second generator run.

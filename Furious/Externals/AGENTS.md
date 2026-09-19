# Translation catalog guidance

Inherit `Furious/AGENTS.md` and its root ancestor. This scope preserves the split between extracted catalog
structure and human-reviewed translations.

## Source and generation contract

- `Furious/Externals/GenTranslation.py` is generator-managed, but its language values and `isReviewed` flags are curated
  data. Repository-root `Translation.py` owns source extraction and catalog structure; neither file is disposable.
- Run `python Translation.py --target <language>` with the repository interpreter for an intentional
  extraction/update. It rebuilds source membership, drops stale keys, preserves reviewed target text, and reports
  collisions. Automatic translation is currently disabled: unresolved/unreviewed target values may be replaced with
  the source text. Review the diff before treating the command as a harmless refresh, especially with `--ignore`.
- Preserve existing translation-key and language-field order. The generator retains dictionary order rather than
  enforcing a universal sort; source traversal can affect newly discovered entries. Do not sort the catalog as cleanup.
  `source` contains deduplicated fully qualified modules and is rebuilt by extraction rather than manually curated.
  Changing a source literal changes catalog identity: extraction may remove the old reviewed entry and introduce a
  new unreviewed one. Review wording changes as translation migrations, including reused keys in other modules.
- Inspect the full diff. Preserve deliberate translations/review flags, HTML/newline semantics, and natural RU/ZH
  meaning. Curated, verified translations need `isReviewed` set to the string `'True'`, as the generator compares that
  literal; a Python Boolean is not equivalent. Review applies to the entry, so inspect its other language values too.
  Do not clear approved review flags or hand-maintain the generated `source` module list. Runtime lookup reverse-maps
  translated text to a source key through a shared reverse index across languages. Equal translations for different
  source keys can therefore affect later retranslation, including after a language switch. Exercise lookup and
  retranslation under explicit locales rather than treating collision diagnostics as cosmetic. A collision-free
  extraction report does not prove reverse lookup is unambiguous across every language; inspect the runtime index
  and language-switch behavior when two source keys share translated text.

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

- Run extraction for every affected language, inspect collision/unreviewed diagnostics and the complete catalog
  diff, then run it again to check stability. Collision and write failures are logged rather than guaranteed to
  produce a nonzero process exit; exit status alone is not validation. Exercise runtime lookup and UI retranslation
  under explicit locales; `tests/test_models_and_services.py` and `tests/test_ui_behavior.py` cover extraction/UI
  consumers.
- Translation generation is a scoped repository mutation: do not run it as an incidental formatter, and do not
  accept broad catalog churn without tracing each changed source literal or intentional stale-key removal. Update
  this guide when extraction or review semantics change; do not generalize generator-managed membership into a ban
  on curated text.

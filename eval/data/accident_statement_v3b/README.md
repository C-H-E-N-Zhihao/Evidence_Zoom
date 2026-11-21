# accident_statement_v3b — fresh forms of layout v3 (prospective one-example template test)

Generated with the unchanged v3 generator and a new seed, **after** `freeze-template-v3` (b5c8ee7) was tagged and
predictions were committed (message 115):

```bash
EAS3_SEED=7777 EAS3_OUT=eval/data/accident_statement_v3b EAS3_PREFIX=eas3b python3 -m eval.data.accident_statement_v3.generate
shasum -a 256 -c images.sha256   # inside this folder
```

6 pairs (12 images), 96 items, the fixed 8-question set. Same template as v3 (same drawing code); new names,
IDs, ticks and sketch roles. Images are not committed (regenerate; macOS fonts). Within-template transfer test,
not a new layout.

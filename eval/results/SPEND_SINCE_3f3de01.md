# API spend since the 3f3de01 reconciliation (claude-guanyu, receipt check as codex-guanyu's fallback)

Sum of `meta.spent_usd` over every run JSON under `eval/results/` added after 3f3de01: on master (`8e53f95`) and on the unmerged branch `claude/agent-intro-messages-07d426` (`72c21ca`). RCP CPU job `guanyu-spend-sum-1122-1059`. Runs with zero spend (local GPU only) are omitted from the list.

| where | run file | spent (USD) | providers |
|---|---|---:|---|
| master | `freeform_ladder__run_20261122-094250.json` | 0.06015 | openrouter |
| master | `freeform_pointer__run_20261122-094410.json` | 0.02639 | local,openrouter |
| master | `infovqa_lnbox_haiku__run_20261122-093738.json` | 0.02653 | local,openrouter |
| master | `infovqa_router_haiku__run_20261122-093537.json` | 0.01441 | openrouter |
| master | `pointer_dev__run80__run_20261122-082228.json` | 0.016 | local,openrouter |
| master | `pointer_dev__smoke__run_20261122-081235.json` | 0.00032 | local,openrouter |
| master | `realdocs_v1_ladder__run_20261122-074800.json` | 0.02042 | openrouter |
| master | `realdocs_v1_ladder_off__run_20261122-075316.json` | 0.01843 | openrouter |
| master | `realdocs_v2_mosaic_dev__run_20261122-080703.json` | 0.00638 | openrouter |
| master | `realdocs_v2_speculate__run_20261122-083600.json` | 0.01256 | local,openrouter |
| master | `receipts_v1_full__run_20261122-081922.json` | 0.05576 | openrouter |
| master | `receipts_v1_ladder__run_20261122-075839.json` | 0.03724 | openrouter |
| master | `receipts_v1_ladder_absent__run_20261122-085737.json` | 0.03469 | openrouter |
| master | `receipts_v1_ladder_redact__run_20261122-085519.json` | 0.03645 | openrouter |
| master | `receipts_v1_lnbox_haiku__run_20261122-093102.json` | 0.05102 | local,openrouter |
| master | `receipts_v1_lnlines_haiku__run_20261122-093101.json` | 0.04696 | local,openrouter |
| master | `receipts_v1_low50__run_20261122-091231.json` | 0.03081 | openrouter |
| master | `receipts_v1_nobox__run_20261122-091150.json` | 0.02244 | openrouter |
| master | `receipts_v1_page__run_20261122-080724.json` | 0.04705 | openrouter |
| master | `receipts_v1_speculate__run_20261122-085517.json` | 0.04008 | local,openrouter |
| master | `receipts_v2_final__run_20261122-092800.json` | 0.0818 | openrouter |
| master | `retype_dev__dfull__run_20261122-082742.json` | 0.00834 | local,openrouter |
| master | `retype_dev__receipts__run_20261122-082419.json` | 0.00793 | local,openrouter |
| master | `retype_dev__smoke__run_20261122-082150.json` | 0.00011 | local,openrouter |
| branch | `freeform_final__run_20261122-100129.json` | 0.0188 | openrouter |
| branch | `freeform_grpo7b_pointer__run_20261122-095412.json` | 0.03755 | local,openrouter |
| branch | `freeform_zeroshot7b_pointer__run_20261122-095342.json` | 0.03376 | local,openrouter |
| branch | `handwriting_final__run_20261122-100153.json` | 0.03556 | openrouter |
| branch | `realdocs_v2_final__run_20261122-101257.json` | 0.11278 | openrouter |
| branch | `receipts_v2_grpo7b_lines__run_20261122-095416.json` | 0.0412 | local,openrouter |
| branch | `receipts_v2_grpo7b_pointer__run_20261122-094944.json` | 0.05955 | local,openrouter |
| branch | `receipts_v2_zeroshot7b_pointer__run_20261122-094845.json` | 0.04501 | local,openrouter |

**Total since 3f3de01: $1.0865** (master $0.7023, branch only $0.3842).

With the approved reconciliation through the resolution tests (about $2.26, andrew-spend-through-frontier), the receipted total is **about $3.35 of the $10 credit**. Not included (no committed run JSON): the billing probe (~$0.0014, message 212), the demo red-team (~$0.0045, 257) and live checks in the app (each under $0.01). The provider dashboard gives the live balance.

# Does selective refinement help a reader answer?

**The cheap pixel control already changes the product decision.** At a fixed payload, concentrating detail helped when the question named a window. When the reader had to locate the mark from coarse content, it missed enough windows to erase that gain. This is a reason to expose the router’s selected evidence and to keep a uniform or original-page fallback for uncertain selections.

| CPU experiment | Uniform | Selective | Comparison |
|---|---:|---:|---|
| Which row is marked in the named window? | 149/160 | **157/160** | 28 bytes per window versus 16 per window plus 48 more at the target. Refining another window gave 117/160. |
| Which window and row contain the only mark, or is the page blank? | **124/136** | 108/136 | Uniform located 121/128 marked windows; coarse selection located 102/128. False marks on eight blank pages: two uniform, zero selective. |

Both payloads expose 112 grayscale bytes across four cached windows. The coarse samples are an actual prefix of the fine stream. Positions use a fixed order, so refinement adds bytes without resending them. Figures describe bytes exposed to local readers. They do not measure network savings, GPU time, or billing. When the window is given in advance, sending only the target's 64 bytes is also sufficient for that reader.

The eight held-out rendering styles include stroke, spacing, contrast, position and JPEG variation. The 160 named queries reuse five counterfactual windows per location and style. The 136 search cases recombine those same windows into 16 marked cases and one blank per style. Treat the page styles as the independent groups. All inputs are synthetic. No learned LLM selector is involved. Source-pixel access plus the box interiors gave 160/160 on the named-window task.

**Reproduce:** `python -m experiments.flextok_reader --thumbnails`. Raw outputs are in `thumbnail_controls.jsonl`. For the FlexTok comparison run the same evaluator with `--replay-ids reader_ids.npz` once the RCP cache arrives. The GPU dispatch uses `--codes --save-ids reader_ids.npz`. The primary FlexTok gate was frozen at 203b2be. The content-selection task is an additional exploratory control. Early and late code lengths change only the downstream reader input in this experiment.

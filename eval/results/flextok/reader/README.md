# Does selective refinement help a reader answer?

[Open the offline replay](replay.html) in a browser. Choose any of the 40 held-out composite forms and switch the question and allocation. Every displayed prediction is recomputed from the archived RCP IDs when the exhibit is built. The GPU and local input-image digests match. Rebuild with `python -m experiments.flextok_replay eval/results/flextok/reader/replay.html`.

**FlexTok passed its prespecified comparison.** At 56 IDs total, query-directed refinement read 140/160 correctly, uniform allocation read 113/160, and refining a different window read 88/160. Against uniform 56, 39 questions improved and 12 regressed. Seven of eight held-out styles improved in aggregate; one tied. Uniform 64 scored 119/160. Both query-directed 56 and uniform 64 produced one false mark on 32 blanks. Source-pixel reading with known box interiors scored 160/160.

On the exploratory search task the coarse FlexTok selector localized 111/128 marks versus uniform's 124/128, but refinement improved the joint window-and-row answer from 88/136 to 103/136. The best grayscale search control below still scored 124/136. For the hackathon, use the original-pixel route for answers and use this exhibit to demonstrate what learned prefixes preserve.

RCP job `lh-flextok-reader` encoded 360 windows in 13.6 seconds, with 1.56 GB peak allocated on one A100-40GB. This is encoder-plus-transfer timing. All policies reused the same encodings. No end-to-end inference saving was measured. See [archived IDs and GPU output](codes_stdout.jsonl) and [CPU replay](replay_stdout.jsonl).

**The cheap pixel control already changes the product decision.** At a fixed payload, concentrating detail helped when the question named a window. When the reader had to locate the mark from coarse content, it missed enough windows to erase that gain. This is a reason to expose the router’s selected evidence and to keep a uniform or original-page fallback for uncertain selections.

| CPU experiment | Uniform | Selective | Comparison |
|---|---:|---:|---|
| Which row is marked in the named window? | 149/160 | **157/160** | 28 bytes per window versus 16 per window plus 48 more at the target. Refining another window gave 117/160. |
| Which window and row contain the only mark, or is the page blank? | **124/136** | 108/136 | Uniform located 121/128 marked windows; coarse selection located 102/128. False marks on eight blank pages: two uniform, zero selective. |

Both payloads expose 112 grayscale bytes across four cached windows. The coarse samples are an actual prefix of the fine stream. Positions use a fixed order, so refinement adds bytes without resending them. Figures describe bytes exposed to local readers. They do not measure network savings, GPU time, or billing. When the window is given in advance, sending only the target's 64 bytes is also sufficient for that reader.

The eight held-out rendering styles include stroke, spacing, contrast, position and JPEG variation. The 160 named queries reuse five counterfactual windows per location and style. The 136 search cases recombine those same windows into 16 marked cases and one blank per style. Treat the page styles as the independent groups. All inputs are synthetic. No learned LLM selector is involved. Source-pixel access plus the box interiors gave 160/160 on the named-window task.

**Reproduce:** `python -m experiments.flextok_reader --thumbnails`. Raw outputs are in `thumbnail_controls.jsonl`. For the FlexTok comparison run the same evaluator with `--replay-ids reader_ids.npz` using the archived RCP cache. The GPU dispatch uses `--codes --save-ids reader_ids.npz`. The primary FlexTok gate was frozen at 203b2be. The content-selection task is an additional exploratory control. Early and late code lengths change only the downstream reader input in this experiment.

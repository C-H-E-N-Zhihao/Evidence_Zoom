# Does selective refinement help a reader answer?

[Open the offline replay](replay.html) in a browser. Choose any of the 40 held-out composite forms and switch the question and allocation. Every displayed prediction is recomputed from the archived RCP IDs when the exhibit is built. The GPU and local input-image digests match. Rebuild with `python -m experiments.flextok_replay eval/results/flextok/reader/replay.html`.

**Directing more detail to the named window helped both readers. At equal payload the simple grayscale reader scored 157/160, ahead of FlexTok at 140/160.** At 56 IDs total, query-directed refinement read 140/160 correctly, uniform allocation read 113/160, and refining a different window read 88/160. Against uniform 56, 39 questions improved and 12 regressed. Seven of eight held-out styles improved in aggregate; one tied. Uniform 64 scored 119/160. Both query-directed 56 and uniform 64 produced one false mark on 32 blanks. Source-pixel reading with known box interiors scored 160/160.

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

## Can the reader tell when it has enough detail?

On these forms I would keep the read budget fixed. The confidence-based FlexTok reader used 58.5 target bytes per question on average and scored 135/160, exactly the count from always reading 64 bytes. Both falsely marked three of 32 blank windows. The extra decisions cost time: median cached CPU readout rose from 4.6 to 9.8 microseconds. A fixed 128-byte prefix scored 156/160 with zero false marks and took 6.5 microseconds. All timings include code lookup and every executed classifier pass on the local arm64 CPU; encoding, transfer over a network, and selection of the window are outside the timer.

| FlexTok policy | Correct | Mean target bytes | Mean classifier passes |
|---|---:|---:|---:|
| Fixed 8 IDs | 79/160 | 16 | 1 |
| Fixed 32 IDs | 135/160 | 64 | 1 |
| Fixed 64 IDs | 156/160 | 128 | 1 |
| Margin-based exit at 8, 32, or 64 IDs | 135/160 | 58.5 | 1.875 |

Seven rendering styles train each linear classifier. Three separate styles set exit thresholds, using the difference between the two highest class scores. Each early exit requires a margin above the largest mistaken margin among calibration questions reaching that stage, and at least five accepted calibration examples. At evaluation, 25 questions exited at 8 IDs, 130 at 32, and five reached 64. The adaptive reader lost 22 answers the longest prefix got right and recovered one of its mistakes. Eight evaluation styles were excluded from fitting and calibration, but their previous fixed-budget results were known; this is exploratory. The earlier ten-style fit and this seven-style fit should not be pooled.

Grayscale gave a different trade-off: progressive stopping scored 146/160 with seven false marks, versus 142/160 and six false marks at the full 128 samples. A separately resized 8×8 antialiased thumbnail scored 136/160 in this seven-style fit. The progressive samples come from a fixed 8×16 tile; early prefixes of that tile are distinct from independently resized thumbnails.

Run `OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python -m experiments.flextok_stopping --time`. [Raw results, calibration counts and timings](stopping.jsonl). Each timing arm warms up once and then checks 1,600 decisions across shuffled query orders against the offline predictions. Cached codes were reused throughout. A next test with higher product value is whether the region selector supplies the correct window on independently acquired scan or phone images, with originals available to verify marks.

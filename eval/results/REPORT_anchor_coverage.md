# OCR-anchored region selection: gold-evidence coverage (offline, $0)

`python -m bench.anchor_coverage` · 36 visual items · selection uses OCR only, no model. Geometric degradations move the gold boxes slightly, so coverage there is approximate.

| input | question | n | covered | partial | missed | crop px (median) | img tok/q (est.) |
|---|---|---:|---:|---:|---:|---|---:|
| clean | q4 | 12 | 12 | 0 | 0 | 147×883 | 173 |
| clean | q5 | 12 | 12 | 0 | 0 | 482×161 | 103 |
| clean | q6 | 12 | 12 | 0 | 0 | 1568×468 | 978 |
| scale_1024 | q4 | 12 | 12 | 0 | 0 | 72×410 | 39 |
| scale_1024 | q5 | 12 | 12 | 0 | 0 | 226×74 | 22 |
| scale_1024 | q6 | 12 | 12 | 0 | 0 | 744×222 | 220 |
| scale_768 | q4 | 12 | 12 | 0 | 0 | 55×311 | 23 |
| scale_768 | q5 | 12 | 12 | 0 | 0 | 174×57 | 13 |
| scale_768 | q6 | 12 | 12 | 0 | 0 | 557×167 | 124 |
| jpeg_q40 | q4 | 12 | 12 | 0 | 0 | 147×883 | 173 |
| jpeg_q40 | q5 | 12 | 12 | 0 | 0 | 482×161 | 103 |
| jpeg_q40 | q6 | 12 | 12 | 0 | 0 | 1568×468 | 978 |
| blur_1.5 | q4 | 12 | 12 | 0 | 0 | 147×887 | 174 |
| blur_1.5 | q5 | 12 | 12 | 0 | 0 | 478×155 | 99 |
| blur_1.5 | q6 | 12 | 12 | 0 | 0 | 1568×468 | 978 |
| rotate_2 | q4 | 12 | 12 | 0 | 0 | 153×891 | 182 |
| rotate_2 | q5 | 12 | 12 | 0 | 0 | 486×165 | 107 |
| rotate_2 | q6 | 12 | 12 | 0 | 0 | 1568×460 | 962 |
| rotate_5 | q4 | 12 | 12 | 0 | 0 | 162×889 | 192 |
| rotate_5 | q5 | 12 | 12 | 0 | 0 | 492×164 | 108 |
| rotate_5 | q6 | 12 | 12 | 0 | 0 | 1568×449 | 939 |
| perspective_3% | q4 | 12 | 0 | 12 | 0 | 147×884 | 173 |
| perspective_3% | q5 | 12 | 0 | 12 | 0 | 494×161 | 106 |
| perspective_3% | q6 | 12 | 12 | 0 | 0 | 1568×468 | 978 |
| phone_photo | q4 | 12 | 0 | 10 | 2 | 89×499 | 59 |
| phone_photo | q5 | 12 | 12 | 0 | 0 | 282×89 | 33 |
| phone_photo | q6 | 12 | 12 | 0 | 0 | 950×278 | 352 |

q4 = which boxes did B tick (rows 1-17 × [B ticks, row numbers]); q5 = did A tick 8 (rows 7-9 × [A ticks, label]); q6 = sketch panel. Full page ≈ 1531 image tokens (est.); gold_crop_px:384 ≈ 197.

Deskew: the page tilt is estimated from the 'VEHICLE A'/'VEHICLE B' headers and the page is rotated upright before selection (|tilt| 0.7–10°); boxes are mapped back to the original image. rotate_* rows score against gold boxes transformed onto the deskewed page (exact up to the tilt estimate). perspective/phone_photo rows still score against untransformed gold, so 'partial' there mostly means the gold box moved. 'missed' with crop size 0×0 means no anchor was found: the question falls back to the overview.

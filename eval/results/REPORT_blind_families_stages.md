# Blind document families: $0 stage report (no model answers)

Invocation: `python -m bench.blind_stage_report --out eval/results/REPORT_blind_families_stages.md (run from a worktree at 944e679 with this script copied in)` · commit `944e679` · `pipeline/` tree `25220c27ceff` · matches freeze: `freeze-router-v2` · pipeline dirty: False · eval dirty: False

Router run with `anchor=True, fallback='page'` (the shipped router@v2 defaults) and a fake model that only records the request. 'wrong exit' = an OCR answer that differs from gold.

| set | items | images = images.sha256 | OCR exits | wrong exits | router route | errors |
|---|---:|---|---:|---:|---|---:|
| `breaker_panel` | 80 | 10/10 | 0/80 | 0 | full page: 80 | 0 |
| `repair_invoice` | 80 | 10/10 | 0/80 | 0 | full page: 80 | 0 |
| `travel_claim` | 80 | 10/10 | 0/80 | 0 | full page: 80 | 0 |
| `vehicle_damage` | 80 | 10/10 | 0/80 | 0 | full page: 80 | 0 |

Fake-model requests recorded: 320. No answer quality is measured here: routing every item to a page call says nothing about accuracy or equality with `full_image` (different prompt and image size).

## Evaluated image checksums

```
400d520f9ef35eeae35c2ae9874be0eccda808fa44f0b6f8c7ead41897817e0c  eval/data/breaker_panel/images/bp-001a.png
1fbd7b94b9ef3a7be5a1aadb7962dc4dd1173fc601b5627924d21f6331f15eb4  eval/data/breaker_panel/images/bp-001b.png
aa6bbbab13a79018b86723af462884748c7989265b89e19af784e67172b75d82  eval/data/breaker_panel/images/bp-002a.png
142b20f1127172bf06ac655569a925955cf82e28d40bf141fb8c11776187a1aa  eval/data/breaker_panel/images/bp-002b.png
be284059ec3c7fadd1aff0bae8a7bd5ec907cf694cddd70fb784c5f6b41b3302  eval/data/breaker_panel/images/bp-003a.png
e1a04ebe3d137ed56ba5979a307ef41bedeec391587fa063e832b3a2d3459b92  eval/data/breaker_panel/images/bp-003b.png
4a5a400c5f74bf9cb818b81ebdf462a000ccf060bb04134cd929ad2056a46b1b  eval/data/breaker_panel/images/bp-004a.png
90183b3d1279d3a95293dcceb0a2989b3cc06e41b85383e699210c11f05eb100  eval/data/breaker_panel/images/bp-004b.png
99e5bf2124adaac6b41c2af00a375c2466226872345a301bffa60f7bc4029d92  eval/data/breaker_panel/images/bp-005a.png
a62a9a40973a9a9d11b3e5fa99e945c53a00cb047120acb2173ca3cf0f6c8eed  eval/data/breaker_panel/images/bp-005b.png
f75aef227a495bac7088d0fc7bf65ce52c0ca169b6118c84f879daf01279d51c  eval/data/repair_invoice/images/inv-001a.png
1de107624d46ae2279d291b64c3cc21561a38700e2be901acc6c5ec374487c4f  eval/data/repair_invoice/images/inv-001b.png
5683da297d5c31a3996efa1403c0b32f9840ede618618383e2c162af005ff42c  eval/data/repair_invoice/images/inv-002a.png
79393385c7c29656a8a0ab06e81674a88bc93c79d6afa84a61ddaa6dd4ce22c1  eval/data/repair_invoice/images/inv-002b.png
8f1652831b96e1e88e5f874a8fc3aeed42d561c3964d2031c1b88c846e9656aa  eval/data/repair_invoice/images/inv-003a.png
bf50dbac12cfea4eea472aa753b08863a5d876d1b34f8c3006f3fbb502b9284f  eval/data/repair_invoice/images/inv-003b.png
c2529e6347d0b005b14e55e97d7d456802fa7fad3bdb91d3e8503a070d1c9d51  eval/data/repair_invoice/images/inv-004a.png
f34aa0bc857e6148a4d907dfd5e7deaab33fa4bfa33f176259b1bf06634cdd17  eval/data/repair_invoice/images/inv-004b.png
2eb179e4a5ee6a7ae882e348879e2e81ecc9569619762d753e885541e47e7f2a  eval/data/repair_invoice/images/inv-005a.png
f71dfed4a57a49f3fdf7c1f8a4fe107f7d5c6c512d9e3268e163e58e01b87d52  eval/data/repair_invoice/images/inv-005b.png
7a346e6b68115fb45c2cc82170910a3563d2937c851196a1d55d036a3230c382  eval/data/travel_claim/images/clm-001a.png
7e09c43381f056c5396f8a05c868654da6364f9eb9b12a7bc31ccfe5e8de6e3a  eval/data/travel_claim/images/clm-001b.png
588d4de4b25de7f64d1058d884e688083d0901bf0763baf307ef5f74d4081ea6  eval/data/travel_claim/images/clm-002a.png
11b31b08193171ce8624c77c06586a7a791ee635cbd9f68e2fd01d035e7556e7  eval/data/travel_claim/images/clm-002b.png
a85d98459a3d59c5855b8b0d90f96557f65c7e8b6999a61fda8bab5e6a97fed8  eval/data/travel_claim/images/clm-003a.png
f969ad9a2e233eee0956e06f9d3e7e10a623d940b23b90cfced9f51b8fa1d30d  eval/data/travel_claim/images/clm-003b.png
4969cf4e5fcb2dfe36447fe0c87e281128bab0672dbee382f4872190d9214366  eval/data/travel_claim/images/clm-004a.png
27c5b76c9ca9bc09c83ab12d21b9516f0392ab43d25bb7b7bc192c934b380eef  eval/data/travel_claim/images/clm-004b.png
51845aa7e8f20725d89cbf982893c32731d146088b6dc218b6ac3bf7223b2dab  eval/data/travel_claim/images/clm-005a.png
7aac23cea1764f9cfce30b347bc0e5ee98aee5e387e7facab7e58ec32a6be5e8  eval/data/travel_claim/images/clm-005b.png
77bdd1fb8e4da1bfca14f6b4dcc5e81c45288a3f70f74fd7ca226d8add5b0fd5  eval/data/vehicle_damage/images/dmg-001a.png
05041671782b25a00bc0d0b281dc4df9930fec02cd89af41f44ae532a9a3b977  eval/data/vehicle_damage/images/dmg-001b.png
5d62023908997eca46da2f0ffdadf3337364930e600e31e34a882db9120a46ca  eval/data/vehicle_damage/images/dmg-002a.png
64b055e0ffe6d0804a2e12659198f3ba364289df9b020407df2f192328d4342c  eval/data/vehicle_damage/images/dmg-002b.png
660e38b8054e64c3cfd7b4e4cc534ac9504c63a612431f6b2786ad4904fd3f26  eval/data/vehicle_damage/images/dmg-003a.png
17e9918e06e9ac835cfef9b5088a9dc670bba0617b173606cd27d8c040cab959  eval/data/vehicle_damage/images/dmg-003b.png
b92cf8bdbf82fc908457dac02045db5512d71482155c447ced8bee9504d6491d  eval/data/vehicle_damage/images/dmg-004a.png
5977599c042af52e954ad032f70c18d9906a23188f6b181a3e01ed11698fbcf2  eval/data/vehicle_damage/images/dmg-004b.png
2f221556cbf498116a566f4215dc50fac621bc80a0d97298fdd12bfa8641536d  eval/data/vehicle_damage/images/dmg-005a.png
5464089f2763a5182daab34b1c3af6f8f2795f635e021a770dffb9ec0f3b9c75  eval/data/vehicle_damage/images/dmg-005b.png
```

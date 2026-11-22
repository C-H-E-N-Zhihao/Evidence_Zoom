# Independent scoring of the LN-head regions (claude-guanyu, eval.grid_coverage; random rates exact, 184)

| set | k | n with gold box | centre in top-k | random | ratio | top-k cells on box | random | argmax on box | random |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| receipts_v1 | 1 | 121 | 0.008 | 0.004 | 2.12x | 0.256 | 0.066 | 0.256 | 0.066 |
| receipts_v1 | 4 | 121 | 0.041 | 0.016 | 2.64x | 0.202 | 0.066 | 0.256 | 0.066 |
| receipts_v1 | 16 | 121 | 0.124 | 0.062 | 1.98x | 0.172 | 0.066 | 0.256 | 0.066 |

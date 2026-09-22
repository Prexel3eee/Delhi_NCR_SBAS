# PIPELINE IMMUTABILITY

Everything upstream of this line is **immutable**. No scientific-processing
step may modify, re-clip, re-generate or re-download any of it.

| Layer | Path | Status |
|---|---|---|
| HyP3 corpus (ZIPs + extracted) | `data/production_zips/`, `data/production_extracted/` | immutable, hash-inventoried |
| Frozen network (336 pairs) | `freeze/v1/` | immutable, read-only, `freeze_id cf2bdbfd...` |
| MintPy input (336 pairs / 119 dates) | this directory | immutable, hash-pinned |
| Clipped rasters | `mintpy/production_clipped/` | derived, regenerable from the corpus |
| MintPy working dirs | `mintpy/<branch>_work/` | mutable, one per branch |

The HyP3 corpus is never altered by any downstream step.

## Freeze

**freeze_id:** `0cbe4c4f38b8a20f38b2cb71d135ec803f5e88797a6dbca2af8e393aea8261cf`

```text
interferograms  336
dates           119
unwrapPhase     (336, 2407, 2939)
first / last    20211006 / 20250927
network fp      399aa1445a6f0fefa40ea4c0cfa2b7bb38f419f0f55214c2043214a1c2d88b22
```

Verify with `python scripts/verify_mintpy_input_v1.py`.

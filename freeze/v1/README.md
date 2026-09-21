# Freeze v1 — immutable production baseline

**freeze_id:** `cf2bdbfd4fa722dd0df9608afba13bf7cd9361a0897dea14ea70e724c8b1924d`

Created 2026-09-21T22:32:16.731133+00:00.

This directory is a read-only snapshot. Do not edit files here: editing them
breaks the freeze and `scripts/verify_freeze.py` will fail.

## Decision

```text
accepted acquisitions   119
interferogram pairs     336
bursts per job (K)      4
pilot                   7 jobs @ 10x2 = 35 credits
production @ 10x2       1680 credits
excluded                2025-05-18 (027_056011_IW2) — permanently, for v1
```

Production remains **blocked** pending pilot QC and explicit owner approval.

## Verify

```bash
python scripts/verify_freeze.py
```

Exit code 0 means the snapshot and the working manifests still agree with
`freeze_id`. Any other exit means drift: stop and investigate before spending
HyP3 credits.

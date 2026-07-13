# Regression clip fixtures

Place real `.mp4` files here and add entries to `../registry.json`.

Each registry entry needs:

- `id` — stable slug
- `clip` — filename under `clips/`
- `metadata` — passed to `ClipAnalysisMetadata.from_job_upload` (`clip_label`, `stance`, `obstacle`, `tricks`, `duration_seconds`, optional `mime_type`, `account_tier`)
- `contract` — assertion rules (see `test_gemini_hallucination.py`)
- `consistency_check` (optional) — if true, `test_output_consistency` runs the clip twice

Do not commit large binaries; keep clips local or in private storage.

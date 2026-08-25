# OF-002 — Freeze the current intelligence contract

Date: 2026-08-21

Characterization only. No production behavior changes. No renaming. No new architecture.

## Files changed

- [`services/api/tests/test_intelligence_contract.py`](../services/api/tests/test_intelligence_contract.py) (added)

No files under `services/api/app/` were modified.

## Tests added

Sixteen tests (eighteen cases with the `review_readiness` parametrize) covering:

1. Valid provider JSON → `GeminiClipAnalysis`
2. Empty input → `gemini_empty`
3. Unclosed JSON → `gemini_malformed_json`
4. Valid JSON, invalid schema → `gemini_schema_mismatch`
5. Leading prose around `{...}` → parse succeeds (observed)
6. Trailing prose after `{...}` → `gemini_malformed_json` (observed)
7. Gemini assembly → `ClipResultPayload`
8. Twelve Labs JSON uses the same `GeminiClipAnalysis` parse path
9. Pegasus `review_model` currently fails `NormalizedReviewPayload.model` (`Literal["gemini"]` only)
10. Gemini `normalized_review.model == "gemini"`
11. `landed` / `land_score` survive when landed is yes; score dropped when landed is no
12. Observations survive as flattened presentation text
13. Known `review_readiness` values survive; unknown becomes `limited`
14. `best_cue` and `first_actionable_cue_shown` survive

Existing suites were left alone:

- `tests/test_gemini_analysis_parse.py`
- `tests/test_clip_review_assembly.py`
- `tests/test_expected_mechanics_gate.py`
- `tests/test_degraded_provider_result.py`

## Test command

```bash
cd services/api
python -m pytest -q tests/test_intelligence_contract.py tests/test_gemini_analysis_parse.py tests/test_clip_review_assembly.py tests/test_expected_mechanics_gate.py tests/test_degraded_provider_result.py
python -m pytest -q
```

## Passing result

| Suite | Result |
|-------|--------|
| Focused (contract + existing parse/assembly/gate/degraded) | 41 passed |
| Full API | 451 passed, 4 skipped, 2 failed |

The two full-suite failures are pre-existing quota tests, not this contract file:

- `tests/test_auth_and_list.py::test_clip_submission_monthly_quota_exceeded_returns_429`
- `tests/test_clip_quota_release.py::test_released_bonus_credit_is_returned_to_the_user`

## Frozen behavior (do not “clean up” in OF-003 by accident)

```
raw JSON
→ parse_gemini_clip_analysis_dict
→ validate_gemini_clip_analysis
→ apply_expected_mechanics_gate
→ build_completed_result_from_gemini
→ ClipResultPayload
```

- Strip fences, then `json.loads`, then balanced `{...}` fallback.
- Leading prose + valid object parses. Trailing prose after the object is `gemini_malformed_json`.
- Twelve Labs already parses into `GeminiClipAnalysis` via those same functions.
- `land_score` is kept only when `landed == "yes"`.
- Unknown `review_readiness` becomes `"limited"` on `build_completed_result_from_gemini`.
- Observations are flattened to `"[Video pass] ..."` and `"{title}: {detail} [{severity}]"`.
- `NormalizedReviewPayload.model` is `Literal["gemini"]` only. `review_model="pegasus"` currently raises `ValidationError` before a payload is returned. That raise is frozen; the schema was not widened.

## Anything surprising

1. The shared provider contract today is `GeminiClipAnalysis`, not a dual-label `ClipResultPayload`.
2. Pegasus assembly cannot currently complete because of the `Literal["gemini"]` constraint.
3. Leading vs trailing prose are not the same outcome.

## How I did this

1. Ran the parser and Pegasus assembler first, then wrote tests to match those results.
2. Split empty / unclosed / schema-invalid, and treated leading vs trailing prose as two cases.
3. Compared providers at `GeminiClipAnalysis`; froze the Pegasus `Literal["gemini"]` failure instead of changing production.
4. Added one contract file, ran the focused suite (green), then the full API suite, and left the unrelated quota failures alone.

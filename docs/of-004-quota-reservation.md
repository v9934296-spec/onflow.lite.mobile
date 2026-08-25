# OF-004 — Quota reservation and finalization (BE-002)

**Status:** Closed at the **working-tree verification** level.  
**Date:** 2026-08-24  
**Phase:** 0 contract verification  
**Spec names:** BE-002 · §9 change 12 · §2 decision 17 · §18 gate item 3

No production quota change. Railway / deployed parity is **unverified**.

This ticket closed as a **stale/racy test correction**. The original monthly-cap fixture created unreadable clips, which correctly refunded `monthly`, so that test never established quota exhaustion.

---

## Files changed (this closeout)

- [`services/api/tests/test_auth_and_list.py`](../services/api/tests/test_auth_and_list.py) — `test_clip_submission_monthly_quota_exceeded_returns_429` only
- This document (ticket → closeout)
- [`docs/README.md`](./README.md) index status

No files under `services/api/app/` were modified for OF-004 (`clip_quota.py`, worker finalization, and unreadable refund behavior are unchanged).

---

## Tests added/modified

Modified one test: `tests/test_auth_and_list.py::test_clip_submission_monthly_quota_exceeded_returns_429`.

The first three submissions now stub a usable first pass, wait for terminal `completed` jobs with `quota_source=monthly`, assert `count_monthly_free_jobs == 3`, then expect **429** on the fourth `complete-upload`.

Did not add a second monthly-cap test. Did not cover the failed-job retry edge (spec §8.3 documents “quota not re-charged”; out of scope for BE-002 closure).

---

## Test command

```bash
cd services/api
python -m pytest -q tests/test_auth_and_list.py::test_clip_submission_monthly_quota_exceeded_returns_429
python -m pytest -q tests/test_clip_quota_release.py tests/test_clips_v1_quota.py tests/test_quota_lock.py tests/test_quota_query_sargability.py tests/test_try_claim_and_enqueue_refund.py tests/test_auth_and_list.py::test_clip_submission_monthly_quota_exceeded_returns_429
python -m pytest -q
```

## Passing result

| Suite | Result |
|-------|--------|
| Repaired 429 test | **1 passed** |
| Focused BE-002 files | **29 passed, 1 failed** |
| Full API | **452 passed, 4 skipped, 1 failed** |

The repaired 429 test is green in isolation and in the full suite.

### Classified leftovers (not production quota bugs)

Same fixture class as the old 429 test: `MINIMAL_VIDEO_SNIFF_BYTES` + in-process worker → `video_unreadable` → `monthly_refunded` / `bonus_refunded` before the assertion reads `quota_source`.

| Test | When | What happened |
|------|------|----------------|
| `test_clips_v1_quota.py::test_complete_upload_records_quota_source` | Focused run + isolation | Expected `monthly`, got `monthly_refunded` |
| `test_clip_quota_release.py::test_released_bonus_credit_is_returned_to_the_user` | Full suite | Expected `bonus` immediately after complete, got `bonus_refunded` |

OF-003 already noted the bonus test as a flake (failed on OF-002’s full run, passed on OF-003). Step 5 did not edit those tests.

These do not reopen OF-003 (attempt-sync). They do not justify changing unreadable refunds.

---

## What was proven (working tree)

Charge is reserved at **`complete-upload` job insert** (`create_job_charging_quota`), not initiate, not Gemini.

Counted monthly slots: `clip_jobs.quota_source IS NULL OR = 'monthly'` this UTC month vs `ONFLOW_RATE_LIMIT_FREE`. Refunds stamp `monthly_refunded` / `bonus_refunded` so the row drops out of the count.

| BE-002 bullet | Working-tree result |
|---------------|---------------------|
| Reserve at accepted submission | Satisfied (`complete-upload` insert) |
| Finalize on usable completion | Satisfied (`usable` **and** `limited` keep the charge) |
| Release on provider failure | Satisfied |
| Release on infrastructure failure | Satisfied (`enqueue_failed`) |
| Explicit unreadable policy | Satisfied: **release**, do not bill |
| Idempotent reserve / finalize / release | Satisfied on mapped paths |

Historical spec line “released only when enqueue throws” is **not** current working-tree behavior.

---

## Why the old 429 test never proved the cap

`MINIMAL_VIDEO_SNIFF_BYTES` passes complete-upload, then the worker marks `video_unreadable` and releases the reservation. After three such jobs, `count_monthly_free_jobs == 0`, so the fourth complete correctly returned **200**. The test also raced background `create_task` analysis.

That was a stale assertion against pre-refund occupancy, not a missing monthly cap.

---

## Explicit scope of this closeout

**Verified:** local working-tree reserve/finalize/release map; unreadable refund policy; repaired HTTP monthly-429 fixture.

**Not verified:** Railway or any deployed API. Do not treat local pytest as production parity. Deploy/commit is a separate step.

§18 gate item 3 (“Failed-analysis quota release decided and ticketed”) is closed **against this working tree**. The V1 spec stays Draft until remaining §18 items close.

---

## Original ticket (kept for sequence)

OF-001 mapped the clip path. OF-002 froze the intelligence contract. OF-003 closed attempt-sync (working tree). OF-004 was §16.3 item 2 because a skater must not stay charged unless usable analysis returns.

Out of scope (honored): BE-003/004 session-end, Gemini rename, `NormalizedReviewPayload.model`, R2, failed-job retry accounting, production quota edits.

---

## What comes next (do not pull forward)

**BE-003 + BE-004** together (session-end conflict and ended-session clip window). Then EXP-001. Provider-neutral intelligence types remain next-release; OF-002 stays the freeze.

Sibling racy quota assertions (`records_quota_source`, bonus immediate-read) are the same test-fixture class. They are not this closeout’s production work.

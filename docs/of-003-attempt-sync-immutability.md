# OF-003 — Attempt-sync immutability (BE-001)

**Status:** Closed at the **working-tree verification** level.  
**Date:** 2026-08-24  
**Phase:** 0 contract verification  
**Spec names:** BE-001 · §9 change 11 · §18 gate item 2

No production remediation. Railway / deployed parity is **unverified**.

---

## Files changed (this closeout)

- This document (ticket → closeout)
- [`docs/README.md`](./README.md) index status

No files under `services/api/app/` were modified for OF-003. Characterization used the existing working-tree suite [`services/api/tests/test_attempt_sync_immutability.py`](../services/api/tests/test_attempt_sync_immutability.py).

---

## Test command

```bash
cd services/api
python -m pytest -q tests/test_attempt_sync_immutability.py
python -m pytest -q
```

## Passing result

| Suite | Result |
|-------|--------|
| Focused BE-001 (`test_attempt_sync_immutability.py`) | **12 passed** |
| Full API | **452 passed, 4 skipped, 1 failed** |

The sole full-suite failure is quota, not attempt-sync:

- `tests/test_auth_and_list.py::test_clip_submission_monthly_quota_exceeded_returns_429` (expected 429, got 200)

That belongs to **BE-002 / OF-004**. It does not reopen OF-003.

(`test_released_bonus_credit_is_returned_to_the_user` failed during OF-002’s full run and passed on this OF-003 run. Still quota, still not this ticket.)

---

## What was proven (working tree)

`POST /api/v1/session-attempts/sync` is **immutable replay, not an upsert**.

| BE-001 bullet | Working-tree result |
|---------------|---------------------|
| Identical `(user_id, attempt_id)` payload → accepted, no mutation | Satisfied |
| Changed payload → structured reject; row untouched | Satisfied (`session_immutable` / `outcome_immutable` / `attempt_immutable`) |
| Attempt cannot change sessions | Satisfied |
| Deleted attempt cannot resurrect | Satisfied (`attempt_deleted`) |
| Unknown outcome never coerced to `missed` | Satisfied (ingress 422; `_to_out` omits) |
| Unique `(user_id, id)` | Satisfied (PK on `id` plus `uq_session_attempts_user_attempt`) |
| Tests cover the bullets | Satisfied (12 tests) |

Identity compared: `(session_id, trick_id, canonical_name, outcome, logged_at UTC)`. Existing rows are never written. Lookup is by global `id`, then `user_id` (`forbidden` if another account).

---

## Explicit scope of this closeout

**Verified:** local working tree (`session_attempts` router/schema, untracked migration `20260804_attempt_sync_immutability.py`, existing BE-001 tests).

**Not verified:** Railway or any deployed API. Do not treat “12/12 locally” as production parity. Deploy/commit is a separate step.

§18 gate item 2 (“Attempt-ID mutation resolved”) is closed **against this working tree**. The V1 spec stays Draft until the remaining §18 items close. The spec is still **not** approved for launch-client feature implementation.

---

## Original ticket (kept for sequence)

OF-001 mapped the clip path. OF-002 froze the intelligence contract. OF-003 was §16.3 item 1 because a silently mutated manual outcome is unrecoverable.

Out of scope (honored): Gemini rename, `NormalizedReviewPayload.model` widen, BE-002/003/004/005, EXP-001, launch UI.

---

## What comes next

**OF-004 / BE-002** — quota reservation, finalization, and release (§9 change 12, §18 item 3). Start from the remaining red test above. Do not pull session-end, compression, or provider-neutral types forward.

---

## How I did this

1. Mapped live sync from the router, schema, model, migration, and BE-001 tests (no production edits).
2. Compared each §16.3 bullet; all held in the working tree.
3. Ran focused 12/12, then full API; classified the remaining 429 failure as BE-002.
4. Wrote this closeout and marked the docs index closed at working-tree verification only.

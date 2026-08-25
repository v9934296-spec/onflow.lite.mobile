# OF-005 — Ended-session upload + session-end conflict (BE-004 / BE-003)

**Status:** Closed at the **working-tree verification** level.  
**Date:** 2026-08-24  
**Phase:** 0 contract verification  
**Spec names:** BE-004 · BE-003 · §9 changes 13 and 6 · §11.8–11.9 · §16.3 items 3–4 · §18 gate item 4

This ticket **did change production** (unlike OF-003 and OF-004): two proven gaps only. Railway / deployed parity is **unverified**.

---

## Files changed (this closeout)

- [`services/api/app/routers/sessions.py`](../services/api/app/routers/sessions.py) — conditional `UPDATE … WHERE ended_at IS NULL`; recap only when `rowcount == 1`
- [`services/api/app/models.py`](../services/api/app/models.py) — `ClipModel.captured_at` (nullable)
- [`services/api/app/routers/clips_v1.py`](../services/api/app/routers/clips_v1.py) — persist `captured_at` at initiate
- [`services/api/app/services/clip_v1_pipeline.py`](../services/api/app/services/clip_v1_pipeline.py) — complete-upload gate uses `clip.captured_at`, never `created_at`
- [`services/api/migrations/versions/20260824_clips_captured_at.py`](../services/api/migrations/versions/20260824_clips_captured_at.py)
- [`services/api/tests/test_session_end_contract.py`](../services/api/tests/test_session_end_contract.py) — three regression tests
- This document; [`docs/README.md`](./README.md)

Quota, intelligence, and attempt-sync were not modified.

---

## Tests added/modified

Added three tests in `test_session_end_contract.py`:

1. `test_concurrent_first_end_keeps_one_winner_and_one_recap` — overlapping PATCH; one durable `ended_at`; loser receives the winner; one recap
2. `test_complete_upload_keeps_captured_at_across_ended_session` — capture before end, initiate after end inside 24h, complete **200**
3. `test_legacy_complete_upload_without_captured_at_uses_window_only` — omitted `captured_at`; complete **200** (window only)

Existing sequential first-end, identical replay, conflicting sequential end, open-session upload, capture-after/before, window expiry, and legacy initiate tests were left in place.

---

## Test command

```bash
cd services/api
python -m pytest -q tests/test_session_end_contract.py
python -m pytest -q
```

## Passing result

| Suite | Result |
|-------|--------|
| Focused (`test_session_end_contract.py`) | **11 passed** |
| Full API | **456 passed, 4 skipped, 0 failed** |

---

## What was proven (working tree)

### BE-003 — Session-end conflict

`PATCH /sessions/{id}` applies unrelated fields, then:

```sql
UPDATE skate_sessions
SET ended_at = :incoming
WHERE id = :session_id AND user_id = :user_id
  AND ended_at IS NULL AND deleted_at IS NULL
```

Reload and return the stored timestamp. Recap runs only if that statement updated one row (`NULL → ended_at`).

| Bullet | Result |
|--------|--------|
| First end | Incoming timestamp wins |
| Identical replay | 200, same value, no second recap |
| Sequential conflict | 200, original winner returned; `notes` still apply |
| Concurrent conflict | Exactly one durable `ended_at`; both responses return it |
| Recap once | Only the transitioning request calls the generator (unique index remains defense-in-depth) |

### BE-004 — Ended-session clip reconciliation

| Bullet | Result |
|--------|--------|
| Open session accepts | Unchanged |
| Capture must predate `ended_at` | Initiate uses body `captured_at`; complete uses persisted `clips.captured_at` |
| 24h window | Unchanged (`now` vs `ended_at + 24h`) |
| Structured codes | Unchanged |
| Legacy omit `captured_at` | Store NULL; complete is **window-only**, not `created_at` as capture |

---

## Explicit scope of this closeout

**Verified:** local working tree (conditional end, `clips.captured_at`, focused + full pytest).

**Not verified:** Railway or any deployed API. The new Alembic revision must run on deploy. Do not treat local green as production parity.

§18 gate item 4 (uploads into ended sessions restricted) is closed **against this working tree**. The V1 spec stays Draft until remaining §18 items close.

---

## Original ticket (kept for sequence)

OF-001 mapped the clip path. OF-002 froze intelligence. OF-003 closed attempt-sync. OF-004 closed quota (test-side). OF-005 was §16 order-of-work item 3 because offline reconciliation is wrong if either late clips or stale `pending_end` can rewrite the session.

Out of scope (honored): quota, Gemini rename, EXP-001, R2, client `pending_end` UI.

---

## What comes next (do not pull forward)

**EXP-001** (physical compression). Then remaining UNVERIFIED / DOC-001. Provider-neutral intelligence types remain next-release; OF-002 stays the freeze.

# OnFlow P0 Remediation Log

Branch: `remediation/p0`
Originally written against `c:\onflow-lite-mobile`; restored into `c:\onflowdemo`
as the audit trail for P0 fixes (user-scoped storage and related work). Some
follow-on architecture (Flow/PTE, server history, RevenueCat, crash-recovery
stores) landed after these entries — see current `docs/` release checklists.
Issue register: `ONFLOW_REDUCED_LAUNCH_ISSUES.md` (reduced). The deep register
(`ONFLOW_REPOMIX_DEEP_ISSUE_REGISTER.md`) with the 15 authoritative P0s was not
provided; entries below map to the reduced register's issue groups.

## Environment capabilities (affects what can be verified here)

- Node v24.18.0 / npm 11.16.0 — available. Frontend tests, typecheck, and iOS
  bundle run and are authoritative.
- Python 3.12.10 — installed via winget (user scope) after the initial pass.
  Backend venv at `services/api/.venv` (gitignored) with `requirements.txt`
  installed. Backend pytest suite now runs locally.
- Still unavailable: Docker (container build checks) and a real Postgres/Redis
  (production-config startup + clean-DB Alembic-on-Postgres checks). Backend
  tests run against SQLite via the test fixtures.

### Backend test baseline (no backend code changed yet)

`python -m pytest -q` → 341 passed, 4 skipped, 3 failed initially. The 3
failures are ENVIRONMENTAL, not regressions:

- `test_production_settings_require_redis_url`
- `test_production_settings_reject_non_redis_url`
- `test_session_rate_limited`

Root cause: `app/core/config.py` `Settings` loads `env_file=services/api/.env`.
These tests do not set `ONFLOW_ADMIN_EMAILS` themselves and rely on it coming
from a local `.env` (absent in a clean clone), so `Settings()` trips on the
admin-emails production guard before reaching the assertion under test.
Re-running the three with `ONFLOW_ADMIN_EMAILS` set → all 3 PASS. Effective
baseline: 344 pass, 4 skipped, 0 genuine failures. (Latent test-isolation
weakness worth fixing separately: these tests should set/clear their own env
rather than depend on `.env`.)

---

## Entry 1 — Group 2 (partial): user-scoped on-device storage

Issue group: 2 (Progression data has no single source of truth).
Sub-problem addressed: "Several local keys are not scoped to the authenticated
user" → on a shared device, account B could read account A's local data.

Scope of this fix (deliberately narrow): on-device (AsyncStorage) isolation
only. The larger Group 2 work — canonical server-side `SessionAttempt` model,
offline outbox, server-generated recaps — is backend and remains open.

### Root cause

All local stores wrote to global AsyncStorage keys with no user namespace:
`onflow_lite_log_v1`, `onflow_lite_progress_v1`, `onflow.sessionAttempts.v1`,
`onflow.completedSessions.v1`, `onflow.activeSession.v2`,
`onflow.lastRecapSession.v2`.

### Change

- New `src/storage/userScope.ts`: holds the active user id, derives
  `u:<userId>:<baseKey>` via `scopedKey()`, and runs a one-time device
  migration (`activateStorageForUser`) that moves legacy unscoped values into
  the first authenticated user's namespace, then deletes the legacy keys and
  records a device migration flag.
- All six per-user keys now resolved through `scopedKey()` in the five stores.
- `src/auth/accountContext.tsx`: on `refreshUser()` success, calls
  `activateStorageForUser(user_id)`; on failure / `clearUser()`, calls
  `setStorageUserId(null)`.
- Identity keys (`onflow_session_*`, secureStorage keys) intentionally NOT
  scoped — they define who the user is.

### Files changed

- `src/storage/userScope.ts` (new)
- `src/storage.ts`
- `src/progress.ts`
- `src/sessionAttempts/sessionAttemptStore.ts`
- `src/sessionRecap/completedSessionStore.ts`
- `src/activeSessionStore.ts`
- `src/auth/accountContext.tsx`

### Migrations added

None (backend). On-device migration is one-time and self-contained in
`userScope.ts`.

### Tests added / updated

- `src/__tests__/storage/userScope.test.ts` (new, 7 tests): base-key fallback
  when signed out, per-user namespacing, blank-id handling, cross-account log
  isolation, per-account clear isolation, one-time legacy migration, and proof
  that a later account does not inherit migrated data.
- Existing storage tests unchanged and still green (base-key fallback preserves
  prior behavior when no user is set).

### Commands run / results

- `npm run typecheck` → PASS (exit 0)
- `npm test` → PASS, 150/150 tests across 32 files (7 new)
- `npm run bundle:ios` → PASS (exit 0), `dist-ios` exported

### Acceptance criteria status (reduced register, Group 2)

- [x] Account A records never appear for Account B (local) — proven by tests.
- [x] Existing local data has a documented migration path — one-time device
      migration; behavior documented here.
- [ ] Manual attempts survive reinstall / device change — NOT addressed
      (requires server sync; backend).
- [ ] Offline attempts synchronize without duplication — NOT addressed (backend).
- [ ] Server-generated recaps match history/progression — NOT addressed (backend).

### Remaining risks / decisions to confirm

- Migration attribution: the one-time migration assigns pre-existing unscoped
  local data to the FIRST account that signs in after the update. For the
  common single-user device this is correct. Residual edge case: if the device
  had data from account A but account B signs in first post-update, B inherits
  A's local cache once. Safer-but-lossier alternative: discard legacy local data
  entirely. Flagging for product/privacy decision.
- This is on-device isolation only. It does not resolve the core Group 2
  architectural problem (no canonical server attempt model). That work is
  backend and blocked in this environment (no Python).

---

## Entry 2 — Group 5: server-side upload size verification

Issue group: 5 (Upload validation). Sub-problem addressed: the V1
complete-upload path trusted the client's declared `size_bytes` and only checked
object *existence* before charging product quota and enqueuing (expensive)
analysis. A client could declare a tiny size, upload an empty or oversized
object, and still burn a quota slot / enqueue a doomed job.

### Root cause

- `ObjectStorage` protocol exposed `exists()` but no way to read the actual
  stored object size, so `complete_v1_clip_upload` could not verify bytes.
- `complete_v1_clip_upload` gated only on `storage.exists(key)`, then charged
  quota and enqueued.

### Change

- `app/services/object_storage.py`: added `async size(key) -> int | None` to the
  `ObjectStorage` protocol, `LocalStorage` (`Path.stat().st_size`), and
  `S3Storage` (`head_object` → `ContentLength`).
- `app/core/config.py`: added `clip_max_upload_bytes` (default 200 MiB, `0`
  disables), tunable via `ONFLOW_CLIP_MAX_UPLOAD_BYTES`.
- `app/services/clip_v1_pipeline.py`: after the existence check and BEFORE any
  quota reservation / enqueue, measure the real object:
  - empty/unreadable (`size None` or `<= 0`) → delete object, `422`.
  - over `clip_max_upload_bytes` → delete object, `413`.
  - otherwise overwrite the client-declared `clip.size_bytes` with the
    server-measured value (server metadata replaces client claim).

### Files changed

- `services/api/app/services/object_storage.py`
- `services/api/app/core/config.py`
- `services/api/app/services/clip_v1_pipeline.py`

### Migrations added

None.

### Tests added / updated

- `tests/test_clips_complete_upload.py` (3 new): empty object → 422 + object
  deleted + clip stays `pending` + no `ClipJob`; oversized object (env-lowered
  ceiling) → 413 + object deleted + no `ClipJob`; server-measured size overwrites
  the declared value.
- `tests/test_api_contract.py`: `test_empty_upload_fails_job_with_video_unreadable`
  rewrote to `test_empty_upload_rejected_at_complete_upload` — the old behavior
  (empty upload silently enqueued, worker later fails `video_unreadable`, quota
  already spent) is replaced by early `422` with no job created.

### Commands run / results

- `pytest tests/test_clips_complete_upload.py -q` → 8 passed.
- `pytest tests/test_api_contract.py tests/test_rate_limit_security.py -q` →
  contract file green; the single remaining failure is the pre-existing
  order-dependent `test_session_rate_limited` (see baseline note below).
- Full suite `pytest -q` → 345 passed, 4 skipped, 2 failed. Both failures are
  pre-existing/environmental, NOT from this change:
  - `test_session_rate_limited` — passes in isolation; fails only after sibling
    tests exhaust the shared in-memory slowapi limiter bucket for `ip:testclient`
    (test-isolation weakness; the limiter is not reset between tests).
  - (the earlier 3 `ONFLOW_ADMIN_EMAILS` env failures are resolved by exporting
    that var, as documented in the baseline.)

### Acceptance criteria status (reduced register, Group 5)

- [x] A client cannot upload more bytes than allowed — verified.
- [x] Empty/unreadable uploads are rejected before analysis is enqueued —
      verified.
- [x] Rejected objects are deleted immediately — verified.
- [x] Server-extracted size replaces the client claim — verified (size only).
- [ ] Full media probing (duration/dimensions/MIME sniff via OpenCV at
      complete-upload) — NOT done here. The worker already probes on analysis;
      pushing full probe forward to complete-upload is a follow-up to avoid
      changing worker/analysis semantics mid-fix.
- [ ] Expire abandoned `pending` uploads (reaper) — separate scope; flagged.

### Remaining risks / decisions to confirm

- `clip_max_upload_bytes` default (200 MiB) is a chosen ceiling, not a product
  requirement — confirm against real device clip sizes / bitrate.
- Rejection leaves the `clip` row `pending` (object deleted). A `pending`
  reaper (Group 5/Group 3 overlap) is still needed to sweep abandoned rows.

---

## Entry 3 — Group 4 (partial): uncapped data export

Issue group: 4 (Privacy deletion/export). Sub-problem addressed: the data-export
endpoint silently truncated a user's clip history.

### Root cause

`GET /api/v1/account/export` called `repo.list_full_for_user(user_id, limit=500)`,
but BOTH repository implementations hard-cap that method at `min(limit, 100)`
(a legitimate guard for the paginated `/clips` list view, which shares the
method). Net effect: any user with >100 clips received an export missing rows —
a GDPR/CCPA completeness failure, and worse than the `500` the register cited.

### Change

- `app/repositories/clip_jobs.py`: added `iter_all_for_user(user_id, *, batch_size=1000)`
  to the protocol + both impls. The SQL impl reads in bounded batches (one SELECT
  per batch; a single SELECT when the history fits in one batch, preserving the
  export endpoint's constant-query contract) ordered by `(updated_at desc, id desc)`
  for deterministic paging. Records are materialized inside the session to avoid
  detached-instance access.
- `app/routers/account.py`: export now iterates `iter_all_for_user(user_id)`
  instead of the capped `list_full_for_user(..., limit=500)`.
- `list_full_for_user` (and its 100-row cap) is left UNCHANGED because the
  `/clips` list endpoint relies on it.

### Migrations added

None.

### Tests added / updated

- `tests/test_data_export.py`: new `test_export_is_not_truncated_beyond_legacy_cap`
  seeds 230 clips (> old 100 cap and 500 request limit) and asserts all 230 are
  exported with unique ids.
- `tests/test_export_query_count.py`: unchanged and still green — the batched
  iterator issues a single `clip_jobs` SELECT for the seeded volumes, so the
  N+1/constant-query regression guards still hold.

### Commands run / results

- `pytest tests/test_data_export.py tests/test_export_query_count.py -q` →
  7 passed.

### Acceptance criteria status (reduced register, Group 4)

- [x] Export returns the user's complete clip history (no silent truncation) —
      verified.
- [ ] Deletion removes ALL user data across tables + object storage, with purge
      verification — NOT addressed (needs a data-retention/asset-inventory
      decision + real object storage to verify). Gated on privacy decision.
- [ ] Export includes every user-owned table (attempts, sessions, consent,
      billing) — only clips + consent today; expanding scope needs the retention
      decision. Flagged.

### Remaining risks / decisions to confirm

- Very large exports now stream all rows into one JSON response. For a user with
  an extreme history this is a large payload; batching bounds DB memory but not
  response size. A future streaming/`NDJSON` or async-export-file approach may be
  warranted — flag for product.
- The broader Group 4 privacy work (deletion completeness + asset purge
  verification + full-table export coverage) remains open pending a retention
  policy decision.

---

## Entry 4 — Group 8: CI coverage + deterministic backend suite

Issue group: 8 (CI only ran frontend checks). Also fixes a latent test-isolation
bug that had to be resolved before backend CI could be trusted.

### Root cause

- `.github/workflows/ci.yml` ran only Node steps (typecheck, `npm test`,
  `bundle:ios`). No backend tests, no migration check, no container build — a
  whole language/half the system was unguarded.
- The backend suite was not order-independent: the slowapi `limiter` is a
  module-level singleton with in-memory storage that persists across app
  instances, so one rate-limit test's requests pushed the next test over its
  limit (`test_session_rate_limited` failed in full runs, passed in isolation).
- Two production-settings tests relied on `ONFLOW_ADMIN_EMAILS` coming from a
  local `.env`, so they failed on a clean clone / CI.

### Change

- `tests/conftest.py`: new autouse `_reset_rate_limiter_between_tests` fixture
  resets `limiter._storage` before and after every test.
- `tests/test_rate_limit_security.py`: the two production-settings tests now set
  `ONFLOW_ADMIN_EMAILS` themselves (self-contained; no `.env` dependency).
- `.github/workflows/ci.yml`: split into jobs —
  - `frontend` (unchanged steps),
  - `backend` — Python 3.12, `pip install -r requirements.txt`, `python -m pytest -q`,
  - `backend-migrations` — Postgres 16 service, `alembic upgrade head` (clean-DB
    migration check) + `alembic check` (drift guard, `continue-on-error` for now),
  - `docker-build` — builds `services/api/Dockerfile` from the repo root.

### Files changed

- `.github/workflows/ci.yml`
- `services/api/tests/conftest.py`
- `services/api/tests/test_rate_limit_security.py`

### Tests / verification

- Full backend suite with a CLEAN environment (no external env vars):
  `python -m pytest -q` → **348 passed, 4 skipped, 0 failed** (was 2 failed:
  the order-dependent limiter test + the `.env`-dependent settings tests).
- `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` →
  parses OK.

### Acceptance criteria status (reduced register, Group 8)

- [x] CI runs the backend test suite — added and locally verified green.
- [x] CI applies migrations against a real Postgres (clean-DB) — job added.
      NOTE: the `alembic upgrade head` / `alembic check` and `docker build` jobs
      are standard GitHub Actions patterns but were NOT run here (no Docker /
      Postgres / GH runner locally). They will first execute on GitHub.
- [x] CI builds the backend container image — `docker-build` job added (same
      caveat).
- [ ] Android bundle validation — NOT added (no verified `bundle:android`
      script confirmed; flag if one exists).
- [ ] Secret scanning (gitleaks/trufflehog) — NOT added; deliberately omitted to
      avoid a noisy unverified gate. Flagged as a fast follow.

### Remaining risks

- `alembic check` may report pre-existing model/migration drift; it is
  non-blocking until reviewed, then should be promoted to a hard failure.
- The Postgres/Docker jobs are unverified locally; watch the first GitHub run.

---

## Decision-gated P0s (flagged, NOT implemented) — need your call

These P0s cannot be responsibly "finished" as code changes without a product /
billing / privacy / infra decision. Per the remediation rules I flag them with a
concrete recommendation instead of shipping speculative behavior.

### Group 3 (slice) — refund quota on provider/terminal failure  [BILLING + MIGRATION]

Current behavior (verified): quota is charged at complete-upload
(`reserve_clip_submission`). Monthly-free usage is derived by
`count_monthly_free_jobs`, which counts every monthly job in the month
**regardless of status** — so a job that fails due to *our* provider/system
error still burns a free slot. Bonus credits are decremented via
`try_consume_one_bonus` with **no refund path**.

Why not auto-fixed: deciding *which* failures refund is a billing-policy call,
and it is exploitable if wrong (users could intentionally trigger "failures" to
farm free analyses). It also needs a schema change (a `refunded_at` / distinct
`quota_source`) that must be migration-verified on Postgres — not possible here.

Proposed design (pending approval):
- Classify terminal failures into `our_fault` (provider outage, timeout,
  internal exception) vs `user_fault` (`video_unreadable`, no trick detected).
- On `our_fault` terminal failure only: for `bonus` → add a
  `identity.refund_one_bonus(user_id)`; for `monthly` → mark the job
  `quota_source="monthly_refunded"` (new value) and exclude it from
  `count_monthly_free_jobs`.
- Migration: add the column/enum value; backfill nothing.
- Hook point: the job terminal-failure path (worker) / `sync_v1_clip_from_job_result(..., failed=True)`.

DECISION NEEDED: (1) confirm the our-fault vs user-fault mapping; (2) confirm
monthly failures are refundable at all, or only bonus.

### Group 1 — production analytics  [INFRA/PROVIDER]

Current behavior (verified): `src/analytics.ts` `track()` is a no-op outside
`__DEV__`. There is a backend `ClientFunnelEventModel` + a beta-event route, so a
first-party sink may already be partially present.

Why not auto-fixed: choosing the sink is an infrastructure decision.

Options:
- A) First-party: batch/flush client events to an existing backend ingest
  endpoint writing `ClientFunnelEventModel`. No third party; most privacy-
  friendly; needs a dashboard/query later.
- B) Third-party SDK (PostHog / Amplitude / Segment). Fastest dashboards; adds a
  vendor + consent/privacy review.

If you pick (A) I can implement the client buffer + flush seam and the ingest
wiring here and unit-test it (no infra decision beyond "use our backend").

## Architectural gap report — Groups 2 & 3 (NOT attempted)

The core of Groups 2 and 3 are multi-week backend rewrites that also require
clean-DB Postgres migration + production-startup verification unavailable in
this environment. Attempting them as one-shot patches would violate the
"no speculative, unverifiable changes" rule.

- Group 2 core: canonical server-side `SessionAttempt` model, offline outbox
  with idempotent sync, server-generated recaps as the single source of truth.
  (Only the on-device isolation slice was completed — Entry 1.)
- Group 3 core: transactional outbox for job/state transitions, compare-and-set
  job state machine, quota ledger (append-only), idempotent worker + recovery of
  interrupted jobs. (Only the pre-charge upload validation guard — Entry 2 —
  reduces one failure mode: invalid uploads no longer reach quota/enqueue.)

Recommended sequencing when a backend env is available: quota ledger → CAS job
state machine → transactional outbox → recovery sweeper → canonical attempt
model + offline sync. Each needs its own migration + Postgres verification.

---

## Entry 5 — Group 4 (partial): deletion media completeness + in-app delete/export

Issue group: 4 (Privacy deletion/export). Sub-problems addressed:

1. Hard-delete only walked `clip_jobs` storage refs, so **pending V1 uploads**
   (ClipModel.storage_key with no job row) were orphaned after account delete.
2. **Retention copies** under `{retention_dir}/{user_id}/` were never purged.
3. Client Settings had no in-app delete/export — only an external info URL
   (App Store 5.1.1(v) risk when accounts are created in-app).

### Change

- `list_v1_clip_storage_keys(user_id)` — collect ClipModel storage/thumbnail keys
  **before** `purge_user_owned_rows`.
- `enqueue_hard_delete(..., extra_storage_keys=)` — pass keys into ARQ / sync path.
- `_hard_delete_user_clips_impl` merges extra keys with job refs, deletes once.
- `purge_retention_dir_for_user` — path-safe `rmtree` of retention tree.
- Client: `src/api/accountApi.ts` (`deleteMyAccount`, `exportMyData`); Settings
  wires confirm → DELETE, Share export JSON, then sign-out.

### Files changed

- `services/api/app/services/deletion_queue.py`
- `services/api/app/routers/account.py`
- `services/api/tests/test_account_deletion.py`
- `services/api/tests/test_hard_delete_pipeline.py`
- `src/api/accountApi.ts` (new)
- `src/api/index.ts`
- `src/__tests__/api/accountApi.test.ts` (new)
- `app/settings.tsx`

### Tests / verification

- `pytest tests/test_account_deletion.py tests/test_hard_delete_pipeline.py -q`
  → **14 passed**
- `npm test -- src/__tests__/api/accountApi.test.ts` → **2 passed**
- `npm run typecheck` → PASS

### Acceptance criteria status (Group 4)

- [x] Pending V1 upload objects deleted on account delete — verified.
- [x] Retention dir for user purged on account delete — verified.
- [x] In-app delete account + export entry points — implemented.
- [ ] Full-table export (sessions, feed, stats, billing…) — still limited to
      clips + consent; product/policy decision open.
- [ ] Pending-upload reaper for abandoned non-deleted accounts — separate P1.

---

## Entry 6 — Export expand, quota/CAS, analytics, paywall, pending reaper

### Group 4 — full-table export (decision-free tables)

`build_account_export` now includes sessions, feed_events, trick_stats,
milestones, custom_lines, line_attempts, plus billing fields on `user`.
Clip history remains uncapped via `iter_all_for_user`.

### Group 3 — enqueue failure refund + CAS claim (partial)

- `complete_v1_clip_upload`: on enqueue failure → mark job failed, set
  `quota_source=monthly_refunded` or `refund_one_bonus`, clip `failed`, HTTP 503.
- `try_claim_for_processing`: pending → processing CAS in SQL + in-memory repos;
  worker uses it before analysis.
- Full transactional outbox / quota ledger still open (arch).

### Group 1 — first-party analytics

- `POST /api/v1/beta/client-events` persists **all** allowlisted kinds to
  `client_funnel_events` (not only share).
- Client `track()` fire-and-forgets to that endpoint when signed in; buffers
  offline; still logs in `__DEV__`.

### Billing / paywall (superseded — see Entry 9)

Historically this entry noted a free-only Lite paywall before RevenueCat IAP
shipped. **Live product:** RevenueCat entitlements (`onflow-lite Pro`), client
Purchases SDK, paywall + Customer Center, and `POST /api/v1/billing/sync` +
RevenueCat webhooks. Treat older “no IAP / server-side Pro only” wording as
archived.

### Group 5 follow-up — pending upload reaper

- `reap_abandoned_pending_clips` on API startup; `ONFLOW_CLIP_PENDING_REAP_HOURS`
  (default 24). (Also hourly on the ARQ worker as of Entry 9.)

### Verification

- Backend: export, CAS/enqueue refund, reaper, deletion suites green.
- Frontend: analytics + accountApi tests + typecheck green.

---

## Status summary (reduced register)

| Group | Title | Status |
|-------|-------|--------|
| 1 | Production analytics | DONE (first-party) — Entry 6; vendor option still available later |
| 2 | Progression single source of truth | PARTIAL — on-device isolation DONE (Entry 1); server canonical model open (arch) |
| 3 | Job/quota/queue reliability | MOSTLY DONE — FOR UPDATE quota charge + leases + reaper cron (Entries 6–9); SSE hub still in-process |
| 4 | Privacy deletion/export | MOSTLY DONE — export tables + media purge + in-app delete/export (Entries 3–6) |
| 5 | Upload validation | DONE — size check (Entry 2) + pending reaper (Entries 6 + 9); media-probe optional follow-up |
| 8 | CI coverage | DONE — backend pytest + Postgres migration + Docker jobs |

## Entry 7 — Media sniff at complete-upload + quota lock + exclusive create

### Group 5 — magic-byte sniff before charge

`complete_v1_clip_upload` downloads/opens the object and runs `looks_like_video`
**before** quota charge or enqueue. Non-video → delete object, 422, no job.

### Group 3 — process-local quota serialization

- `create_job_charging_quota`: per-user lock around decide-quota + insert
- `create_exclusive` / `JobAlreadyExists` for concurrent same-clip_id completes
- Concurrent free-tier stress test (`test_quota_lock`) pins cap respect
- **Superseded for multi-replica:** Entry 9 moves charge to `SELECT … FOR UPDATE`

### Verification

- Upload/quota/contract/auth tests: 36 passed

## Entry 8 — Group 2: server SessionAttempt + offline outbox

### Backend
- `session_attempts` table (client id PK for idempotency) + Alembic
  `20260717_session_attempts`
- `POST /api/v1/session-attempts/sync` batch upsert
- `GET /api/v1/sessions/{id}/attempts`
- Account purge + export include attempts; session `attempt_count` prefers
  synced rows

### Client
- `attemptApi` + `attemptOutbox` (scoped AsyncStorage)
- `appendSessionAttempt` enqueues + flushes; `loadSessionAttempts` merges
  server; flush on sign-in

### Verification
- Backend `test_session_attempts` + export/delete: green
- Frontend attemptApi + store tests + typecheck: green

## Entry 9 — P1/P2 hardening (quota, schema, reaper, SSE, ops)

### P1-1 — Quota multi-replica
- `create_job_charging_quota` SQL path: lock user row (`FOR UPDATE`), count
  monthly free jobs, insert clip job in one transaction; bonus consume under
  the same lock. Process-local locks remain as an intra-process fast path.

### P1-2 — No `create_all` in prod/staging
- `create_db_tables` no-ops when `is_production_or_staging`; Alembic owns schema.
- Worker / deletion paths no longer call `create_db_tables` per job.

### P1-3 — Pending upload reaper on a schedule
- ARQ cron `reap_pending_clips_cron` hourly (`WorkerSettings.cron_jobs`) in
  addition to API startup sweep.

### P1-4 — Worker codified for Railway
- `railway.worker.toml` → `Dockerfile.worker`; ops checklist requires API + worker.

### P2-2 — Docs match RevenueCat billing
- Remediation log + ops checklist describe live IAP / entitlements (not free-only).

### P2-3 — SSE query auth
- `?token=` accepts only short-lived `purpose=sse` tickets from
  `POST /api/v1/feed/sse-ticket` (not the long-lived session JWT). Bearer still OK.

### P2-4 — Accurate `Retry-After`
- Rate-limit handler derives seconds from slowapi detail window (minute/hour/day),
  not a hardcoded 86400.

### P2-5 — Lifespan teardown
- After yield: close async Redis, ARQ pool, dispose SQLAlchemy engine.

Still open (arch): Redis-backed SSE fan-out across API replicas; deep issue
register file if restored separately.

## Entry 10 — Migration graph split head + no-empty-DB bootstrap gap

Found during a senior build review (2026-08-14), verified against a local
Postgres 16 instance (Docker unavailable; installed the server package directly).

### Fixed

- **Split Alembic head.** `20260801_clip_job_leases` and
  `20260802_rc_entitlement_state` both set
  `down_revision = "20260717_session_attempts"` independently, so
  `alembic upgrade head` — Railway's `preDeployCommand` — failed with
  "Multiple head revisions are present" against a fresh database. Added a
  no-op merge migration (`20260803_merge_heads.py`); `alembic heads` now
  returns one head. Caught by `tests/test_schema_migrations.py`, which was
  red on this branch before the fix.
- **Order-dependent test.** `test_fetch_prior_respects_exclude_job` opened a
  `Session` directly via `get_engine()` without ever triggering
  `create_db_tables()` (only the FastAPI lifespan, via `TestClient`, does
  that), so it failed with `no such table: trick_stats` — in isolation and in
  the full run, contradicting the CI workflow's own comment that the suite is
  "self-contained and order-independent." Fixed by depending on the `client`
  fixture, matching every other test that mixes direct `Session` access with
  the app's schema setup. Full backend suite: 400 passed / 0 failed / 4
  skipped (was 398 / 2 failed).

### Found, not fixed here — scoped as follow-up

- **No migration creates the base tables.** Fixing the split head above
  surfaced a deeper, pre-existing gap while verifying `alembic upgrade head`
  against a truly empty Postgres 16: it fails on `CREATE INDEX … ON
  clip_jobs` because `clip_jobs` (and `users`, and every other base table)
  is never created by any migration — the earliest one, `add_oauth_providers`,
  explicitly no-ops when `users` doesn't exist yet (`if not
  insp.has_table("users"): return`). The whole chain was written assuming
  `create_db_tables()` had already run once against the target database. That
  call is intentionally disabled in production/staging (Entry 9, P1-2), so a
  **genuinely new** Postgres instance — a new Railway project, a
  disaster-recovery restore into an empty database, a fresh staging
  environment — currently has no automatic path to stand itself up. Today's
  production database only works because it predates this constraint or was
  bootstrapped manually before Alembic tracking began.
- This was deliberately **not** fixed by writing a genesis migration in the
  same pass: inferring full DDL (types, constraints, defaults, indexes) for
  ~17 tables from the current SQLModel definitions and getting it right on
  the first try is a higher-risk change than the two fixes above, and
  deserves its own review rather than being bundled into a blocker-fix pass.
- **Interim workaround, documented in `docs/ios-testflight-ops-checklist.md`**
  ("Bootstrapping a genuinely new environment"): set
  `ONFLOW_ALLOW_CREATE_ALL=1` once to create tables via
  `SQLModel.metadata.create_all()`, unset it, then `alembic stamp head` to
  mark the database current without replaying the broken chain. Manual, and
  depends on a human running it correctly on every new environment — not a
  substitute for a real genesis migration.

Still open: write a genesis migration (or squash the chain) so
`alembic upgrade head` alone can bootstrap a truly empty database.

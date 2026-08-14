# iOS TestFlight launch ops checklist

Use this after the billing/API code gates land. Do not commit secrets here.

## Railway (API + worker)

1. Confirm **two** services from this repo:
   - **API** — config `railway.toml` → `services/api/Dockerfile` (Alembic pre-deploy + `/health`).
   - **Worker** — config `railway.worker.toml` → `services/api/Dockerfile.worker` (ARQ + hourly pending-upload reaper). Do not ship API-only envs.
2. Shared: Postgres, Redis, R2 credentials on **both** services.
3. Before traffic: `python3.12 -m alembic upgrade head` (Railway pre-deploy / release; bare `alembic` is not on PATH in the API image). `create_all` is disabled in production/staging.
   - **This only works against a database that already has the base tables** (`users`, `clip_jobs`, `trick_stats`, etc.). No migration in `services/api/migrations/versions` creates them from empty — the earliest one (`add_oauth_providers`) no-ops if `users` doesn't exist — because the chain was written assuming `create_db_tables()` had already run once. That call is disabled in production/staging by design (P1-2), so a **genuinely new** Postgres (new Railway project, disaster recovery restore into an empty instance, new staging) has no automatic bootstrap path today. A real genesis migration is scoped as separate follow-up work; see `docs/remediation-log.md` Entry 10 for the stamp-based workaround.
4. API replicas: quota charge uses Postgres `SELECT … FOR UPDATE` (`clip_quota.py`). Keep feed SSE fan-out in mind — the SSE hub is still in-process (clients pin to one replica or use Bearer + ticket refresh).
5. Env (production) — API **and** worker. Boot fails closed without JWT, RC webhook secret, RC Pro product IDs, Redis, S3, and provider keys (also required for `staging`):
   - `ONFLOW_ENV=production` (never leave unset — defaults to development)
   - `ONFLOW_JWT_SECRET`
   - `ONFLOW_DATABASE_URL` / `ONFLOW_REDIS_URL`
   - R2: `ONFLOW_S3_BUCKET`, `ONFLOW_S3_ENDPOINT`, `ONFLOW_S3_ACCESS_KEY`, `ONFLOW_S3_SECRET_KEY`
   - `ONFLOW_GEMINI_API_KEY` + `ONFLOW_TWELVELABS_API_KEY`
   - `ONFLOW_ADMIN_EMAILS`
   - `ONFLOW_APPLE_BUNDLE_ID=com.onflow.lite`
   - `ONFLOW_RC_WEBHOOK_SECRET`
   - `ONFLOW_RC_PRO_PRODUCT_IDS` = App Store product IDs for lifetime/yearly/monthly
   - `ONFLOW_CORS_ORIGINS` = explicit origins (`*` rejected in production/staging)
6. Webhook URL: `https://<api-host>/api/v1/webhooks/revenuecat` with Bearer auth = webhook secret.
7. Smoke: `/health` OK; `/docs` absent in production; enqueue a clip and confirm the **worker** processes it.

## Bootstrapping a genuinely new environment

Only needed once per environment (new Railway project, disaster-recovery restore
into an empty Postgres, a fresh staging instance) — an environment that already
has tables just needs step 3 above on every deploy.

1. Temporarily set `ONFLOW_ALLOW_CREATE_ALL=1` on the API service and deploy (or
   run the API image once with that var set, pointed at the target
   `ONFLOW_DATABASE_URL`). This creates every current table via
   `SQLModel.metadata.create_all()` — the same path `create_db_tables()` uses in
   development.
2. Confirm tables exist (`\dt` in `psql`, or `GET /health`), then **unset
   `ONFLOW_ALLOW_CREATE_ALL`** — leaving it set means future schema drift between
   models and migrations is silently papered over instead of caught in CI.
3. Run `python3.12 -m alembic stamp head` against that database. This marks it as
   already at the latest revision **without replaying the migration chain**
   (which would fail — see step 3 above). From this point on, normal
   `alembic upgrade head` on every deploy works as usual.
4. Continue with the standard Railway checklist above (env vars, webhook URL, smoke test).

This is a manual stopgap, not a fix — it depends on a human remembering to run it
correctly on every new environment. Writing a proper genesis migration (one that
creates the full schema from empty, so `alembic upgrade head` alone is sufficient)
is scoped as separate follow-up work; see `docs/remediation-log.md` Entry 10.

## RevenueCat dashboard

1. Entitlement id exactly: `onflow-lite Pro`
2. Current Offering packages: `lifetime`, `yearly`, `monthly` → attach to entitlement
3. Paywall on current Offering; Customer Center enabled
4. Copy Store product IDs into `ONFLOW_RC_PRO_PRODUCT_IDS`

## EAS (preview → TestFlight)

1. EAS env **preview** + **production**:
   - `EXPO_PUBLIC_API_URL` = Railway API URL
   - `EXPO_PUBLIC_REVENUECAT_API_KEY` = production/public SDK key (required; no code fallback)
   - optional `EXPO_PUBLIC_LEGAL_BASE_URL`
2. `eas build --profile preview --platform ios`
3. Device smoke:
   - Apple Sign-In
   - Session → capture → R2 upload → analyze
   - Quota → paywall
   - Sandbox purchase/restore → backend Pro
   - Customer Center from Settings
   - Export + delete account
4. Then: `npm run build:production:ios` → TestFlight

## Explicitly deferred

- Android Google Sign-In
- Cross-replica SSE pub/sub (Redis) for feed streams
- App Store submit metadata polish beyond TestFlight

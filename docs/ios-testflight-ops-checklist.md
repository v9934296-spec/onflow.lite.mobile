# iOS TestFlight launch ops checklist

Use this after the billing/API code gates land. Do not commit secrets here.

## Railway (API + worker)

1. Confirm **two** services: API (`services/api/Dockerfile`) and Worker (`services/api/Dockerfile.worker`).
2. Shared: Postgres, Redis, R2 credentials on **both** services.
3. Before traffic: `alembic upgrade head` (API release step or one-off run).
4. **Single API replica** until distributed quota lock exists (`clip_quota.py`).
5. Env (production):
   - `ONFLOW_ENV=production`
   - `ONFLOW_JWT_SECRET`
   - `ONFLOW_DATABASE_URL` / `ONFLOW_REDIS_URL`
   - R2: `ONFLOW_S3_BUCKET`, `ONFLOW_S3_ENDPOINT`, `ONFLOW_S3_ACCESS_KEY`, `ONFLOW_S3_SECRET_KEY`
   - `ONFLOW_GEMINI_API_KEY` + `ONFLOW_TWELVELABS_API_KEY`
   - `ONFLOW_ADMIN_EMAILS`
   - `ONFLOW_APPLE_BUNDLE_ID=com.onflow.lite`
   - `ONFLOW_RC_WEBHOOK_SECRET`
   - `ONFLOW_RC_PRO_PRODUCT_IDS` = App Store product IDs for lifetime/yearly/monthly
   - `ONFLOW_CORS_ORIGINS` = explicit origins (not `*`)
6. Webhook URL: `https://<api-host>/api/v1/webhooks/revenuecat` with Bearer auth = webhook secret.
7. Smoke: `/health` OK; `/docs` absent in production.

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
- Multi-replica quota ledger
- App Store submit metadata polish beyond TestFlight

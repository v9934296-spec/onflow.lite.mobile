# Legacy API Map — ai-pop (source)

Maps the **source** API layer in `c:\ai-pop\apps\mobile` for controlled migration into `onflow-lite`. Do not copy wholesale.

Contract reference: `c:\ai-pop\apps\docs\API_CONTRACT.md`

## Core files — Phase 1 kernel (migrate/adapt)

| ai-pop file | Purpose | Action |
|-------------|---------|--------|
| `lib/apiConfig.ts` | Env guard, missing-URL messages, startup logging | Adapt to `src/api/config.ts` |
| `lib/clipClient.ts` (`getApiBaseUrl`) | Base URL + web LAN rewrite | Extract to `src/api/baseUrl.ts` |
| `lib/apiErrors.ts` | FastAPI `detail` parsing, network hints | Adapt to `src/api/errors.ts` |
| `lib/apiTelemetryHeaders.ts` | `X-App-Version`, `X-Build-Number`, `X-Platform` | Adapt to `src/api/telemetry.ts` |
| `lib/apiHttp.ts` | Auth header builder, 401 notify re-exports | Partial — `src/api/auth.ts` hook only |
| `lib/__tests__/apiConfig.test.ts` | Env config tests | Adapt to `src/__tests__/api/config.test.ts` |

## Do NOT migrate in Phase 1

| ai-pop area | Reason | Target phase |
|-------------|--------|----------------|
| `lib/sessionClient.ts` | Session CRUD + upload | Phases 3, 6, 8 |
| `lib/feedClient.ts`, `lib/api/feedSSE.ts` | Feed + SSE (XMLHttpRequest) | Phase 10 |
| `lib/statsClient.ts` | Stats/telemetry (loose error handling) | Later |
| `lib/progressionClient.ts`, `lib/trickCompareClient.ts` | Progression features | Later |
| `lib/billingSync.ts` | RevenueCat sync | Phase 11 |
| `lib/clipClient.ts` (auth, jobs, upload, account) | Domain + auth flows | Phases 2, 8, 9 |
| `lib/api/*` React Query hooks | Caching layer | When domain features need it |
| `lib/authStorage.ts`, `lib/onflowSession.ts` | Secure token storage | Phase 2 |
| `@tanstack/react-query` | Not needed for health check | Defer |
| `expo-secure-store` | Auth storage dependency | Phase 2 |
| `components/ApiConfigBanner.tsx` styling | ai-pop theme | Reimplement with onflow-lite `src/theme.ts` |

## Environment variable contract

### Phase 1 subset

| Variable | Required | Notes |
|----------|----------|-------|
| `EXPO_PUBLIC_API_URL` | Yes (for API calls) | Primary base URL; trailing `/` stripped |
| `EXPO_PUBLIC_API_URL_WEB` | Optional | Web-only override; disables LAN→127.0.0.1 rewrite |

### Later phases (document only — do not add in Phase 1)

| Variable | Phase | Notes |
|----------|-------|-------|
| `EXPO_PUBLIC_BETA_CODES` | — | Removed (invite codes retired) |
| `EXPO_PUBLIC_BETA_PRO_CODES` | — | Removed (invite codes retired) |
| `EXPO_PUBLIC_RC_API_KEY_*` | 11 | RevenueCat |
| `EXPO_PUBLIC_LEGAL_BASE_URL` | 12 | Legal links |
| `EXPO_PUBLIC_DEV_SKIP_SIGN_IN` | 2 | Dev auto-session |
| `EXPO_PUBLIC_DEBUG_JOB_POLL` | 9 | Job poll diagnostics |

### EAS configuration (new app — intentional improvement)

ai-pop hardcodes `EXPO_PUBLIC_API_URL` in `eas.json` beta/production profiles.

**Do not replicate.** Use EAS environment variables:

```json
{
  "build": {
    "preview": { "distribution": "internal", "environment": "preview" },
    "production": { "environment": "production" }
  }
}
```

Set `EXPO_PUBLIC_API_URL` in the EAS dashboard per environment.

## Auth-header behavior (ai-pop)

1. Invite JWT from `authStorage` → `Authorization: Bearer <jwt>` (preferred).
2. Else OnFlow session from `onflowSession` → `Authorization: Bearer <session_token>`.
3. If neither exists → throw user-facing "not signed in" error.
4. Telemetry headers always merged: `X-App-Version`, `X-Build-Number`, `X-Platform`.
5. 401 → `notifyAuthExpiredOn401` fires registered callback.

**Phase 1:** `setAuthTokenProvider()` returns `null` by default. Health check is unauthenticated.

**SSE exception:** feed stream passes token as `?token=` query param — not Authorization header. Phase 10.

## Timeout behavior (ai-pop vs new app)

| Context | ai-pop | onflow-lite (Phase 1) |
|---------|--------|----------------------|
| Normal fetch | **No timeout** | `AbortController`, 15s default |
| Job poller | 15 min hard stop | Phase 9 |
| Feed SSE connect | 3s | Phase 10 |
| Session refetch while analyzing | 5s | Phase 9 |

## Error handling (ai-pop pattern)

```ts
async function safeReadJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text.trim()) return null;
  try { return JSON.parse(text); }
  catch { return { _nonJson: text.slice(0, 200) }; }
}
```

- Prefer `res.text()` then parse.
- FastAPI `{ detail }` via `extractApiErrorBody` / `formatApiDetail`.
- Network catch → `networkFailureHint(apiBase)`.

**Phase 1 improvements:**

| Kind | When |
|------|------|
| `configuration` | Missing `EXPO_PUBLIC_API_URL` — before fetch |
| `network` | Fetch failed / offline |
| `timeout` | AbortController fired |
| `unauthorized` | HTTP 401 |
| `client` | HTTP 4xx except 401 (400, 403, 404, 409, 422, …) |
| `server` | HTTP 5xx |
| `malformed` | Non-JSON or missing required fields |

## Endpoint inventory

### Phase 1 (implement)

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/health` | No | `{ status: string, db?, gemini_configured?, ... }` |

Require `status` only in mobile parser; other fields optional diagnostics.

### Auth / account (Phase 2+)

| Method | Path |
|--------|------|
| POST | `/api/v1/auth/google` |
| POST | `/api/v1/auth/apple` |
| POST | `/api/v1/auth/session` |
| POST | `/api/v1/auth/claim` | Removed — invite codes retired |
| GET | `/api/v1/account/me` |
| DELETE | `/api/v1/account` |
| GET | `/api/v1/consent` |
| POST | `/api/v1/consent/grant` |
| POST | `/api/v1/billing/sync` |
| POST | `/api/v1/beta/client-events` |
| GET | `/api/v1/account/quota` |

### Sessions (Phases 3, 6, 7)

| Method | Path |
|--------|------|
| POST | `/api/v1/sessions` |
| GET | `/api/v1/sessions/{id}` |
| PATCH | `/api/v1/sessions/{id}` |
| GET | `/api/v1/sessions/{id}/recap` |

### Clips / jobs (Phases 8, 9)

| Method | Path |
|--------|------|
| POST | `/api/v1/clips/initiate-upload` |
| PUT | `{presigned upload_url}` |
| POST | `/api/v1/clips/{id}/complete-upload` |
| GET | `/api/v1/clips/jobs?limit=` |
| GET | `/api/v1/clips/jobs/{jobId}` |

### Feed / progression (Phase 10)

| Method | Path |
|--------|------|
| GET | `/api/v1/feed?limit&cursor` |
| GET | `/api/v1/feed/stream?token&lastEventId` |
| GET | `/api/v1/progression/timeline?page&page_size` |
| GET | `/api/v1/progression/tricks/{name}/compare` |

### Stats / lines (later)

| Method | Path |
|--------|------|
| GET | `/api/v1/stats/tricks` |
| GET | `/api/v1/stats/tricks/{name}` |
| GET | `/api/v1/stats/tricks/{name}/progression` |
| GET | `/api/v1/stats/sessions/latest` |
| GET | `/api/v1/stats/sessions/{id}` |
| GET | `/api/v1/stats/progression/overview` |
| GET | `/api/v1/stats/progression/whats-next` |
| GET | `/api/v1/stats/milestones` |
| GET/POST | `/api/v1/lines` |
| GET/DELETE | `/api/v1/lines/{id}` |

## Package requirements

| Package | ai-pop | onflow-lite Phase 1 |
|---------|--------|---------------------|
| `fetch` (native) | Yes | Yes — no new HTTP lib |
| `expo-constants` | Yes | Already installed |
| `@tanstack/react-query` | Yes | **Do not add** |
| `expo-secure-store` | Yes (auth) | Phase 2 |
| `@react-native-community/netinfo` | Yes (UI only) | Defer |

## Upload flow (reference — Phase 8)

Presigned PUT, not multipart to API:

1. `POST /api/v1/clips/initiate-upload` → `{ clip_id, upload_url, storage_key, upload_expires_at }`
2. `PUT upload_url` with video blob
3. `POST /api/v1/clips/{clipId}/complete-upload` (409 = success)

## Legacy behavior vs intentional improvements

| Area | ai-pop | onflow-lite |
|------|--------|-------------|
| Fetch timeout | None | 15s AbortController default |
| Missing API URL | Sometimes treated as connectivity | `configuration` error kind |
| 4xx classification | Often lumped with server | `client` vs `unauthorized` |
| Health payload | Implicit full shape | `status` required; rest optional |
| EAS env URLs | Hardcoded in eas.json | EAS dashboard per environment |
| Dev health probe | None | Non-blocking `__DEV__` Metro log |
| Health endpoint usage | Server-only ops tool | Mobile reachability check |

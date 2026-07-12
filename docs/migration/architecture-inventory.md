# Architecture Inventory — onflow-lite (destination)

Recorded at migration baseline. Describes the **new app as it exists today**, not the source `ai-pop` codebase.

## Stack

| Item | Value |
|------|-------|
| Framework | Expo SDK ~53 |
| React Native | 0.79.2 |
| React | 19.0.0 |
| Routing | expo-router ~5 (file-based) |
| Language | TypeScript (strict) |
| Native arch | New Architecture enabled |
| Bundle IDs | `com.onflow.lite` (iOS + Android) |

## Folder structure

```
onflow-lite/
├── app/                    # expo-router screens
│   ├── _layout.tsx         # root Stack + SessionProvider
│   ├── index.tsx           # home
│   ├── trick.tsx           # call the trick
│   ├── capture.tsx         # sample clips or camera/library
│   ├── analyzing.tsx       # fake progress UI
│   ├── result.tsx          # analysis + manual log
│   └── log.tsx             # session log
├── src/
│   ├── session.tsx         # React Context — loop state
│   ├── storage.ts          # AsyncStorage log persistence
│   ├── progress.ts         # land attempts, streaks
│   ├── flow.ts             # route guards
│   ├── engine.ts           # local PTE engine (pte-lite-v0.1)
│   ├── analytics.ts        # typed event stub (__DEV__ only)
│   ├── types.ts            # domain types
│   ├── theme.ts            # colors + fonts
│   ├── ui.tsx              # shared UI primitives
│   ├── charts.tsx          # SVG charts
│   ├── logSummary.ts       # session stats
│   └── __tests__/          # Vitest unit tests
├── docs/                   # product + migration docs
├── .github/workflows/ci.yml
├── app.json, eas.json, package.json, vitest.config.ts, tsconfig.json
```

## Expected locations for migrated code

| Concern | Location |
|---------|----------|
| API client | `src/api/` |
| API domain types | `src/types/api/` |
| Hooks (when needed) | `src/hooks/` |
| Screens | `app/` |
| Shared UI | `src/ui.tsx` or `src/components/` |
| Tests | `src/__tests__/` |

## Navigation

- **Pattern:** single `Stack` navigator in `app/_layout.tsx` (no tabs/drawer).
- **Routes:**

| File | Path | Purpose |
|------|------|---------|
| `app/index.tsx` | `/` | Home — film CTA, session log, 7-day streak |
| `app/trick.tsx` | `/trick` | Call the trick |
| `app/capture.tsx` | `/capture` | Sample clips or camera/library video |
| `app/analyzing.tsx` | `/analyzing` | Fake progress UI, then `replace("/result")` |
| `app/result.tsx` | `/result` | Analysis + manual log |
| `app/log.tsx` | `/log` | Session log |

- **Flow guards:** `src/flow.ts` `getFlowRedirect()` protects `/capture`, `/analyzing`, `/result` — requires `trick`, then matching `analysis`.

- **Current user journey:** `home → trick → capture → analyzing → result → log`

  This differs from Milestone 1 session loop (`start session → pick trick → land/miss → end → recap → history`). Milestone 1 screens will be added or replace placeholders in later phases.

## State management

- **No Redux, Zustand, or React Query.**
- `SessionProvider` + `useSession()` in `src/session.tsx` (React Context).
- AsyncStorage via `src/storage.ts` (log) and `src/progress.ts` (attempts).
- Pure modules: `engine.ts`, `flow.ts`, `progress.ts`, `logSummary.ts`.

Session state: `trick`, `analysis`, `log`, `attempts`, hydration, storage warnings, `reportManualLog`, `deleteClip`, `clearSessionLog`, `resetLoop`.

Storage keys: `onflow_lite_log_v1`, progress attempts key in `progress.ts`.

## API / services

| Piece | Status |
|-------|--------|
| HTTP client | **None** — greenfield (Phase 1 adds `src/api/`) |
| Backend calls | **None** |
| Auth / tokens | **None** |
| Analytics | `src/analytics.ts` — `__DEV__` console stub only |

## Environment variables

| Mechanism | Status |
|-----------|--------|
| `.env` / `.env.example` | Not present at baseline (Phase 1 adds `.env.example`) |
| `EXPO_PUBLIC_*` usage | None |
| `expo-constants` | Dependency present; unused in app code at baseline |
| EAS `extra.eas.projectId` | Set in `app.json` |

## Tests

- **Runner:** Vitest (`vitest.config.ts`, `environment: "node"`).
- **Scripts:** `npm test`, `npm run test:watch`, `npm run typecheck`.
- **Unit tests:** `src/__tests__/` — engine, flow, storage, progress, logSummary.
- **CI:** `.github/workflows/ci.yml` — typecheck, test, `expo export --platform ios`.
- **Lint:** not configured.
- **Smoke script:** not configured; CI uses `bundle:ios` as bundle-check proxy.

## Known placeholders

| Location | What it fakes |
|----------|---------------|
| `app/analyzing.tsx` | "uploading clip" step — timed UI, no network |
| `src/analytics.ts` | Real analytics provider |
| `src/engine.ts` | Backend analysis pipeline (`pte-lite-v0.1` local only) |
| `docs/PTE_SCORE_DETERMINISM.md` | Production `services/api` spec — not in this repo |

## Dependencies (runtime)

```
@expo-google-fonts/archivo, @expo-google-fonts/space-mono
@react-native-async-storage/async-storage
expo, expo-asset, expo-constants, expo-font, expo-image-picker
expo-linking, expo-router, expo-status-bar
react, react-native, react-native-safe-area-context
react-native-screens, react-native-svg
```

No HTTP libraries (axios, react-query, etc.) at baseline. Phase 1 uses native `fetch` only.

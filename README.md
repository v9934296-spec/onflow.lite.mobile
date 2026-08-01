# OnFlow Lite

Film a trick, get an honest read, log the session. Expo Router mobile app + FastAPI backend (`services/api`).

## Setup

```powershell
cd C:\onflowdemo
npm install
npx expo install --fix
npx expo start
```

For native IAP (RevenueCat) and camera workflows, use an EAS development or preview build — Expo Go is not sufficient for store purchases.

Copy `.env.example` → `.env` for the mobile app, and `services/api/.env.example` → `services/api/.env` for the API. Never commit real secrets.

## Type check & tests

```powershell
npm run typecheck
npm test
```

API tests live under `services/api` (pytest).

## EAS / TestFlight

```powershell
npm i -g eas-cli
eas login
```

```powershell
npm run build:production:ios
npm run submit:ios
```

Identifiers:

- iOS / Android: `com.onflow.lite`

Profiles: `development`, `preview`, `production` (see `eas.json`). Ops details: [`docs/ios-testflight-ops-checklist.md`](docs/ios-testflight-ops-checklist.md).

## Honesty rules (P.T.E.)

See [`docs/PTE_MANIFESTO.md`](docs/PTE_MANIFESTO.md). Analyses include **evidenceClass**, **confidence**, **receipts**, and **engineVersion** (`pte-lite-v0.1`).

- Sample clips: scripted analyses labeled as samples.
- User footage: **ESTIMATE** only until a real detection pipeline exists.
- Ratings abstain when confidence is too low or the clip is too short.

## Documentation

See [`docs/README.md`](docs/README.md).

## Structure

```
app/                 Expo Router screens
assets/              App icon
docs/                Product / ops docs
services/api/        FastAPI + ARQ worker (Railway)
src/
  analysis/          Clip job polling + analysis mapping
  api/               HTTP clients
  auth/              Session + secure storage
  billing/           RevenueCat + quota helpers
  components/        Shared UI pieces
  sessionAttempts/   Local attempts + sync outbox
  sessionRecap/      Completed session recaps
  skateSession/      Active skate session state
  storage/           User-scoped AsyncStorage helpers + clip log
  tricks/            Trick library + search
  engine.ts          P.T.E. lite engine
  progressionAdapter.ts  Progression / feed adapters
  flowGuard.ts       Capture/analyzing/result route guards
  session.tsx        Demo loop session provider
```

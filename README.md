# OnFlow Lite

One-loop lite of OnFlow: **call it → film it → get it straight → log it.**
Standalone project — nothing here touches the main OnFlow repo.

## Setup (Windows / PowerShell)

```powershell
cd C:\onflow-lite
npm install
npx expo install --fix
npx expo start
```

`npx expo install --fix` aligns every Expo package to the SDK version npm resolved —
run it once after install and any version-mismatch warnings go away.

Scan the QR with Expo Go on your phone. No native build needed — everything here
runs in Expo Go.

## Type check & tests

```powershell
npm run typecheck
npm test
```

## EAS setup and TestFlight

The repository contains production-ready EAS profiles, but the Expo project must be linked once so Expo can assign the real project ID.

```powershell
npm i -g eas-cli
eas login
eas init
```

`eas init` writes the Expo-assigned `extra.eas.projectId` into `app.json`. Do not add a made-up or placeholder project ID.

Then build iOS for App Store Connect:

```powershell
npm run build:production:ios
```

When the build succeeds, submit the latest build to TestFlight:

```powershell
npm run submit:ios
```

Or build and submit in one command:

```powershell
eas build --platform ios --profile production --auto-submit
```

Current application identifiers:

- iOS: `com.onflow.lite`
- Android: `com.onflow.lite`

Before the first public release, confirm those identifiers are the permanent identifiers you want. Apple and Google do not let an existing app change its identifier after release.

### EAS profiles

- `development`: development client distributed internally
- `preview`: internal tester build
- `production`: store build with remote version management and automatic build-number incrementing
- `submit.production`: TestFlight/App Store Connect submission profile

## The 60-second Lite Script

1. Open the app. "You film a trick, it tells you the truth about it."
2. Film a clip → call **Kickflip** → tap the kickflip sample. Point at the evidence
   tags: detected on film, or estimated. Never a guess dressed up as a fact.
3. Another clip → call **Tre Flip** → tap the kickflip sample again. "I lied about
   the trick. It caught it."
4. Another clip → call **Ollie** → tap the 5-stair sample. The landing isn't in
   frame, so it refuses to rate it. **That refusal is the product.**
5. Tap **Did you land it?** — streak builds on home and log. Open the session log.

## Honesty rules (P.T.E.)

See [`docs/PTE_MANIFESTO.md`](docs/PTE_MANIFESTO.md). Every analysis includes **evidenceClass**, **confidence**, **receipts**, and **engineVersion** (`pte-lite-v0.1`).

- Sample clips: scripted analyses labeled as samples.
- User footage: **ESTIMATE** only — never `DETECTED` without a real pipeline.
- Ratings abstain when confidence < 50% or clip duration is insufficient.
- Post-result manual log: landed / missed / unsure, attempts, spot, notes.

## Documentation

See [`docs/README.md`](docs/README.md) — manifesto (constitution) and production score-determinism build spec.

## Structure

```
app/              expo-router screens (index, trick, capture, analyzing, result, log)
docs/             PTE_MANIFESTO.md, PTE_SCORE_DETERMINISM.md
src/engine.ts     P.T.E. lite engine (abstention, receipts, versioning)
src/progress.ts   land attempts, 7-day view, streaks
src/logSummary.ts session stats (attempts, landed %, evidence tally)
src/charts.tsx    hand-rolled SVG rating line + breakdown bars
src/session.tsx   loop state, log, progress, storage warnings
src/storage.ts    AsyncStorage log persistence
src/analytics.ts  typed event stub (__DEV__ logs only)
src/ui.tsx        Btn, Tag, Card, Eyebrow, LiteBanner, WeekRow, Field
```

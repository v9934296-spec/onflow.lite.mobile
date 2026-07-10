# OnFlow Lite

one-loop lite of OnFlow: **call it → film it → get it straight → log it.**
Standalone project — nothing here touches the main OnFlow repo.

## Setup (Windows / PowerShell)

Unzip this folder to `C:\onflow-lite`, then:

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

## Type check

```powershell
npm run typecheck
```

## The 60-second Lite Script

1. Open the app. "You film a trick, it tells you the truth about it."
2. Film a clip → call **Kickflip** → tap the kickflip sample. Point at the evidence
   tags: detected on film, or estimated. Never a guess dressed up as a fact.
3. Another clip → call **Tre Flip** → tap the kickflip sample again. "I lied about
   the trick. It caught it."
4. Another clip → call **Ollie** → tap the 5-stair sample. The landing isn't in
   frame, so it refuses to rate it. **That refusal is the product.**
5. Open the session log: rating curve, component breakdown, evidence tally — the
   session builds itself.

## Honesty rules (enforced in `src/engine.ts`)

- Sample clips carry scripted analyses — they show real-engine output and
  are labeled as samples.
- User footage never gets a `DETECTED` tag. The lite engine can't see video, so
  every claim about your own clip is an `ESTIMATE` and the copy says so.
- Clips under 2 seconds abstain: `NO RATING`, refilm guidance.
- Every result screen carries the `LITE ENGINE` banner.

## Structure

```
app/            expo-router screens (index, trick, capture, analyzing, result, log)
src/theme.ts    Bay Fade tokens (aluminum outlines, red complements volt)
src/engine.ts   lite analysis engine
src/charts.tsx  hand-rolled SVG rating line + breakdown bars
src/session.tsx in-memory loop state + persisted log
src/storage.ts  AsyncStorage
src/ui.tsx      Btn, Tag, Card, Eyebrow, LiteBanner
```

# AGENTS.md

## Cursor Cloud specific instructions

OnFlow Lite is an **Expo SDK 53 / React Native (TypeScript)** mobile client. It is
designed to run in **Expo Go on a physical phone**; there is no web target and no
iOS simulator / Android emulator available in the cloud VM, so a full on-device GUI
walkthrough cannot be produced here. Verify changes with the checks below.

Package manager is **npm** (`package-lock.json`). Dependencies are installed by the
update script; no extra system deps are required.

Standard commands (see `package.json` scripts and `.github/workflows/ci.yml`):

- Typecheck: `npm run typecheck`
- Tests: `npm test` (Vitest, node env; suite lives in `src/__tests__`)
- Bundle / build (CI's build step): `npm run bundle:ios` (`expo export`, outputs `dist-ios/`)
- Dev server: `npm start` (`expo start`, Metro on port **8081**)

Non-obvious notes:

- `npm start` runs Metro but nothing connects without Expo Go on a device. To confirm
  the app actually compiles headlessly, request the entry bundle after Metro is up:
  `curl "http://localhost:8081/node_modules/expo-router/entry.bundle?platform=ios&dev=true&transform.routerRoot=app"`
  (expect HTTP 200, multi-MB JS). Use `CI=1 npx expo start` to avoid watch mode.
- `expo start` rewrites `tsconfig.json` (`include` / `paths` formatting) on launch.
  This is harmless but shows up as a git diff — revert it (`git checkout tsconfig.json`)
  if you did not intend to change it.
- The backend API is **external and not in this repo**. The app runs standalone using
  scripted sample clips and the local P.T.E. engine, so no database/services are needed
  for local dev. Backend URL comes from `EXPO_PUBLIC_API_URL` (copy `.env.example` to
  `.env` only if you need to point at a real backend).
- Core product logic (the P.T.E. analysis engine) is pure TypeScript in `src/engine.ts`
  (`analyzeSample` / `analyzeUserClip`, called by `app/capture.tsx`). It is covered by
  `src/__tests__` and can be exercised headlessly by importing it in a script and running
  it through esbuild (`npx esbuild <file> --bundle --platform=node --format=cjs | node`).

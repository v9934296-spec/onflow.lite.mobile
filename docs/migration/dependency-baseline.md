# Dependency Baseline

Reproducible snapshot recorded before migration work begins.

## Reproducibility

| Field | Value |
|-------|-------|
| Baseline commit SHA | `47ae7d82f6b20951de92fe188997d7d8cb0e437a` |
| Node version | `v20.19.6` |
| npm version | `10.8.2` |
| Expo SDK | `~53.0.0` (from `package.json`) |
| Package-lock checksum (SHA256) | `436EA648D41FA62A53900D6E2E735D6179D72A78471CAF36107A3D3D81ED5CB5` |
| Date verified | 2026-07-11 |
| Platform verified | Windows 10 (build 26200); commands run locally |

## Test commands and results

| Command | Configured | Result |
|---------|------------|--------|
| `npm run typecheck` | Yes | **PASS** — `tsc --noEmit` exit 0 |
| `npm run lint` | **No** | N/A — ESLint not configured |
| `npm test` | Yes | **PASS** — 5 files, 33 tests, exit 0 |
| `npm run smoke` | **No** | N/A — no smoke script |
| `npm run bundle:ios` | Yes (CI proxy) | **PASS** — `expo export --platform ios` exit 0 |

### `npm test` output summary

```
Test Files  5 passed (5)
     Tests  33 passed (33)
  Duration  2.17s
```

Files: `engine.test.ts`, `flow.test.ts`, `storage.test.ts`, `progress.test.ts`, `logSummary.test.ts`.

## Runtime dependencies (snapshot)

From `package.json` at baseline SHA:

```json
{
  "@expo-google-fonts/archivo": "^0.2.3",
  "@expo-google-fonts/space-mono": "^0.2.3",
  "@react-native-async-storage/async-storage": "2.1.2",
  "expo": "~53.0.0",
  "expo-asset": "~11.1.7",
  "expo-constants": "~17.1.3",
  "expo-font": "~13.3.0",
  "expo-image-picker": "~16.1.4",
  "expo-linking": "~7.1.3",
  "expo-router": "~5.0.3",
  "expo-status-bar": "~2.2.3",
  "react": "19.0.0",
  "react-native": "0.79.2",
  "react-native-safe-area-context": "5.4.0",
  "react-native-screens": "~4.10.0",
  "react-native-svg": "15.11.2"
}
```

Dev: `typescript ~5.8.3`, `vitest ^3.2.4`, `@types/react ~19.0.10`.

## Baseline failure rule

If a future baseline check fails before a migration commit:

1. Record the failure honestly in this file.
2. Fix in a **separate** `fix: restore pre-migration test baseline` commit.
3. Then proceed with documentation or feature commits.

Documentation commits must not mix code repairs.

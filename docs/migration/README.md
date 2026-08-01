# OnFlow Controlled Migration

This folder documents the controlled rebuild of OnFlow by migrating proven functionality from `ai-pop` one feature at a time into `onflow-lite`.

## Documents

| File | Purpose |
|------|---------|
| [architecture-inventory.md](./architecture-inventory.md) | **Destination** — new app as it exists today |
| [migration-tracker.md](./migration-tracker.md) | Feature status table and migration rules |
| [dependency-baseline.md](./dependency-baseline.md) | Reproducible pre-migration baseline |
| [legacy-api-map.md](./legacy-api-map.md) | **Source** — ai-pop API layer dependency map |

## Core rules

1. One feature or tightly related infrastructure change per commit.
2. No giant copy-paste operations from `ai-pop`.
3. Keep `onflow-lite` architecture; adapt migrated code to it.
4. A feature is migrated only when it works on a real device, handles loading/empty/success/failure, tests pass, placeholders are replaced, and it is committed as a stable checkpoint.
5. Do not start the next feature while the current one has unresolved runtime errors.
6. Do not mix migration work with unrelated cleanup.

## Milestone 1 (core session loop)

Complete when this journey works end to end on a real device:

```
Open app → start session → choose trick → log land or miss → end session → see recap → reopen recap from history
```

Until Milestone 1 is complete, defer: feed, social, AI analysis, subscriptions, paywalls, notifications, animation polish, and production-release work.

## Commit sequence (Phases 0–1)

1. `docs: establish migration baseline and architecture inventory`
2. `docs: map legacy API client dependencies`
3. `feat: add API client and environment configuration`

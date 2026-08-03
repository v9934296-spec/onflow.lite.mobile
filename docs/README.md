# OnFlow Lite — Documentation

| Document | Purpose |
|----------|---------|
| [PTE_MANIFESTO.md](./PTE_MANIFESTO.md) | Constitution — 8 principles + Principle Zero. All code answers to this. |
| [PTE_SCORE_DETERMINISM.md](./PTE_SCORE_DETERMINISM.md) | Production API spec: content hashes, engine registry, worker dedup, CI stability gate. Targets `services/api`. |
| [ios-testflight-ops-checklist.md](./ios-testflight-ops-checklist.md) | Ops checklist for EAS iOS / TestFlight / Railway / RevenueCat / R2. |
| [release/production-hardening-qa.md](./release/production-hardening-qa.md) | Production hardening QA checklist. |
| [remediation-log.md](./remediation-log.md) | P0 remediation audit trail (user-scoped storage and related fixes). |
| [migration/README.md](./migration/README.md) | Controlled migration docs (historical; architecture inventory is superseded). |

**OnFlow Lite mobile** (`pte-lite-v0.1` in `src/engine.ts`) implements a local subset of the manifesto — self-report, abstention, receipts — without the full production pipeline.

The manifesto and the build doc are complementary: principles define *why*; the build doc defines *how* production enforces principles 3, 4, and 8.

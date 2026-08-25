# OnFlow Lite — Documentation

| Document | Purpose |
|----------|---------|
| [PTE_MANIFESTO.md](./PTE_MANIFESTO.md) | Constitution — 8 principles + Principle Zero. All code answers to this. |
| [PTE_SCORE_DETERMINISM.md](./PTE_SCORE_DETERMINISM.md) | Production API spec: content hashes, engine registry, worker dedup, CI stability gate. Targets `services/api`. |
| [ios-testflight-ops-checklist.md](./ios-testflight-ops-checklist.md) | Ops checklist for EAS iOS / TestFlight / Railway / RevenueCat / R2. |
| [release/production-hardening-qa.md](./release/production-hardening-qa.md) | Production hardening QA checklist. |
| [remediation-log.md](./remediation-log.md) | P0 remediation audit trail (user-scoped storage and related fixes). |
| [of-002-intelligence-contract.md](./of-002-intelligence-contract.md) | OF-002 **closed:** characterization tests freezing the current AI parse/assemble contract. |
| [of-003-attempt-sync-immutability.md](./of-003-attempt-sync-immutability.md) | OF-003 **closed** (working-tree verification): attempt-sync immutability (spec BE-001). Railway parity unverified. |
| [of-004-quota-reservation.md](./of-004-quota-reservation.md) | OF-004 **closed** (working-tree verification): quota reserve/finalize/release (spec BE-002). Stale 429 fixture corrected; no production quota change. Railway parity unverified. |
| [of-005-session-lifecycle.md](./of-005-session-lifecycle.md) | OF-005 **closed** (working-tree verification): ended-session uploads + session-end conflict (spec BE-004 / BE-003). Production remediation for concurrent `ended_at` and `clips.captured_at`. Railway parity unverified. |
| [of-006-compression-contract.md](./of-006-compression-contract.md) | OF-006 **open / device-blocked** (EXP-001). Steps 1–2 done. No encoder until PUT-file matrix. Phase 0 not complete. |
| [migration/README.md](./migration/README.md) | Controlled migration docs (historical; architecture inventory is superseded). |

## Phase 0 ledger

Contract verification against the V1 build spec. **Not complete** while OF-006 / §18 gate item 7 is open. Do not start launch-client feature implementation.

| Ticket | Contract | Status |
|--------|----------|--------|
| OF-001 | Live analysis-path mapping | **Closed** |
| OF-002 | Intelligence parse/assemble freeze | **Closed** |
| OF-003 | BE-001 attempt immutability | **Closed** (working tree; Railway unverified) |
| OF-004 | BE-002 quota reservation/finalization | **Closed** (working tree; Railway unverified) |
| OF-005 | BE-003 + BE-004 session lifecycle | **Closed** — production remediation (Railway unverified; `clips.captured_at` migration must deploy with app code) |
| OF-006 | EXP-001 compression | **OPEN — physical-device blocked** |

Resume OF-006 only with the five PUT-file artifacts → probe → matrix → Step 4 remediation. Do not add an encoder or invent work while waiting.

**OnFlow Lite mobile** (`pte-lite-v0.1` in `src/engine.ts`) implements a local subset of the manifesto — self-report, abstention, receipts — without the full production pipeline.

The manifesto and the build doc are complementary: principles define *why*; the build doc defines *how* production enforces principles 3, 4, and 8.

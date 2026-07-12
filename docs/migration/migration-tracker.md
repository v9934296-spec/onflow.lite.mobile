# Migration Tracker

## Definition: feature migrated

A feature is **not** migrated because the code compiles or because a screen exists.

A feature is migrated only when **all** of the following are true:

- It works in the new app on a real device.
- It handles loading, empty, success, and failure states.
- Its tests pass.
- Placeholder data/code in the core path has been replaced.
- It has been committed as a stable checkpoint.

## Feature migration checklist

Use for every migrated feature:

```
[ ] Source feature located in ai-pop
[ ] Required files identified
[ ] Required dependencies identified
[ ] Deprecated code excluded
[ ] New project architecture preserved
[ ] Types migrated or rewritten
[ ] API calls connected
[ ] Loading state implemented
[ ] Empty state implemented
[ ] Error state implemented
[ ] Success state implemented
[ ] Unit tests passing
[ ] Smoke/bundle checks passing
[ ] Real-device test passing
[ ] Placeholder replaced
[ ] Dead code removed
[ ] Feature committed
[ ] Commit pushed
```

## Status definitions

- **Complete:** Functional implementation, automated validation, and real-device validation passed.
- **Integrated — device QA pending:** Functional implementation exists and automated checks pass, but the current build still needs manual device validation.
- **Shell only:** Navigation and presentation exist, but the underlying product capability is not implemented.
- **Not implemented:** No production-capable implementation exists.

## Status table

| Order | Feature | Status | Device Tested | Automated Validation | Commit |
| ----- | ----------------------------- | ------------------------------ | ------------ | -------------------- | ------ |
| 0 | Migration baseline | Complete | No | Yes | `b9c4eaa` |
| 1 | API client and environment | Complete | Yes | Yes | `f6bc3a4` |
| 2 | Authentication and user state | Integrated — revalidation pending | Pending | Pending hardening CI | `c76b24a` + hardening branch |
| 3 | Session creation | Integrated — revalidation pending | Pending | Pending hardening CI | `d57b2cf` + hardening branch |
| 4 | Trick catalog and picker | Complete | Yes | Yes | `12c6596` |
| 5 | Attempt logging | Integrated — revalidation pending | Pending | Pending hardening CI | `eaa71e8` + hardening branch |
| 6 | End-session recap | Integrated — revalidation pending | Pending | Pending hardening CI | `30579af` + hardening branch |
| 7 | Session history | Integrated — revalidation pending | Pending | Pending hardening CI | `f4f542b` + hardening branch |
| 8 | Clip selection and upload | Integrated — device QA pending | Pending | Pending hardening CI | `e900950` + hardening branch |
| 9 | Analysis job status and recovery | Integrated — device QA pending | Pending | Pending hardening CI | `e900950` + hardening branch |
| 10 | Feed list and pagination | Integrated — device QA pending | Pending | Yes before hardening | `4f44a01` |
| 10b | Friend graph, reactions, battles, and full social layer | Not implemented in Lite | No | No | — |
| 11 | Paywall presentation | Shell only | No | UI tests only | `4f44a01` |
| 11b | In-app purchase, restore, and verified entitlement sync | Not implemented in Lite | No | No | — |
| 12 | Settings, legal links, and haptics | Integrated — device QA pending | Pending | Yes before hardening | `4f44a01` |
| 12b | Notification inbox and push notifications | Shell only / push not implemented | No | No production integration | `4f44a01` |

## Production hardening gate

The `agent/production-hardening-1-10` branch addresses the release blockers found during the senior-engineer review:

- Apple Sign-In native entitlement and config plugin.
- Fail-closed encrypted credential storage.
- User-scoped local persistence.
- Pending analysis recovery after app termination.
- Strict API parsing and honest confidence presentation.
- Recoverable session-finalization journal.
- Native binary clip upload with limits, timeout, progress, and method validation.
- Abortable polling with permanent/transient failure classification.
- Regression tests for isolation and recovery.
- A real-device release checklist in `docs/release/production-hardening-qa.md`.

Do not mark the hardening gate complete until CI and the real-device checklist both pass.

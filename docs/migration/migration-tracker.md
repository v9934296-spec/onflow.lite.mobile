# Migration Tracker

## Definition: feature migrated

A feature is **not** migrated because the code compiles.

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

## Status table

| Order | Feature | Status | Device Tested | Tests Passing | Commit |
| ----- | ----------------------------- | ---------------------: | ------------: | ------------: | ------ |
| 0 | Migration baseline | Complete | No | Yes | `b9c4eaa` |
| 1 | API client and environment | Complete | Pending manual | Yes (66) | — |
| 2 | Authentication and user state | Not started | No | No | — |
| 3 | Session creation | Not started | No | No | — |
| 4 | Trick catalog and picker | Not started | No | No | — |
| 5 | Attempt logging | Not started | No | No | — |
| 6 | End-session recap | Not started | No | No | — |
| 7 | Session history | Not started | No | No | — |
| 8 | Clip selection and upload | Blocked by Milestone 1 | No | No | — |
| 9 | Analysis job status | Blocked by upload | No | No | — |
| 10 | Feed and social features | Deferred | No | No | — |
| 11 | Subscriptions and paywall | Deferred | No | No | — |
| 12 | Notifications and polish | Deferred | No | No | — |

Update this table after each completed feature commit.

# OnFlow.skate → OnFlow Lite Mobile UI/UX Transplant

## Goal

Move the proven UI/UX from `onflow.skate` into `onflow.lite.mobile` **without rebuilding the app architecture**.

The destination remains `onflow.lite.mobile`. Its API wiring, auth, session lifecycle, storage, tests, and migration work stay intact. We transplant presentation and interaction patterns onto those existing contracts.

## Non-negotiable guardrails

1. No new app architecture.
2. No V4/V5 reset.
3. Do not copy old business logic when Lite already has a working equivalent.
4. Do not replace working API clients, auth, session state, upload flow, or backend contracts merely to match old screen code.
5. Port visual structure and interaction behavior first; adapt bindings to Lite's existing hooks/contexts.
6. Every checkpoint must typecheck/test/bundle before the next screen group is migrated.
7. Missing features must be classified as `present`, `hidden/disconnected`, `needs adapter`, or `actually missing` before implementation.

## Source of truth

### Presentation source

`v9934296-spec/onflow.skate/apps/mobile`

Use it as the reference for:

- information hierarchy
- screen composition
- navigation feel
- card/button treatment
- spacing and typography hierarchy
- Flow/PTE presentation
- Battle presentation
- progression surfaces
- feed/session recap presentation

### Runtime destination

`v9934296-spec/onflow.lite.mobile`

Keep its current:

- API client/environment layer
- authentication and user state
- session creation/end lifecycle
- trick catalog integration
- attempt logging
- recap/history data contracts
- clip upload + job polling
- feed/social API integration
- subscriptions/paywall
- notification wiring

## Brand tokens

- Background: near-black/charcoal
- Primary accent: `#54FF00`
- Secondary accent: `#FF0044`
- Primary text: off-white
- Gray is supporting text only, not the dominant visual system

Green and red/pink are a paired OnFlow identity. Red/pink is not reserved only for destructive actions.

## Screen migration map

| Product area | Source UX | Lite destination | Action |
| --- | --- | --- | --- |
| Home | `apps/mobile/app/(tabs)/home.tsx` | `app/index.tsx` | Port hierarchy; bind to Lite state |
| Flow | `apps/mobile/app/(tabs)/flow.tsx` + `/flow/*` | current session/trick/capture/recap routes | Port experience; keep Lite lifecycle |
| PTE.Flow | `apps/mobile/app/(tabs)/pte.tsx` + progression views | new Lite PTE surface using migrated APIs | Restore as first-class destination |
| Battle | battle state/presentation in Home/PTE/Flow source | Lite session entry + battle mode adapter | Restore alternate session mode without changing normal session loop |
| Feed | source feed UI/cards | `app/feed.tsx` | Port presentation; keep Lite feed API |
| Recap | `apps/mobile/app/flow/recap.tsx` | `app/recap.tsx` | Port visual hierarchy; keep Lite recap data |
| History | progression/session history source | `app/history.tsx` | Port rows/navigation; keep Lite history store/API |
| Settings/Profile | source profile/settings surfaces | `app/settings.tsx` | Port compact list hierarchy |

## Checkpoints

### Checkpoint 1 — shared visual shell

- Restore production green + red/pink tokens.
- Remove the prototype-era aluminum outline treatment from every card/button.
- Establish shared surfaces/controls that resemble the proven OnFlow presentation.
- No feature logic changes.

### Checkpoint 2 — navigation + Home

- Restore product-level navigation hierarchy.
- Port Home command-center composition from `onflow.skate`.
- Remove giant menu-button navigation from Home.
- Preserve all existing Lite routes and state bindings.

### Checkpoint 3 — Flow/session UX

- Port Flow entry and active-session presentation.
- Make Land/Miss primary session controls.
- Keep existing Lite attempt APIs and session lifecycle.
- Preserve clip filming/upload path.

### Checkpoint 4 — PTE.Flow + progression visualization

- Surface migrated progression endpoints in a real PTE.Flow destination.
- Restore meaningful charts/trends rather than placeholder day dots only.
- Reuse deterministic PTE outputs already present in the backend.

### Checkpoint 5 — Battle

- Verify existing backend/session fields and adapters first.
- Restore `Session` vs `Battle` entry.
- Do not fork the entire session stack; Battle should reuse the same session lifecycle wherever possible.

### Checkpoint 6 — Feed, recap, history, settings

- Port presentation screen-by-screen.
- Keep Lite data/service contracts.
- Remove remaining prototype-only language and sample/demo surfaces from production paths.

### Checkpoint 7 — regression gate

Required before merge:

- Typecheck passes.
- Unit tests pass.
- iOS bundle/export passes.
- Existing auth/session/upload/recap/feed flows remain functional.
- Manual device check verifies Home → Session/Battle → Trick → Attempt → Clip → End → Recap → History.
- PTE.Flow loads real progression data and handles empty/error/loading states.

## Rule for every ported screen

**Reuse the UX decisions, not the old technical debt.**

A source screen should be visually/behaviorally recognizable as OnFlow.skate while its data and actions are supplied by Lite's current architecture.

# OnFlow.skate → OnFlow Demo UI/UX Transplant

## Goal

**Demo is the product.** Skate is a **parts warehouse** for rebuilt presentation only.

Harvest the proven UI/UX from `onflow.skate/apps/mobile` into `onflowdemo` **without importing skate architectural debt**. Demo keeps the cleaner Lite foundation (auth, session lifecycle, upload, API clients, FastAPI backend).

Prior Demo transplant-era chrome (including commit `4b448ea` marketing-hero shell) is **discarded**. Skate rebuilt UI is the presentation source.

## Non-negotiable guardrails

1. No new app architecture / V4 reset.
2. Do not copy old business logic when Demo already has a working equivalent.
3. Do not replace working API clients, auth, session state, upload flow, or backend contracts merely to match skate file structure.
4. Port visual structure and interaction behavior; adapt bindings to Demo hooks/contexts.
5. Hide or stub sections Demo cannot feed yet — never paper over with skate-only clients.
6. Evolve product UI only in Demo after harvest.

## Brand tokens (shipped)

- Background: charcoal scale (`#1A1A1C` base)
- Primary accent (volt): `#B8F035`
- Secondary accent (red): `#D42B2B`
- Typography: Rubik + JetBrains Mono
- Edge-accent cards; no aluminum prototype outlines on product surfaces

## Screen map (shipped)

| Product area | Skate source | Demo destination | Status |
| --- | --- | --- | --- |
| Shell / tokens | `theme/tokens.ts` | `src/theme.ts`, `src/ui.tsx`, `_layout` | Done |
| Nav | tabs layout | `src/components/AppNav.tsx` (Home / Flow / PTE) | Done |
| Core components | `components/core/*` | `src/components/*` | Done |
| Home | `(tabs)/home.tsx` | `app/index.tsx` command-center | Done |
| Flow | `(tabs)/flow.tsx` + session | `app/flow.tsx` (Lite Land/Miss kept) | Done |
| PTE.Flow | `(tabs)/pte.tsx` | `app/pte.tsx` | Done |
| Feed | `home/feed.tsx` + FeedCard | `app/feed.tsx` | Done |
| Profile | `home/profile.tsx` | `app/settings.tsx` | Done |
| History | `progression/timeline.tsx` | `app/history.tsx` | Done |
| Recap | `flow/recap.tsx` | `app/recap.tsx` (hierarchy retained) | Done |

## Architecture kept in Demo

- API client / env layer
- Authentication and user state
- Session create / end lifecycle
- Attempt logging + clip upload + job polling
- Feed / billing contracts
- Colocated FastAPI backend

## Regression gate

- `npm run typecheck`
- `npm test`
- Manual: Home → Session/Battle → Trick → Attempt → Clip → End → Recap → History; PTE empty/error/loaded; Feed list/empty

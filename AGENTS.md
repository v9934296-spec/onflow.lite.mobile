# Agent notes

## Explain the work process

After every OF-* ticket, and after any code, test, or doc edits, end the user-facing reply with a short **How I did this** section.

Teach the method, not only the result. Keep it numbered, short, and concrete.

Include:

1. What you searched or read first
2. What you treated as source of truth
3. What you changed (or explicitly did not change)
4. How you verified

Do not dump tool names, jargon, or internals. Write so a person could repeat the same steps on the next ticket.

This is in addition to the ticket's definition of done, not a replacement for it.

## Cursor Cloud specific instructions

- API dependencies live in `services/api/.venv` (Python 3.12). Creating that venv needs the `python3.12-venv` package. Local development uses SQLite, so Postgres, Redis, Gemini, and Twelve Labs are not required. Readiness is `GET /health` on port 8000. `GET /health/deep` stays 503 until a Gemini key is set.
- Start the API from `services/api` with `.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- The browser app is `npm run web` (`expo start --web`) on port 8081. Set `EXPO_NO_TYPESCRIPT_SETUP=1` so Expo does not rewrite `tsconfig.json`. Copy `.env.example` to `.env` and set `EXPO_PUBLIC_API_URL=http://127.0.0.1:8000`. The sign-in screen renders, and dev email sign-in reaches `POST /api/v1/auth/session`. The app then stores the token with `expo-secure-store`, which fails closed on web, so the home screen stays on a native client. Signed-in API checks belong in `/docs` or curl.
- Checks: `npm run typecheck` and `npm test` at the repo root; `services/api/.venv/bin/python -m pytest -q` in `services/api`.
- This environment has no iOS simulator or Android emulator. EAS, RevenueCat, and store credentials are not part of local setup.

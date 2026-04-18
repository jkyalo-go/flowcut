# Auth & Invitations Plan

**Goal:** Close the audit's C4 (OAuth/CORS/CSRF) and H4 (invitation race), fix session storage, add rate limiting.

## Changes

1. **PKCE on Google OAuth** — new `oauth_states` table; `oauth/google/start` generates `code_verifier`/`code_challenge`, persists verifier keyed by state; `oauth/google/callback` retrieves verifier and sends to token exchange.
2. **CSRF double-submit** — `CSRFMiddleware` checks state-changing requests for `X-CSRF-Token` header matching the `flowcut_csrf` cookie. Skips GET/HEAD/OPTIONS and websocket routes. Cookie set on every session creation.
3. **Session cookie SameSite=Strict**.
4. **Membership unique constraint** migration `(workspace_id, user_id)`.
5. **Invitation accept race fix** — `with_for_update()` on the Invitation row; `IntegrityError` on duplicate membership is non-fatal (idempotent).
6. **Invitation GET read-only** — no state mutation on read.
7. **Rate limit** — slowapi on `GET /invitations/{token}` (30/min/IP) and `POST /invitations/{token}/accept` (5/min/IP).
8. **Frontend 401 handler** — ApiError with status 401 triggers redirect to `/login?redirect=<current>`.
9. **Frontend token cleanup** — drop in-memory token copy from authStore; rely on httpOnly cookie + csrf cookie only.

## Migrations

- `add_oauth_states` — new table with columns `state TEXT PRIMARY KEY`, `code_verifier TEXT NOT NULL`, `created_at TIMESTAMPTZ DEFAULT NOW()`, `expires_at TIMESTAMPTZ NOT NULL`.
- `add_memberships_workspace_user_unique` — UNIQUE(workspace_id, user_id).

## Tests

- `test_oauth_pkce.py` — start issues code_challenge, callback requires valid verifier lookup, replay rejected.
- `test_csrf.py` — POST without token → 403; with matching cookie+header → pass; GET unaffected.
- `test_invitation_race.py` — concurrent accept with same token results in exactly one membership; second call gets 409.
- `test_invitation_get_readonly.py` — GET does not mutate status.

All live in `backend/tests/`.

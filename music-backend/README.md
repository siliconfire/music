# Music Backend Board Layout

This backend stores the board widget layout in `board.json` and exposes two endpoints:

- `GET /board` returns the current widget layout (public, no auth).
- `PUT /board` updates widget order; admins can also set pinned widgets.

## Passkeys (WebAuthn)

Backend-only passkey endpoints are available for future `/account` enroll and `/login/passkeys` login flows:

- `POST /account/passkeys/options` (auth required) -> registration options
- `POST /account/passkeys/verify` (auth required) -> store credential
- `POST /login/passkeys/options` -> authentication options
- `POST /login/passkeys/verify` -> verify assertion + issue JWT

Environment variables used:

- `PASSKEY_RP_ID` (default: `localhost`)
- `PASSKEY_RP_ORIGIN` (default: `http://localhost:4321`)
- `PASSKEY_RP_NAME` (default: `Music Board`)

## Run notes

This feature is integrated into the existing FastAPI app. No extra services are required.

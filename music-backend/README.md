# Music Backend Board Layout

This backend stores the board widget layout in `board.json` and exposes two endpoints:

- `GET /board` returns the current widget layout (public, no auth).
- `PUT /board` updates widget order; admins can also set pinned widgets.

## Run notes

This feature is integrated into the existing FastAPI app. No extra services are required.

# Mistake Bank — working notes

An SAT wrong-answer journal: log a miss, an AI analyses and files it, and it returns on
a fixed 1h / 24h / 72h / 1w / 1mo ladder. See `README.md` for how to run it.

## Rules that come from real bugs in this repo

- **Open the app at `http://localhost:PORT`, never `http://127.0.0.1:PORT`.** Next
  blocks its own dev resources for an unexpected host. The page still renders, so it
  looks fine — it just never hydrates, issues no API calls, and sits on the loading
  skeleton. `allowedDevOrigins` in `next.config.ts` covers the IP now; the failure mode
  is worth remembering because nothing about it says "wrong hostname".
- **CORS is load-bearing and silent.** `next dev` moves to a free port whenever 3000 is
  taken. A dev origin that is not allowed gets a 400 on preflight and the whole app is
  a blank page. `cors_origin_regex` covers any localhost port; `tests/test_cors.py`
  keeps it that way.
- **Timestamps go through `UtcDateTime`, never a bare `DateTime(timezone=True)`.**
  SQLite stores no offset, so a plain column reads back naive, and the first time a
  naive value from the database meets a freshly built aware one the request raises.
- **Screenshot the app and look at it before saying a screen works.** Every one of the
  bugs above passed the whole test suite.
- **Prove a sabotage applied before trusting a calibration run** (`assert s != before`),
  and sabotage at the depth the bug would live.

## Shape of the code

- `backend/app/review.py` — the ladder. The one file to read first.
- `backend/app/analysis/` — the analyzer contract, the offline stub, the Claude adapter.
  Adding a provider is one new file plus a line in `__init__.py`.
- `backend/app/services.py` — runs the analyzer and writes its verdict. Never raises on
  an analyzer failure: the mistake is logged and on the ladder regardless.
- `frontend/src/lib/types.ts` mirrors `backend/app/schemas.py`. Change them together.

## Conventions

- The analysis text is **always** the AI's. The app stores, groups and displays it; it
  does not hand-author explanations.
- `ErrorType` is a closed vocabulary. Free-text "why" labels would make the slot view
  ungroupable. Add a member rather than letting the model invent one.
- Every domain query is scoped by `user_id`, today from the `X-User-Id` header.
- Lean on prewritten libraries and skin them; never rebuild a solved system (calendar,
  data table, form validation, rich text).
- Every feature ships with tests; every bug fix ships with the test that would have
  caught it. Run the full pipeline in `README.md` before calling anything done.

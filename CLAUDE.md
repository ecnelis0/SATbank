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

- `backend/app/review.py` — the ladder, and `URGENCY_RANK`, the case expression that
  orders the due queue. The one file to read first.
- `backend/app/analysis/` — the analyzer contract, the offline stub, the Claude adapter.
  Adding a provider is one new file plus a line in `__init__.py`.
- `backend/app/services.py` — runs the analyzer and writes its verdict. Never raises on
  an analyzer failure: the mistake is logged and on the ladder regardless.
- `backend/app/routers/mistakes.py` — `POST /mistakes?analyze=false` logs without asking
  the AI, `PATCH /mistakes/{id}` edits any field, `POST /mistakes/{id}/analyze` asks for
  the debrief and refuses (409) to overwrite an edited analysis without `force=true`.
- `frontend/src/lib/types.ts` mirrors `backend/app/schemas.py`. Change them together.

## Conventions

- **Adding a column means altering the dev database by hand.** `create_all` only creates
  missing tables; it will not add a column to one that already exists, and the app then
  fails on every read with `no such column`. Until Alembic lands, `ALTER TABLE` it.
- The AI writes the analysis, and the student can overwrite any of it. Anything they
  write is credited to them (`analyzed_by = "you"`), marked with `analysis_edited_at`,
  and guarded against a careless re-run. The app itself still authors no explanations.
- **A shared query helper must not carry an `.order_by()`.** SQLAlchemy *appends*
  ordering, so a caller adding its own key silently gets it second. `_open_for_user`
  returns unordered; each endpoint orders itself.
- `ErrorType` and `Urgency` are closed vocabularies. Free-text "why" labels would make the slot view
  ungroupable. Add a member rather than letting the model invent one.
- Every domain query is scoped by `user_id`, today from the `X-User-Id` header.
- Lean on prewritten libraries and skin them; never rebuild a solved system (calendar,
  data table, form validation, rich text).
- Every feature ships with tests; every bug fix ships with the test that would have
  caught it. Run the full pipeline in `README.md` before calling anything done.

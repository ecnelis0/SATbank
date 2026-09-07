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
- `backend/app/analysis/` — the analyzer contract (`analyze`, `interpret`, `summarise`),
  the offline stub, the Claude adapter. Adding a provider is one new file plus a line in
  `__init__.py`.
- `backend/app/images.py` — upload validation. Every rule there is "do not trust the
  upload": the filename is generated, the type comes from decoding the pixels, the size
  is capped while reading.
- `backend/app/query.py` — `BankQuery`, the structured filter the assistant produces.
  **The model writes the filter; the database writes the answer.** Never hand the model
  the bank and ask it to count - it will approximate, and the student cannot tell.
- `backend/app/services.py` — runs the analyzer and writes its verdict. Never raises on
  an analyzer failure: the mistake is logged and on the ladder regardless.
- `backend/app/routers/mistakes.py` — `POST /mistakes?analyze=false` logs without asking
  the AI, `PATCH /mistakes/{id}` edits any field, `POST /mistakes/{id}/analyze` asks for
  the debrief and refuses (409) to overwrite an edited analysis without `force=true`.
- `frontend/src/lib/types.ts` mirrors `backend/app/schemas.py`. Change them together.
- `frontend/src/lib/facets.ts` — the multi-select model, and the only place facets are
  translated to and from the URL. The URL is the source of truth for the bank's filters,
  so there is no state to keep in sync when the rail navigates there.

## Testing note

The Playwright specs share one e2e database and run in a single worker, so **no test may
assume the bank lacks something** — another spec will eventually add it. Assert invariants
("every row returned matches the filter") or build the exact condition from an
impossible value in the URL. One test was written the wrong way and started failing the
moment an unrelated spec logged a fundamental math question.

## Two traps this codebase keeps setting

- **`assert s != before` proves *a* replacement applied, not *every* one.** An edit doing
  two replacements in one file passed its assert with only the first applied, and the
  vocabulary silently never reached the interpret prompt. Assert per replacement, or
  grep for the result afterwards.

- **`toBeVisible()` on an `<img>` says nothing about whether it loaded.** Visibility
  lands before the bytes do, so assert the decode with `expect.poll(... img.complete &&
  img.naturalWidth > 0)` rather than reading it once.

- **A new row's collections must be initialised, not left to lazy-load.** Returning a
  freshly created `Mistake` or `Concept` and letting Pydantic read `.images` /
  `.concepts` raises `MissingGreenlet` at response time, not at the line that forgot.
  `blank_collections()` and `mistake_options()` sit next to each other in `models.py`
  for that reason - a new relationship goes in both.
- **Duplicate accessible names are bugs.** The concepts page had a header button and an
  empty-state button both called "Write a concept", and the empty one linked to the page
  it was already on. It surfaced as a Playwright strict-mode violation; the fix was the
  UI, not the selector.

## Conventions

- **Adding a column means altering the dev database by hand.** `create_all` only creates
  missing tables; it will not add a column to one that already exists, and the app then
  fails on every read with `no such column`. Until Alembic lands, `ALTER TABLE` it.
- The AI writes the analysis, and the student can overwrite any of it. Anything they
  write is credited to them (`analyzed_by = "you"`), marked with `analysis_edited_at`,
  and guarded against a careless re-run. The app itself still authors no explanations.
- **The side rail is fixed-position, mounted only when open, with no clip-path and no
  transform on a clipped child** - the two ways a panel here has previously been laid
  out, opaque, and still unpainted. If you restyle it, hit-test its centre afterwards.
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

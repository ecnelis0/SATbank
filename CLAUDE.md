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

The e2e suite has **its own database and its own upload directory** (`e2e.db`,
`e2e-uploads/`). It did not always: sharing `uploads/` with a dev session meant an e2e
run wrote into the real bank, and the `rm -rf` before a run deleted the real bank's
pictures. If you add another kind of stored state, isolate it in `playwright.config.ts`
at the same time.


The Playwright specs share one e2e database and run in a single worker, so **no test may
assume the bank lacks something** — another spec will eventually add it. Assert invariants
("every row returned matches the filter") or build the exact condition from an
impossible value in the URL. One test was written the wrong way and started failing the
moment an unrelated spec logged a fundamental math question.

## Two traps this codebase keeps setting

- **Never render an empty state for a failed load.** The bank said "Nothing here",
  review said "Nothing is due", and the rail rendered blank whenever the API was
  unreachable — in an app whose whole promise is not losing your work, that is the most
  alarming and least true thing it could say. Every list surface branches on `isError`
  to `<Unreachable/>` first, and a test asserts the empty state is *not* shown.

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
- **A control that navigates is a link, not a button.** Base UI's
  `<Button render={<Link/>}>` keeps `role="button"`, which tells a screen reader the
  wrong thing about what will happen. Style the `Link` with `buttonVariants()` instead.
- **An empty result caused by correct filtering still needs explaining.** A concept with
  nothing tagged filters to an empty bank, which is right and reads as broken. Name the
  cause and offer the way out.
- **Duplicate accessible names are bugs.** The concepts page had a header button and an
  empty-state button both called "Write a concept", and the empty one linked to the page
  it was already on. It surfaced as a Playwright strict-mode violation; the fix was the
  UI, not the selector.

## Design

The palette lives in `frontend/src/app/globals.css`, and its names mirror the Figma file's
"Colour" collection one-for-one (`bg/page`, `text/secondary`, `accent/base`, `urgency/*`)
so the two cannot quietly drift. Figma file:
https://www.figma.com/design/vMy6YVeJtHlUwdUSFUDLOF

Three primitives carry the whole front end; use them rather than assembling a page out
of raw cards and headings:

- `PageHeader` — display-serif title, one line of lede, actions on the right. Every page
  opens the same way, which is most of what makes a set of screens feel like one product.
- `Section` — a small, spaced, quiet eyebrow over its content. A same-size bold heading
  always competes with the thing it is labelling.
- `Panel` — the one card. `spine` paints a coloured left edge from `SPINE[urgency]`, so a
  card's status is legible before any of it is read.

Type: **Fraunces** for page titles only (`h1`, via `--font-display`), the body face for
everything else. A display serif on every heading turns a study tool into a magazine
spread; on the page title alone it gives the product a voice.

`next/font` rejects `axes` alongside pinned `weight` values — "Axes can only be defined
for variable fonts" — and it fails at build time, not typecheck. Load the page after
touching fonts.

Two things the palette is deliberately doing: warm paper rather than pure white, because
this is a study notebook someone stares at for hours; and one colour per urgency level, so
Fundamental / Very important / Important read as a scale instead of three identical chips.

The Figma plan is Starter, which allows **one mode per variable collection** — dark values
therefore live only in the CSS, under `.dark`. Change both together.

## Conventions

- **A model change needs a migration in the same commit.** The API migrates on startup
  and `tests/test_migrations.py` compares the migrated schema against the models, so
  forgetting one fails the suite rather than surfacing as `no such column` at the first
  query. Autogenerate renders custom types by their qualified name, which is why
  `script.py.mako` imports `app.models`.
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

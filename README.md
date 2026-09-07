# Mistake Bank — an SAT wrong-answer journal

You get a question wrong. You log it. An AI explains *why* you got it wrong and files
it under the kind of mistake it was. Then it comes back — at **1 hour, 24 hours,
72 hours, 1 week and 1 month**.

That schedule is the product. The intervals are fixed and identical for every
question; this is deliberately not an SM-2/Anki ease-factor scheduler. Miss a review
and the ladder restarts from the top.

## What is here

| | |
|---|---|
| `backend/` | FastAPI + SQLAlchemy 2.0 (async). Owns the database, the ladder, and the analyzer. |
| `frontend/` | Next.js App Router + TypeScript, shadcn/ui, TanStack Query, Motion. |

Screens: a dashboard of slots ("why you're losing points"), a log form, the bank with
filters, a question detail page with the analysis and its ladder, and a review session.

## The AI is optional, and nothing it writes is final

- **Log it and ask the AI** runs the debrief straight away.
- **Just log it** saves the question with no analysis at all. The ladder still starts.
  The question then sits there offering two buttons: *Ask the AI to debrief this*, and
  *Write it myself*.
- **Everything is editable** — the question, source, choices, both answers, your note,
  and every field the AI wrote: the slot, topic, difficulty, why-you-got-it-wrong, the
  trap, the reasoning, the takeaway, the tags.
- An analysis you wrote or edited **files exactly like an AI one** — same slots, same
  filters, same counts — and is credited to you.
- Re-running the AI over an analysis you have edited **asks first**, and the API refuses
  it outright without `force=true`. Your words are not lost to a stray click.

## Running it

Two processes. The defaults need no configuration at all — SQLite on disk and the
offline analyzer.

```bash
# API on :8000
cd backend && uv sync && uv run uvicorn app.main:app --reload

# Web on :3000
cd frontend && npm install && npm run dev
```

Then open **http://localhost:3000** — `localhost`, not `127.0.0.1`. (The IP works too,
but only because `allowedDevOrigins` is set in `next.config.ts`; without it Next blocks
its own dev resources and the page renders a loading skeleton forever.)

## Configuration

Copy `.env.example` to `.env` at the repo root. Everything has a working default.

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./sat_bank.db` | Neon: `postgresql+asyncpg://…?ssl=require` |
| `AI_PROVIDER` | `stub` | `stub` or `claude` |
| `ANTHROPIC_API_KEY` | — | Required when `AI_PROVIDER=claude` |
| `ANTHROPIC_MODEL` | `claude-opus-5` | |
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Where the browser finds the API |

**The analyzer is pluggable and the provider is still an open decision.** `stub` is an
offline analyzer: no API key, no network, deterministic output, and what the test suite
runs against. `claude` is the real one, using structured outputs so the response is a
validated object rather than prose to scrape. Adding an OpenAI adapter means one file
implementing `Analyzer` in `backend/app/analysis/` plus a line in its `__init__.py`.

## The ladder, precisely

Logging a mistake arms five review events immediately, anchored to the moment it was
logged — before the analyzer runs, so a slow or failed analysis never costs you your
first review.

Completing a review:

- **correct** or **skipped** — the rest of the ladder is untouched.
- **wrong** — the rungs you never reached are retired as `superseded` (kept, not
  deleted, so the history stays readable) and a fresh cycle is armed from now.

A failed analysis leaves the question logged, on the ladder, and re-analyzable from its
detail page. The schedule never depends on the AI succeeding.

## Tests

```bash
cd backend  && uv run pytest && uv run ruff check app tests
cd frontend && npm run typecheck && npm run lint && npm test && npm run e2e
```

`npm run e2e` starts its own API and production build on ports 8001/3401 against a
separate database file, so it never touches your dev data.

## Not done yet

- **Auth.** Every query is already scoped by a user id, but it comes from an
  `X-User-Id` header that defaults to `local`. Clerk goes here.
- **Migrations.** Tables are created at startup, and `create_all` will not alter a
  table that already exists — adding `analysis_edited_at` meant an `ALTER TABLE` by
  hand on the dev database. Alembic before this holds data anyone would mind losing.
- **Notifications.** Nothing tells you a review came due; you have to open the app.

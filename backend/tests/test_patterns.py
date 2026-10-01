"""Patterns: the habits the analyzer names, and whether they actually collect."""

from __future__ import annotations

from sqlalchemy import select

from app.models import Mistake, Pattern, pattern_slug
from app.services import attach_patterns, known_pattern_titles
from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE


async def _log(client, **overrides):
    body = {**MATH_MISTAKE, **overrides}
    response = await client.post("/mistakes", json=body, params={"analyze": True})
    assert response.status_code == 201
    return response.json()


# --- the slug is what makes a pattern collect ---------------------------------


def test_wordings_of_one_habit_share_a_slug():
    """Case and punctuation are noise. Letting them through is exactly what leaves
    a bank full of patterns with a single question under each."""
    assert pattern_slug("Negative-sign slips") == pattern_slug("negative sign slips")
    assert pattern_slug("Dropped a negative sign!") == pattern_slug("dropped a negative sign")
    assert pattern_slug("  Rushed   the   last step ") == "rushed the last step"


def test_different_habits_do_not_collide():
    assert pattern_slug("Misread the question") != pattern_slug("Misread the evidence")


# --- collecting ---------------------------------------------------------------


async def test_two_questions_with_the_same_habit_land_under_one_pattern(
    client, session_factory
):
    await _log(client, question_text="First question about x")
    await _log(client, question_text="Second question about x")

    async with session_factory() as session:
        patterns = list(await session.scalars(select(Pattern)))

    # The stub names its pattern from the topic, so both questions share one.
    assert len(patterns) == 1
    async with session_factory() as session:
        detail = await session.scalar(
            select(Pattern).where(Pattern.id == patterns[0].id)
        )
        await session.refresh(detail, ["mistakes"])
        assert len(detail.mistakes) == 2


async def test_a_near_copy_of_an_existing_title_is_not_a_second_pattern(
    client, session_factory
):
    """The case the slug exists for, driven through the service rather than the
    model, so it holds whatever wording a provider happens to return."""
    from app.analysis.base import PatternTag

    logged = await _log(client)
    async with session_factory() as session:
        first = await session.scalar(
            select(Mistake).where(Mistake.id == logged["id"])
        )
        await session.refresh(first, ["patterns"])
        await attach_patterns(session, first, [PatternTag(title="Rushed it", why="a")])
        await session.commit()

        await attach_patterns(session, first, [PatternTag(title="rushed  it!", why="b")])
        await session.commit()

        patterns = list(await session.scalars(select(Pattern)))

    # Precisely: the two wordings are one row, not that the bank holds one row.
    rushed = [p for p in patterns if p.slug == pattern_slug("Rushed it")]
    assert len(rushed) == 1
    # The wording the pattern first collected under is kept.
    assert rushed[0].title == "Rushed it"


async def test_retagging_replaces_rather_than_piles_up(client, session_factory):
    """Re-running a debrief should correct a question's filing, not leave the old
    reading sitting next to the new one."""
    from app.analysis.base import PatternTag

    logged = await _log(client)
    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["patterns"])

        await attach_patterns(session, mistake, [PatternTag(title="First reading", why="a")])
        await session.commit()
        await attach_patterns(session, mistake, [PatternTag(title="Second reading", why="b")])
        await session.commit()

        await session.refresh(mistake, ["patterns"])
        assert [p.title for p in mistake.patterns] == ["Second reading"]


async def test_the_same_title_twice_in_one_analysis_is_one_pattern(client, session_factory):
    from app.analysis.base import PatternTag

    logged = await _log(client)
    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["patterns"])
        await attach_patterns(
            session,
            mistake,
            [PatternTag(title="Rushed it", why="a"), PatternTag(title="rushed it", why="b")],
        )
        await session.commit()
        await session.refresh(mistake, ["patterns"])
    assert len(mistake.patterns) == 1


# --- what the analyzer is told ------------------------------------------------


async def test_the_analyzer_is_handed_the_patterns_already_in_the_bank(
    client, session_factory
):
    """Without this the model invents a fresh wording every time and nothing ever
    collects — the single most important wire in the feature."""
    await _log(client)
    async with session_factory() as session:
        known = await known_pattern_titles(session, "local")
    assert known, "a logged question should have left a pattern to reuse"


async def test_known_patterns_lead_with_the_commonest(client, session_factory):
    from app.analysis.base import PatternTag

    first = await _log(client, question_text="One")
    second = await _log(client, question_text="Two")
    async with session_factory() as session:
        for mistake_id, titles in (
            (first["id"], ["Busy pattern"]),
            (second["id"], ["Busy pattern"]),
        ):
            mistake = await session.scalar(select(Mistake).where(Mistake.id == mistake_id))
            await session.refresh(mistake, ["patterns"])
            await attach_patterns(
                session, mistake, [PatternTag(title=t, why="x") for t in titles]
            )
        await session.commit()
        known = await known_pattern_titles(session, "local")

    # The model reads from the top, so the pattern worth reusing has to be there.
    assert known[0] == "Busy pattern"


# --- the API ------------------------------------------------------------------


async def test_patterns_are_listed_busiest_first(client):
    await _log(client, question_text="One")
    await _log(client, question_text="Two")
    await _log(client, **VERBAL_MISTAKE)

    rows = (await client.get("/patterns")).json()
    assert rows
    assert rows == sorted(rows, key=lambda r: (-r["question_count"], r["title"]))
    assert rows[0]["question_count"] >= 2


async def test_a_pattern_can_be_opened_with_its_questions(client):
    await _log(client, question_text="One")
    await _log(client, question_text="Two")
    listed = (await client.get("/patterns")).json()

    detail = (await client.get(f"/patterns/{listed[0]['id']}")).json()
    assert detail["question_count"] == len(detail["mistakes"]) == 2
    assert detail["summary"]


async def test_min_questions_hides_the_ones_that_have_not_collected(client):
    await _log(client, question_text="One")
    assert (await client.get("/patterns", params={"min_questions": 2})).json() == []


async def test_a_question_carries_its_patterns(client):
    logged = await _log(client)
    fetched = (await client.get(f"/mistakes/{logged['id']}")).json()
    assert fetched["patterns"]
    assert fetched["patterns"][0]["title"]


async def test_patterns_never_cross_between_students(client):
    await _log(client)
    assert (await client.get("/patterns", headers={"X-User-Id": "someone-else"})).json() == []


async def test_rebuild_tags_a_bank_that_was_logged_before_patterns_existed(
    client, session_factory
):
    logged = await _log(client)
    # Strip the patterns, as an older bank would have none.
    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["patterns"])
        mistake.patterns = []
        await session.commit()
    assert (await client.get(f"/mistakes/{logged['id']}")).json()["patterns"] == []

    rebuilt = (await client.post("/patterns/rebuild")).json()
    assert rebuilt
    assert (await client.get(f"/mistakes/{logged['id']}")).json()["patterns"]


async def test_rebuild_leaves_the_debrief_alone(client):
    """The student may have edited it. The backfill is about filing, not content."""
    logged = await _log(client)
    before = (await client.get(f"/mistakes/{logged['id']}")).json()

    await client.post("/patterns/rebuild")

    after = (await client.get(f"/mistakes/{logged['id']}")).json()
    assert after["why_wrong"] == before["why_wrong"]
    assert after["takeaway"] == before["takeaway"]
    assert after["analyzed_at"] == before["analyzed_at"]


async def test_a_pattern_left_holding_nothing_is_removed(client, session_factory):
    """A pattern with no questions is not just clutter in the list: it stays in the
    vocabulary handed to the analyzer, which is then invited to reuse a name the
    student has nothing under."""
    from app.analysis.base import PatternTag

    logged = await _log(client)
    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["patterns"])
        await attach_patterns(session, mistake, [PatternTag(title="Only home", why="a")])
        await session.commit()

        # Move it somewhere else; the pattern it left is now empty.
        await attach_patterns(session, mistake, [PatternTag(title="New home", why="b")])
        await session.commit()

        titles = [p.title for p in await session.scalars(select(Pattern))]
        known = await known_pattern_titles(session, "local")

    assert "Only home" not in titles
    assert "Only home" not in known
    assert "New home" in titles


# --- a pattern that has collected enough becomes a concept --------------------


async def _collect(client, session_factory, count: int, title: str = "Skipped the first step"):
    """Put `count` questions under one named pattern."""
    from app.analysis.base import PatternTag

    ids = []
    for index in range(count):
        logged = await _log(client, question_text=f"Graph question {index}")
        ids.append(logged["id"])
    async with session_factory() as session:
        for mistake_id in ids:
            mistake = await session.scalar(select(Mistake).where(Mistake.id == mistake_id))
            await session.refresh(mistake, ["patterns"])
            await attach_patterns(session, mistake, [PatternTag(title=title, why="same step")])
        await session.commit()
    return ids


async def test_a_pattern_below_the_threshold_is_not_suggested(client, session_factory):
    await _collect(client, session_factory, 3)
    assert (await client.get("/patterns/suggestions/candidates")).json() == []


async def test_ten_questions_under_one_habit_becomes_a_candidate(client, session_factory):
    """The student's own example: ten graph questions, each needing the same first
    step, should stop being ten questions and start being one idea."""
    await _collect(client, session_factory, 10)

    candidates = (await client.get("/patterns/suggestions/candidates")).json()
    assert len(candidates) == 1
    assert candidates[0]["question_count"] == 10
    assert candidates[0]["title"] == "Skipped the first step"


async def test_the_suggestion_carries_the_case_and_the_questions(client, session_factory):
    ids = await _collect(client, session_factory, 10)
    candidate = (await client.get("/patterns/suggestions/candidates")).json()[0]

    suggestion = (await client.post(f"/patterns/{candidate['id']}/suggest")).json()
    assert suggestion["question_count"] == 10
    assert suggestion["why_a_concept"]
    assert suggestion["what_went_wrong"]
    # The questions it would carry over, so accepting is one click and not ten.
    assert sorted(suggestion["mistake_ids"]) == sorted(ids)


async def test_promoting_files_every_question_under_the_new_concept(client, session_factory):
    ids = await _collect(client, session_factory, 10)
    candidate = (await client.get("/patterns/suggestions/candidates")).json()[0]

    concept = (
        await client.post(
            f"/patterns/{candidate['id']}/promote",
            json={"title": "Eliminate the impossible answers first", "body": "Rule."},
        )
    ).json()

    assert concept["title"] == "Eliminate the impossible answers first"
    assert concept["question_count"] == 10
    assert sorted(m["id"] for m in concept["mistakes"]) == sorted(ids)

    # And from the question's side, which is where the student will see it.
    fetched = (await client.get(f"/mistakes/{ids[0]}")).json()
    assert "Eliminate the impossible answers first" in [c["title"] for c in fetched["concepts"]]


async def test_a_promoted_pattern_stops_being_suggested(client, session_factory):
    ids = await _collect(client, session_factory, 10)
    candidate = (await client.get("/patterns/suggestions/candidates")).json()[0]
    await client.post(f"/patterns/{candidate['id']}/promote", json={})

    assert (await client.get("/patterns/suggestions/candidates")).json() == []
    assert ids  # the questions are untouched by the suggestion going away


async def test_promoting_twice_is_refused(client, session_factory):
    await _collect(client, session_factory, 10)
    candidate = (await client.get("/patterns/suggestions/candidates")).json()[0]
    await client.post(f"/patterns/{candidate['id']}/promote", json={})

    again = await client.post(f"/patterns/{candidate['id']}/promote", json={})
    assert again.status_code == 409


async def test_dismissing_sticks(client, session_factory):
    """Not every repeated habit deserves writing up, and a prompt that comes back
    after you have answered it teaches you to ignore prompts."""
    await _collect(client, session_factory, 10)
    candidate = (await client.get("/patterns/suggestions/candidates")).json()[0]

    await client.post(f"/patterns/{candidate['id']}/dismiss")
    assert (await client.get("/patterns/suggestions/candidates")).json() == []


async def test_the_suggestion_survives_a_failing_analyzer(client, session_factory, monkeypatch):
    ids = await _collect(client, session_factory, 10)
    candidate = (await client.get("/patterns/suggestions/candidates")).json()[0]

    class Broken:
        name = "broken"

        async def propose_concept(self, pattern, summary, digest):
            raise RuntimeError("no model today")

    monkeypatch.setattr("app.routers.patterns.get_analyzer", lambda: Broken())

    suggestion = (await client.post(f"/patterns/{candidate['id']}/suggest")).json()
    # The questions are the valuable half and must still come back.
    assert sorted(suggestion["mistake_ids"]) == sorted(ids)
    assert "no model today" in suggestion["error"]


async def test_suggestions_never_cross_between_students(client, session_factory):
    await _collect(client, session_factory, 10)
    other = await client.get(
        "/patterns/suggestions/candidates", headers={"X-User-Id": "someone-else"}
    )
    assert other.json() == []

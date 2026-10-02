"""Questions get filed under concepts without the student doing it by hand."""

from __future__ import annotations

from sqlalchemy import select

from app.analysis.base import ConceptMatch, Filing
from app.models import Concept, Mistake
from app.services import autofile_concepts, concept_briefs, file_under_named_concepts
from tests.conftest import MATH_MISTAKE


async def _concept(client, title: str, body: str = "A rule."):
    response = await client.post("/concepts", json={"title": title, "body": body})
    assert response.status_code == 201
    return response.json()


async def _log(client, analyze: bool = True, **overrides):
    body = {**MATH_MISTAKE, **overrides}
    response = await client.post("/mistakes", json=body, params={"analyze": analyze})
    assert response.status_code == 201
    return response.json()


# --- what the debrief is shown ------------------------------------------------


async def test_the_debrief_is_handed_the_concepts_the_student_keeps(client, session_factory):
    """Without this the debrief cannot file anything: it would be matching against
    a list it was never shown."""
    await _concept(client, "Dividing at the last step")
    async with session_factory() as session:
        briefs = await concept_briefs(session, "local")

    assert [b.title for b in briefs] == ["Dividing at the last step"]
    assert briefs[0].body == "A rule."


# --- filing one question ------------------------------------------------------


async def test_a_named_concept_is_attached(client, session_factory):
    concept = await _concept(client, "Dividing at the last step")
    logged = await _log(client, analyze=False)

    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["concepts"])
        await file_under_named_concepts(session, mistake, ["Dividing at the last step"])
        await session.commit()

    fetched = (await client.get(f"/mistakes/{logged['id']}")).json()
    assert [c["id"] for c in fetched["concepts"]] == [concept["id"]]


async def test_the_title_is_matched_whatever_the_case(client, session_factory):
    await _concept(client, "Dividing At The Last Step")
    logged = await _log(client, analyze=False)

    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["concepts"])
        await file_under_named_concepts(session, mistake, ["dividing at the last step"])
        await session.commit()

    assert (await client.get(f"/mistakes/{logged['id']}")).json()["concepts"]


async def test_a_concept_the_model_invented_is_dropped(client, session_factory):
    """Filing is matching against what exists. Inventing concepts is what videos
    and pattern promotion are for, and a debrief quietly creating them would fill
    the student's own list with the model's wording."""
    await _concept(client, "Dividing at the last step")
    logged = await _log(client, analyze=False)

    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["concepts"])
        await file_under_named_concepts(session, mistake, ["Something I just made up"])
        await session.commit()
        assert len(list(await session.scalars(select(Concept)))) == 1

    assert (await client.get(f"/mistakes/{logged['id']}")).json()["concepts"] == []


async def test_filing_adds_and_never_removes(client, session_factory):
    """A tag the student made by hand outranks the model's reading, and re-running
    a debrief must not quietly untag their work."""
    mine = await _concept(client, "Tagged by hand")
    theirs = await _concept(client, "Dividing at the last step")
    logged = await _log(client, analyze=False)
    await client.post(f"/concepts/{mine['id']}/questions/{logged['id']}")

    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["concepts"])
        await file_under_named_concepts(session, mistake, ["Dividing at the last step"])
        await session.commit()

    fetched = (await client.get(f"/mistakes/{logged['id']}")).json()
    titles = {c["title"] for c in fetched["concepts"]}
    assert titles == {"Tagged by hand", "Dividing at the last step"}
    assert theirs["id"]


async def test_filing_the_same_concept_twice_does_not_duplicate(client, session_factory):
    await _concept(client, "Dividing at the last step")
    logged = await _log(client, analyze=False)

    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["concepts"])
        await file_under_named_concepts(session, mistake, ["Dividing at the last step"])
        await session.commit()
        await file_under_named_concepts(session, mistake, ["Dividing at the last step"])
        await session.commit()

    assert len((await client.get(f"/mistakes/{logged['id']}")).json()["concepts"]) == 1


async def test_an_empty_list_leaves_the_question_alone(client, session_factory):
    """Filing nothing is a good answer, and has to be harmless."""
    mine = await _concept(client, "Tagged by hand")
    logged = await _log(client, analyze=False)
    await client.post(f"/concepts/{mine['id']}/questions/{logged['id']}")

    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["concepts"])
        await file_under_named_concepts(session, mistake, [])
        await session.commit()

    assert len((await client.get(f"/mistakes/{logged['id']}")).json()["concepts"]) == 1


async def test_you_cannot_be_filed_under_someone_elses_concept(client, session_factory):
    await client.post(
        "/concepts", json={"title": "Not yours"}, headers={"X-User-Id": "someone-else"}
    )
    logged = await _log(client, analyze=False)

    async with session_factory() as session:
        mistake = await session.scalar(select(Mistake).where(Mistake.id == logged["id"]))
        await session.refresh(mistake, ["concepts"])
        await file_under_named_concepts(session, mistake, ["Not yours"])
        await session.commit()

    assert (await client.get(f"/mistakes/{logged['id']}")).json()["concepts"] == []


# --- filing a whole bank under new concepts -----------------------------------


async def test_new_concepts_collect_the_questions_already_logged(
    client, session_factory, monkeypatch
):
    """The point of adding a video: what you have already got wrong gets attached
    to what it teaches, without tagging a hundred questions by hand."""
    logged = await _log(client)
    concept = await _concept(client, "Semicolons join independent clauses")

    class Filer:
        name = "filer"

        async def file_questions(self, concepts, digest):
            assert any(c.title.startswith("Semicolons") for c in concepts)
            # The id has to be in the digest for this to be answerable at all.
            assert logged["id"] in digest
            return Filing(
                matches=[
                    ConceptMatch(concept_title=concepts[0].title, mistake_ids=[logged["id"]])
                ]
            )

    monkeypatch.setattr("app.services.get_analyzer", lambda: Filer())

    async with session_factory() as session:
        rows = list(await session.scalars(select(Concept).where(Concept.id == concept["id"])))
        added = await autofile_concepts(session, "local", rows)
        await session.commit()

    assert added == 1
    fetched = (await client.get(f"/mistakes/{logged['id']}")).json()
    assert [c["id"] for c in fetched["concepts"]] == [concept["id"]]


async def test_autofiling_never_untags(client, session_factory, monkeypatch):
    mine = await _concept(client, "Tagged by hand")
    logged = await _log(client)
    await client.post(f"/concepts/{mine['id']}/questions/{logged['id']}")
    other = await _concept(client, "From the video")

    class Filer:
        name = "filer"

        async def file_questions(self, concepts, digest):
            return Filing(
                matches=[ConceptMatch(concept_title="From the video", mistake_ids=[logged["id"]])]
            )

    monkeypatch.setattr("app.services.get_analyzer", lambda: Filer())
    async with session_factory() as session:
        rows = list(await session.scalars(select(Concept).where(Concept.id == other["id"])))
        await autofile_concepts(session, "local", rows)
        await session.commit()

    fetched = (await client.get(f"/mistakes/{logged['id']}")).json()
    titles = {c["title"] for c in fetched["concepts"]}
    assert titles == {"Tagged by hand", "From the video"}


async def test_a_failing_filer_costs_nothing(client, session_factory, monkeypatch):
    """The concepts the video produced are already saved. Filing is a convenience
    laid on top and must not take them down with it."""
    await _log(client)
    concept = await _concept(client, "From the video")

    class Broken:
        name = "broken"

        async def file_questions(self, concepts, digest):
            raise RuntimeError("no model today")

    monkeypatch.setattr("app.services.get_analyzer", lambda: Broken())
    async with session_factory() as session:
        rows = list(await session.scalars(select(Concept).where(Concept.id == concept["id"])))
        added = await autofile_concepts(session, "local", rows)
        await session.commit()

    assert added == 0
    assert (await client.get(f"/concepts/{concept['id']}")).status_code == 200


async def test_an_id_the_model_made_up_is_ignored(client, session_factory, monkeypatch):
    await _log(client)
    concept = await _concept(client, "From the video")

    class Filer:
        name = "filer"

        async def file_questions(self, concepts, digest):
            return Filing(
                matches=[ConceptMatch(concept_title="From the video", mistake_ids=["f" * 32])]
            )

    monkeypatch.setattr("app.services.get_analyzer", lambda: Filer())
    async with session_factory() as session:
        rows = list(await session.scalars(select(Concept).where(Concept.id == concept["id"])))
        added = await autofile_concepts(session, "local", rows)
        await session.commit()
    assert added == 0


async def test_nothing_to_file_under_is_not_a_model_call(client, session_factory, monkeypatch):
    called = False

    class Filer:
        name = "filer"

        async def file_questions(self, concepts, digest):
            nonlocal called
            called = True
            return Filing()

    monkeypatch.setattr("app.services.get_analyzer", lambda: Filer())
    async with session_factory() as session:
        assert await autofile_concepts(session, "local", []) == 0
    assert called is False


async def test_the_filer_only_sees_the_students_own_questions(
    client, session_factory, monkeypatch
):
    await _log(client)
    await client.post(
        "/mistakes",
        json=MATH_MISTAKE,
        params={"analyze": True},
        headers={"X-User-Id": "someone-else"},
    )
    concept = await _concept(client, "From the video")
    seen: list[str] = []

    class Filer:
        name = "filer"

        async def file_questions(self, concepts, digest):
            seen.append(digest)
            return Filing()

    monkeypatch.setattr("app.services.get_analyzer", lambda: Filer())
    async with session_factory() as session:
        rows = list(await session.scalars(select(Concept).where(Concept.id == concept["id"])))
        await autofile_concepts(session, "local", rows)

    async with session_factory() as session:
        theirs = list(
            await session.scalars(select(Mistake).where(Mistake.user_id == "someone-else"))
        )
    assert theirs
    assert theirs[0].id not in seen[0]

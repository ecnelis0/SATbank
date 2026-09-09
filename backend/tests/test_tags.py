"""The student's own labels, and filing under a concept while logging."""

from __future__ import annotations

from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE


async def _log(client, **overrides):
    response = await client.post("/mistakes", json={**MATH_MISTAKE, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


async def _concept(client, title="Circumference gives the radius"):
    return (await client.post("/concepts", json={"title": title})).json()


# --- labelling while logging ----------------------------------------------------


async def test_a_question_can_be_labelled_as_it_is_logged(client):
    body = await _log(client, tags=["by mistake", "ran out of time"])

    assert body["tags"] == ["by mistake", "ran out of time"]


async def test_labels_survive_the_analysis(client):
    """The AI no longer writes tags, so it must not wipe the student's either."""
    body = await _log(client, tags=["by mistake"])

    stored = (await client.get(f"/mistakes/{body['id']}")).json()
    assert stored["analysis_status"] == "ready"
    assert stored["tags"] == ["by mistake"]


async def test_labels_are_tidied_rather_than_taken_literally(client):
    body = await _log(client, tags=["  by   mistake  ", "", "   "])

    assert body["tags"] == ["by mistake"]


async def test_the_same_label_in_two_cases_is_one_label(client):
    """ "By Mistake" and "by mistake" as separate tags would split every count."""
    body = await _log(client, tags=["By Mistake", "by mistake", "BY MISTAKE"])

    assert body["tags"] == ["By Mistake"]


async def test_labels_can_be_changed_afterwards(client):
    body = await _log(client, tags=["guessed"])

    updated = (
        await client.patch(f"/mistakes/{body['id']}", json={"tags": ["knew it, blanked"]})
    ).json()

    assert updated["tags"] == ["knew it, blanked"]


# --- reusing them ---------------------------------------------------------------


async def test_tags_in_use_are_offered_back_commonest_first(client):
    await _log(client, tags=["by mistake", "guessed"])
    await _log(client, tags=["by mistake"])

    tags = (await client.get("/tags")).json()
    used = [t for t in tags if not t["suggested"]]

    assert used[0] == {"tag": "by mistake", "count": 2, "suggested": False}
    assert {"tag": "guessed", "count": 1, "suggested": False} in used


async def test_a_starting_vocabulary_is_offered_before_anything_is_used(client):
    tags = (await client.get("/tags")).json()

    assert all(t["suggested"] for t in tags)
    assert "by mistake" in [t["tag"] for t in tags]


async def test_a_suggestion_stops_being_a_suggestion_once_used(client):
    await _log(client, tags=["by mistake"])

    tags = (await client.get("/tags")).json()
    entry = next(t for t in tags if t["tag"].casefold() == "by mistake")

    assert entry["suggested"] is False and entry["count"] == 1
    # And it is not offered twice.
    assert [t["tag"].casefold() for t in tags].count("by mistake") == 1


async def test_your_own_invented_label_comes_back_too(client):
    await _log(client, tags=["forgot the +C"])

    tags = [t["tag"] for t in (await client.get("/tags")).json()]

    assert "forgot the +C" in tags


async def test_tags_are_yours_alone(client):
    await _log(client, tags=["by mistake"])

    tags = (await client.get("/tags", headers={"X-User-Id": "someone-else"})).json()

    assert all(t["suggested"] for t in tags)


# --- filtering by them ----------------------------------------------------------


async def test_the_bank_can_be_filtered_by_a_label(client):
    tagged = await _log(client, tags=["by mistake"])
    await _log(client, tags=["guessed"])

    found = (await client.post("/mistakes/search", json={"tags": ["by mistake"]})).json()

    assert [m["id"] for m in found] == [tagged["id"]]


async def test_a_label_filter_ignores_case(client):
    tagged = await _log(client, tags=["By Mistake"])

    found = (await client.post("/mistakes/search", json={"tags": ["by mistake"]})).json()

    assert [m["id"] for m in found] == [tagged["id"]]


async def test_one_label_is_not_matched_by_another_containing_it(client):
    """ "guessed" must not match a question tagged only "guessed the units"."""
    await _log(client, tags=["guessed the units"])

    found = (await client.post("/mistakes/search", json={"tags": ["guessed"]})).json()

    assert found == []


async def test_a_label_narrows_alongside_the_other_facets(client):
    both = await _log(client, tags=["by mistake"], urgency="fundamental")
    await _log(client, tags=["by mistake"], urgency="important")

    found = (
        await client.post(
            "/mistakes/search",
            json={"tags": ["by mistake"], "urgency": ["fundamental"]},
        )
    ).json()

    assert [m["id"] for m in found] == [both["id"]]


async def test_the_assistant_is_told_which_labels_exist(client, session_factory):
    """A model cannot filter on a label it has never seen."""
    await _log(client, tags=["forgot the +C"])

    from app.query import vocabulary

    async with session_factory() as session:
        words = await vocabulary(session, "local")

    assert "forgot the +C" in words.tags
    assert "forgot the +C" in words.render()


# --- filing under a concept while logging ---------------------------------------


async def test_a_question_can_be_filed_under_a_concept_as_it_is_logged(client):
    concept = await _concept(client)

    body = await _log(client, concept_ids=[concept["id"]])

    assert [c["title"] for c in body["concepts"]] == [concept["title"]]
    detail = (await client.get(f"/concepts/{concept['id']}")).json()
    assert [m["id"] for m in detail["mistakes"]] == [body["id"]]


async def test_a_question_can_be_filed_under_several_concepts_at_once(client):
    first = await _concept(client, "Circumference gives the radius")
    second = await _concept(client, "Read the units")

    body = await _log(client, concept_ids=[first["id"], second["id"]])

    assert sorted(c["title"] for c in body["concepts"]) == [
        "Circumference gives the radius",
        "Read the units",
    ]


async def test_logging_under_no_concept_is_still_normal(client):
    body = await _log(client)

    assert body["concepts"] == []


async def test_you_cannot_file_a_question_under_someone_elses_concept(client):
    concept = await _concept(client)

    response = await client.post(
        "/mistakes",
        json={**VERBAL_MISTAKE, "concept_ids": [concept["id"]]},
        headers={"X-User-Id": "someone-else"},
    )

    assert response.status_code == 201
    assert response.json()["concepts"] == []


async def test_a_concept_id_that_does_not_exist_is_ignored_not_fatal(client):
    body = await _log(client, concept_ids=["deadbeef" * 4])

    assert body["concepts"] == []

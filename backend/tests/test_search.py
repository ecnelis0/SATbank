"""Multi-facet search, and topics reported under the section they belong to."""

from __future__ import annotations

from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE


async def _log(client, payload, **overrides):
    mistake_id = (await client.post("/mistakes", json=payload)).json()["id"]
    if overrides:
        response = await client.patch(f"/mistakes/{mistake_id}", json=overrides)
        assert response.status_code == 200, response.text
    return mistake_id


async def test_topics_are_grouped_under_their_section(client):
    await _log(client, MATH_MISTAKE, topic="linear equations")
    await _log(client, MATH_MISTAKE, topic="circles")
    await _log(client, VERBAL_MISTAKE, topic="command of evidence")

    topics = (await client.get("/stats")).json()["topics"]

    by_section: dict[str, set[str]] = {}
    for entry in topics:
        by_section.setdefault(entry["section"], set()).add(entry["topic"])

    assert by_section["math"] == {"linear equations", "circles"}
    assert by_section["reading_writing"] == {"command of evidence"}
    # A topic is never reported loose - it always carries its section.
    assert all(entry["section"] for entry in topics)


async def test_the_same_topic_in_two_sections_is_two_entries(client):
    await _log(client, MATH_MISTAKE, topic="rates")
    await _log(client, VERBAL_MISTAKE, topic="rates")

    topics = (await client.get("/stats")).json()["topics"]
    rates = [entry for entry in topics if entry["topic"] == "rates"]

    assert len(rates) == 2
    assert {entry["section"] for entry in rates} == {"math", "reading_writing"}


async def test_search_ands_across_facets(client):
    wanted = await _log(
        client,
        MATH_MISTAKE,
        topic="math fundamentals",
        error_type="concept_gap",
        urgency="very_important",
    )
    # Each of these differs from the target in exactly one facet.
    await _log(
        client, MATH_MISTAKE, topic="circles", error_type="concept_gap", urgency="very_important"
    )
    await _log(
        client,
        MATH_MISTAKE,
        topic="math fundamentals",
        error_type="trap_answer",
        urgency="very_important",
    )
    await _log(
        client,
        MATH_MISTAKE,
        topic="math fundamentals",
        error_type="concept_gap",
        urgency="important",
    )
    await _log(
        client,
        VERBAL_MISTAKE,
        topic="math fundamentals",
        error_type="concept_gap",
        urgency="very_important",
    )

    found = (
        await client.post(
            "/mistakes/search",
            json={
                "section": ["math"],
                "topics": ["math fundamentals"],
                "error_type": ["concept_gap"],
                "urgency": ["very_important"],
            },
        )
    ).json()

    assert [m["id"] for m in found] == [wanted]


async def test_search_ors_within_a_facet(client):
    fundamental = await _log(client, MATH_MISTAKE, urgency="fundamental")
    very = await _log(client, MATH_MISTAKE, urgency="very_important")
    await _log(client, MATH_MISTAKE, urgency="important")

    found = (
        await client.post("/mistakes/search", json={"urgency": ["fundamental", "very_important"]})
    ).json()

    assert {m["id"] for m in found} == {fundamental, very}


async def test_an_empty_search_returns_the_whole_bank(client):
    await _log(client, MATH_MISTAKE)
    await _log(client, VERBAL_MISTAKE)

    found = (await client.post("/mistakes/search", json={})).json()

    assert len(found) == 2


async def test_search_can_be_sorted_by_urgency(client):
    await _log(client, MATH_MISTAKE, urgency="important")
    urgent = await _log(client, MATH_MISTAKE, urgency="fundamental")

    found = (await client.post("/mistakes/search", json={"sort": "most_urgent"})).json()

    assert found[0]["id"] == urgent


async def test_search_only_ever_sees_your_own_bank(client):
    await _log(client, MATH_MISTAKE)

    found = (
        await client.post("/mistakes/search", json={}, headers={"X-User-Id": "someone-else"})
    ).json()

    assert found == []


async def test_search_rejects_a_facet_value_that_is_not_in_the_vocabulary(client):
    response = await client.post("/mistakes/search", json={"urgency": ["kind of urgent"]})

    assert response.status_code == 422


# --- finding the questions that carry no concept -------------------------------


async def test_untagged_questions_can_be_singled_out(client):
    """The gap the side rail cannot show: questions filed under nothing."""
    tagged = await _log(client, MATH_MISTAKE)
    untagged = await _log(client, VERBAL_MISTAKE)
    concept = (await client.post("/concepts", json={"title": "A concept"})).json()
    await client.post(f"/concepts/{concept['id']}/questions/{tagged}")

    without = (await client.post("/mistakes/search", json={"has_concept": False})).json()
    with_one = (await client.post("/mistakes/search", json={"has_concept": True})).json()

    assert [m["id"] for m in without] == [untagged]
    assert [m["id"] for m in with_one] == [tagged]


async def test_leaving_has_concept_unset_returns_both(client):
    tagged = await _log(client, MATH_MISTAKE)
    await _log(client, VERBAL_MISTAKE)
    concept = (await client.post("/concepts", json={"title": "A concept"})).json()
    await client.post(f"/concepts/{concept['id']}/questions/{tagged}")

    assert len((await client.post("/mistakes/search", json={})).json()) == 2


async def test_stats_counts_the_questions_with_no_concept(client):
    tagged = await _log(client, MATH_MISTAKE)
    await _log(client, VERBAL_MISTAKE)
    await _log(client, VERBAL_MISTAKE)
    concept = (await client.post("/concepts", json={"title": "A concept"})).json()
    await client.post(f"/concepts/{concept['id']}/questions/{tagged}")

    stats = (await client.get("/stats")).json()

    assert stats["total_mistakes"] == 3
    assert stats["untagged_questions"] == 2


async def test_a_concept_with_nothing_tagged_is_reported_as_such(client):
    """The bug: clicking an empty concept looked like the filter was broken."""
    await _log(client, MATH_MISTAKE)
    empty = (await client.post("/concepts", json={"title": "inverse trig"})).json()

    found = (await client.post("/mistakes/search", json={"concept_ids": [empty["id"]]})).json()

    assert found == []
    assert empty["question_count"] == 0
    # And the concept itself is still there to be seen and tagged into.
    assert (await client.get(f"/concepts/{empty['id']}")).status_code == 200

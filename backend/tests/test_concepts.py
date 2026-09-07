"""Concepts: the things worth knowing, and the questions filed under them."""

from __future__ import annotations

from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE

CONCEPT = {
    "title": "Circumference gives you the radius first",
    "body": "C = 2πr, so r = C / 2π. Every circle question that starts from the "
    "circumference needs this step before anything else.",
    "section": "math",
}


async def _concept(client, **overrides):
    response = await client.post("/concepts", json={**CONCEPT, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


async def _question(client, payload=MATH_MISTAKE):
    return (await client.post("/mistakes", json=payload)).json()["id"]


async def test_a_concept_can_be_written_down(client):
    concept = await _concept(client)

    assert concept["title"] == CONCEPT["title"]
    assert concept["body"].startswith("C = 2πr")
    assert concept["section"] == "math"
    assert concept["question_count"] == 0


async def test_a_concept_needs_only_a_title(client):
    concept = await _concept(client, body=None, section=None)

    assert concept["body"] is None
    assert concept["section"] is None


async def test_a_blank_title_is_rejected(client):
    assert (await client.post("/concepts", json={"title": "   "})).status_code == 422


async def test_a_question_is_tagged_after_it_was_created(client):
    """The point of the feature: tag an existing question, not one being written."""
    mistake_id = await _question(client)
    concept = await _concept(client)

    tagged = (await client.post(f"/concepts/{concept['id']}/questions/{mistake_id}")).json()

    assert [m["id"] for m in tagged["mistakes"]] == [mistake_id]
    assert tagged["question_count"] == 1

    # And the question knows about it, so the tag is visible from either side.
    mistake = (await client.get(f"/mistakes/{mistake_id}")).json()
    assert [c["title"] for c in mistake["concepts"]] == [CONCEPT["title"]]


async def test_tagging_the_same_question_twice_is_not_an_error(client):
    mistake_id = await _question(client)
    concept = await _concept(client)

    await client.post(f"/concepts/{concept['id']}/questions/{mistake_id}")
    again = await client.post(f"/concepts/{concept['id']}/questions/{mistake_id}")

    assert again.status_code == 200
    assert again.json()["question_count"] == 1


async def test_one_question_can_sit_under_several_concepts(client):
    mistake_id = await _question(client)
    first = await _concept(client, title="Circumference gives the radius")
    second = await _concept(client, title="Read the units before answering")

    await client.post(f"/concepts/{first['id']}/questions/{mistake_id}")
    await client.post(f"/concepts/{second['id']}/questions/{mistake_id}")

    mistake = (await client.get(f"/mistakes/{mistake_id}")).json()
    assert sorted(c["title"] for c in mistake["concepts"]) == [
        "Circumference gives the radius",
        "Read the units before answering",
    ]


async def test_a_concept_collects_many_questions(client):
    concept = await _concept(client)
    first = await _question(client)
    second = await _question(client, VERBAL_MISTAKE)

    await client.post(f"/concepts/{concept['id']}/questions/{first}")
    await client.post(f"/concepts/{concept['id']}/questions/{second}")

    detail = (await client.get(f"/concepts/{concept['id']}")).json()
    assert {m["id"] for m in detail["mistakes"]} == {first, second}
    assert detail["question_count"] == 2


async def test_untagging_leaves_the_question_alone(client):
    mistake_id = await _question(client)
    concept = await _concept(client)
    await client.post(f"/concepts/{concept['id']}/questions/{mistake_id}")

    after = (await client.delete(f"/concepts/{concept['id']}/questions/{mistake_id}")).json()

    assert after["mistakes"] == []
    # The question itself, and its ladder, survive being untagged.
    mistake = (await client.get(f"/mistakes/{mistake_id}")).json()
    assert mistake["concepts"] == []
    assert len(mistake["reviews"]) == 5


async def test_deleting_a_concept_does_not_delete_its_questions(client):
    mistake_id = await _question(client)
    concept = await _concept(client)
    await client.post(f"/concepts/{concept['id']}/questions/{mistake_id}")

    assert (await client.delete(f"/concepts/{concept['id']}")).status_code == 204

    assert (await client.get(f"/concepts/{concept['id']}")).status_code == 404
    assert (await client.get(f"/mistakes/{mistake_id}")).status_code == 200
    assert (await client.get(f"/mistakes/{mistake_id}")).json()["concepts"] == []


async def test_deleting_a_question_removes_it_from_its_concepts(client):
    mistake_id = await _question(client)
    concept = await _concept(client)
    await client.post(f"/concepts/{concept['id']}/questions/{mistake_id}")

    assert (await client.delete(f"/mistakes/{mistake_id}")).status_code == 204

    detail = (await client.get(f"/concepts/{concept['id']}")).json()
    assert detail["mistakes"] == []
    assert detail["question_count"] == 0


async def test_a_concept_can_be_rewritten(client):
    concept = await _concept(client)

    updated = (
        await client.patch(
            f"/concepts/{concept['id']}",
            json={"title": "Radius first, always", "body": "Shorter.", "section": "math"},
        )
    ).json()

    assert updated["title"] == "Radius first, always"
    assert updated["body"] == "Shorter."
    assert updated["updated_at"] is not None


async def test_concepts_are_listed_with_the_busiest_first(client):
    quiet = await _concept(client, title="Rarely used")
    busy = await _concept(client, title="Comes up constantly")
    for _ in range(2):
        await client.post(f"/concepts/{busy['id']}/questions/{await _question(client)}")

    listed = (await client.get("/concepts")).json()

    assert [c["id"] for c in listed] == [busy["id"], quiet["id"]]
    assert listed[0]["question_count"] == 2


async def test_concepts_belong_to_one_student(client):
    concept = await _concept(client)
    other = {"X-User-Id": "someone-else"}

    assert (await client.get("/concepts", headers=other)).json() == []
    assert (await client.get(f"/concepts/{concept['id']}", headers=other)).status_code == 404
    assert (
        await client.patch(f"/concepts/{concept['id']}", json={"title": "x"}, headers=other)
    ).status_code == 404


async def test_you_cannot_tag_someone_elses_question(client):
    mistake_id = await _question(client)
    concept = await _concept(client)

    response = await client.post(
        f"/concepts/{concept['id']}/questions/{mistake_id}",
        headers={"X-User-Id": "someone-else"},
    )

    assert response.status_code == 404


async def test_the_bank_can_be_filtered_to_one_concept(client):
    tagged = await _question(client)
    await _question(client, VERBAL_MISTAKE)
    concept = await _concept(client)
    await client.post(f"/concepts/{concept['id']}/questions/{tagged}")

    found = (await client.post("/mistakes/search", json={"concept_ids": [concept["id"]]})).json()

    assert [m["id"] for m in found] == [tagged]


async def test_a_concept_filter_narrows_alongside_the_others(client):
    both = await _question(client)
    concept_only = await _question(client)
    concept = await _concept(client)
    await client.post(f"/concepts/{concept['id']}/questions/{both}")
    await client.post(f"/concepts/{concept['id']}/questions/{concept_only}")
    await client.patch(f"/mistakes/{both}", json={"urgency": "fundamental"})
    await client.patch(f"/mistakes/{concept_only}", json={"urgency": "important"})

    found = (
        await client.post(
            "/mistakes/search",
            json={"concept_ids": [concept["id"]], "urgency": ["fundamental"]},
        )
    ).json()

    assert [m["id"] for m in found] == [both]


async def test_stats_counts_the_questions_under_each_concept(client):
    concept = await _concept(client)
    empty = await _concept(client, title="Nothing tagged yet")
    await client.post(f"/concepts/{concept['id']}/questions/{await _question(client)}")

    stats = (await client.get("/stats")).json()

    assert {"key": CONCEPT["title"], "count": 1} in stats["by_concept"]
    assert {"key": empty["title"], "count": 0} in stats["by_concept"]

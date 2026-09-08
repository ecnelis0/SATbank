"""Text search. Every one of these returned nothing before it was rewritten."""

from __future__ import annotations

import pytest

MATH = {
    "section": "math",
    "source": "Bluebook Practice Test 4, Q17",
    "question_text": "A circle has a circumference of 12π. What is its area?",
    "your_answer": "12π",
    "correct_answer": "36π",
    "student_note": "Forgot to halve the diameter.",
}
VERBAL = {
    "section": "reading_writing",
    "source": "Khan Academy drill",
    "question_text": "Which choice provides the best evidence for the previous answer?",
    "your_answer": "Lines 4-6",
    "correct_answer": "Lines 20-22",
}


async def _log(client, payload, **overrides):
    mistake_id = (await client.post("/mistakes", json=payload)).json()["id"]
    if overrides:
        assert (await client.patch(f"/mistakes/{mistake_id}", json=overrides)).status_code == 200
    return mistake_id


async def _search(client, term: str) -> list[str]:
    response = await client.get("/mistakes", params={"q": term})
    return [m["id"] for m in response.json()]


async def test_a_word_in_the_question_still_matches(client):
    circle = await _log(client, MATH)
    await _log(client, VERBAL)

    assert await _search(client, "circumference") == [circle]


@pytest.mark.parametrize("term", ["circle", "Circle", "CIRCLE", "cIrClE"])
async def test_search_ignores_case(client, term):
    circle = await _log(client, MATH)

    assert await _search(client, term) == [circle]


async def test_you_can_search_by_where_the_question_came_from(client):
    """ "Bluebook" and "Khan" found nothing at all before."""
    bluebook = await _log(client, MATH)
    khan = await _log(client, VERBAL)

    assert await _search(client, "Bluebook") == [bluebook]
    assert await _search(client, "Khan") == [khan]


async def test_you_can_search_by_an_answer(client):
    circle = await _log(client, MATH)
    await _log(client, VERBAL)

    assert await _search(client, "36") == [circle]
    assert await _search(client, "Lines 20-22") != [circle]


async def test_you_can_search_by_your_own_note(client):
    circle = await _log(client, MATH)
    await _log(client, VERBAL)

    assert await _search(client, "diameter") == [circle]


async def test_you_can_search_by_topic(client):
    circle = await _log(client, MATH, topic="circles and arcs")
    await _log(client, VERBAL, topic="command of evidence")

    assert await _search(client, "arcs") == [circle]


async def test_words_may_appear_in_any_order_and_in_different_fields(client):
    """The big one: a single LIKE '%area circle%' can never match this."""
    circle = await _log(client, MATH)
    await _log(client, VERBAL)

    assert await _search(client, "area circle") == [circle]
    assert await _search(client, "circle area") == [circle]
    # One word from the question, one from the source.
    assert await _search(client, "Bluebook circumference") == [circle]


async def test_every_word_has_to_match_not_just_one(client):
    await _log(client, MATH)
    await _log(client, VERBAL)

    # "circle" matches the first, "evidence" the second, so neither satisfies both.
    assert await _search(client, "circle evidence") == []


async def test_extra_spaces_do_not_break_a_search(client):
    circle = await _log(client, MATH)

    assert await _search(client, "  area   circle  ") == [circle]


async def test_a_blank_search_returns_everything(client):
    await _log(client, MATH)
    await _log(client, VERBAL)

    assert len(await _search(client, "   ")) == 2


async def test_the_bank_search_and_the_assistant_agree(client):
    """Same matcher behind both, so a search means one thing wherever it is typed."""
    circle = await _log(client, MATH)
    await _log(client, VERBAL)

    from_bank = await _search(client, "area circle")
    from_search = [
        m["id"]
        for m in (await client.post("/mistakes/search", json={"text": "area circle"})).json()
    ]

    assert from_bank == from_search == [circle]


async def test_search_still_only_sees_your_own_bank(client):
    await _log(client, MATH)

    response = await client.get(
        "/mistakes", params={"q": "circle"}, headers={"X-User-Id": "someone-else"}
    )

    assert response.json() == []

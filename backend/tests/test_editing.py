"""Logging by hand, asking for the debrief later, and editing anything at all."""

from __future__ import annotations

from tests.conftest import MATH_MISTAKE


async def test_a_question_can_be_logged_without_asking_the_ai(client):
    response = await client.post("/mistakes", params={"analyze": "false"}, json=MATH_MISTAKE)
    assert response.status_code == 201
    body = response.json()

    assert body["analysis_status"] == "not_requested"
    assert body["why_wrong"] is None
    # Not asking the AI must not cost the student the review schedule.
    assert len(body["reviews"]) == 5

    # And nothing runs in the background behind their back.
    later = (await client.get(f"/mistakes/{body['id']}")).json()
    assert later["analysis_status"] == "not_requested"


async def test_the_ai_can_be_asked_for_a_debrief_afterwards(client):
    mistake_id = (
        await client.post("/mistakes", params={"analyze": "false"}, json=MATH_MISTAKE)
    ).json()["id"]

    analysed = (await client.post(f"/mistakes/{mistake_id}/analyze")).json()

    assert analysed["analysis_status"] == "ready"
    assert analysed["analyzed_by"] == "stub"
    assert analysed["why_wrong"]
    assert analysed["error_type"]


async def test_any_field_of_the_question_can_be_edited(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    updated = (
        await client.patch(
            f"/mistakes/{mistake_id}",
            json={
                "question_text": "If 3x + 7 = 22, solve for x.",
                "choices": ["3", "5"],
                "your_answer": "3",
                "correct_answer": "5",
                "source": "Bluebook Practice Test 4, Q18",
                "student_note": "Actually I misread the sign.",
                "section": "reading_writing",
            },
        )
    ).json()

    assert updated["question_text"] == "If 3x + 7 = 22, solve for x."
    assert updated["choices"] == ["3", "5"]
    assert updated["your_answer"] == "3"
    assert updated["source"] == "Bluebook Practice Test 4, Q18"
    assert updated["section"] == "reading_writing"


async def test_editing_one_field_leaves_the_others_alone(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    updated = (
        await client.patch(f"/mistakes/{mistake_id}", json={"student_note": "new note"})
    ).json()

    assert updated["student_note"] == "new note"
    assert updated["question_text"] == MATH_MISTAKE["question_text"]
    assert updated["your_answer"] == MATH_MISTAKE["your_answer"]


async def test_the_ais_own_analysis_can_be_rewritten_by_hand(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    updated = (
        await client.patch(
            f"/mistakes/{mistake_id}",
            json={
                "error_type": "misread_question",
                "topic": "linear equations",
                "difficulty": "hard",
                "why_wrong": "I read 22 as 2.",
                "correct_reasoning": "Subtract 7, divide by 3.",
                "takeaway": "Read the constant twice.",
                "trap": "22 and 2 look alike in the margin.",
                "tags": ["algebra", "careless"],
            },
        )
    ).json()

    assert updated["error_type"] == "misread_question"
    assert updated["takeaway"] == "Read the constant twice."
    assert updated["tags"] == ["algebra", "careless"]
    assert updated["analysis_edited_at"] is not None


async def test_a_hand_written_analysis_counts_as_an_analysis(client):
    """Filling it in yourself should file the question in a slot like any other."""
    mistake_id = (
        await client.post("/mistakes", params={"analyze": "false"}, json=MATH_MISTAKE)
    ).json()["id"]

    updated = (
        await client.patch(
            f"/mistakes/{mistake_id}",
            json={"error_type": "time_pressure_guess", "why_wrong": "Ran out of clock."},
        )
    ).json()

    assert updated["analysis_status"] == "ready"
    assert updated["analyzed_by"] == "you"

    by_slot = (await client.get("/mistakes", params={"error_type": "time_pressure_guess"})).json()
    assert [m["id"] for m in by_slot] == [mistake_id]

    stats = (await client.get("/stats")).json()
    assert {"key": "time_pressure_guess", "count": 1} in stats["by_error_type"]


async def test_editing_the_question_does_not_mark_the_analysis_as_edited(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    updated = (
        await client.patch(f"/mistakes/{mistake_id}", json={"question_text": "reworded"})
    ).json()

    assert updated["analysis_edited_at"] is None


async def test_re_analysing_refuses_to_silently_discard_your_edits(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await client.patch(f"/mistakes/{mistake_id}", json={"takeaway": "Mine, not the AI's."})

    refused = await client.post(f"/mistakes/{mistake_id}/analyze")
    assert refused.status_code == 409

    kept = (await client.get(f"/mistakes/{mistake_id}")).json()
    assert kept["takeaway"] == "Mine, not the AI's."


async def test_forcing_a_re_analysis_replaces_the_edit_and_clears_the_marker(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await client.patch(f"/mistakes/{mistake_id}", json={"takeaway": "Mine, not the AI's."})

    forced = (await client.post(f"/mistakes/{mistake_id}/analyze", params={"force": "true"})).json()

    assert forced["takeaway"] != "Mine, not the AI's."
    assert forced["analysis_edited_at"] is None
    assert forced["analyzed_by"] == "stub"


async def test_an_edit_cannot_blank_out_a_required_field(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    response = await client.patch(f"/mistakes/{mistake_id}", json={"question_text": "   "})

    assert response.status_code == 422


async def test_you_cannot_edit_another_students_question(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    response = await client.patch(
        f"/mistakes/{mistake_id}",
        json={"takeaway": "not yours"},
        headers={"X-User-Id": "someone-else"},
    )

    assert response.status_code == 404

"""Videos: a link in, concepts out, filed under a tab you named."""

from __future__ import annotations

import pytest

from app.models import subject_slug
from app.videos import (
    Snippet,
    VideoUnreadable,
    _assemble,
    at_second,
    clip,
    from_pasted,
    youtube_id,
)
from tests.conftest import MATH_MISTAKE

TRANSCRIPT = "\n".join(
    [
        "[0s] Today we are looking at semicolons and when you are allowed to use one.",
        "[45s] A semicolon joins two independent clauses, each of which could stand alone.",
        "[120s] Colons are different: what follows a colon explains what came before it.",
    ]
)


async def _add(client, **body):
    payload = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", **body}
    payload.setdefault("transcript", TRANSCRIPT)
    response = await client.post("/videos", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# --- reading the link ---------------------------------------------------------


def test_every_shape_of_youtube_link_is_understood():
    expected = "dQw4w9WgXcQ"
    for url in (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=42",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc",
        "youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    ):
        assert youtube_id(url) == expected, url


def test_a_link_that_is_not_a_video_is_refused():
    """A playlist id sailing through as a video id would fail much later, with a
    message about missing captions rather than about the link."""
    for url in ("https://vimeo.com/123", "https://www.youtube.com/playlist?list=PLabc", ""):
        with pytest.raises(VideoUnreadable):
            youtube_id(url)


def test_a_timestamp_link_opens_at_the_moment():
    assert at_second("abc12345678", 125).endswith("&t=125s")
    assert "t=" not in at_second("abc12345678", None)


def test_the_transcript_is_stamped_often_enough_to_be_useful_but_not_per_cue():
    """Captions arrive every two or three seconds; a stamp on each buries the words."""
    snippets = [Snippet(start=float(i * 3), text="word " * 12) for i in range(10)]
    lines = _assemble(snippets).splitlines()
    assert 1 < len(lines) < 10
    assert lines[0].startswith("[0s]")


def test_a_long_transcript_is_cut_rather_than_failing():
    text, truncated = clip("x" * 200_000)
    assert truncated and len(text) < 200_000
    assert clip("short")[1] is False


def test_an_empty_pasted_transcript_is_refused():
    with pytest.raises(VideoUnreadable):
        from_pasted("   ")


def test_subject_tabs_are_one_tab_however_they_are_typed():
    assert subject_slug("Grammar") == subject_slug(" grammar ") == "grammar"
    assert subject_slug("") is None and subject_slug(None) is None


# --- the pipeline -------------------------------------------------------------


async def test_a_video_becomes_concepts(client):
    video = await _add(client, subject="Grammar", directions="Focus on the rules only.")
    assert video["status"] == "pending"

    # BackgroundTasks run before the response is handed back by the test client.
    detail = (await client.get(f"/videos/{video['id']}")).json()
    assert detail["status"] == "ready", detail["error"]
    assert detail["concepts"]
    assert detail["summary"]


async def test_concepts_carry_the_moment_they_are_explained(client):
    video = await _add(client)
    detail = (await client.get(f"/videos/{video['id']}")).json()

    first = detail["concepts"][0]
    assert first["start_seconds"] == 0
    # The whole point of the stamp: a link that opens the video there.
    assert first["watch_url"].endswith("&t=0s")


async def test_the_tab_is_remembered_and_reaches_the_concepts(client):
    video = await _add(client, subject="Grammar")
    detail = (await client.get(f"/videos/{video['id']}")).json()

    assert detail["subject"] == "grammar"
    assert all(c["subject"] == "grammar" for c in detail["concepts"])


async def test_the_directions_are_kept_for_the_next_read(client):
    """Re-reading should start from the instruction that was given, not from
    nothing."""
    video = await _add(client, directions="Only the comma rules.")
    assert (await client.get(f"/videos/{video['id']}")).json()["directions"] == (
        "Only the comma rules."
    )


async def test_subjects_are_listed_as_tabs(client):
    await _add(client, subject="Grammar")
    await _add(client, subject="Grammar")
    await _add(client, subject="Reading")
    await _add(client)

    tabs = (await client.get("/videos/subjects")).json()
    assert [t["subject"] for t in tabs] == ["grammar", "reading", None]
    assert tabs[0]["video_count"] == 2
    assert tabs[0]["concept_count"] > 0


async def test_videos_can_be_filtered_to_one_tab(client):
    await _add(client, subject="Grammar")
    await _add(client, subject="Reading")

    grammar = (await client.get("/videos", params={"subject": "grammar"})).json()
    assert len(grammar) == 1
    assert grammar[0]["subject"] == "grammar"


async def test_a_video_with_no_captions_says_so_and_does_not_invent_concepts(
    client, monkeypatch
):
    def refuse(video_id, languages=("en",)):
        raise VideoUnreadable("That video has no English captions.")

    monkeypatch.setattr("app.videos.fetch_transcript", refuse)

    response = await client.post(
        "/videos", json={"url": "https://youtu.be/dQw4w9WgXcQ", "subject": "grammar"}
    )
    video = response.json()
    detail = (await client.get(f"/videos/{video['id']}")).json()

    assert detail["status"] == "failed"
    assert "captions" in detail["error"]
    assert detail["concepts"] == []


async def test_a_bad_link_is_refused_before_anything_is_stored(client):
    response = await client.post("/videos", json={"url": "https://vimeo.com/123"})
    assert response.status_code == 422
    assert (await client.get("/videos")).json() == []


# --- linking questions, which is the point ------------------------------------


async def test_questions_tagged_to_a_video_concept_show_up_on_the_video(client):
    """"I could link more SAT problems under those grammar videos" — from the
    video's side, so it reads as what you have got wrong on what it teaches."""
    video = await _add(client, subject="Grammar")
    detail = (await client.get(f"/videos/{video['id']}")).json()
    concept_id = detail["concepts"][0]["id"]

    logged = (await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})).json()
    await client.post(f"/concepts/{concept_id}/questions/{logged['id']}")

    again = (await client.get(f"/videos/{video['id']}")).json()
    assert [m["id"] for m in again["mistakes"]] == [logged["id"]]
    assert again["concepts"][0]["question_count"] == 1


async def test_rereading_keeps_a_concept_that_has_questions_on_it(client):
    """A re-read must not silently untag work the student did by hand."""
    video = await _add(client, subject="Grammar")
    detail = (await client.get(f"/videos/{video['id']}")).json()
    concept_id = detail["concepts"][0]["id"]

    logged = (await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})).json()
    await client.post(f"/concepts/{concept_id}/questions/{logged['id']}")

    await client.post(f"/videos/{video['id']}/reread")

    after = (await client.get(f"/videos/{video['id']}")).json()
    assert concept_id in [c["id"] for c in after["concepts"]]
    assert (await client.get(f"/mistakes/{logged['id']}")).json()["concepts"]


async def test_deleting_a_video_keeps_concepts_that_carry_questions(client):
    video = await _add(client, subject="Grammar")
    detail = (await client.get(f"/videos/{video['id']}")).json()
    concept_id = detail["concepts"][0]["id"]

    logged = (await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})).json()
    await client.post(f"/concepts/{concept_id}/questions/{logged['id']}")

    assert (await client.delete(f"/videos/{video['id']}")).status_code == 204

    # The concept survives, detached from the video it came from.
    assert (await client.get(f"/concepts/{concept_id}")).status_code == 200
    assert (await client.get(f"/mistakes/{logged['id']}")).json()["concepts"]


async def test_deleting_a_video_takes_its_untouched_concepts_with_it(client):
    video = await _add(client, subject="Grammar")
    detail = (await client.get(f"/videos/{video['id']}")).json()
    orphan = detail["concepts"][0]["id"]

    await client.delete(f"/videos/{video['id']}")
    assert (await client.get(f"/concepts/{orphan}")).status_code == 404


async def test_moving_a_video_to_another_tab_moves_what_it_taught(client):
    video = await _add(client, subject="Grammar")
    await client.patch(f"/videos/{video['id']}", json={"subject": "Reading"})

    detail = (await client.get(f"/videos/{video['id']}")).json()
    assert detail["subject"] == "reading"
    assert all(c["subject"] == "reading" for c in detail["concepts"])


async def test_videos_never_cross_between_students(client):
    await _add(client, subject="Grammar")
    assert (await client.get("/videos", headers={"X-User-Id": "someone-else"})).json() == []

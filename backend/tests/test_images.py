"""Uploading pictures of a question: what is accepted, and what is refused."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from tests.conftest import MATH_MISTAKE


def png(size=(60, 40), colour="red") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, "PNG")
    return buffer.getvalue()


def jpeg(size=(20, 20)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "blue").save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    """A fresh upload directory per test, so nothing leaks between them."""
    from app import config
    from app.analysis import get_analyzer

    directory = tmp_path / "uploads"
    monkeypatch.setenv("UPLOAD_ROOT", str(directory))
    config.get_settings.cache_clear()
    get_analyzer.cache_clear()
    yield directory
    config.get_settings.cache_clear()
    get_analyzer.cache_clear()


async def _question(client) -> str:
    return (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]


async def _upload(client, mistake_id, data, name="shot.png", content_type="image/png"):
    return await client.post(
        f"/mistakes/{mistake_id}/images",
        files={"file": (name, data, content_type)},
    )


async def test_a_picture_can_be_attached_to_a_question(client, uploads):
    mistake_id = await _question(client)

    response = await _upload(client, mistake_id, png())

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["images"]) == 1
    image = body["images"][0]
    assert image["content_type"] == "image/png"
    assert (image["width"], image["height"]) == (60, 40)
    assert image["url"].startswith("/uploads/")
    # And the bytes really are on disk under the name the response advertises.
    assert (uploads / Path(image["url"]).name).exists()


async def test_a_question_carries_its_pictures_wherever_it_is_read(client, uploads):
    mistake_id = await _question(client)
    await _upload(client, mistake_id, png())

    assert len((await client.get(f"/mistakes/{mistake_id}")).json()["images"]) == 1
    assert len((await client.get("/mistakes")).json()[0]["images"]) == 1
    assert len((await client.post("/mistakes/search", json={})).json()[0]["images"]) == 1


async def test_several_pictures_keep_the_order_they_were_added(client, uploads):
    mistake_id = await _question(client)
    await _upload(client, mistake_id, png(size=(10, 10)), name="one.png")
    await _upload(client, mistake_id, png(size=(20, 20)), name="two.png")
    body = (await _upload(client, mistake_id, png(size=(30, 30)), name="three.png")).json()

    assert [image["width"] for image in body["images"]] == [10, 20, 30]
    assert [image["position"] for image in body["images"]] == [0, 1, 2]


async def test_jpegs_are_fine_too(client, uploads):
    mistake_id = await _question(client)

    body = (await _upload(client, mistake_id, jpeg(), name="photo.jpg")).json()

    assert body["images"][0]["content_type"] == "image/jpeg"
    assert body["images"][0]["url"].endswith(".jpg")


async def test_the_stored_name_is_generated_not_taken_from_the_upload(client, uploads):
    """A client-supplied filename is how you get written outside the upload directory."""
    mistake_id = await _question(client)

    body = (await _upload(client, mistake_id, png(), name="../../../etc/passwd.png")).json()

    stored = Path(body["images"][0]["url"]).name
    assert "/" not in stored and ".." not in stored
    assert stored != "passwd.png"
    # Nothing was written outside the upload directory.
    assert [path.name for path in uploads.iterdir()] == [stored]


async def test_a_file_that_is_not_an_image_is_refused(client, uploads):
    mistake_id = await _question(client)

    response = await _upload(client, mistake_id, b"#!/bin/sh\nrm -rf /\n", name="evil.png")

    assert response.status_code == 422
    assert "not an image" in response.json()["detail"]
    assert list(uploads.iterdir()) == [] if uploads.exists() else True


async def test_the_declared_content_type_is_not_believed(client, uploads):
    """The type comes from decoding the bytes, not from what the client claimed."""
    mistake_id = await _question(client)

    body = (
        await _upload(client, mistake_id, jpeg(), name="lying.png", content_type="image/png")
    ).json()

    assert body["images"][0]["content_type"] == "image/jpeg"


async def test_an_empty_file_is_refused(client, uploads):
    mistake_id = await _question(client)

    response = await _upload(client, mistake_id, b"")

    assert response.status_code == 422


async def test_an_oversized_image_is_refused(client, uploads, monkeypatch):
    from app import images

    monkeypatch.setattr(images, "MAX_BYTES", 500)
    mistake_id = await _question(client)

    response = await _upload(client, mistake_id, png(size=(400, 400), colour="white"))

    assert response.status_code == 422
    assert "limit" in response.json()["detail"]


async def test_deleting_a_picture_removes_the_row_and_the_file(client, uploads):
    mistake_id = await _question(client)
    body = (await _upload(client, mistake_id, png())).json()
    image = body["images"][0]
    path = uploads / Path(image["url"]).name
    assert path.exists()

    after = (await client.delete(f"/mistakes/{mistake_id}/images/{image['id']}")).json()

    assert after["images"] == []
    assert not path.exists()


async def test_deleting_a_question_takes_its_pictures_with_it(client, uploads):
    mistake_id = await _question(client)
    first = (await _upload(client, mistake_id, png(), name="a.png")).json()["images"][0]
    second = (await _upload(client, mistake_id, png(), name="b.png")).json()["images"][1]
    paths = [uploads / Path(image["url"]).name for image in (first, second)]
    assert all(path.exists() for path in paths)

    assert (await client.delete(f"/mistakes/{mistake_id}")).status_code == 204

    assert (await client.get(f"/mistakes/{mistake_id}")).status_code == 404
    # The rows cascade; the bytes have to be removed on purpose, or every deleted
    # question leaves its pictures on disk forever.
    assert not any(path.exists() for path in paths)


async def test_you_cannot_attach_a_picture_to_someone_elses_question(client, uploads):
    mistake_id = await _question(client)

    response = await client.post(
        f"/mistakes/{mistake_id}/images",
        files={"file": ("shot.png", png(), "image/png")},
        headers={"X-User-Id": "someone-else"},
    )

    assert response.status_code == 404
    # Ownership is checked before anything is written, so the disk stays clean.
    assert not uploads.exists() or list(uploads.iterdir()) == []


async def test_you_cannot_delete_someone_elses_picture(client, uploads):
    mistake_id = await _question(client)
    image = (await _upload(client, mistake_id, png())).json()["images"][0]

    response = await client.delete(
        f"/mistakes/{mistake_id}/images/{image['id']}",
        headers={"X-User-Id": "someone-else"},
    )

    assert response.status_code == 404
    assert (uploads / Path(image["url"]).name).exists()


async def test_deleting_an_image_that_is_not_there(client, uploads):
    mistake_id = await _question(client)

    response = await client.delete(f"/mistakes/{mistake_id}/images/deadbeef")

    assert response.status_code == 404

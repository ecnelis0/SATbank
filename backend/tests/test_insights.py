"""The whole-bank analysis: counted by the database, written by the model, kept."""

from __future__ import annotations

from app.analysis import StubAnalyzer
from app.analysis.base import AnalysisFailed, CoachPoint, CoachReport
from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE


class Recording(StubAnalyzer):
    name = "recording"

    def __init__(self, cite: list[str] | None = None) -> None:
        self.handed: list[tuple[str | None, str]] = []
        self.cite = cite or []

    async def coach(self, focus: str | None, digest: str) -> CoachReport:
        self.handed.append((focus, digest))
        return CoachReport(
            answer="Mostly arithmetic." if focus else "",
            overview="You rush the last step.",
            doing_well=[CoachPoint(title="Honest notes", detail="You say what happened.")],
            going_wrong=[
                CoachPoint(title="Rushing", detail="Twice.", question_ids=self.cite)
            ],
            next_steps=["Check the final step."],
        )


class Broken(StubAnalyzer):
    async def coach(self, focus: str | None, digest: str) -> CoachReport:
        raise AnalysisFailed("out of credit")


async def _log(client, body=MATH_MISTAKE) -> dict:
    response = await client.post("/mistakes", json=body)
    assert response.status_code == 201
    return response.json()


async def test_the_model_reads_everything_the_student_has_said(client, monkeypatch):
    logged = await _log(client)
    await client.post(
        f"/mistakes/{logged['id']}/debrief", json={"message": "I always rush the end."}
    )
    recording = Recording()
    monkeypatch.setattr("app.routers.insights.get_analyzer", lambda: recording)

    response = await client.post("/insights", json={"focus": "What do I keep doing?"})
    assert response.status_code == 201
    focus, digest = recording.handed[-1]
    assert focus == "What do I keep doing?"
    assert f"id={logged['id']}" in digest
    assert MATH_MISTAKE["student_note"] in digest
    assert "they told the debrief: I always rush the end." in digest
    assert "you_put='7'" in digest


async def test_the_counts_come_from_the_database_not_the_model(client, monkeypatch):
    first = await _log(client)
    await _log(client, VERBAL_MISTAKE)
    due = (await client.get("/reviews/upcoming")).json()
    review = next(d["review"] for d in due if d["mistake"]["id"] == first["id"])
    await client.post(f"/reviews/{review['id']}/complete", json={"outcome": "correct"})
    monkeypatch.setattr("app.routers.insights.get_analyzer", lambda: Recording())

    body = (await client.post("/insights", json={})).json()
    stats = body["stats"]
    assert stats["questions"] == 2
    assert stats["reviews_right"] == 1
    assert stats["reviews_wrong"] == 0
    assert {c["label"]: c["count"] for c in stats["by_section"]} == {
        "Math": 1,
        "Reading & Writing": 1,
    }
    assert sum(c["count"] for c in stats["by_reason"]) == 2
    assert body["question_count"] == 2


async def test_an_id_the_model_invented_is_dropped(client, monkeypatch):
    logged = await _log(client)
    monkeypatch.setattr(
        "app.routers.insights.get_analyzer",
        lambda: Recording(cite=[logged["id"], "not-a-real-id", logged["id"]]),
    )
    body = (await client.post("/insights", json={})).json()
    assert body["report"]["going_wrong"][0]["question_ids"] == [logged["id"]]


async def test_analyses_are_kept_and_can_be_read_again(client, monkeypatch):
    await _log(client)
    monkeypatch.setattr("app.routers.insights.get_analyzer", lambda: Recording())
    first = (await client.post("/insights", json={"focus": "Math?"})).json()
    second = (await client.post("/insights", json={})).json()

    listed = (await client.get("/insights")).json()
    assert [i["id"] for i in listed] == [second["id"], first["id"]]
    again = (await client.get(f"/insights/{first['id']}")).json()
    assert again["focus"] == "Math?"
    assert again["report"]["answer"] == "Mostly arithmetic."
    assert again["analyzer"] == "recording"

    assert (await client.delete(f"/insights/{first['id']}")).status_code == 204
    assert [i["id"] for i in (await client.get("/insights")).json()] == [second["id"]]


async def test_a_failed_model_stores_nothing(client, monkeypatch):
    """An empty analysis in the history would read as "the AI found nothing"."""
    await _log(client)
    monkeypatch.setattr("app.routers.insights.get_analyzer", lambda: Broken())
    response = await client.post("/insights", json={})
    assert response.status_code == 502
    assert "out of credit" in response.json()["detail"]
    assert (await client.get("/insights")).json() == []


async def test_an_empty_bank_says_so(client):
    response = await client.post("/insights", json={})
    assert response.status_code == 422


async def test_the_offline_reader_names_itself_and_cites_real_questions(client):
    logged = await _log(client)
    body = (await client.post("/insights", json={"focus": "anything"})).json()
    assert body["analyzer"] == "stub"
    assert "offline" in body["report"]["overview"]
    assert body["report"]["going_wrong"][0]["question_ids"] == [logged["id"]]


async def test_someone_elses_analysis_is_not_yours(client):
    await _log(client)
    made = (await client.post("/insights", json={})).json()
    other = {"X-User-Id": "someone-else"}
    assert (await client.get(f"/insights/{made['id']}", headers=other)).status_code == 404
    assert (await client.get("/insights", headers=other)).json() == []
    assert (await client.delete(f"/insights/{made['id']}", headers=other)).status_code == 404

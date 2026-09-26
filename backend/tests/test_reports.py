"""The period report: what it counts, what it concludes, and that the PDF is real."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.models import Mistake, ReviewEvent, ReviewOutcome, utcnow
from app.pdf import render_pdf
from app.report import Window, build_report
from app.routers.reports import resolve_window
from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE


async def _log(client, body, **params):
    response = await client.post("/mistakes", json=body, params={"analyze": False, **params})
    assert response.status_code == 201
    return response.json()


async def _backdate(session_factory, mistake_id: str, days: int) -> None:
    """Push a question into the past. The whole feature is about windows, so the
    tests have to be able to put rows on either side of one."""
    async with session_factory() as session:
        mistake = await session.get(Mistake, mistake_id)
        mistake.created_at = utcnow() - timedelta(days=days)
        await session.commit()


# --- the window ---------------------------------------------------------------


def test_named_periods_resolve_against_today():
    today = date(2026, 3, 15)
    window, title = resolve_window("month", None, None, today=today)
    assert window.since == date(2026, 2, 13)
    assert window.until == today
    assert title == "The past month"


def test_all_time_has_no_bounds():
    window, title = resolve_window("all", None, None, today=date(2026, 3, 15))
    assert window.since is None and window.until is None
    assert title == "Everything you have logged"


def test_explicit_dates_beat_a_named_period():
    """The assistant reading a real range out of the sentence is better than a
    round number of days, so the dates must not be thrown away."""
    window, _ = resolve_window(
        "month", date(2026, 1, 1), date(2026, 1, 31), today=date(2026, 3, 15)
    )
    assert (window.since, window.until) == (date(2026, 1, 1), date(2026, 1, 31))


def test_unknown_period_falls_back_to_a_month_not_to_everything():
    """A model that invents a period name must not silently widen the report to
    the whole bank — that is the one failure the student would not notice."""
    window, _ = resolve_window("fortnight", None, None, today=date(2026, 3, 15))
    assert window.since == date(2026, 2, 13)


def test_window_labels_read_as_english():
    span = Window(since=date(2026, 1, 5), until=date(2026, 2, 5))
    assert span.label == "5 Jan 2026 to 5 Feb 2026"
    assert Window(since=date(2026, 1, 5)).label == "since 5 Jan 2026"
    assert Window().label == "all time"


# --- what the report counts ---------------------------------------------------


async def test_the_window_excludes_what_falls_outside_it(client, session_factory):
    inside = await _log(client, MATH_MISTAKE)
    outside = await _log(client, VERBAL_MISTAKE)
    await _backdate(session_factory, outside["id"], days=90)

    async with session_factory() as session:
        report = await build_report(
            session, "local", Window(since=utcnow().date() - timedelta(days=30))
        )

    assert report.logged_count == 1
    assert [q.id for q in report.questions] == [inside["id"]]


async def test_every_question_carries_the_date_it_was_logged(client, session_factory):
    logged = await _log(client, MATH_MISTAKE)
    await _backdate(session_factory, logged["id"], days=3)

    async with session_factory() as session:
        report = await build_report(session, "local", Window())

    assert report.questions[0].logged_at.date() == (utcnow() - timedelta(days=3)).date()


async def test_concepts_carry_their_own_date_and_their_count_in_the_window(
    client, session_factory
):
    concept = (await client.post("/concepts", json={"title": "Dividing at the end"})).json()
    logged = await _log(client, MATH_MISTAKE)
    tagged = await client.post(f"/concepts/{concept['id']}/questions/{logged['id']}")
    assert tagged.status_code == 200

    async with session_factory() as session:
        report = await build_report(session, "local", Window())

    line = next(c for c in report.concepts if c.id == concept["id"])
    assert line.questions_in_window == 1
    assert line.questions_total == 1
    assert isinstance(line.created_at, datetime)


async def test_reviews_are_counted_by_when_they_were_answered(client, session_factory):
    """Revising an old question this month is this month's work. Counting reviews
    by the question's logged date instead would credit it to the wrong window."""
    logged = await _log(client, MATH_MISTAKE)
    await _backdate(session_factory, logged["id"], days=200)

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(ReviewEvent).where(ReviewEvent.mistake_id == logged["id"])
            )
        )
        rows[0].completed_at = utcnow()
        rows[0].outcome = ReviewOutcome.wrong
        await session.commit()

    async with session_factory() as session:
        report = await build_report(
            session, "local", Window(since=utcnow().date() - timedelta(days=30))
        )

    # The question itself is 200 days old and out of the window...
    assert report.logged_count == 0
    # ...but the review was answered today, so it belongs to this one.
    assert report.reviews_answered == 1
    assert report.reviews_wrong == 1


async def test_still_due_is_the_bank_now_not_the_window(client, session_factory):
    """A review due today must show even when the question is older than the
    window — hiding it would be the report actively misleading the student."""
    logged = await _log(client, MATH_MISTAKE)
    await _backdate(session_factory, logged["id"], days=300)
    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(ReviewEvent).where(ReviewEvent.mistake_id == logged["id"])
            )
        )
        rows[0].due_at = utcnow() - timedelta(hours=1)
        await session.commit()

    async with session_factory() as session:
        report = await build_report(
            session, "local", Window(since=utcnow().date() - timedelta(days=7))
        )

    assert report.logged_count == 0
    assert report.still_due >= 1


# --- what the report concludes ------------------------------------------------


async def test_focus_names_a_repeated_slot_and_stays_quiet_about_a_single_one(
    client, session_factory
):
    async with session_factory() as session:
        for index in range(3):
            body = dict(MATH_MISTAKE)
            body["question_text"] = f"Repeated slip {index}"
            await _log(client, body)
        # Two share a diagnosis, one is alone with its own.
        rows = list(await session.scalars(select(Mistake)))
        rows[0].error_type = "algebra_slip"
        rows[1].error_type = "algebra_slip"
        rows[2].error_type = "vocabulary_gap"
        await session.commit()

    async with session_factory() as session:
        report = await build_report(session, "local", Window())

    joined = " ".join(report.focus)
    assert "Algebra slip" in joined
    assert "Vocabulary gap" not in joined


async def test_focus_says_so_when_nothing_repeats(client, session_factory):
    """One question, already filed, with no repeated diagnosis: there is genuinely
    nothing to single out, and the report has to say that rather than pad."""
    concept = (await client.post("/concepts", json={"title": "Filed"})).json()
    logged = await _log(client, MATH_MISTAKE)
    await client.post(f"/concepts/{concept['id']}/questions/{logged['id']}")

    async with session_factory() as session:
        report = await build_report(session, "local", Window())
    assert "Nothing repeated" in " ".join(report.focus)


async def test_focus_chases_untagged_questions_even_when_nothing_repeats(
    client, session_factory
):
    """An untagged question is still something to do, so the quiet-window line
    must not crowd it out."""
    await _log(client, MATH_MISTAKE)
    async with session_factory() as session:
        report = await build_report(session, "local", Window())
    joined = " ".join(report.focus)
    assert "filed under no concept" in joined
    assert "Nothing repeated" not in joined


async def test_focus_is_stable_across_runs(client, session_factory):
    """A report that reorders itself between two generations of the same month is
    not a report. Equal counts have to break ties deterministically."""
    for index in range(4):
        body = dict(MATH_MISTAKE)
        body["question_text"] = f"Question {index}"
        await _log(client, body)

    async with session_factory() as session:
        first = await build_report(session, "local", Window())
        second = await build_report(session, "local", Window())
    assert first.focus == second.focus
    assert [q.id for q in first.questions] == [q.id for q in second.questions]


# --- the PDF ------------------------------------------------------------------


async def test_the_pdf_is_a_pdf_with_the_content_in_it(client, session_factory):
    await _log(client, MATH_MISTAKE)
    async with session_factory() as session:
        report = await build_report(session, "local", Window())

    pdf = render_pdf(report, title="The past month")

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    # A header and a stat row alone would clear a naive size check, so this is
    # about a real multi-section document having been laid out.
    assert len(pdf) > 4000


async def test_the_pdf_survives_markup_in_a_students_own_words(client, session_factory):
    """reportlab's paragraphs are mini-HTML. An unescaped < in a maths question is
    the difference between a report and a 500."""
    body = dict(MATH_MISTAKE)
    body["question_text"] = "If x < 5 & y > 2, which is true? <b>Pick one</b>"
    body["student_note"] = "I read <= as < again"
    await _log(client, body)

    async with session_factory() as session:
        report = await build_report(session, "local", Window())

    pdf = render_pdf(report)
    assert pdf.startswith(b"%PDF-")


async def test_an_empty_window_still_renders(client, session_factory):
    """The month you logged nothing is exactly when you might ask for the report."""
    async with session_factory() as session:
        window = Window(since=date(2020, 1, 1), until=date(2020, 2, 1))
        report = await build_report(session, "local", window)
    assert report.logged_count == 0
    assert render_pdf(report).startswith(b"%PDF-")


# --- the endpoints ------------------------------------------------------------


async def test_the_json_endpoint_reports_the_window(client):
    await _log(client, MATH_MISTAKE)
    response = await client.get("/reports", params={"period": "month"})
    assert response.status_code == 200
    body = response.json()
    assert body["logged_count"] == 1
    assert body["window"]["since"] is not None
    assert body["questions"][0]["logged_at"]


async def test_the_pdf_endpoint_serves_a_downloadable_file(client):
    await _log(client, MATH_MISTAKE)
    response = await client.get("/reports.pdf", params={"period": "month"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")


async def test_the_pdf_can_be_opened_inline(client):
    await _log(client, MATH_MISTAKE)
    response = await client.get("/reports.pdf", params={"period": "month", "download": False})
    assert "inline" in response.headers["content-disposition"]


async def test_a_report_never_crosses_between_students(client):
    await _log(client, MATH_MISTAKE)
    response = await client.get(
        "/reports", params={"period": "all"}, headers={"X-User-Id": "someone-else"}
    )
    assert response.json()["logged_count"] == 0


async def test_a_report_long_enough_to_break_across_pages_still_renders(client, session_factory):
    """The questions are wrapped so a heading is never stranded at a page foot and
    no question splits mid-answer. That wrapping is the part most likely to break
    the build, so it needs a report that actually overflows a page."""
    for index in range(12):
        body = dict(MATH_MISTAKE)
        body["question_text"] = f"Question {index}. " + ("A long stem. " * 40)
        body["student_note"] = "A note that also takes up room. " * 6
        await _log(client, body)

    async with session_factory() as session:
        report = await build_report(session, "local", Window())

    pdf = render_pdf(report, title="The past month")
    assert pdf.startswith(b"%PDF-")
    # More than one page actually got laid out.
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") >= 2

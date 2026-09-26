"""Period reports: the same numbers as JSON for the screen and as a PDF to keep."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Query, Response

from ..deps import SessionDep, UserDep
from ..pdf import render_pdf
from ..report import PeriodReport, Window, build_report

router = APIRouter(prefix="/reports", tags=["reports"])

# The windows the chat can name. Anything else comes through as explicit dates,
# so a phrase the model invents can never silently become "all time".
PERIODS: dict[str, int | None] = {
    "week": 7,
    "month": 30,
    "quarter": 90,
    "half_year": 182,
    "year": 365,
    "all": None,
}

PERIOD_TITLES: dict[str, str] = {
    "week": "The past week",
    "month": "The past month",
    "quarter": "The past 3 months",
    "half_year": "The past 6 months",
    "year": "The past year",
    "all": "Everything you have logged",
}


def resolve_window(
    period: str | None,
    since: date | None,
    until: date | None,
    today: date | None = None,
) -> tuple[Window, str]:
    """Turn either a named period or a pair of dates into a window and a title.

    Explicit dates win over a named period: if the assistant worked out a real
    range from the sentence, that reading is better than a round number of days.
    """
    today = today or datetime.now(UTC).date()
    if since or until:
        return Window(since=since, until=until), "Your report"
    days = PERIODS.get(period or "month", 30)
    title = PERIOD_TITLES.get(period or "month", "Your report")
    if days is None:
        return Window(), title
    return Window(since=today - timedelta(days=days), until=today), title


@router.get("", response_model=PeriodReport)
async def period_report(
    session: SessionDep,
    user_id: UserDep,
    period: str | None = Query(default=None, description=f"One of {', '.join(PERIODS)}."),
    since: date | None = None,
    until: date | None = None,
) -> PeriodReport:
    window, _ = resolve_window(period, since, until)
    return await build_report(session, user_id, window)


@router.get(".pdf", response_class=Response)
async def period_report_pdf(
    session: SessionDep,
    user_id: UserDep,
    period: str | None = None,
    since: date | None = None,
    until: date | None = None,
    download: bool = Query(default=True, description="False opens it in the tab instead."),
) -> Response:
    window, title = resolve_window(period, since, until)
    report = await build_report(session, user_id, window)
    pdf = render_pdf(report, title=title)

    stamp = report.generated_at.strftime("%Y-%m-%d")
    name = f"mistake-bank-{(period or 'report')}-{stamp}.pdf"
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            # RFC 5987, so a filename is never mangled and never injects a header.
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(name)}",
        },
    )

"""Logging a wrong question, and browsing the bank."""

from __future__ import annotations

import io
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..analysis import Turn, get_analyzer
from ..analysis.base import AnalysisFailed
from ..analysis.scan import ScanInput, ScanKind, ScannedQuestion, get_scanner
from ..config import get_settings
from ..deps import SessionDep, UserDep
from ..images import ALLOWED_FORMATS, MAX_BYTES
from ..images import delete as delete_file
from ..models import (
    AnalysisStatus,
    Concept,
    ErrorType,
    Mistake,
    Section,
    Urgency,
    blank_collections,
    mistake_options,
    utcnow,
)
from ..query import BankQuery, run_query, text_filter
from ..readiness import analyzer_ready
from ..review import build_ladder
from ..schemas import MistakeCreate, MistakeRead, MistakeUpdate
from ..services import analyze_in_background, analyze_mistake

router = APIRouter(prefix="/mistakes", tags=["mistakes"])

# A page of a practice test is a bigger PDF than a screenshot is a PNG, so the
# two limits differ. The read cap is the larger; the kind is checked after.
MAX_SCAN_PDF_BYTES = 32 * 1024 * 1024
MAX_SCAN_BYTES = MAX_SCAN_PDF_BYTES


def _sniff_scan(data: bytes) -> tuple[ScanKind, str, bytes]:
    """Decide what was uploaded from the bytes, never the filename or declared type.

    Returns the bytes back because HEIC is re-encoded on the way through: Claude
    reads PNG, JPEG, GIF and WebP, and an iPhone screenshot is none of those.
    """
    if not data:
        raise HTTPException(status_code=422, detail="That file is empty.")

    if data.startswith(b"%PDF"):
        if len(data) > MAX_SCAN_PDF_BYTES:
            raise HTTPException(status_code=422, detail="That PDF is over the 32MB limit.")
        return "pdf", "application/pdf", data

    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format
    except (UnidentifiedImageError, OSError, ValueError):
        image_format = None

    if image_format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=415,
            detail="That is not a picture we can read. Send a PNG, JPEG, WebP, HEIC or PDF.",
        )
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="That image is over the 10MB limit.")

    media_type = ALLOWED_FORMATS[image_format][0]
    if media_type == "image/heic":
        with Image.open(io.BytesIO(data)) as image:
            out = io.BytesIO()
            image.convert("RGB").save(out, format="JPEG", quality=90)
        return "image", "image/jpeg", out.getvalue()
    return "image", media_type, data



@router.post("", response_model=MistakeRead, status_code=201)
async def log_mistake(
    body: MistakeCreate,
    session: SessionDep,
    user_id: UserDep,
    background: BackgroundTasks,
    analyze: bool = Query(
        default=True,
        description="Ask the AI now. False logs the question and waits to be asked.",
    ),
) -> Mistake:
    """Log a question you got wrong.

    The ladder is armed immediately, anchored to now - a slow, failed, or unasked-for
    analysis must never cost the student their 1-hour review.
    """
    logged_at = utcnow()
    fields = body.model_dump()
    concept_ids = fields.pop("concept_ids", [])
    mistake = Mistake(
        user_id=user_id,
        created_at=logged_at,
        analysis_status=AnalysisStatus.pending if analyze else AnalysisStatus.not_requested,
        # An urgency chosen here is the student's, and the analyzer must not
        # overwrite it a moment later.
        urgency_is_yours=fields.get("urgency") is not None,
        **fields,
    )
    mistake.reviews.extend(build_ladder(mistake.id, logged_at))
    blank_collections(mistake)

    if concept_ids:
        # Scoped to the student: a concept id from someone else's bank must not
        # attach a question to it.
        concepts = await session.scalars(
            select(Concept).where(Concept.id.in_(concept_ids), Concept.user_id == user_id)
        )
        mistake.concepts = list(concepts)
    session.add(mistake)
    await session.commit()

    if analyze:
        background.add_task(analyze_in_background, mistake.id)
    return mistake


class Discussion(BaseModel):
    """A follow-up about one question, with everything said about it so far."""

    question: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=40)


class Reply(BaseModel):
    answer: str
    analyzer: str
    analyzer_ready: bool
    error: str | None = None


def render_for_discussion(mistake: Mistake) -> str:
    """Everything the tutor is allowed to know about this question.

    Built here rather than handing over the ORM object, for the same reason
    `MistakeInput` exists: what goes to a model should be a decision, not a
    side effect of what happens to be on the row.
    """
    parts = [f"Section: {mistake.section}"]
    if mistake.source:
        parts.append(f"Source: {mistake.source}")
    parts.append(f"Question: {mistake.question_text}")
    if mistake.choices:
        rendered = "; ".join(
            f"{chr(65 + i)}) {choice}" for i, choice in enumerate(mistake.choices)
        )
        parts.append(f"Choices: {rendered}")
    parts.append(f"The student answered: {mistake.your_answer}")
    parts.append(f"The correct answer: {mistake.correct_answer}")
    if mistake.student_note:
        parts.append(f"What the student said happened: {mistake.student_note}")
    if mistake.topic:
        parts.append(f"Topic: {mistake.topic}")
    if mistake.error_type:
        parts.append(f"Diagnosis: {mistake.error_type}")
    if mistake.why_wrong:
        parts.append(f"Why it was wrong: {mistake.why_wrong}")
    if mistake.correct_reasoning:
        parts.append(f"Correct reasoning: {mistake.correct_reasoning}")
    if mistake.trap:
        parts.append(f"The trap: {mistake.trap}")
    if mistake.takeaway:
        parts.append(f"Takeaway: {mistake.takeaway}")
    return "\n".join(parts)


@router.post("/{mistake_id}/ask", response_model=Reply)
async def ask_about_mistake(
    mistake_id: str, body: Discussion, session: SessionDep, user_id: UserDep
) -> Reply:
    """Ask the AI about this one question - what a word in the debrief means, why
    the answer given was wrong, how to do it next time.

    Scoped to the question on purpose. The side panel answers about the whole
    bank; this one has the question in front of it and may explain and re-word,
    which is the thing a debrief alone cannot do.
    """
    mistake = await _load(session, user_id, mistake_id)
    settings = get_settings()

    conversation = [*body.history, Turn(role="student", text=body.question)]
    try:
        answer = await get_analyzer().discuss(render_for_discussion(mistake), conversation)
        error = None
    except Exception as exc:
        # The debrief is still on the page; losing the follow-up is survivable.
        answer = "That could not be answered just now. The debrief above is unchanged."
        error = f"{type(exc).__name__}: {exc}"[:500]

    return Reply(
        answer=answer,
        analyzer=settings.ai_provider.lower(),
        analyzer_ready=analyzer_ready(settings),
        error=error,
    )


@router.get("", response_model=list[MistakeRead])
async def list_mistakes(
    session: SessionDep,
    user_id: UserDep,
    error_type: ErrorType | None = None,
    urgency: Urgency | None = None,
    section: Section | None = None,
    topic: str | None = None,
    status: AnalysisStatus | None = None,
    q: str | None = Query(
        default=None,
        description="Words to find. Every word must appear somewhere on the question - "
        "its text, source, answers, note, topic or analysis.",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Mistake]:
    stmt = (
        select(Mistake)
        .where(Mistake.user_id == user_id)
        .options(*mistake_options())
        .order_by(Mistake.created_at.desc())
    )
    if error_type is not None:
        stmt = stmt.where(Mistake.error_type == error_type)
    if urgency is not None:
        stmt = stmt.where(Mistake.urgency == urgency)
    if section is not None:
        stmt = stmt.where(Mistake.section == section)
    if topic is not None:
        stmt = stmt.where(Mistake.topic == topic)
    if status is not None:
        stmt = stmt.where(Mistake.analysis_status == status)
    if q:
        # The same matcher the bank and the assistant use, so a search means the
        # same thing wherever it is typed.
        clause = text_filter(q)
        if clause is not None:
            stmt = stmt.where(clause)

    result = await session.scalars(stmt.limit(limit).offset(offset))
    return list(result)


async def _load(session: SessionDep, user_id: str, mistake_id: str) -> Mistake:
    mistake = await session.scalar(
        select(Mistake)
        .where(Mistake.id == mistake_id, Mistake.user_id == user_id)
        .options(*mistake_options())
    )
    if mistake is None:
        raise HTTPException(status_code=404, detail="No such mistake")
    return mistake


@router.post("/search", response_model=list[MistakeRead])
async def search(body: BankQuery, session: SessionDep, user_id: UserDep) -> list[Mistake]:
    """Filter the bank by any combination of facets.

    A POST because the filter is a structure, not a handful of scalars: each facet
    takes a list, OR within a list and AND across them. The same `BankQuery` the
    assistant produces, so the panel and the bank page cannot drift apart.
    """
    return await run_query(session, user_id, body)



@router.post("/scan", response_model=ScannedQuestion)
async def scan_question(file: Annotated[UploadFile, File()]) -> ScannedQuestion:
    """Read a picture of a question and return the log form, filled in.

    Sits above `/{mistake_id}` next to `/search`, for reading order rather than
    correctness: no POST is declared on `/{mistake_id}`, so a method mismatch
    there is only a partial match and the router keeps looking regardless.

    Nothing is written and nothing is stored - the endpoint takes no session at
    all. It answers with what the model read; the student corrects whatever it
    got wrong and logs it themselves.
    """
    data = await file.read(MAX_SCAN_BYTES + 1)
    kind, media_type, data = _sniff_scan(data)

    try:
        return await get_scanner().read(ScanInput(kind=kind, media_type=media_type, data=data))
    except AnalysisFailed as exc:
        raise HTTPException(status_code=502, detail=f"Could not read that picture: {exc}") from exc


@router.get("/{mistake_id}", response_model=MistakeRead)
async def get_mistake(mistake_id: str, session: SessionDep, user_id: UserDep) -> Mistake:
    return await _load(session, user_id, mistake_id)


@router.patch("/{mistake_id}", response_model=MistakeRead)
async def update_mistake(
    mistake_id: str,
    body: MistakeUpdate,
    session: SessionDep,
    user_id: UserDep,
) -> Mistake:
    """Edit any field, the AI's included. Only the keys sent are changed."""
    mistake = await _load(session, user_id, mistake_id)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(mistake, field, value)

    if "urgency" in body.model_fields_set and body.urgency is not None:
        mistake.urgency_is_yours = True
    if body.touches_analysis():
        mistake.analysis_edited_at = utcnow()
        # Hand-written analysis counts as analysis: it should read, group and filter
        # exactly like the AI's, and the question should stop asking to be analysed.
        if mistake.analysis_status != AnalysisStatus.ready:
            mistake.analysis_status = AnalysisStatus.ready
            mistake.analysis_error = None
        if mistake.analyzed_by is None:
            mistake.analyzed_by = "you"

    await session.commit()
    return mistake


@router.post("/{mistake_id}/analyze", response_model=MistakeRead)
async def analyze(
    mistake_id: str,
    session: SessionDep,
    user_id: UserDep,
    force: bool = Query(
        default=False, description="Required to overwrite an analysis you have edited."
    ),
) -> Mistake:
    """Ask the AI to debrief this question, synchronously, so the caller sees the result.

    Covers the first run for a hand-logged question and a re-run for one that failed.
    """
    mistake = await _load(session, user_id, mistake_id)

    if mistake.analysis_edited_at is not None and not force:
        raise HTTPException(
            status_code=409,
            detail="You have edited this analysis. Re-run with force=true to replace it.",
        )

    return await analyze_mistake(session, mistake)


@router.delete("/{mistake_id}", status_code=204)
async def delete_mistake(mistake_id: str, session: SessionDep, user_id: UserDep) -> None:
    """Deletes the question, its ladder, and the bytes of its pictures.

    The image rows cascade; the files on disk do not, so without this every deleted
    question leaves its pictures behind forever.
    """
    mistake = await _load(session, user_id, mistake_id)
    filenames = [image.filename for image in mistake.images]

    await session.delete(mistake)
    await session.commit()

    root = get_settings().upload_root
    for filename in filenames:
        delete_file(filename, root)

"""Videos: study material broken into concepts, filed under tabs you name."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..deps import SessionDep, UserDep
from ..models import (
    Concept,
    Video,
    VideoStatus,
    concept_mistakes,
    mistake_options,
    subject_slug,
)
from ..schemas import (
    SubjectTab,
    VideoConceptRead,
    VideoCreate,
    VideoDetail,
    VideoRead,
    VideoUpdate,
)
from ..services import read_video_in_background
from ..videos import VideoUnreadable, at_second, from_pasted, watch_url, youtube_id

router = APIRouter(prefix="/videos", tags=["videos"])


def _read(video: Video, concept_count: int = 0) -> VideoRead:
    return VideoRead(
        id=video.id,
        created_at=video.created_at,
        youtube_id=video.youtube_id,
        url=video.url,
        title=video.title,
        author=video.author,
        subject=video.subject,
        directions=video.directions,
        status=video.status,
        error=video.error,
        summary=video.summary,
        duration_seconds=video.duration_seconds,
        summarised_at=video.summarised_at,
        concept_count=concept_count,
        has_transcript=bool(video.transcript),
    )


async def _load(session, user_id: str, video_id: str) -> Video:
    video = await session.scalar(
        select(Video)
        .where(Video.id == video_id, Video.user_id == user_id)
        .options(selectinload(Video.concepts))
    )
    if video is None:
        raise HTTPException(status_code=404, detail="No such video")
    return video


@router.post("", response_model=VideoRead, status_code=201)
async def add_video(
    body: VideoCreate,
    session: SessionDep,
    user_id: UserDep,
    background: BackgroundTasks,
) -> VideoRead:
    """Put a video in. Reading it happens in the background, as a debrief does.

    The same video can be added twice on purpose: a second pass with different
    directions is a legitimate thing to want, and refusing it would be the app
    deciding how someone studies.
    """
    try:
        found = youtube_id(body.url)
    except VideoUnreadable as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    transcript = None
    if body.transcript:
        try:
            transcript = from_pasted(body.transcript).text
        except VideoUnreadable as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    video = Video(
        user_id=user_id,
        youtube_id=found,
        url=watch_url(found),
        subject=subject_slug(body.subject),
        directions=(body.directions or "").strip() or None,
        transcript=transcript,
        status=VideoStatus.pending,
    )
    video.concepts = []
    session.add(video)
    await session.commit()

    background.add_task(read_video_in_background, video.id)
    return _read(video)


@router.get("", response_model=list[VideoRead])
async def list_videos(
    session: SessionDep,
    user_id: UserDep,
    subject: str | None = Query(default=None, description="Only this tab."),
) -> list[VideoRead]:
    stmt = select(Video).where(Video.user_id == user_id).options(selectinload(Video.concepts))
    if subject is not None:
        stmt = stmt.where(Video.subject == subject_slug(subject))
    videos = await session.scalars(stmt.order_by(Video.created_at.desc()))
    return [_read(v, len(v.concepts)) for v in videos]


@router.get("/subjects", response_model=list[SubjectTab])
async def subjects(session: SessionDep, user_id: UserDep) -> list[SubjectTab]:
    """The tabs, with what is under each. Busiest first, unfiled last."""
    rows = await session.execute(
        select(Video.subject, func.count(func.distinct(Video.id)), func.count(Concept.id))
        .select_from(Video)
        .outerjoin(Concept, Concept.video_id == Video.id)
        .where(Video.user_id == user_id)
        .group_by(Video.subject)
    )
    tabs = [
        SubjectTab(subject=subject, video_count=videos, concept_count=concepts)
        for subject, videos, concepts in rows
    ]
    tabs.sort(key=lambda tab: (tab.subject is None, -tab.video_count, tab.subject or ""))
    return tabs


@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(video_id: str, session: SessionDep, user_id: UserDep) -> VideoDetail:
    video = await _load(session, user_id, video_id)

    rows = await session.execute(
        select(concept_mistakes.c.concept_id, func.count())
        .where(concept_mistakes.c.concept_id.in_([c.id for c in video.concepts] or [""]))
        .group_by(concept_mistakes.c.concept_id)
    )
    counts = {concept_id: count for concept_id, count in rows}
    # Every question filed under any of this video's concepts: what the student
    # has actually got wrong on the thing the video teaches.
    mistakes = []
    if video.concepts:
        from ..models import Mistake

        mistakes = list(
            await session.scalars(
                select(Mistake)
                .join(concept_mistakes, Mistake.id == concept_mistakes.c.mistake_id)
                .where(concept_mistakes.c.concept_id.in_([c.id for c in video.concepts]))
                .options(*mistake_options())
                .distinct()
                .order_by(Mistake.created_at.desc())
            )
        )

    return VideoDetail(
        **_read(video, len(video.concepts)).model_dump(),
        concepts=[
            VideoConceptRead(
                id=c.id,
                title=c.title,
                body=c.body,
                subject=c.subject,
                start_seconds=c.start_seconds,
                question_count=counts.get(c.id, 0),
                watch_url=at_second(video.youtube_id, c.start_seconds),
            )
            for c in video.concepts
        ],
        mistakes=mistakes,
    )


@router.patch("/{video_id}", response_model=VideoRead)
async def update_video(
    video_id: str, body: VideoUpdate, session: SessionDep, user_id: UserDep
) -> VideoRead:
    video = await _load(session, user_id, video_id)
    fields = body.model_dump(exclude_unset=True)
    if "subject" in fields:
        video.subject = subject_slug(fields["subject"])
        # Moving a video to another tab moves what it taught with it.
        for concept in video.concepts:
            concept.subject = video.subject
    if "directions" in fields:
        video.directions = (fields["directions"] or "").strip() or None
    if "title" in fields and fields["title"]:
        video.title = fields["title"]
    await session.commit()
    return _read(video, len(video.concepts))


@router.post("/{video_id}/reread", response_model=VideoRead)
async def reread(
    video_id: str,
    session: SessionDep,
    user_id: UserDep,
    background: BackgroundTasks,
) -> VideoRead:
    """Read it again - after changing the directions, or after a failure.

    The transcript is kept, so this costs no second fetch and works even for a
    video whose captions were pasted by hand.
    """
    video = await _load(session, user_id, video_id)
    video.status = VideoStatus.pending
    video.error = None
    await session.commit()
    background.add_task(read_video_in_background, video.id)
    return _read(video, len(video.concepts))


@router.delete("/{video_id}", status_code=204)
async def delete_video(video_id: str, session: SessionDep, user_id: UserDep) -> None:
    """Deletes the video and the concepts it produced.

    Except the ones carrying questions: those have been built on, and taking them
    out would silently untag work the student did by hand.
    """
    video = await _load(session, user_id, video_id)
    # Explicit rather than left to a cascade: the two outcomes differ per concept,
    # and "delete the parent and hope the right children go" is how hand-tagged
    # work gets silently thrown away.
    for concept in list(video.concepts):
        await session.refresh(concept, ["mistakes"])
        if concept.mistakes:
            concept.video_id = None
        else:
            await session.delete(concept)
    await session.flush()
    await session.delete(video)
    await session.commit()

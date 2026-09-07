"""Concepts: the things worth knowing, and the questions filed under them."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..deps import SessionDep, UserDep
from ..images import MAX_BYTES, ImageRejected, store
from ..images import delete as delete_file
from ..models import (
    Concept,
    ConceptImage,
    Mistake,
    concept_mistakes,
    concept_options,
    mistake_options,
    utcnow,
)
from ..schemas import ConceptCreate, ConceptDetail, ConceptRead, ConceptUpdate

router = APIRouter(prefix="/concepts", tags=["concepts"])


async def _load(session, user_id: str, concept_id: str, *, with_mistakes: bool = False):
    stmt = select(Concept).where(Concept.id == concept_id, Concept.user_id == user_id)
    if with_mistakes:
        stmt = stmt.options(
            selectinload(Concept.mistakes).options(*mistake_options()),
            selectinload(Concept.images),
        )
    else:
        stmt = stmt.options(*concept_options())

    concept = await session.scalar(stmt)
    if concept is None:
        raise HTTPException(status_code=404, detail="No such concept")
    return concept


def _read(concept: Concept) -> ConceptRead:
    return ConceptRead(
        id=concept.id,
        created_at=concept.created_at,
        updated_at=concept.updated_at,
        title=concept.title,
        body=concept.body,
        section=concept.section,
        question_count=len(concept.mistakes),
        images=concept.images,
    )


@router.post("", response_model=ConceptRead, status_code=201)
async def create_concept(body: ConceptCreate, session: SessionDep, user_id: UserDep) -> ConceptRead:
    concept = Concept(user_id=user_id, **body.model_dump())
    # Same reason as a new question's concepts: a brand-new concept has no questions,
    # and `_read` counting them must not become a lazy load after the commit.
    # Both collections, for the same reason `blank_collections` exists for questions.
    concept.mistakes = []
    concept.images = []
    session.add(concept)
    await session.commit()
    return _read(concept)


@router.get("", response_model=list[ConceptRead])
async def list_concepts(session: SessionDep, user_id: UserDep) -> list[ConceptRead]:
    """Concepts with their question counts, the ones you have tagged most first."""
    counts = dict(
        (
            await session.execute(
                select(concept_mistakes.c.concept_id, func.count()).group_by(
                    concept_mistakes.c.concept_id
                )
            )
        ).all()
    )
    concepts = await session.scalars(
        select(Concept)
        .where(Concept.user_id == user_id)
        .options(selectinload(Concept.images))
        .order_by(Concept.title)
    )
    reads = [
        ConceptRead(
            id=concept.id,
            created_at=concept.created_at,
            updated_at=concept.updated_at,
            title=concept.title,
            body=concept.body,
            section=concept.section,
            question_count=counts.get(concept.id, 0),
            images=concept.images,
        )
        for concept in concepts
    ]
    return sorted(reads, key=lambda c: (-c.question_count, c.title.lower()))


@router.get("/{concept_id}", response_model=ConceptDetail)
async def get_concept(concept_id: str, session: SessionDep, user_id: UserDep) -> ConceptDetail:
    concept = await _load(session, user_id, concept_id, with_mistakes=True)
    return ConceptDetail(**_read(concept).model_dump(), mistakes=concept.mistakes)


@router.patch("/{concept_id}", response_model=ConceptRead)
async def update_concept(
    concept_id: str, body: ConceptUpdate, session: SessionDep, user_id: UserDep
) -> ConceptRead:
    concept = await _load(session, user_id, concept_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(concept, field, value)
    concept.updated_at = utcnow()
    await session.commit()
    return _read(concept)


@router.delete("/{concept_id}", status_code=204)
async def delete_concept(concept_id: str, session: SessionDep, user_id: UserDep) -> None:
    """Deletes the concept, its tags and its diagrams. The questions are untouched."""
    concept = await _load(session, user_id, concept_id)
    filenames = [image.filename for image in concept.images]

    await session.delete(concept)
    await session.commit()

    root = get_settings().upload_root
    for filename in filenames:
        delete_file(filename, root)


async def _own_mistake(session, user_id: str, mistake_id: str) -> Mistake:
    mistake = await session.scalar(
        select(Mistake).where(Mistake.id == mistake_id, Mistake.user_id == user_id)
    )
    if mistake is None:
        raise HTTPException(status_code=404, detail="No such question")
    return mistake


@router.post("/{concept_id}/questions/{mistake_id}", response_model=ConceptDetail)
async def tag_question(
    concept_id: str, mistake_id: str, session: SessionDep, user_id: UserDep
) -> ConceptDetail:
    """File a question under a concept. Tagging twice is not an error."""
    concept = await _load(session, user_id, concept_id, with_mistakes=True)
    mistake = await _own_mistake(session, user_id, mistake_id)

    if mistake not in concept.mistakes:
        concept.mistakes.append(mistake)
        await session.commit()
        concept = await _load(session, user_id, concept_id, with_mistakes=True)

    return ConceptDetail(**_read(concept).model_dump(), mistakes=concept.mistakes)


@router.delete("/{concept_id}/questions/{mistake_id}", response_model=ConceptDetail)
async def untag_question(
    concept_id: str, mistake_id: str, session: SessionDep, user_id: UserDep
) -> ConceptDetail:
    concept = await _load(session, user_id, concept_id, with_mistakes=True)
    mistake = await _own_mistake(session, user_id, mistake_id)

    if mistake in concept.mistakes:
        concept.mistakes.remove(mistake)
        await session.commit()
        concept = await _load(session, user_id, concept_id, with_mistakes=True)

    return ConceptDetail(**_read(concept).model_dump(), mistakes=concept.mistakes)


# --- pictures -----------------------------------------------------------------


@router.post("/{concept_id}/images", response_model=ConceptDetail, status_code=201)
async def upload_concept_image(
    concept_id: str,
    session: SessionDep,
    user_id: UserDep,
    file: Annotated[UploadFile, File()],
) -> ConceptDetail:
    """Attach a diagram to a concept. Ownership is checked before anything is written."""
    concept = await _load(session, user_id, concept_id, with_mistakes=True)

    data = await file.read(MAX_BYTES + 1)
    try:
        stored = store(data, get_settings().upload_root)
    except ImageRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    concept.images.append(
        ConceptImage(
            concept_id=concept.id,
            filename=stored.filename,
            content_type=stored.content_type,
            byte_size=stored.size,
            width=stored.width,
            height=stored.height,
            position=len(concept.images),
        )
    )
    await session.commit()

    concept = await _load(session, user_id, concept_id, with_mistakes=True)
    return ConceptDetail(**_read(concept).model_dump(), mistakes=concept.mistakes)


@router.delete("/{concept_id}/images/{image_id}", response_model=ConceptDetail)
async def delete_concept_image(
    concept_id: str, image_id: str, session: SessionDep, user_id: UserDep
) -> ConceptDetail:
    concept = await _load(session, user_id, concept_id, with_mistakes=True)

    image = next((found for found in concept.images if found.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="No such image")

    filename = image.filename
    concept.images.remove(image)
    await session.commit()
    delete_file(filename, get_settings().upload_root)

    concept = await _load(session, user_id, concept_id, with_mistakes=True)
    return ConceptDetail(**_read(concept).model_dump(), mistakes=concept.mistakes)

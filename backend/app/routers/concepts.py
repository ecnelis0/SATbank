"""Concepts: the things worth knowing, and the questions filed under them."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..deps import SessionDep, UserDep
from ..models import Concept, Mistake, concept_mistakes, mistake_options, utcnow
from ..schemas import ConceptCreate, ConceptDetail, ConceptRead, ConceptUpdate

router = APIRouter(prefix="/concepts", tags=["concepts"])


async def _load(session, user_id: str, concept_id: str, *, with_mistakes: bool = False):
    stmt = select(Concept).where(Concept.id == concept_id, Concept.user_id == user_id)
    if with_mistakes:
        stmt = stmt.options(selectinload(Concept.mistakes).options(*mistake_options()))
    else:
        stmt = stmt.options(selectinload(Concept.mistakes))

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
    )


@router.post("", response_model=ConceptRead, status_code=201)
async def create_concept(body: ConceptCreate, session: SessionDep, user_id: UserDep) -> ConceptRead:
    concept = Concept(user_id=user_id, **body.model_dump())
    # Same reason as a new question's concepts: a brand-new concept has no questions,
    # and `_read` counting them must not become a lazy load after the commit.
    concept.mistakes = []
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
        select(Concept).where(Concept.user_id == user_id).order_by(Concept.title)
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
    """Deletes the concept and its tags. The questions themselves are untouched."""
    concept = await _load(session, user_id, concept_id)
    await session.delete(concept)
    await session.commit()


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

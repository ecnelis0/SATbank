"""Pictures attached to a question."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select

from ..config import get_settings
from ..deps import SessionDep, UserDep
from ..images import MAX_BYTES, ImageRejected, store
from ..images import delete as delete_file
from ..models import Mistake, MistakeImage, mistake_options
from ..schemas import MistakeRead

router = APIRouter(prefix="/mistakes/{mistake_id}/images", tags=["images"])


async def _load(session, user_id: str, mistake_id: str) -> Mistake:
    mistake = await session.scalar(
        select(Mistake)
        .where(Mistake.id == mistake_id, Mistake.user_id == user_id)
        .options(*mistake_options())
    )
    if mistake is None:
        raise HTTPException(status_code=404, detail="No such question")
    return mistake


@router.post("", response_model=MistakeRead, status_code=201)
async def upload_image(
    mistake_id: str,
    session: SessionDep,
    user_id: UserDep,
    file: Annotated[UploadFile, File()],
) -> Mistake:
    """Attach a picture to a question.

    The question is loaded - and therefore ownership checked - before a single byte
    is written, so an upload aimed at someone else's question never touches the disk.
    """
    mistake = await _load(session, user_id, mistake_id)

    data = await file.read(MAX_BYTES + 1)
    try:
        stored = store(data, get_settings().upload_root)
    except ImageRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    mistake.images.append(
        MistakeImage(
            mistake_id=mistake.id,
            filename=stored.filename,
            content_type=stored.content_type,
            byte_size=stored.size,
            width=stored.width,
            height=stored.height,
            position=len(mistake.images),
        )
    )
    await session.commit()
    return await _load(session, user_id, mistake_id)


@router.delete("/{image_id}", response_model=MistakeRead)
async def delete_image(
    mistake_id: str, image_id: str, session: SessionDep, user_id: UserDep
) -> Mistake:
    mistake = await _load(session, user_id, mistake_id)

    image = next((candidate for candidate in mistake.images if candidate.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="No such image")

    filename = image.filename
    mistake.images.remove(image)
    await session.commit()
    # File last: a row without its file renders as a broken image, but a file without
    # its row is invisible litter that nothing will ever clean up.
    delete_file(filename, get_settings().upload_root)

    return await _load(session, user_id, mistake_id)

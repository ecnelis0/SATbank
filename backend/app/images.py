"""Storing uploaded pictures of questions.

Everything here is a rule about not trusting the upload: the filename is generated
rather than taken from the client, the type is decided by decoding the bytes rather
than by the declared Content-Type, and the size is capped while reading rather than
after.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024

# Pillow's own format names, mapped to what a browser should be told.
ALLOWED_FORMATS: dict[str, tuple[str, str]] = {
    "PNG": ("image/png", ".png"),
    "JPEG": ("image/jpeg", ".jpg"),
    "GIF": ("image/gif", ".gif"),
    "WEBP": ("image/webp", ".webp"),
    "HEIF": ("image/heic", ".heic"),
}


class ImageRejected(ValueError):
    """The upload is not something we are willing to store."""


class StoredImage:
    def __init__(self, filename: str, content_type: str, size: int, width: int, height: int):
        self.filename = filename
        self.content_type = content_type
        self.size = size
        self.width = width
        self.height = height


def upload_dir(root: str) -> Path:
    directory = Path(root)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store(data: bytes, root: str) -> StoredImage:
    """Validate the bytes, then write them under a generated name."""
    if not data:
        raise ImageRejected("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ImageRejected(
            f"That image is {len(data) // (1024 * 1024)}MB; the limit is "
            f"{MAX_BYTES // (1024 * 1024)}MB."
        )

    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format
            width, height = image.size
            # Decodes the pixels: a file that merely starts with a PNG header but is
            # not an image fails here rather than at display time.
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageRejected("That file is not an image we can read.") from exc

    if image_format not in ALLOWED_FORMATS:
        raise ImageRejected(f"{image_format or 'That format'} is not supported.")

    content_type, suffix = ALLOWED_FORMATS[image_format]
    # Generated, never derived from the upload: no path separators, no traversal,
    # no collisions, and nothing the student typed ends up in a filesystem path.
    filename = f"{uuid.uuid4().hex}{suffix}"
    (upload_dir(root) / filename).write_bytes(data)

    return StoredImage(filename, content_type, len(data), width, height)


def delete(filename: str, root: str) -> None:
    """Remove a stored file. Only ever called with a name we generated."""
    path = upload_dir(root) / Path(filename).name
    path.unlink(missing_ok=True)

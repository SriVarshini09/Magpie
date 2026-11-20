"""Uploads: at most 2 images, JPEG/PNG/WebP, 5 MB each; re-encode with Pillow, strip EXIF, hash (PLAN §3.17).

Owner: A. Files live in uploads/<owner_id>/<sha256>.jpg (git-ignored), are served only to the app, and
never go to SingleStore, Amplitude or a store. The stored image is the image Claude sees and the image
we display (long edge <= UPLOAD_MAX_EDGE_PX), so box coordinates need no rescaling.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from app.audit.chain import sha256_hex
from app.config import BACKEND_DIR, get_settings
from app.models import IntakeImage

__all__ = ["save_upload", "find_upload", "read_upload", "UploadError", "ALLOWED_IMAGE_TYPES", "validate_uploads"]

UPLOADS_DIR: Path = BACKEND_DIR / "uploads"  # tests point this at a temp folder
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
_ID = re.compile(r"^img_[0-9a-f]{16}$")
_index: dict[str, Path] = {}


class UploadError(ValueError):
    def __init__(self, error: str, message: str) -> None:
        self.error, self.message = error, message
        super().__init__(message)


def validate_uploads(files: list[tuple[str, str | None, int]]) -> None:
    """`files` is [(filename, content_type, size_bytes)]. Raises UploadError (a 422) on the first problem."""
    s = get_settings()
    if len(files) > s.upload_max_images:
        raise UploadError("too_many_images", f"At most {s.upload_max_images} photos per request")
    for name, ctype, size in files:
        if ctype not in ALLOWED_IMAGE_TYPES:
            raise UploadError("unsupported_file", f"{name}: use JPEG, PNG or WebP")
        if size > s.upload_max_mb * 1024 * 1024:
            raise UploadError("file_too_large", f"{name}: larger than {s.upload_max_mb} MB")


def save_upload(run_id: str, data: bytes, content_type: str | None, filename: str = "upload") -> IntakeImage:
    """Validate, re-encode as JPEG (EXIF dropped), downscale to the long-edge limit, sha256, store.

    `run_id` is the owner folder: the intake id before a run exists, the run id from the workspace composer.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    s = get_settings()
    validate_uploads([(filename, content_type, len(data))])
    try:
        with Image.open(io.BytesIO(data)) as im:
            if _FORMATS.get(im.format or "") not in ALLOWED_IMAGE_TYPES:
                raise UploadError("unsupported_file", f"{filename}: use JPEG, PNG or WebP")
            im = ImageOps.exif_transpose(im)  # bake the orientation in, then drop EXIF
            im = im.convert("RGB")
            if max(im.size) > s.upload_max_edge_px:
                im.thumbnail((s.upload_max_edge_px, s.upload_max_edge_px), Image.LANCZOS)
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=88, optimize=True)  # no exif argument: metadata is not copied
            w, h = im.size
    except UploadError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise UploadError("unsupported_file", f"{filename}: not a readable image") from exc
    jpeg = out.getvalue()
    sha = sha256_hex(jpeg)
    image_id = f"img_{sha[:16]}"
    safe_owner = re.sub(r"[^A-Za-z0-9_-]", "_", run_id)[:64] or "intake"
    folder = UPLOADS_DIR / safe_owner
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sha}.jpg"
    if not path.is_file():
        path.write_bytes(jpeg)
    _index[image_id] = path
    return IntakeImage(image_id=image_id, url=f"/api/uploads/{image_id}", w=w, h=h, sha256=sha)


def find_upload(image_id: str) -> Path | None:
    """The stored file for an image id, or None. Ids are checked strictly (no path characters)."""
    if not _ID.match(image_id):
        return None
    path = _index.get(image_id)
    if path and path.is_file():
        return path
    if UPLOADS_DIR.is_dir():
        for cand in UPLOADS_DIR.glob(f"*/{image_id[4:]}*.jpg"):
            _index[image_id] = cand
            return cand
    return None


def read_upload(image_id: str) -> bytes | None:
    path = find_upload(image_id)
    return path.read_bytes() if path else None

"""Helpers for V1 two-step clip upload (initiate → presigned PUT)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.services.object_storage import LocalStorage, ObjectStorage, S3Storage


def new_clip_id() -> str:
    return str(uuid.uuid4())


def clip_storage_key(user_id: str, clip_id: str, content_type: str) -> str:
    ext = "mov" if content_type == "video/quicktime" else "mp4"
    return f"clips/{user_id}/{clip_id}.{ext}"


def presigned_put_url(
    storage: ObjectStorage,
    key: str,
    content_type: str,
    *,
    expires_seconds: int = 3600,
) -> tuple[str, datetime]:
    """Return (upload_url, expires_at) for a direct PUT upload."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)
    if isinstance(storage, S3Storage):
        url = storage._s3.generate_presigned_url(  # noqa: SLF001 — internal client access
            "put_object",
            Params={
                "Bucket": storage._bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_seconds,
        )
        return url, expires_at
    # Local dev / tests: placeholder URL — complete-upload not implemented in 5B.1
    return f"local://upload/{key}", expires_at


def iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat().replace("+00:00", "Z")

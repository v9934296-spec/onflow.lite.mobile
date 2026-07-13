"""
Attach optional playback URLs to completed clip-review results — no synthesized media.

Sources (in order of precedence for video):
  1. Sanitized HTTPS/HTTP URLs found in clip job metadata (client or gateway-supplied).
  2. S3-compatible presigned GET URLs when ``ONFLOW_CLIP_PLAYBACK_PRESIGNED_TTL_SECONDS`` > 0
     and uploads use configured S3 storage (objects are retained instead of deleted).
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from structlog import get_logger

from app.core.config import Settings, get_settings

logger = get_logger(__name__)

_VIDEO_META_KEYS = (
    "video_playback_url",
    "playback_url",
    "playbackUrl",
    "secure_url",
    "secureUrl",
    "cloudinary_secure_url",
    "source_video_url",
    "sourceVideoUrl",
    "video_url",
    "videoUrl",
    "clip_url",
    "clipUrl",
    "media_url",
    "mediaUrl",
)

_THUMB_META_KEYS = (
    "thumbnail_url",
    "thumbnailUrl",
    "poster_url",
    "posterUrl",
    "playback_thumbnail_url",
    "playbackThumbnailUrl",
    "preview_url",
    "previewUrl",
)


def sanitize_public_media_url(raw: Any) -> str | None:
    """
    Accept only http/https without embedded userinfo — avoids stuffing credentials into JSON.
    """
    if raw is None or not isinstance(raw, str):
        return None
    u = raw.strip()
    if not u:
        return None
    try:
        parsed = urlparse(u)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return u


def _layer_dicts(meta: dict[str, Any]) -> list[dict[str, Any]]:
    layers = [meta]
    clip_like = meta.get("clip") or meta.get("clip_asset") or meta.get("media")
    if isinstance(clip_like, dict):
        layers.append(clip_like)
    return layers


def extract_playback_from_metadata(meta: dict[str, Any]) -> tuple[str | None, str | None]:
    """First non-empty sanitized video URL and thumbnail URL from metadata (+ nested clip-like dict)."""
    video: str | None = None
    thumb: str | None = None
    for layer in _layer_dicts(meta):
        if video is None:
            for k in _VIDEO_META_KEYS:
                cand = sanitize_public_media_url(layer.get(k))
                if cand:
                    video = cand
                    break
        if thumb is None:
            for k in _THUMB_META_KEYS:
                cand = sanitize_public_media_url(layer.get(k))
                if cand:
                    thumb = cand
                    break
        if video and thumb:
            break
    return video, thumb


def _presigned_playback_from_s3(storage_key: str, settings: Settings) -> str | None:
    if not storage_key.strip():
        return None
    ttl = int(settings.clip_playback_presigned_ttl_seconds or 0)
    if ttl <= 0:
        return None
    bucket = settings.s3_bucket.strip()
    endpoint = settings.s3_endpoint.strip()
    access = settings.s3_access_key.strip()
    secret = settings.s3_secret_key.strip()
    if not (bucket and endpoint and access and secret):
        logger.debug(
            "clip_playback_presign_skipped",
            reason="s3_not_fully_configured",
        )
        return None
    try:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
        )
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": storage_key},
            ExpiresIn=min(ttl, 604800),
        )
    except Exception:
        logger.warning("clip_playback_presign_failed", exc_info=True)
        return None


def merge_playback_hints_into_result(
    result: dict[str, Any],
    *,
    clip_metadata: dict[str, Any],
    storage_key: str,
    settings: Settings | None = None,
) -> bool:
    """
    Mutates ``result`` in-place with canonical ``video_playback_url`` / ``thumbnail_url`` when safe.

    Returns:
        ``True`` if object storage blobs must be retained (presigned replay enabled).
        Callers must skip remote delete when this is ``True``.
    """
    cfg = settings or get_settings()

    vid, thumb = extract_playback_from_metadata(clip_metadata)

    skip_remote_delete = False
    existing_video = sanitize_public_media_url(result.get("video_playback_url"))  # type: ignore[arg-type]
    existing_thumb = sanitize_public_media_url(result.get("thumbnail_url"))  # type: ignore[arg-type]

    presigned = False
    if not vid:
        cand = _presigned_playback_from_s3(storage_key, cfg)
        if cand:
            vid = sanitize_public_media_url(cand)
            presigned = bool(vid)
            skip_remote_delete = presigned

    if vid and existing_video is None:
        result["video_playback_url"] = vid
    if thumb and existing_thumb is None:
        result["thumbnail_url"] = thumb

    if presigned:
        pn = result.get("processing_notes")
        if isinstance(pn, list):
            notes = list(pn)
        else:
            notes = []
        notes.append(
            "Clip playback uses a temporary download link tied to retained storage "
            "(operator-configured TTL). It may expire; analysis text remains valid."
        )
        result["processing_notes"] = notes

    return skip_remote_delete

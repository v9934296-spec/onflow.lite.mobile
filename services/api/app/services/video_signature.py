"""Cheap magic-byte sniff to reject non-video uploads before decode.

Presigned uploads mean the API never sees the bytes until the worker downloads
them, so a client can PUT arbitrary content to the upload URL. This header check
rejects obviously-bogus uploads (text, images, truncated files) fast and cheaply,
before OpenCV/Gemini are spun up. It is intentionally permissive about *which*
video container — the goal is "is this plausibly a video", not strict MIME parsing.
"""
from __future__ import annotations

# Top-level ISO Base Media box types that legitimately lead an mp4/mov/m4v file.
_ISO_BMFF_LEADING_BOXES = {
    b"ftyp",
    b"moov",
    b"mdat",
    b"free",
    b"skip",
    b"wide",
    b"pnot",
}

_EBML_MAGIC = b"\x1a\x45\xdf\xa3"  # Matroska / WebM


def looks_like_video_bytes(head: bytes) -> bool:
    """Return True if ``head`` (first ~32 bytes) matches a known video container."""
    if len(head) < 12:
        return False

    # ISO Base Media: 4-byte size, then a 4-byte box type.
    if head[4:8] in _ISO_BMFF_LEADING_BOXES:
        return True

    # AVI: "RIFF" .... "AVI "
    if head[0:4] == b"RIFF" and head[8:12] == b"AVI ":
        return True

    # Matroska / WebM
    if head[0:4] == _EBML_MAGIC:
        return True

    return False


def looks_like_video(file_path: str) -> bool:
    """Return True if the file header matches a known video container.

    Recognizes ISO Base Media (mp4/mov/m4v), AVI (RIFF), and Matroska/WebM (EBML).
    Returns False for unreadable, truncated, or non-video files.
    """
    try:
        with open(file_path, "rb") as f:
            head = f.read(32)
    except OSError:
        return False
    return looks_like_video_bytes(head)


# Minimal ISO BMFF "ftyp" header + padding — valid for sniffer, not a real movie.
# Used by tests that need to pass complete-upload without a full sample MP4.
MINIMAL_VIDEO_SNIFF_BYTES = (
    b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2" + b"\x00" * 64
)

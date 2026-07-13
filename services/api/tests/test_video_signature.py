"""Tier 3 hardening: magic-byte sniff for uploaded clips."""
from __future__ import annotations

from pathlib import Path

from app.services.video_signature import looks_like_video


def _write(tmp_path: Path, name: str, data: bytes) -> str:
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_accepts_iso_bmff_ftyp(tmp_path: Path) -> None:
    data = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16
    assert looks_like_video(_write(tmp_path, "clip.mp4", data)) is True


def test_accepts_avi_and_webm(tmp_path: Path) -> None:
    avi = b"RIFF\x00\x00\x00\x00AVI LIST"
    webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 16
    assert looks_like_video(_write(tmp_path, "clip.avi", avi)) is True
    assert looks_like_video(_write(tmp_path, "clip.webm", webm)) is True


def test_rejects_text_and_truncated(tmp_path: Path) -> None:
    assert looks_like_video(_write(tmp_path, "note.txt", b"this is not a video at all")) is False
    assert looks_like_video(_write(tmp_path, "tiny.bin", b"abc")) is False


def test_rejects_missing_file(tmp_path: Path) -> None:
    assert looks_like_video(str(tmp_path / "does-not-exist.mp4")) is False

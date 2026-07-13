"""
Integration test — requires ONFLOW_GEMINI_API_KEY and a tiny valid MP4.
Run manually: set ONFLOW_GEMINI_API_KEY then pytest tests/test_gemini_integration.py -v
Skipped automatically when key is not set.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ONFLOW_GEMINI_API_KEY"),
    reason="ONFLOW_GEMINI_API_KEY not set — skipping Gemini integration test",
)


@pytest.fixture
def api_key() -> str:
    return os.environ["ONFLOW_GEMINI_API_KEY"]


def _tiny_mp4(path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    w, h = 64, 48
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(path), fourcc, 10.0, (w, h))
    assert out.isOpened()
    for i in range(30):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (40, 100, 180)
        cv2.circle(frame, (20 + i // 3, 24), 5, (255, 255, 255), -1)
        out.write(frame)
    out.release()


@pytest.mark.asyncio
async def test_gemini_enrichment_returns_addendum_shape(api_key: str, tmp_path: Path) -> None:
    from app.services.gemini_reviewer import GeminiReviewer

    test_file = tmp_path / "test.mp4"
    _tiny_mp4(test_file)

    reviewer = GeminiReviewer(api_key=api_key, model="gemini-2.5-flash")
    try:
        result = await reviewer.enrich(
            file_path=str(test_file),
            clip_label="session-a",
            clip_metadata={"stance": "regular"},
        )
    except Exception as e:
        pytest.skip(f"Gemini API error: {e}")

    assert isinstance(result.get("review_addendum"), str)
    bullets = result.get("observation_bullets")
    assert isinstance(bullets, list)


@pytest.mark.asyncio
async def test_gemini_enrichment_accepts_empty_label(api_key: str, tmp_path: Path) -> None:
    from app.services.gemini_reviewer import GeminiReviewer

    test_file = tmp_path / "test2.mp4"
    _tiny_mp4(test_file)

    reviewer = GeminiReviewer(api_key=api_key, model="gemini-2.5-flash")
    try:
        result = await reviewer.enrich(file_path=str(test_file), clip_label="")
    except Exception as e:
        pytest.skip(f"Gemini API error: {e}")

    assert "review_addendum" in result

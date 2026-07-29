"""
Optional Gemini pass: short, honest beta clip narrative — not trick detection.

Only supplements the first-pass technical review; failures are handled by the worker.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Awaitable, Callable, TypeVar

import structlog
from google import genai
from google.genai import types

from app.services.gemini_structured_schemas import ENRICHMENT_RESPONSE_JSON_SCHEMA
from app.services.landing_status import normalize_landed_signal

logger = structlog.get_logger(__name__)

# Hard ceilings for a single GeminiReviewer.enrich invocation. The class
# self-enforces all three so callers cannot accidentally bypass them via
# external retry wrappers or response-size assumptions.
MAX_RETRIES = 3
MAX_OUTPUT_TOKENS = 2048
GEMINI_CALL_TIMEOUT_SECONDS = 60.0
RETRY_BASE_DELAY_SECONDS = 1.0

_T = TypeVar("_T")


class GeminiReviewerExhaustedError(Exception):
    """
    Raised when GeminiReviewer exhausted its retry budget or its per-call timeout.

    Carries the reason ("timeout" or "transient_failures"), the number of attempts
    actually made, and the last underlying exception so the caller can decide
    whether to degrade gracefully or surface it. Callers must handle this
    explicitly — never swallow.
    """

    def __init__(
        self,
        reason: str,
        *,
        attempts: int,
        last_error: BaseException | None,
    ) -> None:
        super().__init__(f"GeminiReviewer exhausted after {attempts} attempt(s): {reason}")
        self.reason = reason
        self.attempts = attempts
        self.last_error = last_error


async def _call_with_ceiling(
    operation: Callable[[], Awaitable[_T]],
    *,
    clip_label: str,
    user_id: str | None,
    max_attempts: int = MAX_RETRIES,
    timeout_seconds: float = GEMINI_CALL_TIMEOUT_SECONDS,
    backoff_base_seconds: float = RETRY_BASE_DELAY_SECONDS,
) -> _T:
    """
    Run ``operation`` with a per-attempt timeout and a hard retry ceiling.

    Each attempt is wrapped in ``asyncio.wait_for`` so a hung Gemini response
    cannot extend a job indefinitely. After ``max_attempts`` failures the loop
    raises ``GeminiReviewerExhaustedError`` with full context — no swallow.
    """
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.wait_for(operation(), timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            last_error = exc
            logger.warning(
                "gemini_reviewer_call_timeout",
                clip_label=clip_label,
                user_id=user_id,
                attempt=attempt,
                attempts_total=max_attempts,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "gemini_reviewer_call_failed",
                clip_label=clip_label,
                user_id=user_id,
                attempt=attempt,
                attempts_total=max_attempts,
                error_type=type(exc).__name__,
                error_detail=str(exc)[:200],
            )

        if attempt < max_attempts and backoff_base_seconds > 0:
            await asyncio.sleep(backoff_base_seconds * (2 ** (attempt - 1)))

    reason = "timeout" if isinstance(last_error, asyncio.TimeoutError) else "transient_failures"
    logger.error(
        "gemini_reviewer_exhausted",
        clip_label=clip_label,
        user_id=user_id,
        attempts=max_attempts,
        reason=reason,
        last_error_type=type(last_error).__name__ if last_error else "unknown",
    )
    raise GeminiReviewerExhaustedError(reason, attempts=max_attempts, last_error=last_error)

SYSTEM_PROMPT = """\
You support OnFlow, an early beta skate clip review product.

Rules (strict):
- You are NOT a trick detector. Never claim to classify, name, or score tricks unless the skater's own tags in the prompt explicitly name them — treat those names as user context, not model detections.
- No confidence scores, no grades, no "perfect landing", no coach persona theatrics.
- Only describe what you can reasonably see. If lighting, length, or angle limits you, say so plainly.
- If you cannot observe a field clearly, set it to null — never fabricate.
- Tone: confident, casual, direct. Use "you/your", not "the skater".
- Vocabulary: say "trick", "board", "landing", "pop", "shoulders", "front foot", "back foot". Avoid "maneuver", "athlete", "appropriate body positioning", "execution quality".
- Output JSON only, no markdown fences. Shape:
{
  "review_addendum": "1–3 short sentences, hedged, about what the clip shows visually",
  "observation_bullets": ["optional bullet", "..."],
  "coaching": {
    "body_position": "short sentence or null",
    "foot_placement": "short sentence or null",
    "timing": "short sentence or null",
    "board_control": "short sentence or null",
    "commitment": "short sentence or null",
    "balance": "short sentence or null",
    "style_notes": "short sentence or null",
    "improvement_drill": "one specific drill or null"
  },
  "landed": "yes" | "no" | "unclear"
}
- observation_bullets: 0–5 short strings; skip empty fluff.
- coaching fields: each is one short sentence max. Null if not observable. Avoid vague imperatives ("work on timing", "stay balanced", "commit more") — name visible mechanics or a concrete body/board relationship.
- review_addendum length: 1-2 short sentences max.

Few-shot style examples (do not copy facts, only tone/length):
- "Your shoulders open a touch early, so the board drifts before contact."
- "You stay centered over the bolts on landing, which helps the roll-away."
- "Your back foot comes off fast after pop; keep it over the tail a split-second longer."
- "Run 8 slow reps focusing only on landing over the bolts."

LANDED — how to determine this field:
  "yes" — The skater's feet are on the board after the trick AND the skater rides away, rolls out, or is visibly stable on the board post-trick. A clean rollaway is the clearest signal, but even a short roll or stable stand on the board counts. If the skater lands on the board and maintains balance for any visible distance, that is "yes".
  "no" — The skater visibly steps off, falls, the board flies out, feet hit the ground instead of the board, or the skater clearly loses balance and cannot ride away.
  "unclear" — The clip cuts off before you can see whether the skater stayed on the board, the landing is fully off-frame, or camera angle/lighting makes it impossible to tell. Use "unclear" ONLY when you genuinely cannot see the outcome — not as a safe default.

  Bias: When in doubt between "yes" and "unclear", lean toward "yes" if the skater appears stable on the board in the last visible frames. When in doubt between "no" and "unclear", lean toward "no" if the skater is visibly off the board or falling. Reserve "unclear" for truly ambiguous situations where the outcome is not visible at all.

This is supplementary narrative; the product already performed technical frame checks.\
"""


def _build_user_prompt(clip_label: str, clip_metadata: dict[str, Any] | None = None) -> str:
    meta = clip_metadata or {}
    stance = meta.get("stance", "")
    obstacle = meta.get("obstacle", "")
    tricks_raw = meta.get("tricks", [])
    tricks = tricks_raw if isinstance(tricks_raw, list) else []

    lines: list[str] = [
        "Skater context (may be empty) — use only as self-reported tags, not detections:",
    ]
    if stance:
        lines.append(f"- stance: {stance}")
    if obstacle:
        lines.append(f"- terrain/obstacle: {obstacle}")
    if tricks:
        trick_strs = [t.strip() for t in tricks if isinstance(t, str) and t.strip()][:5]
        if trick_strs:
            lines.append(f"- tricks named by skater: {', '.join(trick_strs)}")
    if clip_label and clip_label.strip() and clip_label.strip() != "untagged":
        lines.append(f'- clip label: "{clip_label.strip()}"')

    lines.append(
        "Watch the attached clip and produce JSON as specified. "
        "Pay close attention to the end of the clip to determine if the trick was landed — "
        "look for the skater's feet on the board and any rollaway or stable riding after the trick."
    )
    return "\n".join(lines)


class GeminiReviewer:
    def __init__(
        self,
        api_key: str,
        model: str,
        inline_max_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required. Set ONFLOW_GEMINI_API_KEY.")
        if not (model or "").strip():
            raise ValueError("Gemini model is required — use resolve_gemini_model_for_tier from callers.")
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._inline_max_bytes = inline_max_bytes

    async def _wait_file_active(self, name: str) -> types.File:
        for _ in range(120):
            f = await self._client.aio.files.get(name=name)
            st = f.state
            if st == types.FileState.ACTIVE:
                return f
            if st == types.FileState.FAILED:
                raise RuntimeError("Uploaded file processing failed on Gemini side.")
            await asyncio.sleep(1)
        raise TimeoutError("Uploaded file did not become ACTIVE in time.")

    async def enrich(
        self,
        *,
        file_path: str,
        clip_label: str,
        clip_metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Returns enrichment dict for merging into clip review (addendum, bullets, coaching, landed).

        Self-enforces the module-level retry, response-token, and call-timeout
        ceilings. Raises ``GeminiReviewerExhaustedError`` on exhaustion — the
        caller is responsible for the degradation policy and must not silently
        swallow this exception.
        """
        file_size = os.path.getsize(file_path)
        mime_type = _guess_mime(file_path)
        user_prompt = _build_user_prompt(clip_label, clip_metadata)

        if file_size <= self._inline_max_bytes:
            video_bytes = _read_file(file_path)
            video_part = types.Part(
                inline_data=types.Blob(data=video_bytes, mime_type=mime_type),
                video_metadata=types.VideoMetadata(fps=10),
            )
        else:
            uploaded = await self._client.aio.files.upload(
                file=file_path,
                config=types.UploadFileConfig(mime_type=mime_type),
            )
            ready = await self._wait_file_active(uploaded.name)
            video_part = types.Part(
                file_data=types.FileData(file_uri=ready.uri, mime_type=ready.mime_type or mime_type),
                video_metadata=types.VideoMetadata(fps=10),
            )

        async def _generate() -> Any:
            return await self._client.aio.models.generate_content(
                model=self._model,
                contents=types.Content(
                    parts=[video_part, types.Part.from_text(text=user_prompt)],
                ),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.25,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    response_mime_type="application/json",
                    response_schema=ENRICHMENT_RESPONSE_JSON_SCHEMA,
                ),
            )

        response = await _call_with_ceiling(
            _generate,
            clip_label=clip_label,
            user_id=user_id,
        )

        raw_text = (response.text or "").strip()
        return _parse_enrichment_json(raw_text)


def _read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".m4v": "video/x-m4v",
        ".avi": "video/x-msvideo",
    }.get(ext, "video/mp4")


_COACHING_FIELDS = (
    "body_position",
    "foot_placement",
    "timing",
    "board_control",
    "commitment",
    "balance",
    "style_notes",
    "improvement_drill",
)


def _parse_enrichment_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        return _empty_enrichment()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return _empty_enrichment()

        # Legacy fields
        add = parsed.get("review_addendum", "")
        if not isinstance(add, str):
            add = str(add) if add is not None else ""
        bullets = parsed.get("observation_bullets", [])
        if not isinstance(bullets, list):
            bullets = []

        # Coaching observations
        coaching_raw = parsed.get("coaching")
        coaching: dict[str, str | None] = {}
        if isinstance(coaching_raw, dict):
            for field in _COACHING_FIELDS:
                val = coaching_raw.get(field)
                if isinstance(val, str) and val.strip() and val.strip().lower() != "null":
                    coaching[field] = val.strip()
                else:
                    coaching[field] = None
        else:
            coaching = {f: None for f in _COACHING_FIELDS}

        # Landed
        landed_raw = parsed.get("landed")
        landed = normalize_landed_signal(landed_raw) or "unclear"

        return {
            "review_addendum": add.strip(),
            "observation_bullets": bullets,
            "coaching": coaching,
            "landed": landed,
        }
    except json.JSONDecodeError:
        logger.warning("Gemini enrichment was not valid JSON: %.200s", cleaned)
        return _empty_enrichment()


def _empty_enrichment() -> dict[str, Any]:
    return {
        "review_addendum": "",
        "observation_bullets": [],
        "coaching": {f: None for f in _COACHING_FIELDS},
        "landed": "unclear",
    }

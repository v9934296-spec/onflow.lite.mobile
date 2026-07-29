"""
Gemini hallucination regression suite.

Purpose: enforce OnFlow's trust architecture at the AI layer. Each test here
guards against specific failure modes where Gemini fabricates detail that
wasn't in the clip. These tests run against LIVE Gemini (not mocked) because
the risk is prompt/model drift, which a mock cannot catch.

Pipeline under test matches production: primary analysis
(``analyze_clip_with_gemini``) plus enrichment (``GeminiReviewer.enrich``) for
``landed`` / coaching fields.

Run locally with::

    set GEMINI_REGRESSION_ENABLED=1
    set ONFLOW_GEMINI_API_KEY=...
    pytest tests/regression/test_gemini_hallucination.py -v

Skipped in CI unless ``GEMINI_REGRESSION_ENABLED=1`` is set, because each run
costs tokens. Recommended cadence: before every production deploy, and on any
change to the Gemini prompt or model version.

Each fixture is run ``REPEAT_COUNT`` times to catch variance-driven hallucination.
A single passing run is not proof of correctness at temperature > 0.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.core.tiers import normalize_tier, resolve_gemini_model_for_tier
from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.gemini_clip_analyzer import analyze_clip_with_gemini
from app.services.gemini_prompt import ClipAnalysisMetadata
from app.services.gemini_reviewer import GeminiReviewer

REGRESSION_ENABLED = os.getenv("GEMINI_REGRESSION_ENABLED") == "1"
REPEAT_COUNT = int(os.getenv("GEMINI_REGRESSION_REPEATS", "5"))
FIXTURES_DIR = Path(__file__).parent / "fixtures"
REGISTRY_PATH = FIXTURES_DIR / "registry.json"


def _load_registry() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.is_file():
        return []
    try:
        with REGISTRY_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("fixtures", [])
        return raw if isinstance(raw, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _load_clip_bytes(filename: str) -> bytes:
    path = FIXTURES_DIR / "clips" / filename
    if not path.is_file():
        pytest.skip(f"Fixture clip missing: {filename} (add under fixtures/clips/)")
    return path.read_bytes()


@dataclass
class RegressionGeminiResult:
    """Primary clip analysis + enrichment (landed / coaching), as in clip_worker."""

    primary: GeminiClipAnalysis
    enrichment: dict[str, Any]

    @property
    def landed(self) -> str | None:
        v = self.enrichment.get("landed")
        if isinstance(v, str) and v.strip().lower() in ("yes", "no", "unclear"):
            return v.strip().lower()
        return None

    @property
    def bail_description(self) -> str:
        """
        Narrative most likely to falsely describe stepping off / missing when the skater
        actually rolled away. Uses primary improvement areas + observation text (not metadata).
        """
        parts: list[str] = list(self.primary.improvement_areas)
        for obs in self.primary.observations:
            parts.append(f"{obs.title} {obs.detail}")
        return " ".join(parts).strip()

    @property
    def trick_name(self) -> str:
        """Compatibility shim: no model-emitted trick name; use empty (see trick_must_contain vs blob)."""
        return ""


def _resolve_path(result: RegressionGeminiResult, path: str) -> Any:
    parts = path.split(".")
    if not parts:
        return None
    if parts[0] == "primary":
        cur: Any = result.primary
        for p in parts[1:]:
            cur = getattr(cur, p, None)
            if cur is None:
                return None
        return cur
    if parts[0] == "enrichment":
        cur = result.enrichment
        for p in parts[1:]:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur
    return None


async def analyze_clip(clip_bytes: bytes, metadata: dict[str, Any], *, fixture_id: str) -> RegressionGeminiResult:
    """Run primary + enrichment on a clip file (bytes), matching production."""
    settings = get_settings()
    if not (settings.gemini_api_key or "").strip():
        pytest.skip("ONFLOW_GEMINI_API_KEY (or GEMINI_API_KEY) not set")

    suffix = ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(clip_bytes)
        video_path = tmp.name

    try:
        tricks_raw = metadata.get("tricks") or []
        tricks_list = tricks_raw if isinstance(tricks_raw, list) else []

        cam = ClipAnalysisMetadata.from_job_upload(
            video_path=video_path,
            clip_label=str(metadata.get("clip_label") or "untagged"),
            stance=str(metadata.get("stance") or ""),
            obstacle=str(metadata.get("obstacle") or ""),
            tricks=[str(t) for t in tricks_list if isinstance(t, str)],
            duration_seconds=metadata.get("duration_seconds")
            if metadata.get("duration_seconds") is not None
            else None,
            mime_type=str(metadata.get("mime_type") or "video/mp4"),
            first_pass_readiness=str(metadata.get("first_pass_readiness") or "usable"),
            technical_quality_summary=str(metadata.get("technical_quality_summary") or "none"),
        )
        tier = normalize_tier(str(metadata.get("account_tier") or "free"))
        primary = await analyze_clip_with_gemini(
            video_path,
            cam,
            settings=settings,
            job_id=f"regression-{fixture_id}",
            account_tier=tier,
        )
        model = resolve_gemini_model_for_tier(tier, settings)
        reviewer = GeminiReviewer(
            settings.gemini_api_key,
            model=model,
            inline_max_bytes=settings.gemini_inline_max_bytes,
        )
        enrichment = await reviewer.enrich(
            file_path=video_path,
            clip_label=str(metadata.get("clip_label") or "untagged"),
            clip_metadata={
                "stance": metadata.get("stance") or "",
                "obstacle": metadata.get("obstacle") or "",
                "tricks": tricks_list,
            },
        )
        return RegressionGeminiResult(primary=primary, enrichment=enrichment)
    finally:
        try:
            os.unlink(video_path)
        except OSError:
            pass


def _serialize_result(result: RegressionGeminiResult) -> str:
    payload = {
        "primary": result.primary.model_dump(mode="json"),
        "enrichment": result.enrichment,
    }
    return json.dumps(payload, ensure_ascii=False)


def _assert_contract(
    result: RegressionGeminiResult,
    contract: dict[str, Any],
    fixture_id: str,
    run: int,
) -> None:
    ctx = f"[{fixture_id} run={run}]"
    blob_all = _serialize_result(result).lower()

    if "landed_must_be" in contract:
        expected = contract["landed_must_be"]
        assert result.landed == expected, (
            f"{ctx} landed={result.landed!r}, expected {expected!r}. "
            f"Model misidentified roll-away state."
        )

    if contract.get("forbid_bail_when_landed") and result.landed == "yes":
        markers = contract.get("when_landed_forbid_substrings") or [
            "bailed",
            "fell off",
            "stepped off",
            "missed the landing",
            "didn't land",
            "did not land",
        ]
        for phrase in markers:
            if phrase.lower() in blob_all:
                raise AssertionError(
                    f"{ctx} Landed=yes but output contains disallowed phrase {phrase!r} "
                    f"(possible fabricated bail / miss narrative)."
                )
        if contract.get("forbid_bail_strict_primary_narrative", False):
            assert not result.bail_description.strip(), (
                f"{ctx} Landed=yes but primary improvement/observation narrative is non-empty "
                f"({result.bail_description[:200]!r}…). Check for hallucinated miss description."
            )

    for phrase in contract.get("forbidden_phrases", []):
        assert phrase.lower() not in blob_all, (
            f"{ctx} Output contained forbidden phrase {phrase!r}. "
            f"Model fabricated detail not agreed for this fixture."
        )

    for field in contract.get("must_be_null", []):
        value = _resolve_path(result, field)
        assert _is_nullish(value), (
            f"{ctx} Field {field!r} was {value!r}, expected null/empty. "
            f"Model invented detail for an unobservable field."
        )

    if "trick_must_contain" in contract:
        needle = contract["trick_must_contain"].lower()
        trick = (result.trick_name or "").lower()
        assert needle in trick or needle in blob_all, (
            f"{ctx} trick_name={trick!r} and output missing expected token {needle!r}."
        )

    for field in contract.get("required_fields", []):
        value = _resolve_path(result, field)
        assert value is not None, (
            f"{ctx} Missing or null required field {field!r}. Schema drift or empty response."
        )


def _is_nullish(v: Any) -> bool:
    if v is None or v == "":
        return True
    if isinstance(v, (list, tuple)) and len(v) == 0:
        return True
    if isinstance(v, dict):
        return all(_is_nullish(x) for x in v.values())
    return False


_REGISTRY = _load_registry()

# Pytest 8: ``@parametrize("fixture", [])`` × ``@parametrize("run", range(N))`` still
# collects N cases with a NOTSET sentinel. Build an explicit (fixture, run) grid instead.
_CONTRACT_PARAMS: list[Any] = [
    pytest.param(f, r, id=f"{f['id']}-run{r}")
    for f in _REGISTRY
    for r in range(REPEAT_COUNT)
]
if not _CONTRACT_PARAMS:
    _CONTRACT_PARAMS = [pytest.param(None, -1, id="registry-empty")]

_CONSISTENCY_FIXTURES = [f for f in _REGISTRY if f.get("consistency_check")]
_CONSISTENCY_PARAMS: list[Any] = [
    pytest.param(f, id=str(f.get("id", "unknown"))) for f in _CONSISTENCY_FIXTURES
]
if not _CONSISTENCY_PARAMS:
    _CONSISTENCY_PARAMS = [pytest.param(None, id="no-consistency-fixtures")]

pytestmark = [
    pytest.mark.skipif(
        not REGRESSION_ENABLED,
        reason="Set GEMINI_REGRESSION_ENABLED=1 to run (costs Gemini tokens).",
    ),
    pytest.mark.skipif(
        REGRESSION_ENABLED and len(_REGISTRY) == 0,
        reason="No fixtures in tests/regression/fixtures/registry.json — add entries and clip files.",
    ),
]


@pytest.mark.parametrize("fixture,run", _CONTRACT_PARAMS)
@pytest.mark.asyncio
async def test_fixture_against_contract(
    fixture: dict[str, Any] | None, run: int
) -> None:
    if fixture is None:
        pytest.skip("No fixtures in registry.json (placeholder row).")
    fid = str(fixture["id"])
    clip_bytes = _load_clip_bytes(str(fixture["clip"]))
    metadata = dict(fixture["metadata"])
    contract = dict(fixture["contract"])

    result = await analyze_clip(clip_bytes, metadata, fixture_id=fid)
    _assert_contract(result, contract, fid, run)


@pytest.mark.parametrize("fixture", _CONSISTENCY_PARAMS)
@pytest.mark.asyncio
async def test_output_consistency(fixture: dict[str, Any] | None) -> None:
    if fixture is None:
        pytest.skip("No fixtures with consistency_check in registry.")
    fid = str(fixture["id"])
    clip_bytes = _load_clip_bytes(str(fixture["clip"]))
    metadata = dict(fixture["metadata"])

    a = await analyze_clip(clip_bytes, metadata, fixture_id=fid)
    b = await analyze_clip(clip_bytes, metadata, fixture_id=fid)

    assert a.landed == b.landed, (
        f"[{fid}] landed flipped between runs: {a.landed} -> {b.landed}. "
        f"Slot-machine failure mode."
    )

    needle = fixture.get("contract", {}).get("trick_must_contain")
    if isinstance(needle, str) and needle.strip():
        n = needle.lower()
        blob_a = _serialize_result(a).lower()
        blob_b = _serialize_result(b).lower()
        assert n in blob_a and n in blob_b, (
            f"[{fid}] trick token {needle!r} not stable across runs."
        )

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _gemini_regression_live(request: pytest.FixtureRequest) -> bool:
    """Live Gemini + token cost — opt-in via GEMINI_REGRESSION_ENABLED=1."""
    return (
        os.getenv("GEMINI_REGRESSION_ENABLED") == "1"
        and "test_gemini_hallucination" in request.node.nodeid
    )


@pytest.fixture(autouse=True)
def _stub_gemini_analyze_for_contract_tests(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Completed jobs require AI analysis; API contract tests stay offline by stubbing analyzers.
    Real Gemini calls remain in test_gemini_integration.py and regression/hallucination tests only.
    """
    if "test_gemini_integration" in request.node.nodeid or _gemini_regression_live(request):
        yield
        return
    from app.schemas.gemini_analysis import GeminiClipAnalysis
    from app.services import gemini_clip_analyzer, twelvelabs_clip_analyzer
    from tests.test_gemini_prompt_pack import SAMPLE_GOOD

    async def _fake_gemini(*_a: object, **_kw: object) -> GeminiClipAnalysis:
        return GeminiClipAnalysis.model_validate(SAMPLE_GOOD)

    async def _fake_twelvelabs(*_a: object, **_kw: object) -> tuple[GeminiClipAnalysis, str]:
        return GeminiClipAnalysis.model_validate(SAMPLE_GOOD), "stub-asset-id"

    monkeypatch.setattr(gemini_clip_analyzer, "analyze_clip_with_gemini", _fake_gemini)
    monkeypatch.setattr(twelvelabs_clip_analyzer, "analyze_clip_with_twelvelabs", _fake_twelvelabs)
    yield


@pytest.fixture(autouse=True)
def _generous_clip_abuse_limits_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Slowapi clip caps default to 10/hour — many tests initiate multiple uploads."""
    monkeypatch.setenv("ONFLOW_CLIP_RATE_LIMIT_PER_HOUR", "10000")
    monkeypatch.setenv("ONFLOW_CLIP_RATE_LIMIT_PER_DAY", "10000")
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _generous_auth_route_limits_for_contract_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Session/claim slowapi limits default to 5/min — many tests POST /auth/session via fixtures
    and would exhaust a shared IP bucket across the suite.
    """
    monkeypatch.setenv("ONFLOW_AUTH_RATE_LIMIT_PER_MINUTE", "10000")
    monkeypatch.setenv("ONFLOW_AUTH_RATE_LIMIT_PER_HOUR", "100000")


@pytest.fixture(autouse=True)
def _no_real_gemini_in_contract_tests(request: pytest.FixtureRequest) -> None:
    """
    Contract tests must stay fast and offline. If a dev machine has provider keys set,
    clip jobs would otherwise call Gemini or Twelve Labs.
    Integration and hallucination regression tests opt out of this.
    """
    if "test_gemini_integration" in request.node.nodeid or _gemini_regression_live(request):
        yield
        return
    prev_gemini = os.environ.get("ONFLOW_GEMINI_API_KEY")
    prev_tl = os.environ.get("ONFLOW_TWELVELABS_API_KEY")
    os.environ["ONFLOW_GEMINI_API_KEY"] = ""
    os.environ["ONFLOW_TWELVELABS_API_KEY"] = ""
    try:
        yield
    finally:
        if prev_gemini is None:
            os.environ.pop("ONFLOW_GEMINI_API_KEY", None)
        else:
            os.environ["ONFLOW_GEMINI_API_KEY"] = prev_gemini
        if prev_tl is None:
            os.environ.pop("ONFLOW_TWELVELABS_API_KEY", None)
        else:
            os.environ["ONFLOW_TWELVELABS_API_KEY"] = prev_tl


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    test_db = tmp_path / "test.db"
    monkeypatch.setenv("ONFLOW_ENV", "development")
    monkeypatch.setenv("ONFLOW_DATABASE_URL", f"sqlite:///{test_db.as_posix()}")
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_RATE_LIMIT_FREE", "10000")
    import app.core.database as database_module

    database_module._engine = None
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    application = create_app()
    with TestClient(application) as c:
        yield c


@pytest.fixture
def authed_client(client: TestClient) -> TestClient:
    """Client with a dev Bearer token (no JWT secret required)."""
    client.headers["Authorization"] = "Bearer dev:test-user-001"
    return client


@pytest.fixture
def admin_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client signed in as admin (direct DB grant for dev email-session fixtures)."""
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "admin-fixture@onflow.test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    r = client.post(
        "/api/v1/auth/session",
        json={"email": "admin-fixture@onflow.test"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    db = client.app.state.db
    user = db.get_user(body["user_id"])
    assert user is not None
    user.is_admin = True
    with db._sf() as session:
        session.add(user)
        session.commit()
    client.headers["Authorization"] = f"Bearer {body['session_token']}"
    return client


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    r = client.post(
        "/api/v1/auth/session",
        json={"email": "beta-contract@onflow.test"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_valid_mp4_bytes(tmp_path: Path) -> bytes:
    """Tiny real MP4 for OpenCV-readable contract tests (requires opencv in env)."""
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    path = tmp_path / "clip.mp4"
    w, h = 64, 48
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(path), fourcc, 12.0, (w, h))
    assert out.isOpened(), "OpenCV VideoWriter unavailable"
    for i in range(45):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (55, 110, 160)
        x0 = 8 + (i % 20)
        cv2.rectangle(frame, (x0, 12), (x0 + 12, 28), (240, 240, 240), -1)
        out.write(frame)
    out.release()
    return path.read_bytes()


_UPLOAD_INIT_BODY = {
    "duration_seconds": 4.5,
    "width_px": 1080,
    "height_px": 1920,
    "content_type": "video/mp4",
}


def write_presigned_upload(client: TestClient, storage_key: str, data: bytes) -> None:
    dest = Path(client.app.state.upload_dir) / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def submit_clip_via_presigned(
    client: TestClient,
    headers: dict[str, str],
    *,
    video_bytes: bytes = b"fake-mp4-bytes",
    client_hint_trick_id: str | None = None,
) -> str:
    """Initiate presigned upload, write bytes locally, complete — returns job/clip id."""
    payload = {
        **_UPLOAD_INIT_BODY,
        "size_bytes": max(len(video_bytes), 1),
    }
    if client_hint_trick_id:
        payload["client_hint_trick_id"] = client_hint_trick_id
    r = client.post("/api/v1/clips/initiate-upload", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    clip_id = body["clip_id"]
    write_presigned_upload(client, body["storage_key"], video_bytes)
    cr = client.post(f"/api/v1/clips/{clip_id}/complete-upload", headers=headers)
    assert cr.status_code == 200, cr.text
    return clip_id


def wait_for_terminal_job(
    client: TestClient,
    job_id: str,
    headers: dict[str, str],
    *,
    timeout_s: float = 15.0,
) -> dict:
    import time

    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        gr = client.get(f"/api/v1/clips/jobs/{job_id}", headers=headers)
        assert gr.status_code == 200, gr.text
        last = gr.json()
        if last["status"] in ("completed", "failed"):
            return last
        time.sleep(0.05)
    return last

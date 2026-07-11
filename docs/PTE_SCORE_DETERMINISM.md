# OnFlow Build Doc — Score Determinism & Re-Analysis
### (P.T.E. Manifesto principles 3, 4, 8 — enforcement in code)

**API:** `services/api`
**Problem:** the same clip uploaded twice must never produce two different results. The system is made deterministic: same content + same engine version = same stored answer, by construction.
**Ship before launch** — version stamps can't be retrofitted onto unstamped history.

**Honest scope note (principle 1 applies to our own claims too):** normalization-based hashing dedups identical files, container remuxes, metadata/orientation differences, and makes our own pipeline idempotent. It does **not** unify third-party re-encodes (Discord, Instagram exports) — those contain different pixels and hash differently. We don't claim otherwise. Perceptual hashing could catch those but introduces false-positive risk; out of scope by decision, not oversight.

---

## Part 1 — Migration: hashes, component versions, registry

**File:** `services/api/alembic/versions/xxxx_determinism.py`

```python
"""determinism: content hashes, engine versioning, registry

Revision ID: fill_in_generated
Revises: fill_in_previous
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # ── engine version registry (why each version exists) ──────────
    op.create_table(
        "engine_versions",
        sa.Column("version", sa.String(64), primary_key=True),   # e.g. pte-1.0.0
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("ruleset_version", sa.String(64), nullable=False),
        sa.Column("pipeline_version", sa.String(64), nullable=False),
        sa.Column("build_manifest", sa.Text(), nullable=False),  # JSON: exact normalization params
        sa.Column("released_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("author", sa.String(128), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("benchmark_ref", sa.String(255), nullable=True),
    )

    # ── analyses columns ────────────────────────────────────────────
    op.add_column("analyses", sa.Column("upload_hash", sa.String(64), nullable=True))
    op.add_column("analyses", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("analyses", sa.Column("engine_version", sa.String(64), nullable=True))
    op.add_column("analyses", sa.Column("is_rerun", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("analyses", sa.Column("supersedes_id", sa.Integer(), nullable=True))
    op.add_column("analyses", sa.Column("resolved_to_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_analyses_engine_version", "analyses", "engine_versions",
                          ["engine_version"], ["version"])
    op.create_index("ix_analyses_upload_hash", "analyses", ["user_id", "upload_hash"])
    op.create_index("ix_analyses_dedup", "analyses", ["user_id", "content_hash", "engine_version"])
    op.create_index(
        "uq_analyses_canonical",
        "analyses",
        ["user_id", "content_hash", "engine_version"],
        unique=True,
        postgresql_where=sa.text("is_rerun = false AND content_hash IS NOT NULL"),
    )

    # ── media metadata (orientation, duration, fps — for UI, not for dedup) ──
    op.create_table(
        "media_metadata",
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id"), primary_key=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("rotation", sa.Integer(), nullable=True),  # 0/90/180/270 from ffprobe
    )

    # ── dedup / cost metrics ────────────────────────────────────────
    op.create_table(
        "dedup_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),  # 'upload' | 'content' | 'rerun'
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table("dedup_events")
    op.drop_table("media_metadata")
    op.drop_index("uq_analyses_canonical", table_name="analyses")
    op.drop_index("ix_analyses_dedup", table_name="analyses")
    op.drop_index("ix_analyses_upload_hash", table_name="analyses")
    op.drop_constraint("fk_analyses_engine_version", "analyses", type_="foreignkey")
    op.drop_column("analyses", "resolved_to_id")
    op.drop_column("analyses", "supersedes_id")
    op.drop_column("analyses", "is_rerun")
    op.drop_column("analyses", "engine_version")
    op.drop_column("analyses", "content_hash")
    op.drop_column("analyses", "upload_hash")
    op.drop_table("engine_versions")
```

Hashes stay hex `String(64)` deliberately: greppable in logs, pasteable in URLs, debuggable at 2am. BYTEA would save 32 bytes/row — irrelevant at our scale, and opacity costs more than it saves. Revisit only if the table ever hits tens of millions of rows.

---

## Part 2 — Version constants (semver + components + build manifest)

**File:** `services/api/app/pte/version.py` (new)

```python
"""Single source of truth for engine versioning.

Semver rules:
  MAJOR — scoring behavior changes for existing clips (model swap, rubric
          weight change, rules logic change). Requires fresh accuracy +
          stability benchmark AND a registry entry BEFORE deploy.
  MINOR — new capability, existing scores unaffected (new trick support,
          new observation type). Registry entry required.
  PATCH — bugfix with no scoring effect. Registry entry required.

The composite ENGINE_VERSION is what gets stamped on every analysis row.
Component versions live in the registry row for debugging: when pte-1.3.0
misbehaves, the registry says whether it was the prompt, the model, the
rules, or the pipeline that moved.

build_manifest is the JSON-serialized normalization params. Stored in the
registry so a future engineer can see exactly what produced a given
content_hash without reconstructing from git history.
"""
import json

MODEL_VERSION = "pegasus-1.2"
PROMPT_VERSION = "prompt-1"
RULESET_VERSION = "rules-1"
PIPELINE_VERSION = "pipe-1"

# Canonical normalization params. ANY change here is a PIPELINE_VERSION bump.
NORMALIZATION = {
    "fps": 30,
    "height": 720,
    "vcodec": "libx264",
    "preset": "medium",
    "crf": 23,
    "pix_fmt": "yuv420p",
    "strip_audio": True,
    "strip_metadata": True,
}

ENGINE_VERSION = "pte-1.0.0"
BUILD_MANIFEST = json.dumps(NORMALIZATION, sort_keys=True)
```

**Deploy-time guard** — a version that isn't in the registry cannot score clips, and the registry's `build_manifest` must match the code:

```python
from app.pte.version import ENGINE_VERSION, BUILD_MANIFEST

async def verify_engine_version_registered(db_session_factory):
    from app.models import EngineVersion
    async with db_session_factory() as db:
        row = await db.get(EngineVersion, ENGINE_VERSION)
        if row is None:
            raise RuntimeError(
                f"ENGINE_VERSION {ENGINE_VERSION} has no engine_versions registry entry. "
                "Write the entry (change_reason, benchmark_ref) before deploying. "
                "Manifesto principle 4: no version ships without its own benchmark."
            )
        if row.build_manifest != BUILD_MANIFEST:
            raise RuntimeError(
                f"ENGINE_VERSION {ENGINE_VERSION} registry build_manifest drifted from code. "
                f"Registry: {row.build_manifest!r}  Code: {BUILD_MANIFEST!r}. "
                "Either bump PIPELINE_VERSION + registry, or fix the mismatch."
            )
```

Registry entries are written at release time:

```sql
INSERT INTO engine_versions
  (version, model_version, prompt_version, ruleset_version, pipeline_version,
   build_manifest, author, change_reason, benchmark_ref)
VALUES
  ('pte-1.0.0', 'pegasus-1.2', 'prompt-1', 'rules-1', 'pipe-1',
   '{"crf": 23, "fps": 30, "height": 720, "pix_fmt": "yuv420p", "preset": "medium", "strip_audio": true, "strip_metadata": true, "vcodec": "libx264"}',
   'vincent',
   'Initial production engine. Pegasus primary after 300-run validation (0 false feedback vs 37-45% Gemini).',
   'benchmarks/2026-06-pegasus-300run');
```

---

## Part 3 — Request path: fast raw-hash dedup only

**No ffmpeg on the request path.** Normalization is expensive (300s timeout, CPU-bound). It belongs in the worker, where it runs once per unique content and the result is cached by `content_hash`.

**File:** `services/api/app/routers/analyze.py` — upload endpoint:

```python
from app.pte.normalize import sha256_file
from app.pte.version import ENGINE_VERSION
from app.models import Analysis, DedupEvent


def _dedup_response(db, user_id: int, existing: Analysis, kind: str):
    db.add(DedupEvent(user_id=user_id, analysis_id=existing.id, kind=kind))
    db.commit()
    return {
        "analysis_id": existing.id,
        "status": existing.status,
        "deduplicated": True,
        "engine_version": existing.engine_version,
    }


# ── inside the endpoint, after the file is saved to a temp path ────

# Stage 1 ONLY: raw-bytes hash — catches double-tap / retry instantly
upload_hash = sha256_file(tmp_upload_path)
raw_dup = (
    db.query(Analysis)
    .filter(
        Analysis.user_id == user.id,
        Analysis.upload_hash == upload_hash,
        Analysis.engine_version == ENGINE_VERSION,
        Analysis.is_rerun.is_(False),
    )
    .first()
)
if raw_dup is not None:
    return _dedup_response(db, user.id, raw_dup, "upload")

# Fresh upload: store raw artifact, enqueue worker for normalize + content dedup
analysis = Analysis(
    user_id=user.id,
    upload_hash=upload_hash,
    content_hash=None,          # worker fills this after normalization
    engine_version=ENGINE_VERSION,
    is_rerun=False,
    status="queued",
    # ...storage_key for raw upload, trick_called, etc.
)
db.add(analysis)
db.commit()
await enqueue_analysis_job(analysis.id)
return {"analysis_id": analysis.id, "status": "queued", "deduplicated": False}
```

---

## Part 4 — Worker path: normalize, content-hash dedup, analyze

**File:** `services/api/app/workers/analyze_worker.py` (adapt to real worker entry)

```python
from sqlalchemy.exc import IntegrityError
from app.pte.normalize import normalize_clip, sha256_file, probe_metadata
from app.pte.version import ENGINE_VERSION
from app.models import Analysis, DedupEvent, MediaMetadata


def _canonical(db, user_id: int, content_hash: str):
    return (
        db.query(Analysis)
        .filter(
            Analysis.user_id == user_id,
            Analysis.content_hash == content_hash,
            Analysis.engine_version == ENGINE_VERSION,
            Analysis.is_rerun.is_(False),
        )
        .first()
    )


async def process_analysis(analysis_id: int, db):
    analysis = db.get(Analysis, analysis_id)

    # Normalize the raw upload → canonical artifact
    norm_path, content_hash = normalize_clip(analysis.raw_storage_key)

    # Stage 2: content-hash dedup — catches remuxes, metadata-stripped re-uploads
    content_dup = _canonical(db, analysis.user_id, content_hash)
    if content_dup is not None:
        analysis.resolved_to_id = content_dup.id
        analysis.status = "deduplicated"
        db.add(DedupEvent(user_id=analysis.user_id, analysis_id=content_dup.id, kind="content"))
        db.commit()
        os.remove(norm_path)
        return  # no Pegasus call

    # Fresh canonical content: store normalized artifact, run Pegasus
    analysis.content_hash = content_hash
    analysis.storage_key = upload_normalized(norm_path)  # R2 key for canonical artifact

    meta = probe_metadata(norm_path)
    db.add(MediaMetadata(
        analysis_id=analysis.id,
        duration_ms=meta.duration_ms,
        fps=meta.fps,
        width=meta.width,
        height=meta.height,
        rotation=meta.rotation,
    ))

    try:
        db.commit()
    except IntegrityError:
        # Race: concurrent identical content won the partial unique index
        db.rollback()
        winner = _canonical(db, analysis.user_id, content_hash)
        analysis.resolved_to_id = winner.id
        analysis.status = "deduplicated"
        db.add(DedupEvent(user_id=analysis.user_id, analysis_id=winner.id, kind="content"))
        db.commit()
        os.remove(norm_path)
        return

    # Run Pegasus on the normalized artifact
    result = await run_pegasus(analysis.storage_key, analysis.trick_called)
    analysis.status = "complete"
    # ...write score, observations, evidence class, etc.
    db.commit()
    os.remove(norm_path)
```

**File:** `services/api/app/pte/normalize.py` (new)

```python
"""Canonical clip normalization. Every clip passes through here in the
worker before Pegasus. The normalized artifact is what gets hashed,
stored, and analyzed — so content_hash is a fingerprint of the engine's
actual input."""
import hashlib
import json
import subprocess
import tempfile
import os
from dataclasses import dataclass

from app.pte.version import NORMALIZATION

CHUNK = 1024 * 1024


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_stream(file_obj) -> str:
    """Hash an upload stream without writing to disk first."""
    h = hashlib.sha256()
    while True:
        chunk = file_obj.read(CHUNK)
        if not chunk:
            break
        h.update(chunk)
    file_obj.seek(0)
    return h.hexdigest()


@dataclass
class ProbeResult:
    duration_ms: int
    fps: float
    width: int
    height: int
    rotation: int  # 0/90/180/270


def probe_metadata(path: str) -> ProbeResult:
    """Extract display metadata via ffprobe. Does NOT affect content_hash."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", path,
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    data = json.loads(out.stdout)
    stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    # rotation from side_data or tags — adapt to ffprobe output shape
    rotation = 0  # parse from stream.get("tags", {}).get("rotate", 0)
    return ProbeResult(
        duration_ms=int(float(data["format"]["duration"]) * 1000),
        fps=eval(stream["r_frame_rate"]),  # "30/1" → 30.0
        width=int(stream["width"]),
        height=int(stream["height"]),
        rotation=int(rotation) % 360,
    )


def normalize_clip(src_path: str) -> tuple[str, str]:
    """Normalize to canonical form. Returns (normalized_path, content_hash).
    Caller owns cleanup of the returned file."""
    fd, out_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    n = NORMALIZATION
    vf = f"scale=-2:{n['height']},fps={n['fps']}"
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-vf", vf,
        "-c:v", n["vcodec"], "-preset", n["preset"], "-crf", str(n["crf"]),
        "-pix_fmt", n["pix_fmt"],
    ]
    if n["strip_audio"]:
        cmd += ["-an"]
    if n["strip_metadata"]:
        cmd += ["-map_metadata", "-1"]
    cmd += ["-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    return out_path, sha256_file(out_path)
```

Railway note: the **worker** image needs ffmpeg (`nixpacks.toml` / Dockerfile: `apt-get install -y ffmpeg`). The API image does not.

---

## Part 5 — Explicit re-analysis (principle 8)

```python
@router.post("/analyses/{analysis_id}/rerun")
async def rerun_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    original = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == user.id)
        .first()
    )
    if original is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    rerun = Analysis(
        user_id=user.id,
        upload_hash=original.upload_hash,
        content_hash=original.content_hash,
        storage_key=original.storage_key,      # same normalized clip in R2
        trick_called=original.trick_called,
        engine_version=ENGINE_VERSION,
        is_rerun=True,
        supersedes_id=original.id,
        status="queued",
    )
    db.add(rerun)
    db.add(DedupEvent(user_id=user.id, analysis_id=original.id, kind="rerun"))
    db.commit()
    db.refresh(rerun)
    await enqueue_analysis_job(rerun.id)

    return {
        "analysis_id": rerun.id,
        "is_rerun": True,
        "supersedes_id": original.id,
        "original_engine_version": original.engine_version,
        "rerun_engine_version": ENGINE_VERSION,
    }
```

**Display rules (mobile):** every result shows its stamp (`ANALYZED · PTE 1.0.0`, Space Mono eyebrow). Re-runs render alongside originals, labeled, never replacing. Progression charts use canonical results; mixing engine versions on one trend line requires a visible version-boundary marker. A same-version re-run that differs from its original is a variance measurement for us, not a new truth for the user — the original remains canonical.

---

## Part 6 — Cache-hit / cost metrics

**File:** `services/api/app/routers/metrics.py` (new; protect behind admin auth)

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import DedupEvent, Analysis
from app.auth.jwt import require_admin  # adapt

router = APIRouter(prefix="/api/v1/admin/metrics", tags=["metrics"])

PEGASUS_COST_PER_ANALYSIS_USD = 0.042
AVG_INFERENCE_SECONDS = 18.0


@router.get("/dedup")
async def dedup_metrics(db: Session = Depends(get_db), _=Depends(require_admin)):
    counts = dict(
        db.query(DedupEvent.kind, func.count(DedupEvent.id))
        .group_by(DedupEvent.kind)
        .all()
    )
    upload_hits = counts.get("upload", 0)
    content_hits = counts.get("content", 0)
    reruns = counts.get("rerun", 0)
    total_hits = upload_hits + content_hits
    fresh = db.query(func.count(Analysis.id)).filter(Analysis.is_rerun.is_(False)).scalar() or 0

    return {
        "dedup_hits_upload": upload_hits,
        "dedup_hits_content": content_hits,
        "reruns": reruns,
        "fresh_analyses": fresh,
        "hit_rate": round(total_hits / (total_hits + fresh), 4) if (total_hits + fresh) else 0.0,
        "pegasus_dollars_saved": round(total_hits * PEGASUS_COST_PER_ANALYSIS_USD, 2),
        "inference_seconds_saved": round(total_hits * AVG_INFERENCE_SECONDS, 1),
    }
```

---

## Part 7 — CI stability gate (scores AND explanations)

A stable score with a flip-flopping explanation is still a broken engine — the observations feed the rubric and the user reads them. Both are benchmarked per engine version.

**File:** `services/api/scripts/benchmark_stability.py` (new)

```python
"""Run each benchmark clip N times through the current engine version.
Measures: score variance, abstention consistency, trick-classification
consistency, stance consistency, and observation-set stability (Jaccard).

Gate: an ENGINE_VERSION bump does not ship unless this passes alongside
the accuracy benchmark. Registry benchmark_ref should point at this run.

Usage: python -m scripts.benchmark_stability --runs 5
"""
import argparse
import asyncio
import statistics
from collections import Counter
from app.pte.version import ENGINE_VERSION
from app.pte.pipeline import analyze_clip_for_benchmark
from scripts.benchmark_clips import BENCHMARK_CLIPS

MAX_SCORE_STDEV = 0.25
MIN_OBS_JACCARD = 0.80


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


async def main(runs: int) -> None:
    print(f"Stability benchmark · engine {ENGINE_VERSION} · {runs} runs/clip\n")
    failures = 0

    for clip in BENCHMARK_CLIPS:
        results = [await analyze_clip_for_benchmark(clip.path, clip.trick_called) for _ in range(runs)]
        problems: list[str] = []

        abstained = sum(1 for r in results if r.score is None)
        if abstained not in (0, runs):
            problems.append(f"inconsistent abstention ({abstained}/{runs})")

        rated = [r for r in results if r.score is not None]

        if len(rated) > 1:
            stdev = statistics.stdev([r.score for r in rated])
            if stdev > MAX_SCORE_STDEV:
                problems.append(f"score stdev {stdev:.3f} > {MAX_SCORE_STDEV}")

        tricks = Counter(r.trick_detected for r in results)
        if len(tricks) > 1:
            problems.append(f"trick classification unstable: {dict(tricks)}")

        stances = Counter(r.stance_detected for r in results)
        if len(stances) > 1:
            problems.append(f"stance unstable: {dict(stances)}")

        obs_sets = [set(o.key for o in r.observations) for r in results]
        pairwise = [
            jaccard(obs_sets[i], obs_sets[j])
            for i in range(len(obs_sets))
            for j in range(i + 1, len(obs_sets))
        ]
        if pairwise and min(pairwise) < MIN_OBS_JACCARD:
            problems.append(f"observation overlap {min(pairwise):.2f} < {MIN_OBS_JACCARD}")

        if problems:
            failures += 1
            print(f"FAIL  {clip.id}: " + "; ".join(problems))
        else:
            note = f"abstained {runs}/{runs}" if abstained == runs else f"scores={[r.score for r in rated]}"
            print(f"OK    {clip.id}: {note}")

    print(f"\n{'PASS' if failures == 0 else 'FAIL'} — {failures} clip(s) unstable")
    raise SystemExit(0 if failures == 0 else 1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=5)
    args = p.parse_args()
    asyncio.run(main(args.runs))
```

Wire into CI:

```yaml
# .github/workflows/ci.yml — add after unit tests
- name: Stability benchmark gate
  run: python -m scripts.benchmark_stability --runs 5
  env:
    DATABASE_URL: ${{ secrets.BENCHMARK_DB_URL }}
    TWELVELABS_API_KEY: ${{ secrets.TWELVELABS_API_KEY }}
```

Requires the pipeline result object to expose `trick_detected`, `stance_detected`, and structured `observations[].key` — if any are missing, close that gap before shipping, because structured observations are also what principle 6 depends on.

---

## Acceptance criteria

- [ ] ffmpeg present in the **worker** image; `normalize_clip` produces identical bytes for the same input run twice
- [ ] Migration applied: two hash columns, semver `engine_version` FK, `engine_versions` registry with `build_manifest`, `media_metadata`, `dedup_events`, partial unique index, `resolved_to_id`
- [ ] Registry row exists for `pte-1.0.0` with change_reason and benchmark_ref; **startup guard refuses to boot on an unregistered version or build_manifest drift**
- [ ] Same file uploaded twice → `deduplicated: true`, kind=`upload`, ffmpeg not run the second time
- [ ] Same content re-uploaded as a remuxed/metadata-stripped copy → worker resolves to canonical via `content_hash`, kind=`content`
- [ ] Concurrent identical uploads → one canonical row, IntegrityError path returns the winner
- [ ] Rerun creates labeled row with `supersedes_id`; original byte-for-byte unmodified; mobile renders both with version stamps
- [ ] `/admin/metrics/dedup` returns hit counts, hit rate, dollars and seconds saved
- [ ] `benchmark_stability.py` passes on `pte-1.0.0`; wired into CI next to the accuracy benchmark
- [ ] Grep confirms `ENGINE_VERSION` and component versions referenced only from `app/pte/version.py`

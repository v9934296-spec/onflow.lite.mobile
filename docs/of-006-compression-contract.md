# OF-006 — Compression contract verification (EXP-001)

**Phase:** 0 contract verification  
**Spec names:** EXP-001 · §7.5 · §8.2 · §11.2 · §16.3 EXP-001 · §16 order of work item 4 · §18 gate item 7 · Q&A 11  
**Not:** quota, session-end, intelligence, attempt-sync, Capture chrome, R2 credentials, rewriting a compressor because APIs “look suspicious”

Status: **Open / device-blocked.** Steps 1–2 are done. Stop here until the launch iPhone exists.

Do **not** add an encoder, pick a bitrate, resolve the compression-failure “ceilings” ambiguity, or normalize initiate 100 MB vs complete 200 MiB while waiting.

The static finding already stands: the launch client **does not satisfy §7.5** because there is no compress-before-initiate derivative. The device matrix does not reopen that decision. It answers what iOS actually writes so Step 4 can choose the **smallest** correct export.

**Phase 0 is not complete.** §18 gate item 7 remains open. Do not mark the spec Approved.
**Spec authority on pass-through:** §7.5 says **“Compress before `initiate-upload`.”** Temp storage describes an app-private **derivative** deleted after successful complete. Failure fallback uploads the **original** only if compression **fails** and that original already meets the ceilings. That is not “compress only as needed.” Native camera output happening to look like H.264/1080 is **not** a substitute for the export stage, and it is **not** a reason to leave compression unimplemented. Device measurement still decides *what the encoder must emit* (bitrate, whether 4K is downscaled in practice, etc.). It does not waive the missing stage.
---

## Why this is OF-006

| Ticket | Role |
|--------|------|
| OF-005 | Session-end + ended-session uploads — **closed** (production) |
| **OF-006** | **Client media contract measured on a physical iPhone** |

§16 order of work item 4: measure compression physically. §18 gate item 7: compression contract measured and filled. Q&A 11 remains OPEN until that measurement exists.

---

## Operational carry-forward (OF-005)

`clips.captured_at` and Alembic `20260824_clips_captured_at.py` **must deploy together.** This ticket does not apply that migration.

---

## Two kinds of proof (do not mix them)

### A. Code-inspectable (this repo + launch client, no device)

These can be answered by reading functions. They are **not** a substitute for rows in the device matrix.

| Requirement | Spec | Where to inspect |
|-------------|------|------------------|
| Accepted input MIME | `video/mp4` or `video/quicktime` | Server `ClipInitiateUploadRequest`; launch `OutboxRow.mimeType`; lite `resolveMimeType` |
| Max duration 30s | §7.5 / initiate `le=30` | Server schema; launch `compressionContract.maxDurationSeconds` + `rejectIfOverCeiling`; lite ImagePicker `videoMaxDuration: 15` |
| Max upload 100 MB | §7.5 / initiate `le=100MB` | Server initiate schema; launch `maxBytes`; complete-upload uses `clip_max_upload_bytes` (**default 200 MiB** — inspect, do not silently equate to 100 MB) |
| Export target H.264 | §7.5 | Candidate in `compression.ts` only unless an encoder call exists |
| Long edge ≤1080p | §7.5 | Candidate `longEdgePx`; initiate may send constants, not probed size |
| Frame rate ≤60 fps | §7.5 | Candidate `maxFps` only unless an encoder call exists |
| Audio survives | §7.5 | Camera `mute={false}` is not proof of the **uploaded** file |
| Location stripped | §7.5 | `stripLocation: true` unused unless a strip step exists |
| One recompress then reject | §7.5 | Copy `clip_too_large` vs an actual second encode |
| Compression/export failure behavior | §7.5 fallback | Offer original iff it already meets ceilings; never upload a server-reject |
| Imports untouched | §11.2 | Outbox holds a URI; no write-back to the library |

### B. Physical-device proofs (required to close)

For each matrix row, record **source properties → exported/upload bytes → accepted or rejected**, by probing the file that would be PUT (not the constant object).

Use `ffprobe` (or equivalent) on that file: codec, long-edge px, avg fps, audio stream present, GPS/location atoms (`©xyz`, `com.apple.quicktime.location.ISO6709`, etc.). Then the real initiate/complete (or documented reject) result.

Native output is evidence of **what the camera writes today**. It does not satisfy §7.5’s required compress-before-initiate stage.
---

## Device matrix (minimum — not 10 identical sunlight clips)

Spec EXP-001 asked for ten 30s outdoor clips to lock bitrate. That is still useful for Q&A 11 if 6 Mbps is in doubt. **This ticket’s required matrix is smaller and more diagnostic:**

| # | Source (deliberate) | Why |
|---|---------------------|-----|
| 1 | ~1080p / 30 fps, with audio | Baseline export |
| 2 | ~1080p / 60 fps, with audio | fps cap; no interpolation |
| 3 | 4K / 60 fps | long-edge downscale or honest native output |
| 4 | Any of the above with a known audio track | audio must still be on the **upload** file |
| 5 | A source that **forces** the size path (long 4K/60 or similar, aiming >100 MB before/after first encode) | one recompress then reject; no out-of-contract PUT |

Add a library **import** of row 3 or 5 to prove the original camera-roll file is unmodified (§11.2).

Table columns for each row:

`source {codec, long_edge, fps, audio, bytes, gps?} → export {same} → client decision {upload / reject / recompress-once} → server {201/complete / 4xx}`

Optional extra: if rows 1–2 are ≪100 MB, you do not need ten copies to “confirm 6 Mbps.” Lock or change `targetBitrateBps` only from measured bytes, not from 6×30s arithmetic.

---

## Sources of truth

1. Build spec §7.5, §8.2 ceilings, §11.2, EXP-001, Q&A 11  
2. Launch client: `onflow-v1/src/domain/compression.ts`, `app/capture.tsx`, `src/store/enqueueClip.ts`, `src/store/upload.ts`, `src/ui/copy/errors.ts`  
3. Lite (this repo): [`app/capture.tsx`](../app/capture.tsx), [`src/api/clipApi.ts`](../src/api/clipApi.ts)  
4. Server: [`schemas/clips.py`](../services/api/app/schemas/clips.py), [`clip_v1_pipeline.py`](../services/api/app/services/clip_v1_pipeline.py) `_verify_upload_object`

---

## Forced sequence

1. **Static map** — done (this document)  
2. **Spec comparison** — done (Step 2 table)  
3. **Five-row device matrix** — **blocked** on launch iPhone; probe the file `runOutboxRow` would PUT  
4. **Minimum remediation** — only after the matrix: one preset vs special 4K/60, measured bitrate, one-recompress path  
5. Closeout — then DOC-001. Phase 0 stays incomplete until OF-006 closes.

**Pinned, out of OF-006 media work:** initiate **100 MB** vs complete default **200 MiB**. Do not casually set them equal while adding export. Either a later spec pin (both 100 MB) or a separate, narrowly scoped correction.---

## Step 1 — Static map (working tree / launch client)

No encoder rewrite from this map. Constants are a candidate.

### Surfaces

| Surface | Capture | What is uploaded |
|---------|---------|------------------|
| **Launch client** (`onflow-v1`) | `CameraView.recordAsync({ maxDuration: 30 })` or ImagePicker library | `outbox.localUri` as-is via `FileSystem.uploadAsync` |
| **OnFlow Lite** (this repo) | ImagePicker camera/library, `videoMaxDuration: 15`, `quality: 1` | picker `asset.uri` as-is |

There is **no** compression function, ffmpeg, bitrate argument, GPS strip, or second-pass encode in either tree.

### Path (launch)

```text
recordAsync / library pick
  → enqueueClip (duration > 30s → return null, no error UI)
  → runOutboxRow
       rejectIfOverCeiling: duration → failed_permanent clip_too_long
                            size     → failed_permanent clip_too_large
       (no encode between reject and PUT)
  → initiate-upload (width/height sent as 1080/1080 constants, not probed)
  → PUT localUri
  → complete-upload
```

Library finish always sets `mimeType: "video/mp4"` even if the asset is QuickTime.

### Path (lite)

```text
ImagePicker (15s UI cap)
  → read size/duration/width/height from the asset
  → initiate + PUT original URI (signed-in + active session)
  → or local engine.ts (unsigned)
```

Lite does **not** client-check 30s or 100 MB (15s picker is the only duration cap). Oversize library files can hit server initiate 422.

### Server

- Initiate: `content_type` ∈ mp4|quicktime; `duration_seconds` ∈ (0, 30]; `size_bytes` ∈ (0, 100 MB]  
- Complete: object exists; non-empty; magic-byte `looks_like_video`; **`clip_max_upload_bytes` default 200 MiB** (not 100 MB); then quota + enqueue  
- Worker later: `video_readable` — staging check for device rows, not pytest sniff bytes

### Failure / recompress (inspectable)

| Event | Launch behavior |
|-------|-----------------|
| Duration > 30s at enqueue | `enqueueClip` returns `null` (silent) |
| Duration > 30s at outbox run | `clip_too_long` / Film again |
| Size > 100 MB | `clip_too_large` copy says “even after compression” — **no compression ran** |
| Encode failure | **No encode step**, so §7.5 “upload original if already in ceiling” is unimplemented |
| Second bitrate pass | Unimplemented (docs candidate 4 Mbps) |

§11.2: imported URI is referenced; nothing in-repo writes back to the camera roll. Device must still prove the library file’s bytes are unchanged.

---

## Step 2 — Every EXP-001 / §7.5 bullet vs the map

Labels: **Satisfied** (code encodes the contract) · **Device-unverified** (path exists or native output might already do it; PUT file not probed) · **Real gap** (required stage or behavior is missing) · **Spec ambiguity** (spec text does not uniquely decide).

**Pass-through rule (spec, not Expo):** §7.5 happy path is compress/export **before** initiate. Pass-through of the original is the **failure fallback** when compression fails and the original already meets ceilings. EXP-001 protocol step 2 is “Encode H.264 MP4…”. Accidental native compliance does not close those bullets.

| Bullet | Spec text | Map | Verdict |
|--------|-----------|-----|---------|
| Accepted input MP4 / QuickTime | §8.2 `content_type` | Server Literal both; lite maps quicktime; launch library finish hardcodes `video/mp4` | **Satisfied** on server. Launch library MIME **Real gap** (mislabeled MOV). Device-unverified what `recordAsync` actually produces |
| Max duration 30s | §7.5 / initiate `le=30` | Launch `rejectIfOverCeiling` + enqueue; server initiate. Lite picker 15s | **Satisfied** (launch + server). Lite 15s is a different surface, not EXP-001 |
| Max size 100 MB at initiate | §7.5 / initiate `le=100MB` | Launch `maxBytes`; server initiate | **Satisfied** |
| Complete-upload size gate | not 100 MB in §7.5 | `clip_max_upload_bytes` default **200 MiB** | **Spec ambiguity / contract inconsistency** — initiate blocks >100 MB first so a normal launch client cannot complete a 150 MB object; the two gates are not the same product number |
| Container / codec H.264 MP4 | §7.5 launch value; EXP-001 “Encode H.264 MP4” | Candidate constant only; PUT is camera/picker bytes | **Real gap** (no export stage). Codec of native PUT file is **Device-unverified** |
| Long edge ≤1080p, never upscale | §7.5 | No scaler; initiate sends 1080×1080 constants | **Real gap**. Native long edge is **Device-unverified** (4K camera would fail the ceiling if uploaded as-is) |
| Bitrate 6 Mbps | §7.5 candidate; Q&A 11 OPEN; EXP-001 measure | Constant `6_000_000`; no encoder | **Real gap** (no encode). Target value **Device-unverified** until PUT bytes exist. **Spec ambiguity**: 6 Mbps is labeled UNVERIFIED candidate, not a locked launch number |
| Frame rate preserve ≤60, never interpolate | §7.5 | No fps clamp | **Real gap**. Native fps **Device-unverified** |
| Orientation / rotation metadata | §7.5 | No re-encode, so rotation atoms would pass through if present | **Device-unverified** (and **Spec ambiguity** once an encoder exists: must copy rotation, not bake wrong orientation) |
| Audio preserved | §7.5; confirm Phase 0 | Camera `mute={false}`; no export | **Device-unverified** on the PUT file. **Real gap** if export is added without copying audio |
| Location stripped before upload | §7.5 | `stripLocation` unused | **Real gap** |
| Temp / derivative deleted after complete | §7.5 | No derivative | **Real gap** (nothing to delete). Imports must not be that derivative (§11.2) |
| Compress before initiate | §7.5 prose | Validation then PUT original | **Real gap** |
| Failure fallback: original iff in ceiling; never silent server-reject | §7.5 | No compressor, so fallback never runs; size/duration reject exists | **Real gap** for the fallback. Size/duration “never upload over ceiling” is **Satisfied** at initiate. **Spec ambiguity**: “ceilings” = 30s/100MB only vs full H.264/1080/stripped original |
| 30s still >100 MB: recompress once, then reject | §7.5; EXP-001 4 Mbps candidate | Copy claims “even after compression”; no second pass | **Real gap** |
| Engine still reads (`video_readable`) | EXP-001 | Staging, not pytest | **Device-unverified** (needs PUT file on staging) |
| Imports never modified | §11.2 | Outbox URI only | **Satisfied** in code (no write-back). Byte-identity of the roll file is **Device-unverified** |
| Progress from observed bytes; outbox before first byte | §7.5 | Launch outbox then PUT | **Satisfied** (launch). Not EXP-001 encode proof |
| Foreground only at launch | §7.5 | Not mapped as encode | Out of EXP-001 encode scope |

**Do not implement an encoder until Step 3 is filled and Step 4 chooses the minimum remediation.**

---

## Freeze — resume only with PUT-file evidence

When the launch iPhone is available, capture the **exact file** `runOutboxRow` would PUT (today: `outbox.localUri` / camera or picker file). Not JS `width`/`height`/`duration`.

Per matrix row, keep enough evidence to answer:

| Probe | Why |
|-------|-----|
| Codec | H.264 vs whatever iOS wrote |
| Dimensions / long edge | ≤1080 vs 4K pass-through |
| Frame rate | ≤60; no interpolation |
| Audio stream | Survives |
| File size | vs 100 MB |
| Container | MP4 vs QuickTime |
| Location metadata | GPS atoms present or absent |
| Staging `video_readable` | Engine can still read it |

Library-import row: also prove OnFlow did **not** alter the original camera-roll asset (byte identity / timestamps as appropriate).

Rows: 1080p/30 · 1080p/60 · 4K/60 · audio · oversize/recompress candidate · plus import of 3 or 5.

Then **Step 4**: smallest remediation from that evidence + §7.5 (one export preset enough? 4K/60 special? bitrate that survives skate footage? what the one-recompress pass does). Still no bitrate guess and no 100/200 “cleanup.”

---

## Step 3 — Device matrix (blocked)

Empty until those PUT files exist. This environment cannot film or `ffprobe` them.---

## Out of scope

Reopening OF-002–005; OF-005 migration deploy; Gemini/quota; inventing 6 Mbps without measured PUT bytes; **normalizing 100 MB initiate vs 200 MiB complete in this ticket**; expanding to ten identical park clips unless Q&A 11 is still ambiguous after rows 1–2.

---

## Definition of done

- Steps 1–2 frozen as written  
- Five-row device matrix filled from the **PUT file** (plus import original unchanged)  
- Step 4 minimum export implemented only from that evidence + §7.5  
- `targetBitrateBps` locked or still candidate from measured bytes — not from 6×30s arithmetic  
- **100 MB initiate vs 200 MiB complete still unresolved here** (or closed by a separate ticket)  
- Lite vs launch named; Railway unverified; OF-005 migration still a deploy pair  
- **Phase 0 not complete** until this ticket closes (§18 item 7)---

## What comes after

**DOC-001** (remaining UNVERIFIED / §18.3). Then Phase 1.

Review AI-generated scene videos for quality.

Usage: `/fk-review-video <video_id> [--mode light|deep] [--by cli|muse]`

Default mode: `light`. Default reviewer: `cli` (whatever the `video_review`
role points at in `agent/providers.json`).

## Reviewer backends

- **`cli`** (default): `POST /api/videos/<VID>/review` shells out to the
  configured `video_review` role provider. Needs the CLI binary on PATH.
- **`muse`** (official provider): the server builds contact sheets
  (`POST /api/videos/<VID>/review-sheets`), Muse reads them with vision and
  scores each scene, then submits (`POST /api/videos/<VID>/review-submit`).
  Works everywhere — no CLI, no API key. Select it with
  `/fk-change-provider set muse`.

## Prerequisites

- `ffmpeg` + `ffprobe` installed
- Scenes must have completed videos (`${ori}_video_status = COMPLETED`)
- (`cli` only) the review CLI installed; (`muse`) nothing extra

## Step 1: Pre-check

```bash
# Verify server is up (extension NOT required for review)
curl -s http://127.0.0.1:8100/health

# Verify video exists
curl -s http://127.0.0.1:8100/api/videos/<VID>
```

**ABORT** if the server is down or the video is not found.

## Step 2: Check scenes have completed videos

```bash
curl -s "http://127.0.0.1:8100/api/scenes?video_id=<VID>"
```

For each scene, verify `${ori}_video_status = COMPLETED` (orientation auto-detected from meta.json).

**ABORT** if any scene is missing a completed video — tell user to run `/fk-gen-videos` first.

## Step 3a: Self review (`--by muse`)

You — the agent running this skill (Muse, Codex, or agy) — score the sheets
by hand with your own vision. The provider key is `muse` for historical
reasons; it means "me, the agent". Build the contact sheets — no AI CLI
involved:

```bash
curl -s -X POST "http://127.0.0.1:8100/api/videos/<VID>/review-sheets" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<PID>", "mode": "light"}' | python3 -m json.tool
# → {sheets: [{scene_id, sheets: ["/abs/path/sheet_1.jpg", ...],
#               n_frames, fps, prompt (rubric), scene_prompt, ...}]}
```

Sheets persist under `<output>/<slug>/review/sheets/<scene_id>/`. **Read each
sheet image with vision** and score the scene against the rubric in `prompt`:
6 dimensions (0.0–10.0), errors with severity (CRITICAL/HIGH/MINOR) +
time_range + description, usable_segments. Be strict on CRITICAL errors
(character morph, breed swap, role reversal, brand logo, wrong count) —
any CRITICAL caps character_consistency at 3.0 and the verdict below
acceptable.

Submit the scores — the server applies the same validation, severity rules,
and caps as the CLI backend:

```bash
curl -s -X POST "http://127.0.0.1:8100/api/videos/<VID>/review-submit" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<PID>", "mode": "light", "scores": [
    {"scene_id": "<SID>", "n_frames": 32, "fps": 4.0,
     "dimensions": {"character_consistency": 8.0, "prompt_adherence": 7.5,
                    "motion_quality": 7.0, "visual_fidelity": 8.0,
                    "temporal_coherence": 7.5, "composition": 8.0},
     "errors": [{"severity": "MINOR", "time_range": "5s-6s",
                 "description": "background signage garbles"}],
     "usable_segments": [{"time_range": "0s-8s", "score": 8.0}]}
  ]}' | python3 -m json.tool
```

To auto-regenerate bad scenes from your hand scores (bounded by
`max_regenerations` per scene), pass the same `scores` array to
`POST /api/videos/<VID>/review-regenerate`.

## Step 3b: CLI review (default, `--by cli`)

```bash
curl -X POST "http://127.0.0.1:8100/api/videos/<VID>/review?project_id=<PID>&mode=light&orientation=${ORI}"
```

**Parameters:**
- `mode`: `light` (default) or `deep`
- `orientation`: auto-detected from meta.json (`${ORI}`)

The API extracts frames from each scene video, sends them to the configured
review CLI, and returns per-scene quality scores.

## Step 4: Interpret results

The response is an array of per-scene review objects:

```json
[
  {
    "scene_id": "abc-123",
    "display_order": 0,
    "total_score": 8.5,
    "dimensions": {
      "character_consistency": 9.0,
      "prompt_adherence": 8.5,
      "motion_quality": 8.0,
      "visual_fidelity": 8.5,
      "temporal_coherence": 8.0,
      "composition": 9.0
    },
    "errors": ["Slight motion blur at 4s mark"],
    "fix_guide": "Acceptable as-is. If re-generating, add 'sharp focus, crisp motion' to prompt.",
    "usable": true,
    "verdict": "good",
    "usable_segments": [
      {"start": "0s", "end": "4s", "score": 9.0},
      {"start": "5s", "end": "8s", "score": 8.5}
    ]
  }
]
```

### Scoring Dimensions

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Character Consistency | 25% | Characters match refs across frames |
| Prompt Adherence | 20% | Video matches prompt description |
| Motion Quality | 20% | Smooth motion, no artifacts |
| Visual Fidelity | 15% | Resolution, clarity, no banding |
| Temporal Coherence | 10% | Consistent lighting/shadows across frames |
| Composition | 10% | Framing matches camera direction |

`total_score = sum(dimension_score * weight)`

### Verdict Scale

| Score | Verdict | Action |
|-------|---------|--------|
| 9.0–10.0 | Excellent | Ship as-is |
| 7.5–8.9 | Good | Usable, minor polish optional |
| 6.0–7.4 | Acceptable | Cut usable segments, regen weak parts |
| 4.0–5.9 | Poor | Regen scene image first, then video |
| 0–3.9 | Unusable | Rewrite prompt + regen from scratch |

Errors in the `errors` array are prefixed with severity: `[CRITICAL]`, `[HIGH]`, or `[MINOR]`. Any `[CRITICAL]` error forces the scene into the 0–3.9 range regardless of other dimensions. See **Known AI Video Errors** section below.

## Step 5: Act on results

### Poor / Unusable scenes
Regenerate the scene image first, then the video:
```bash
# Force-regenerate scene image (cascades video + upscale)
curl -X POST http://127.0.0.1:8100/api/requests \
  -H "Content-Type: application/json" \
  -d '{"type": "REGENERATE_IMAGE", "scene_id": "<SID>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "${ORI}"}'
```
Then run `/fk-gen-videos <PID> <VID>` after image is complete.

### Acceptable with good segments
Note `usable_segments` time ranges for manual editing. Use `/fk-concat` and trim in post.

### Character drift (low `character_consistency`)
- Verify all entity ref images have `media_id` (UUID format)
- Use `EDIT_IMAGE` to re-anchor character appearance:
  ```bash
  curl -X POST http://127.0.0.1:8100/api/requests \
    -H "Content-Type: application/json" \
    -d '{"type": "EDIT_IMAGE", "scene_id": "<SID>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "${ORI}"}'
  ```

### After fixes
Run review again to verify improvements:
```bash
curl -X POST "http://127.0.0.1:8100/api/videos/<VID>/review?project_id=<PID>&mode=deep"
```

## Modes

- **light** (default): 4 frames/second → 32 frames per 8s video. Fast, good for initial scan to identify problem scenes.
- **deep**: 8 frames/second → 64 frames per 8s video. Thorough, catches subtle artifacts and motion issues. Use before final export.

## Output Summary

Print a table after review completes:

```
Scene | Order | Score | Verdict    | Errors | Usable Segments
------|-------|-------|------------|--------|----------------
s-1   | 0     | 8.5   | good       | 1      | 2s-4s(9.0), 6s-8s(8.5)
s-2   | 1     | 6.2   | acceptable | 2      | 3s-5s(7.0)
s-3   | 2     | 9.1   | excellent  | 0      | full
s-4   | 3     | 3.8   | unusable   | 5      | none
...
Total: 6.9/10 | 4 scenes reviewed | 0 skipped
```

Then print recommended actions:
- Excellent/Good → "Ready for `/fk-concat <VID>`"
- Acceptable → "Note usable segments, trim in post"
- Poor/Unusable → "Run `/fk-gen-images <PID> <VID>` to regenerate, then `/fk-gen-videos <PID> <VID>`"

## Known AI Video Errors

Battle-tested error catalog. Claude Vision flags these in the `errors` array with severity prefix.

### CRITICAL (Auto-fail, score 0–3)

| # | Error | Description | When it happens |
|---|-------|-------------|-----------------|
| 1 | Character Drift | Character morphs mid-video (extra limbs, breed changes) | Common after 3–4s |
| 2 | Breed Swap | Similar characters get mixed up | Common in multi-character scenes |
| 3 | Role Reversal | Wrong character performs the action | ~50% of action scenes |
| 4 | Brand Logo | AI generates real brand logos | Any scene with objects/signage |
| 5 | Character Count | Wrong number of characters rendered | Crowd or paired scenes |

Any CRITICAL error → scene scores 0–3.9 (Unusable). Rewrite prompt + regen from scratch.

### HIGH (Needs trim/regen, score 4–6)

| # | Error | Description | When it happens |
|---|-------|-------------|-----------------|
| 6 | Camera Drift | Sudden unwanted zoom or rotation | ~60% of scenes after 4s |
| 7 | Object Morph | Held items change shape mid-video | Action scenes with props |
| 8 | Reverse Motion | Character does then undoes the action | ~30% of motion scenes |
| 9 | Human Hands | Anthropomorphic characters get human hands | Animal/creature characters |
| 10 | Scale Break | Characters change size relative to environment | Dynamic movement scenes |

HIGH errors → note `usable_segments` before the error timestamp. Trim or regen.

### MINOR (Acceptable, score 7–8)

| # | Error | Description |
|---|-------|-------------|
| 11 | Prop Count | Small props change in number |
| 12 | Clothing Detail | Texture or pattern shifts |
| 13 | Background Blur | Garbled signage or background text |
| 14 | Accessory Loss | Small items (earrings, accessories) appear/disappear |

MINOR errors → acceptable for most use cases. Polish optional.

### Automatic Prompt Healing (Self-Correction Loop for Scores < 7.5)

In compliance with **Critical Rule 16**, any scene scoring below 7.5 undergoes automated diagnostic healing and regeneration (capped at 2 cycles):

1. **Extract Error Vectors from the `errors` Array:**
   - If error contains `Camera Drift`: Append `locked-off static camera, subtle smooth tracking` to the camera sentence.
   - If error contains `Character Drift`: Append `strictly preserves identical facial bone structure and eye color from reference`.
   - If error contains `Object/Anatomy Morph`: Append `natural realistic anatomy, five distinct fingers, rigid solid weapon hilt`.
   - If error contains `Reverse Motion / Jerk`: Append `continuous linear motion, fluid steady trajectory without backward hitch`.

2. **Update Scene via PATCH (Rule 13):**
   ```bash
   curl -X PATCH http://127.0.0.1:8100/api/scenes/<SID> \
     -H "Content-Type: application/json" \
     -d '{"video_prompt": "<healed_video_prompt>"}'
   ```

3. **Dispatch REGENERATE_VIDEO Request:**
   ```bash
   curl -X POST http://127.0.0.1:8100/api/requests \
     -H "Content-Type: application/json" \
     -d '{"type": "REGENERATE_VIDEO", "scene_id": "<SID>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "${ORI}"}'
   ```

---

## Cost Note


Each scene review = 1 Claude Vision API call with N frames.
- Light mode (32 frames/scene): ~$0.01–0.03 per scene
- Deep mode (64 frames/scene): ~2x light mode cost

Reviewing a full video (10 scenes, deep) ≈ 10 API calls. Review light first, then deep only on scenes flagged as poor/acceptable.

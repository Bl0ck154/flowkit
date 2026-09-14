# Gemini Omni Flash: integration guide for agents

FlowKit exposes Gemini Omni Flash video generation through the authenticated Google Flow session in its persistent Chrome profile. An integrating service talks only to the FlowKit REST API; it must not call Google Flow endpoints or the extension WebSocket directly.

## Prerequisites and base URL

Before submitting work, both checks must pass:

```bash
curl -fsS "$FLOWKIT_BASE_URL/health"
curl -fsS "$FLOWKIT_BASE_URL/api/flow/status"
```

Expected state on the migrated Flow transport:

```json
{"status":"ok","extension_connected":true}
{"connected":true,"transport":"batch","authenticated":true,"at_token_present":true}
```

Use `http://127.0.0.1:8100` when the caller runs on the FlowKit host. For a remote integration, set `FLOWKIT_BASE_URL` to the protected HTTPS reverse-proxy URL and allow only the required source IPs or private network. Do not expose Chrome, VNC/noVNC, the extension WebSocket, or port 8100 publicly.

## Supported modes

On the current `flow.google.com` batch transport, every Omni 1.1 Flash video mode exposed by Flow's Video composer is supported and live-verified:

| Mode | Batch status | Endpoint | Current wire |
|---|---|---|---|
| Text to video | **supported** | `POST /api/flow/generate-video-omni-text` | `YhhmEf` + `abra_t2v_<duration>s` |
| First frame to video | **supported** | `POST /api/flow/generate-video` with `model_family=omni_flash` | `eb1hJf` + `abra_i2v_<duration>s` |
| First + Last frame to video | **supported** | `POST /api/flow/generate-video` with `model_family=omni_flash` + `end_image_media_id` | `nprQif` + `omni_flash_i2v_<duration>s_first_last` |
| Ingredients / references to video | **supported** | `POST /api/flow/generate-video-omni` or `/generate-video-refs` | `MZZa6b` + `abra_r2v_<duration>s` |

Reference-conditioned modes support durations `4`, `6`, `8`, and `10` seconds, resolutions `360p` and `720p`, and:

- `VIDEO_ASPECT_RATIO_PORTRAIT` (`9:16`)
- `VIDEO_ASPECT_RATIO_LANDSCAPE` (`16:9`)

For 360p Flow uses `_360p` model variants. The 360p first-frame and Ingredients payloads also carry the same low-resolution option slots captured from the live UI. First+Last uses its dedicated `nprQif` payload and model family.

The migrated wires were re-captured from the live Flow UI on 2026-09-14. Live API smoke tests completed successfully for First frame, First+Last, and Ingredients/R2V and resolved signed `flow-content.google` video URLs through the batch operation poller.

Polling differs only for text-to-video: text-to-video returns `flowkitPolling.mode=batch_media` and uses `/api/flow/check-omni-status`; all image/reference-conditioned modes return `flowkitPolling.mode=batch_operation` and use `/api/flow/check-status` with their `operations` array.

## End-to-end integration flow

1. Check `/health` and `/api/flow/status`.
2. Submit the desired Omni mode.
3. Persist the complete `flowkitPolling` object returned by the submit before doing anything else.
4. If `mode=batch_media`, poll `/api/flow/check-omni-status` using `project_id` + `workflows`.
5. If `mode=batch_operation`, poll `/api/flow/check-status` using `project_id` + `operations`.
6. Continue on pending state; stop on failure; on success immediately download the signed video URL.
7. Store the downloaded video in durable storage because Google URLs are signed and short-lived.

Example text-to-video submit:

```bash
curl -fsS -X POST "$FLOWKIT_BASE_URL/api/flow/generate-video-omni-text" \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "A small red paper boat gently drifts across a calm pond",
    "project_id": "FLOW_PROJECT_ID",
    "duration_s": 4,
    "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE"
  }'
```

Do not convert workflow names into operation handles, and do not convert batch operation handles into workflow names. Persist and replay the polling descriptor exactly as FlowKit returns it.

## Supplying images

Frame, First+Last, and Ingredients/R2V all consume Flow media IDs. Upload or reuse the reference images first, then pass their media IDs to the generation endpoint.

`POST /api/flow/upload-image` is not a multipart upload endpoint. Its `file_path` is an absolute path on the **FlowKit server**, not on the calling server.

For a remote integration, first stage the file on the FlowKit host using an authenticated transfer such as SFTP/SCP, a private shared volume, or a separately secured upload service. Use a unique per-job directory, validate file size/type, and make the file readable by the FlowKit service account. Then call:

```bash
curl -fsS -X POST "$FLOWKIT_BASE_URL/api/flow/upload-image" \
  -H 'Content-Type: application/json' \
  -d '{
    "file_path": "/var/lib/flowkit/input/JOB_ID/start.jpg",
    "project_id": "FLOW_PROJECT_ID",
    "file_name": "start.jpg"
  }'
```

Response:

```json
{"media_id":"FLOW_MEDIA_ID","raw":{}}
```

Use the returned `media_id` in generation requests. Never pass a caller-local path such as `/tmp/image.jpg` unless that exact file also exists on the FlowKit server.

## Prompts

The input images define identity, appearance, objects, and composition. The prompt should primarily describe motion, camera behavior, timing, and audio/dialogue. Avoid restating a person's detailed appearance when reference images already provide it.

Example:

```text
The woman turns naturally toward the camera, smiles, then raises one leg into the final pose. Subtle handheld camera movement, realistic cloth and hair motion, stable face and body proportions.
```

For longer clips, timed instructions are useful, for example: `0-3s: ...; 3-6s: ...; 6-8s: ...`.

## First frame to video

```bash
curl -fsS -X POST "$FLOWKIT_BASE_URL/api/flow/generate-video" \
  -H 'Content-Type: application/json' \
  -d '{
    "model_family": "omni_flash",
    "start_image_media_id": "START_MEDIA_ID",
    "prompt": "The subject looks toward the camera and smiles; subtle cinematic push-in, natural motion.",
    "project_id": "FLOW_PROJECT_ID",
    "scene_id": "JOB_ID",
    "duration_s": 4,
    "resolution": "720p",
    "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
    "user_paygate_tier": "PAYGATE_TIER_ONE"
  }'
```

This uses batch RPC `eb1hJf` with `abra_i2v_<duration>s` (or the `_360p` variant).

## First + Last frame to video

```bash
curl -fsS -X POST "$FLOWKIT_BASE_URL/api/flow/generate-video" \
  -H 'Content-Type: application/json' \
  -d '{
    "model_family": "omni_flash",
    "start_image_media_id": "START_MEDIA_ID",
    "end_image_media_id": "END_MEDIA_ID",
    "prompt": "The subject moves naturally from the first pose to the final pose; stable identity and smooth realistic motion.",
    "project_id": "FLOW_PROJECT_ID",
    "scene_id": "JOB_ID",
    "duration_s": 4,
    "resolution": "720p",
    "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
    "user_paygate_tier": "PAYGATE_TIER_ONE"
  }'
```

This uses batch RPC `nprQif` with the dedicated `omni_flash_i2v_<duration>s_first_last` model family.

## References to video

Use 1-7 media IDs. Reference images act as components/identity/style guidance; they are not treated as fixed first and last frames.

```bash
curl -fsS -X POST "$FLOWKIT_BASE_URL/api/flow/generate-video-omni" \
  -H 'Content-Type: application/json' \
  -d '{
    "reference_media_ids": ["REFERENCE_MEDIA_ID_1", "REFERENCE_MEDIA_ID_2"],
    "prompt": "Cinematic handheld shot with natural character motion and consistent referenced subjects.",
    "project_id": "FLOW_PROJECT_ID",
    "scene_id": "JOB_ID",
    "duration_s": 4,
    "resolution": "720p",
    "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
    "user_paygate_tier": "PAYGATE_TIER_ONE"
  }'
```

The compatible generic endpoint is `POST /api/flow/generate-video-refs` with the same fields plus `"model_family":"omni_flash"`. Both routes use batch RPC `MZZa6b`.

## Submit response and polling

Image/reference-conditioned Omni submits return normal batch operation polling:

```json
{
  "operations": [
    {"operation":{"name":"OPERATION_ID"},"status":"MEDIA_GENERATION_STATUS_PENDING"}
  ],
  "model": "abra_r2v_4s",
  "duration_s": 4,
  "resolution": "720p",
  "flowkitPolling": {
    "mode": "batch_operation",
    "project_id": "FLOW_PROJECT_ID",
    "operations": [
      {"operation":{"name":"OPERATION_ID"},"status":"MEDIA_GENERATION_STATUS_PENDING"}
    ]
  }
}
```

Poll that descriptor without transforming it:

```bash
curl -fsS -X POST "$FLOWKIT_BASE_URL/api/flow/check-status" \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "FLOW_PROJECT_ID",
    "operations": [
      {"operation":{"name":"OPERATION_ID"},"status":"MEDIA_GENERATION_STATUS_PENDING"}
    ]
  }'
```

When complete, the operation contains the generated media ID and signed video URL:

```json
{
  "operations": [
    {
      "operation": {
        "name": "OPERATION_ID",
        "metadata": {
          "video": {
            "mediaId": "MEDIA_ID",
            "fifeUrl": "https://flow-content.google/video/..."
          }
        }
      },
      "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL"
    }
  ]
}
```

Text-to-video remains the exception: it returns `mode=batch_media` with workflow/media descriptors and is polled through `/api/flow/check-omni-status`.

## Retry and failure policy

- HTTP `400`: request/contract error. Do not retry unchanged input.
- HTTP `503`: Chrome extension is disconnected. Pause submission and alert or retry health checks with bounded backoff.
- HTTP `502`: Flow/bridge failure. Retry a small bounded number of times with exponential backoff; preserve the original workflow descriptor.
- Poll result `PENDING`: poll again after 10-20 seconds. Do not submit the generation again.
- Poll result `FAILED`: stop polling and surface the workflow error.
- `COMPLETED` with a null URL or `url_error`: poll again to obtain a fresh signed URL; do not regenerate the video.

Submission is credit-consuming and is not guaranteed to be idempotent. Never blindly retry a timed-out submit unless the integration can determine that no workflow was created.

## Model configuration

Mappings live in `agent/models.json`:

```json
{
  "omni_flash_models": {
    "frame_to_video": {
      "4": "abra_i2v_4s",
      "6": "abra_i2v_6s",
      "8": "abra_i2v_8s",
      "10": "abra_i2v_10s"
    },
    "start_end_frame_to_video": {
      "4": "abra_i2v_4s",
      "6": "abra_i2v_6s",
      "8": "abra_i2v_8s",
      "10": "abra_i2v_10s"
    },
    "reference_to_video": {
      "4": "abra_r2v_4s",
      "6": "abra_r2v_6s",
      "8": "abra_r2v_8s",
      "10": "abra_r2v_10s"
    }
  }
}
```

The legacy mappings above remain for the pre-migration transport. On the migrated batch transport, current Flow wire names are derived from duration + resolution exactly as live-captured: First frame uses `abra_i2v_*`, First+Last uses `omni_flash_i2v_*_first_last`, and Ingredients uses `abra_r2v_*`, with `_360p` appended for 360p. The mappings can still be changed through `PATCH /api/models` for legacy transport if Google rotates old keys. Treat configured credit-cost estimates as informational only: Google can change pricing, so use `GET /api/flow/credits` and the submit response's `remainingCredits` where available.

## Minimal agent checklist

- Use the `/api/flow/...` paths exactly.
- Select Omni explicitly with `model_family: "omni_flash"` on shared endpoints.
- Upload inputs once and reuse returned Flow media IDs.
- Persist the entire returned `flowkitPolling` descriptor before polling.
- Use `/check-status` for `batch_operation` and `/check-omni-status` for `batch_media`; never transform one receipt type into the other.
- Download signed output URLs immediately into durable project storage.
- Do not log Google auth data, extension messages, or complete signed URLs.
- Use a stable `scene_id`/job ID for traceability.
- Start with 4 seconds for smoke tests to limit credit usage.

Omni Flash is an unofficial integration over Google Flow's internal interfaces. Endpoints, model keys, and response shapes may change when Flow changes; integrations should fail visibly and retain job metadata for diagnosis.

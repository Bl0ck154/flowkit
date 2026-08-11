# Gemini Omni Flash

FlowKit can submit Gemini Omni Flash reference-to-video jobs through the same authenticated Chrome extension bridge used by the existing Google Flow integrations.

## Supported in this integration

- Reference-to-video with 1–7 reference images
- Portrait (`9:16`) and landscape (`16:9`)
- 4, 6, 8, and 10 second generations
- Workflow/media polling via each submit response's `primaryMediaId`
- Existing Google Flow account / paygate tier handling

First + last frame interpolation is intentionally not enabled for Omni Flash here.

## Important: Omni does not use legacy Veo polling

Do **not** take the operation-looking handle returned by an Omni submit and send it to the legacy `batchCheckAsyncVideoGenerationStatus` path. Google Flow can reject that with `INVALID_ARGUMENT`.

Omni Flash submits are workflow-backed. The submit response includes `workflows[].metadata.primaryMediaId`; FlowKit normalizes those into:

```json
{
  "flowkitPolling": {
    "mode": "workflow_media",
    "workflows": [
      {
        "name": "<WORKFLOW_NAME>",
        "primary_media_id": "<PRIMARY_MEDIA_ID>"
      }
    ]
  }
}
```

Poll those workflow descriptors through `POST /flow/check-omni-status`, or pass them as `workflows` to the generic `POST /flow/check-status` endpoint.

## REST API

### Submit Omni Flash

```bash
curl -X POST http://127.0.0.1:8100/flow/generate-video-omni \
  -H 'Content-Type: application/json' \
  -d '{
    "reference_media_ids": ["<FLOW_MEDIA_ID>"],
    "prompt": "Cinematic handheld shot, natural motion and dialogue",
    "project_id": "<FLOW_PROJECT_ID>",
    "duration_s": 10,
    "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
    "user_paygate_tier": "PAYGATE_TIER_ONE"
  }'
```

Keep `flowkitPolling.workflows` from the response.

### Poll Omni status

```bash
curl -X POST http://127.0.0.1:8100/flow/check-omni-status \
  -H 'Content-Type: application/json' \
  -d '{
    "workflows": [
      {
        "name": "<WORKFLOW_NAME>",
        "primary_media_id": "<PRIMARY_MEDIA_ID>"
      }
    ]
  }'
```

Equivalent generic form:

```bash
curl -X POST http://127.0.0.1:8100/flow/check-status \
  -H 'Content-Type: application/json' \
  -d '{
    "workflows": [
      {
        "name": "<WORKFLOW_NAME>",
        "primary_media_id": "<PRIMARY_MEDIA_ID>"
      }
    ]
  }'
```

While rendering, FlowKit returns `status: "PENDING"`. Once `/v1/media/<primaryMediaId>` exposes a complete MP4 payload, it returns `MEDIA_GENERATION_STATUS_SUCCESSFUL` and the media ID. Set `include_encoded_video: true` in the poll request only if you actually need the base64 MP4 inline; by default FlowKit avoids returning that large payload.

### Backward-compatible reference endpoint

Existing Veo callers do not need to change. To opt into Omni Flash, add `model_family` and `duration_s`:

```json
{
  "reference_media_ids": ["<FLOW_MEDIA_ID>"],
  "prompt": "Natural cinematic motion",
  "project_id": "<FLOW_PROJECT_ID>",
  "scene_id": "scene-1",
  "model_family": "omni_flash",
  "duration_s": 8,
  "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
  "user_paygate_tier": "PAYGATE_TIER_ONE"
}
```

Submit this body to `POST /flow/generate-video-refs`. Omni responses from this endpoint also include `flowkitPolling.workflows`.

## Model keys

The duration-to-model mapping lives in `agent/models.json` under `omni_flash_models.reference_to_video`:

```json
{
  "4": "abra_r2v_4s",
  "6": "abra_r2v_6s",
  "8": "abra_r2v_8s",
  "10": "abra_r2v_10s"
}
```

The values can be updated through `PATCH /api/models` if Google rotates Flow's internal model keys.

## Notes

Omni Flash is an unofficial Google Flow integration and the underlying internal model keys/endpoints can change as Flow evolves. The submit and polling shapes mirror the workflow-backed Omni implementation used by `crisng95/flowboard`: `batchAsyncGenerateVideoReferenceImages` for submit, then `/v1/media/<primaryMediaId>` for completion polling.

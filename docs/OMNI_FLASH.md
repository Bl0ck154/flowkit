# Gemini Omni Flash

FlowKit can submit Gemini Omni Flash video jobs through the same authenticated Chrome extension bridge used by the existing Google Flow integrations.

## Supported in this integration

- First frame → video
- First + Last frame → video
- Reference-to-video with 1–7 reference images
- Portrait (`9:16`) and landscape (`16:9`)
- 4, 6, 8, and 10 second generations
- Workflow/media polling via each submit response's `primaryMediaId`
- Existing Google Flow account / paygate tier handling

## First frame / First + Last

The existing `POST /flow/generate-video` endpoint remains backward compatible: requests use Veo unless `model_family` is explicitly set to `omni_flash`.

### First frame

```bash
curl -X POST http://127.0.0.1:8100/flow/generate-video \
  -H 'Content-Type: application/json' \
  -d '{
    "start_image_media_id": "<START_MEDIA_ID>",
    "prompt": "Natural cinematic motion, keep the subject consistent",
    "project_id": "<FLOW_PROJECT_ID>",
    "scene_id": "scene-1",
    "model_family": "omni_flash",
    "duration_s": 8,
    "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
    "user_paygate_tier": "PAYGATE_TIER_ONE"
  }'
```

This submits through `batchAsyncGenerateVideoStartImage` with the configured `abra_i2v_<duration>s` key.

### First + Last frame

Add `end_image_media_id` to the same request:

```bash
curl -X POST http://127.0.0.1:8100/flow/generate-video \
  -H 'Content-Type: application/json' \
  -d '{
    "start_image_media_id": "<START_MEDIA_ID>",
    "end_image_media_id": "<END_MEDIA_ID>",
    "prompt": "Move naturally from the first composition to the final composition",
    "project_id": "<FLOW_PROJECT_ID>",
    "scene_id": "scene-1",
    "model_family": "omni_flash",
    "duration_s": 8,
    "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
    "user_paygate_tier": "PAYGATE_TIER_ONE"
  }'
```

This submits through `batchAsyncGenerateVideoStartAndEndImage` and includes both `startImage` and `endImage` in the Flow request.

The First+Last model mapping is stored independently in `models.json`. The current default uses the same `abra_i2v_<duration>s` family as Omni First-frame generation. Keeping it as a separate mapping allows a one-line model-config update if Google changes the key during rollout.

## Reference-to-video

### Dedicated endpoint

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

Or use `POST /flow/generate-video-refs` with `model_family: "omni_flash"` and `duration_s`.

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

While rendering, FlowKit returns `status: "PENDING"`. Once `/v1/media/<primaryMediaId>` exposes a complete MP4 payload, it returns `MEDIA_GENERATION_STATUS_SUCCESSFUL` and the media ID. Set `include_encoded_video: true` only if you actually need the base64 MP4 inline; by default FlowKit avoids returning that large payload.

## Model keys

The duration mappings live in `agent/models.json`:

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

The values can be updated through `PATCH /api/models` if Google rotates Flow's internal model keys.

## Notes

Omni Flash is an unofficial Google Flow integration and its internal model keys/endpoints can change as Flow evolves. First-frame generation uses the wire-proven `abra_i2v_<duration>s` family and `batchAsyncGenerateVideoStartImage`. First+Last uses the same configurable Omni I2V family with `batchAsyncGenerateVideoStartAndEndImage`; this matches the current Flow UI capability while keeping the key isolated so it can be changed without another code release. Reference generation uses `abra_r2v_<duration>s` with `batchAsyncGenerateVideoReferenceImages`.

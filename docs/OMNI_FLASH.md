# Gemini Omni Flash

FlowKit can submit Gemini Omni Flash reference-to-video jobs through the same authenticated Chrome extension bridge used by the existing Google Flow integrations.

## Supported in this integration

- Reference-to-video with 1–7 reference images
- Portrait (`9:16`) and landscape (`16:9`)
- 4, 6, 8, and 10 second generations
- Existing `/flow/check-status` polling
- Existing Google Flow account / paygate tier handling

First + last frame interpolation is intentionally not enabled for Omni Flash here.

## REST API

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

Submit this body to `POST /flow/generate-video-refs`.

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

Omni Flash is an unofficial Google Flow integration and the underlying internal model keys/endpoints can change as Flow evolves. The request shape mirrors the Omni Flash implementation used by `crisng95/flowboard`: `batchAsyncGenerateVideoReferenceImages`, asset-typed `referenceImages`, V2 model config, and `BLOCK_SILENCED_VIDEOS` audio failure preference.

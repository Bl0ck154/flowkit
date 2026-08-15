# Headless 1080p upscale polling

Flow video upscales can return workflow descriptors such as:

```json
{
  "workflows": [
    {
      "name": "<workflow-id>",
      "metadata": {
        "primaryMediaId": "<source-media-id>_upsampled"
      }
    }
  ]
}
```

The legacy `batchCheckAsyncVideoGenerationStatus` and `/v1/media/{id}` paths can return `400 INVALID_ARGUMENT` for these workflow-backed outputs. Unlike Omni generation, the upsample workflow may also be absent from `flow.projectInitialData`.

FlowKit therefore provides an active redirect poller that probes the authenticated Flow UI endpoint directly:

`media.getMediaUrlRedirect?name=<primaryMediaId>`

A redirect to `https://flow-content.google/...` is treated as completion. The extension uses `responseMode: "url"`, so the video body is not buffered or copied through the WebSocket bridge.

## Usage

Submit the upscale as usual:

```bash
curl -sS http://127.0.0.1:8100/api/flow/upscale-video \
  -H 'Content-Type: application/json' \
  -d '{
    "media_id": "<completed-video-media-id>",
    "scene_id": "test-upscale",
    "resolution": "VIDEO_RESOLUTION_1080P",
    "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE"
  }'
```

Keep the returned `workflows` array. Poll it through the headless upscale endpoint:

```bash
curl -sS http://127.0.0.1:8100/api/flow/check-upscale-status \
  -H 'Content-Type: application/json' \
  -d '{
    "workflows": [
      {
        "name": "<workflow-id>",
        "metadata": {
          "primaryMediaId": "<source-media-id>_upsampled"
        }
      }
    ]
  }'
```

While the redirect is unavailable the response remains:

```json
{
  "done": false,
  "status": "PENDING",
  "workflows": [
    {
      "status": "PENDING",
      "probe": {
        "diagnostic": "media redirect not ready"
      }
    }
  ]
}
```

When Flow exposes the completed output:

```json
{
  "done": true,
  "status": "COMPLETED",
  "workflows": [
    {
      "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
      "media": {
        "media_id": "<source-media-id>_upsampled",
        "url": "https://flow-content.google/...",
        "resolved_via": "media.getMediaUrlRedirect"
      }
    }
  ]
}
```

Poll with bounded backoff and a caller-side timeout. Do not blindly resubmit an upscale while its outcome is unknown.

## Live verification needed

The implementation is intentionally isolated from the already verified Omni polling path. The key production check is whether Flow accepts the logical `<source-media-id>_upsampled` value directly in `media.getMediaUrlRedirect` once the 1080p upscale is ready.

If Flow uses a different resolved media name for upscales, the endpoint will remain `PENDING` and expose the probe diagnostics; capture that response before changing the polling contract.

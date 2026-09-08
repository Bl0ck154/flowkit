# Image generation, editing and high-resolution export

FlowKit's current image path runs on `flow.google.com` batchexecute. The public
REST surface deliberately exposes the choices that Flow exposes in its image
composer instead of hiding them in server configuration.

## Capabilities

```bash
curl -fsS http://127.0.0.1:8100/api/flow/image-capabilities
```

The response includes the current image model ids/aliases, all supported aspect
ratios, the generation-count range, and image export qualities. Model discovery
is cached for one hour and reads the currently loaded Flow frontend bundle.
Call with `?refresh=true` to force a rescan.

FlowKit also accepts a syntactically valid Flow image-model wire id even when it
has not appeared in this FlowKit release before. This is intentional: Google can
add a model without requiring a FlowKit code change. Known friendly aliases live
in `agent/models.json` and can still be hot-reloaded through `/api/models`.

Current live UI choices verified on the production Flow account:

- `GEM_PIX_2` / `NANO_BANANA_PRO` — Nano Banana Pro
- `NARWHAL` / `NANO_BANANA_2` — Nano Banana 2
- `HARBOR_SEAL` / `NANO_BANANA_2_LITE` — Nano Banana 2 Lite

## Generate images

```bash
curl -fsS -X POST http://127.0.0.1:8100/api/flow/generate-image \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "A glass greenhouse in soft morning fog",
    "project_id": "FLOW_PROJECT_UUID",
    "image_model": "NANO_BANANA_2",
    "aspect_ratio": "16:9",
    "count": 2
  }'
```

`image_model` may be a friendly configured alias or an exact Flow wire id.
`count` is `1..4`, matching the current Flow UI. FlowKit mirrors the UI exactly:
`count=N` dispatches N independent `ogiZ0b` requests, so every image gets its
own single-use reCAPTCHA token. FlowKit mirrors the current Flow UI launch
cadence (captured x4 at roughly 0.0 / 0.5 / 1.5 / 2.5 seconds) instead of
bursting every request at once; the generations still run concurrently after
submission. This matters for Nano Banana Pro, which rejects the unofficial
multi-item-in-one-RPC shape tolerated by Lite and is more prone to transient RPC
`[8]` failures under an artificial burst. An optional `seed` makes the first
request reproducible; subsequent variants use a deterministic seed stride.
`reference_media_ids` is the generic name for image
references; the older `character_media_ids` field remains accepted and the two
lists are de-duplicated.

Supported aspect ratios are exactly the five choices exposed by the current UI:

| Friendly | Current wire id | Observed source size |
|---|---|---:|
| `1:1` | `IMAGE_ASPECT_RATIO_SQUARE` | 1024×1024 |
| `9:16` | `IMAGE_ASPECT_RATIO_PORTRAIT` | 768×1376 |
| `16:9` | `IMAGE_ASPECT_RATIO_LANDSCAPE` | 1376×768 |
| `3:4` | `IMAGE_ASPECT_RATIO_PORTRAIT_THREE_FOUR` | 896×1200 |
| `4:3` | `IMAGE_ASPECT_RATIO_LANDSCAPE_FOUR_THREE` | 1200×896 |

The old FlowKit spelling `IMAGE_ASPECT_RATIO_PORTRAIT_FOUR_THREE` remains an
alias for 3:4 so existing integrations do not break.

## Real image edit

```bash
curl -fsS -X POST http://127.0.0.1:8100/api/flow/edit-image \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Change only the paper boat from red to blue",
    "source_media_id": "SOURCE_MEDIA_UUID",
    "project_id": "FLOW_PROJECT_UUID",
    "image_model": "GEM_PIX_2",
    "aspect_ratio": "16:9",
    "reference_media_ids": []
  }'
```

On the migrated transport the source is now encoded with Flow's distinct base
image input type, while extra identity/style images remain reference inputs.
This fixes the old migrated implementation, which mistakenly sent the source as
just another reference and therefore behaved like reference-conditioned fresh
generation rather than the editor's base-image flow.

## Export / upscale an image

Flow exposes generated images as 1K originals and synchronous 2K/4K high-
resolution downloads. FlowKit mirrors that operation through the current
`SPrCad` / `FlowService.UpsampleImage` RPC.

```bash
curl -fsS -X POST http://127.0.0.1:8100/api/flow/export-image \
  -H 'Content-Type: application/json' \
  -d '{
    "media_id": "GENERATED_IMAGE_MEDIA_UUID",
    "project_id": "FLOW_PROJECT_UUID",
    "quality": "2k"
  }' \
  -o image-2k.jpg
```

The endpoint returns the image bytes directly (`image/jpeg`). `2k` is the normal
high-resolution export. `4k` uses the same API but is plan-gated by Google Flow.
`POST /api/flow/upscale-image` is retained as a compatibility alias.

Live verification of the migrated 2K wire produced a **2752×1536 JPEG** from a
1376×768 source image.

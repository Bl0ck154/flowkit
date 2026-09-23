<p align="center">
  <img src="docs/images/flowkit_banner.svg" width="720" alt="FlowKit" />
</p>

<h1 align="center">FlowKit — Self-hosted API for Google Flow</h1>

<p align="center">
  Open-source REST API and automation layer for <b>Google Flow</b>:<br/>
  <b>Nano Banana image generation</b>, <b>Omni Flash / Veo video generation</b>, image-to-video, references, project automation, exports and polling.
</p>

<p align="center">
  <a href="https://github.com/Bl0ck154/flowkit/stargazers"><img src="https://img.shields.io/github/stars/Bl0ck154/flowkit?style=flat&logo=github" alt="GitHub stars"/></a>
  <a href="https://github.com/Bl0ck154/flowkit/commits/main"><img src="https://img.shields.io/github/last-commit/Bl0ck154/flowkit?logo=github" alt="Last commit"/></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"/></a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/FastAPI-self--hosted-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Google%20Flow-live%20tested-4285F4?logo=googlechrome&logoColor=white" alt="Google Flow live tested"/>
</p>

> [!IMPORTANT]
> This is an **actively maintained fork of [crisng95/flowkit](https://github.com/crisng95/flowkit)** focused on keeping the Google Flow integration working against live frontend/API changes and making Flow practical as a self-hosted server API. Upstream remains the original project and receives compatible fixes through pull requests when possible.

> [!NOTE]
> **FlowKit itself is free and open source. Google Flow generation is not necessarily free.** Your Google account, subscription tier and Flow credit limits still apply. FlowKit is unofficial and is not affiliated with or endorsed by Google.

## Why this fork exists

Google Flow does not expose a stable public automation API for these generation workflows. Its web app changes over time: RPC payloads, model identifiers, project lifecycle calls and browser-side state can move without notice.

This fork is maintained around that reality:

- **live compatibility fixes** based on current `flow.google.com` behavior;
- **self-hosted FastAPI endpoints** for server-side apps, bots and agents;
- automatic Flow project creation and short-lived session projects — no permanent `FLOW_PROJECT_ID` pin required;
- Nano Banana image generation, editing and export;
- Omni Flash text-to-video, first-frame, first+last-frame and reference-image video modes;
- Veo image-to-video support;
- real Flow credit balance / generation-cost metadata;
- persistent signed-in Chrome profile with automatic Flow tab recovery;
- generation throttling and circuit-breaker behavior for Google risk / unusual-activity responses;
- caller attribution and diagnostics for production integrations;
- regression tests built from live Flow request captures.

The goal is simple: **when Flow changes, fix the integration quickly and upstream the reusable parts.**

## Current status

**Last live validation: 2026-09-23.**

| Capability | Status |
|---|---|
| Nano Banana Pro image generation | ✅ Live tested |
| Nano Banana 2 image generation | ✅ Live tested |
| Nano Banana 2 Lite wire support | ✅ Supported |
| Image references / base-image editing | ✅ Supported |
| Image export | ✅ 2K; 4K where the account/plan allows it |
| Omni Flash text-to-video | ✅ 4 / 6 / 8 / 10 s, 360p / 720p |
| Omni Flash first-frame video | ✅ Live tested |
| Omni Flash first + last frame | ✅ Supported |
| Omni Flash reference / ingredients video | ✅ Supported |
| Veo image-to-video | ✅ Supported |
| Video export / upscale | ✅ 1080p; higher modes depend on Flow/account support |
| Flow project creation | ✅ Automatic |
| Session-scoped projects | ✅ Automatic rotation after idle period |
| Account / credit inspection | ✅ Supported |
| Server REST API | ✅ FastAPI |

Flow changes frequently. If a mode breaks, check the latest commits/issues before assuming your account is blocked.

## What FlowKit actually does

FlowKit runs a local/server FastAPI service next to a persistent Chrome session signed into Google Flow.

```text
┌───────────────────────┐       REST        ┌────────────────────────┐
│ Your app / bot / agent│ ────────────────► │ FlowKit FastAPI        │
└───────────────────────┘                   │ 127.0.0.1:8100         │
                                            └───────────┬────────────┘
                                                        │ WebSocket / CDP
                                                        ▼
                                            ┌────────────────────────┐
                                            │ Chrome + Flow bridge   │
                                            │ signed-in Flow session │
                                            └───────────┬────────────┘
                                                        │
                                                        ▼
                                            ┌────────────────────────┐
                                            │ flow.google.com        │
                                            │ batchexecute / media   │
                                            └────────────────────────┘
```

The browser keeps the authenticated Flow session and page state. FlowKit turns that into a usable local/server API for other software.

## Quick start

### 1. Clone this maintained fork

```bash
git clone https://github.com/Bl0ck154/flowkit.git
cd flowkit
```

### 2. Install

```bash
./setup.sh
```

Or install the Python dependencies manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

You also need Chrome/Chromium and `ffmpeg` for the full media pipeline.

### 3. Load the Chrome extension

Open:

```text
chrome://extensions
```

Enable **Developer mode** → **Load unpacked** → select `extension/`.

Then open `https://flow.google.com/` and sign in to the Google account you want FlowKit to use.

### 4. Start FlowKit

```bash
source venv/bin/activate
python -m agent.main
```

Default API:

```text
http://127.0.0.1:8100
```

Check it:

```bash
curl http://127.0.0.1:8100/health
curl http://127.0.0.1:8100/api/flow/status
```

You **do not need to manually pin one permanent Flow project** for normal direct API usage. FlowKit can create and rotate session projects itself, while callers can still explicitly reuse an existing `project_id` when they need long-lived project context.

## API examples

### Generate an image — Nano Banana

```bash
curl -X POST http://127.0.0.1:8100/api/flow/generate-image \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "cinematic product photo of a red ceramic mug on a white table",
    "image_model": "NANO_BANANA_2",
    "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
    "count": 1
  }'
```

Available configured image families include:

```text
NANO_BANANA_PRO
NANO_BANANA_2
NANO_BANANA_2_LITE
```

See [`docs/IMAGE_API.md`](docs/IMAGE_API.md) for image references, editing, aspect ratios and export.

### Omni Flash text-to-video

```bash
curl -X POST http://127.0.0.1:8100/api/flow/generate-video-omni-text \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "slow cinematic camera push toward a coffee cup by a rainy window",
    "duration_s": 4,
    "resolution": "360p",
    "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE"
  }'
```

### Upload an image

For **external/API callers**, send the image bytes directly. Do not pass a path from the caller's filesystem: `flowkit-agent.service` runs as its own `flowkit` user and uses systemd isolation such as `PrivateTmp=yes`, so caller-local `/tmp/...`, `/root/...` and other protected paths may not exist or be readable inside the service.

#### Recommended: multipart file upload

```bash
curl -X POST http://127.0.0.1:8100/api/flow/upload-image-file \
  -F 'file=@./source.jpg;type=image/jpeg'
```

You can optionally pass an existing Flow project:

```bash
curl -X POST http://127.0.0.1:8100/api/flow/upload-image-file \
  -F 'file=@./source.jpg;type=image/jpeg' \
  -F 'project_id=YOUR_FLOW_PROJECT_ID'
```

If `project_id` is omitted, FlowKit automatically uses/creates the current session project.

#### JSON/base64 upload

Useful when your client already transports JSON:

```bash
IMAGE_B64="$(base64 -w0 ./source.jpg)"
curl -X POST http://127.0.0.1:8100/api/flow/upload-image \
  -H 'Content-Type: application/json' \
  -d "{\"image_base64\":\"$IMAGE_B64\",\"mime_type\":\"image/jpeg\",\"file_name\":\"source.jpg\"}"
```

Base64 is supported for compatibility and JSON-only clients, but expands the request by roughly one third compared with multipart.

#### Server-local `file_path` mode

`file_path` remains available as a convenience **only when the image already exists on the FlowKit server** and is readable by the `flowkit` service user:

```bash
curl -X POST http://127.0.0.1:8100/api/flow/upload-image \
  -H 'Content-Type: application/json' \
  -d '{
    "file_path": "/var/lib/flowkit/imports/source.jpg",
    "file_name": "source.jpg"
  }'
```

Do not use caller-local `/tmp/...` paths for this mode. With systemd `PrivateTmp=yes`, the FlowKit service sees a different `/tmp` namespace. Unreadable paths return a clear 403, and paths not visible in the service namespace return a descriptive 404 instead of an internal traceback.

The response contains a Flow `media_id` and the resolved `project_id`, both of which can be reused for later generation.

### Image-to-video with Omni Flash

```bash
curl -X POST http://127.0.0.1:8100/api/flow/generate-video \
  -H 'Content-Type: application/json' \
  -d '{
    "start_image_media_id": "YOUR_MEDIA_ID",
    "scene_id": "demo-scene",
    "prompt": "slow camera pan, natural subtle motion",
    "model_family": "omni_flash",
    "duration_s": 4,
    "resolution": "360p",
    "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE"
  }'
```

For first+last frame and multi-reference / Ingredients modes, see [`docs/OMNI_FLASH.md`](docs/OMNI_FLASH.md).

### Read the active Google account

```bash
curl http://127.0.0.1:8100/api/flow/account
```

### Read Flow credits

```bash
curl http://127.0.0.1:8100/api/flow/credits
```

Force a visible Flow balance refresh:

```bash
curl 'http://127.0.0.1:8100/api/flow/credits?refresh=true'
```

Generation responses can also include the current balance, estimated generation cost and estimated remaining balance.

## Project lifecycle

Older FlowKit versions commonly relied on one permanently pinned `FLOW_PROJECT_ID`. That becomes increasingly awkward for server workloads because unrelated jobs accumulate in the same Flow project.

This fork supports both patterns:

- **no `project_id` supplied** → FlowKit uses a session project and rotates it after idle time;
- **explicit `project_id` supplied** → FlowKit reuses that exact Flow project;
- higher-level applications can persist an order/job → Flow project mapping and reopen it days later for revisions.

This makes the API suitable for queues, ecommerce workflows, bots and other multi-job systems without losing the ability to return to old Flow projects.

## Production behavior

FlowKit includes several safeguards for unattended server use:

- generation submissions are serialized by default;
- minimum spacing between generation launches;
- `PUBLIC_ERROR_UNUSUAL_ACTIVITY` is treated as a terminal/risk response instead of being blindly retried;
- a short local circuit breaker prevents a failing caller from hammering Flow;
- optional `X-FlowKit-Caller` identifies the integration that triggered a request without logging prompts or media contents;
- `/api/flow/status` exposes generation-guard and session state;
- the Flow tab can close after idle time and be reopened using the persistent browser profile when needed.

## Live API compatibility

Flow's internal request shapes are positional and can change. This fork keeps captured request builders and regression tests for the modes it automates.

Recent examples of live fixes include:

- current Flow project creation RPC;
- Omni Flash 360p model / option slots;
- updated first-frame full-frame crop structure;
- trusted browser interaction for media selection and generation recovery;
- image upload by direct bytes for external callers;
- credit/account visibility and generation-cost estimates.

The capture methodology is documented in [`docs/CAPTURE.md`](docs/CAPTURE.md).

## Dashboard and full video pipeline

FlowKit is more than the low-level API. The repository also contains the original project/dashboard pipeline for multi-scene generation, references, review and post-processing.

<p align="center">
  <img src="docs/images/dashboard_overview.png" width="760" alt="FlowKit dashboard" />
</p>

The low-level REST API can be used independently by your own application, while the higher-level pipeline remains available for larger video workflows.

## Maintained fork vs upstream

This repository started as a fork of **[crisng95/flowkit](https://github.com/crisng95/flowkit)** and keeps the MIT license and upstream attribution.

The projects currently have different maintenance focuses:

| This fork | Upstream |
|---|---|
| Fast live fixes for `flow.google.com` request changes | Original project and broader pipeline direction |
| Server/API integrations and production diagnostics | Video-review/provider tooling and general project features |
| Project/session lifecycle automation | Upstream baseline architecture |
| Credit/account inspection | Original documentation and ecosystem |
| Compatibility patches are submitted upstream when portable | Reviews/merges compatible contributions |

This is **not** intended to erase or replace upstream credit. If you need the original project, use upstream. If you want the compatibility-focused version actively run and updated against live Flow, use this fork.

Current upstream compatibility work is also submitted back through pull requests where practical.

## Automatic compatibility monitoring

Every normal trusted-UI generation now doubles as a **zero-extra-credit compatibility check**. FlowKit captures the actual `f.req` sent by the current Flow UI, strips prompts, media/project IDs, UUIDs, reCAPTCHA/opaque values and random seeds, then compares the remaining structure with the request builder that initiated the job.

`GET /api/flow/status` exposes the latest sanitized `payload_drift` state. Structural changes such as a moved crop slot, changed client descriptor or new resolution flag are logged as `PAYLOAD_DRIFT` without storing the sensitive request payload.

Near-term roadmap:

- automated regression-test / patch branches for simple, whitelisted wire-format changes;
- optional GitHub PR creation when a safe structural patch is inferred and the full suite passes;
- safer periodic upstream syncs without overwriting fork-specific server features.

The goal is to turn a future Flow frontend change from “the API is broken” into “FlowKit detected payload drift and has a tested compatibility patch ready.”

## Search keywords / use cases

FlowKit is relevant if you are looking for a:

- Google Flow API / unofficial Google Flow API;
- self-hosted Google Flow server;
- Nano Banana API or Nano Banana self-hosted automation layer;
- Omni Flash API / Omni image-to-video API;
- Veo image-to-video automation;
- AI image generation REST API;
- AI video generation REST API;
- local FastAPI bridge for Google Flow;
- server-side Flow automation for bots, agents or ecommerce pipelines.

## Important limitations

- This uses **unofficial web interfaces**, not a stable public Google API.
- Google may change Flow without notice.
- A signed-in Google Flow browser session is required.
- Your Google subscription, credit balance, model availability and regional limits still apply.
- Do not treat local cost estimates as billing guarantees; Flow remains authoritative.
- Respect Google's terms and any applicable content/usage policies.

## Contributing

Compatibility reports are most useful when they include:

- FlowKit commit SHA;
- endpoint/mode that failed;
- HTTP/error code;
- whether the same action works manually in the Flow UI;
- sanitized structural differences only — **never post cookies, auth tokens or reCAPTCHA tokens**.

If you capture a changed Flow request shape, add a regression test with the fix so the same drift does not return silently.

## Upstream

Original project: **[crisng95/flowkit](https://github.com/crisng95/flowkit)**

Thanks to the original author and contributors for the architecture this fork builds on.

## License

MIT — see [`LICENSE`](LICENSE).

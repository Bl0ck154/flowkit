# fk-provider — Media providers: choose the generation backend

FlowKit is provider-neutral. A **media provider** is the backend that renders
media: `flow` (Google Flow via the Chrome extension), `assistant` (Muse or any
HTTP-capable external worker), `muse2api` (muse.ai through a
[muse2api](https://github.com/crisng95/muse2api) gateway), or any future
registered provider.

Every generation request, thumbnail, and TTS call accepts an optional
`provider`. Omit it and the server default (`DEFAULT_PROVIDER`, usually
`flow`) is used.

## Check status

```bash
curl -s http://127.0.0.1:8100/api/providers/status | python3 -m json.tool
# {"default": "flow", "providers": {"flow": {"available": true, ...},
#                                   "assistant": {"available": true, ...}}}
```

`flow.available` is true only while the Chrome extension is connected.
`assistant.available` is true when the provider is registered — it needs no
Chrome, but it needs a **worker** (below) to actually do the work.

## Per-request provider

Add `"provider"` to any item in `/api/requests` or `/api/requests/batch`:

```bash
curl -X POST http://127.0.0.1:8100/api/requests/batch \
  -H "Content-Type: application/json" \
  -d '{"requests": [
    {"type": "GENERATE_VIDEO", "scene_id": "<SID>", "project_id": "<PID>",
     "video_id": "<VID>", "orientation": "VERTICAL", "provider": "assistant"}
  ]}'
```

Generation skills (`/fk-gen-images`, `/fk-gen-videos`, `/fk-gen-refs`,
`/fk-gen-chain-videos`, `/fk-thumbnail`) accept `[--provider <name>]` and pass
it through the same way.

Thumbnail: `POST /api/projects/<PID>/generate-thumbnail`
`{"prompt": "...", "provider": "assistant"}`.

TTS: `POST /api/tts/generate` `{"text": "...", "provider": "assistant"}`.
(`"provider": "local"` or omitted = the bundled TTS engine. `flow` cannot do
audio — it is rejected with 400.)

## Capabilities differ per provider

- `flow`: image, edit_image, i2v (image-to-video), r2v, upscale. **No audio.**
- `assistant`: image, edit_image, i2v, r2v, **audio (TTS)**. No upscale.
- `muse2api`: image, i2v. No edit_image, upscale or audio. No end frame and no
  r2v unless `MUSE2API_ALLOW_DEGRADED=1` (then both render as plain i2v).
  Entity reference images are sent with scene images (up to four; an
  unreadable ref fails the job).

Asking a provider for a kind it doesn't support returns 400 with a message
naming the right backend to use instead.

## The muse2api provider needs a gateway

`muse2api` calls a running [muse2api](https://github.com/crisng95/muse2api)
service over HTTP — Flow Kit → `Muse2APIProvider` → muse2api → muse.ai. The
gateway owns the muse.ai accounts, failover and cooldowns; Flow Kit only needs
its URL and key:

```bash
# muse2api side (its own repo): python -m muse2api  →  http://127.0.0.1:18610
export MUSE2API_URL=http://127.0.0.1:18610
export MUSE2API_KEY=<the gateway's MUSE2API_API_KEY>   # data/api_key if auto-generated
# optional: DEFAULT_PROVIDER=muse2api to make it the default backend
```

`muse2api.available` is true once `MUSE2API_URL` is set. Check the gateway
itself with `curl -s $MUSE2API_URL/readyz` — `accounts.available: 0` means
every request will fail `no_account_available` (import an account on the
gateway via its `/admin/accounts`).

Output is downloaded into `output/_shared/muse2api/` and stored as `file://`
URLs, so like the assistant it never needs `/fk-refresh-urls`.

| Error (request `error_message`) | Meaning | Fix |
|---|---|---|
| `muse2api provider is not configured` | `MUSE2API_URL` unset | set it and restart the server |
| `muse2api connection_error` | gateway not reachable | start muse2api / fix the URL |
| `muse2api invalid_api_key (HTTP 401)` | wrong key | use the gateway's `MUSE2API_API_KEY` |
| `muse2api no_account_available (HTTP 503)` | no usable muse.ai account | add/renew accounts on the gateway |
| `muse2api upstream_quota_exhausted (HTTP 429)` | account out of quota | wait for cooldown or add accounts |
| `muse2api has no end-frame input` | chained scene | `MUSE2API_ALLOW_DEGRADED=1`, or use `flow` |

## The assistant provider needs a worker

When a request uses `provider: assistant`, the server creates a **provider
job** (`POST /api/provider-jobs`) and waits for an external worker to claim
and complete it. No worker = the request sits in PROCESSING until the job
times out.

Run the reference worker (it shells out to whatever CLI you configure —
see the top of `agent/worker/assistant_worker.py`):

```bash
cd ~/workspace/flowkit
.venv/bin/python agent/worker/assistant_worker.py \
  --api http://127.0.0.1:8100 --provider assistant --worker-id w1
```

Worker protocol (full spec in the module docstring):

1. `GET /api/provider-jobs/wait-next?provider=assistant&worker_id=w1&timeout_s=60`
   — long-polls and atomically claims the next job (lease granted).
2. `POST /api/provider-jobs/{id}/heartbeat` `{"worker_id": "w1"}`
   — every ~lease/3 while working (default lease 300s).
3. `POST /api/provider-jobs/{id}/progress` `{"worker_id": "w1", "progress": 50}`
   — optional.
4. `POST /api/provider-jobs/{id}/complete`
   `{"worker_id": "w1", "result": {"output_url": "file:///...", "media_id": "<uuid>"}}`
   — or `/fail` `{"worker_id": "w1", "error": "..."}`.

Only the lease holder may heartbeat/progress/complete/fail; strangers get
409. complete/fail are idempotent for the holder (safe to retry after a lost
response). `output_url` should be `file://` or `https://` — the server copies
it into the project output dir.

## Provider jobs: inspect and troubleshoot

```bash
# list recent jobs for a provider
curl -s "http://127.0.0.1:8100/api/provider-jobs?provider=assistant&limit=20" | python3 -m json.tool
# wait for one job to finish (server-side long poll)
curl -s "http://127.0.0.1:8100/api/provider-jobs/<JOB_ID>/wait?timeout_s=600"
```

| Symptom | Meaning | Fix |
|---|---|---|
| Job stuck `QUEUED` | no worker running | start `assistant_worker.py` |
| Job stuck `CLAIMED`/`RUNNING`, no heartbeat | worker died | wait for lease expiry (~5 min), another worker reclaims it |
| `409` on complete/fail | not the lease holder, or job already terminal | check `claimed_by` on the job row |
| Request `PROCESSING` forever, job `FAILED` | worker reported an error | read `error_message` on the job row |
| `400 unknown provider` | typo or unregistered name | use a name from `/api/providers/status` |
| `400 provider 'flow' does not support audio` | TTS via flow | use `assistant` or `local` |

## Local URLs never expire

Assistant-provider output is stored as `file://` URLs on the server. Unlike
Flow's signed GCS URLs, these never expire — **skip `/fk-refresh-urls`**
entirely for assistant-generated media. (The skill itself no-ops when it
finds only local URLs.)

## Adding a new provider

1. Subclass `MediaProvider` in `agent/sdk/services/` (see
   `assistant_provider.py` for the DB-backed reference).
2. Declare `name` and `capabilities` (which kinds it supports).
3. Register it in the provider registry (`agent/sdk/services/registry.py`
   docstring) and add the name to `config`.
4. If it needs an external worker, speak the provider-job protocol above —
   `assistant_worker.py` is the reference implementation.

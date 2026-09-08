"""Current Google Flow image capabilities with forward-compatible model discovery."""

from __future__ import annotations

import asyncio
import re
import time
import urllib.request
from typing import Any

from agent import config
from agent.services import flow_batch as fb
from agent.services.browser_session import _evaluate, _targets

_CACHE_TTL_S = 3600
_cache: tuple[float, set[str]] | None = None

# The frontend ships one compact list used for current image-family handling.
# Parsing this instead of the giant model enum avoids advertising historical
# model ids that are present in the JS but no longer selectable in Flow.
_MODEL_LIST_RE = re.compile(
    r'"((?:[A-Z][A-Z0-9_]+(?: [A-Z][A-Z0-9_]+){2,}))"\.split\(" "\)'
)
_MODEL_SENTINELS = {"GEM_PIX_2", "NARWHAL"}
_IGNORED_DISCOVERED_PARTS = ("_VERTEX", "_UPSAMPLE_")

_KNOWN_LABELS = {
    "GEM_PIX_2": "Nano Banana Pro",
    "NARWHAL": "Nano Banana 2",
    "HARBOR_SEAL": "Nano Banana 2 Lite",
}


def _read_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "FlowKit capability scanner"})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(16_000_000)
    return raw.decode("utf-8", "ignore")


def _extract_models(source: str) -> set[str]:
    out: set[str] = set()
    for match in _MODEL_LIST_RE.finditer(source):
        group = set(match.group(1).split())
        if not _MODEL_SENTINELS.issubset(group):
            continue
        for model_id in group:
            if any(part in model_id for part in _IGNORED_DISCOVERED_PARTS):
                continue
            if fb.IMAGE_MODEL_ID_RE.fullmatch(model_id):
                out.add(model_id)
    return out


async def discover_frontend_image_models(*, refresh: bool = False) -> set[str]:
    """Discover current selectable-family wire ids from the loaded Flow bundle.

    This is best-effort and cached. Generation itself does not depend on this
    scan: any syntactically valid wire id is passed through by
    :func:`flow_batch.resolve_image_model`, so a newly added Flow model can be
    used immediately even before this discovery endpoint learns its friendly
    label.
    """
    global _cache
    now = time.monotonic()
    if not refresh and _cache and now - _cache[0] < _CACHE_TTL_S:
        return set(_cache[1])

    urls: list[str] = []
    try:
        flow_pages = [
            target for target in await _targets()
            if target.get("type") == "page"
            and str(target.get("url", "")).startswith("https://flow.google.com/")
            and target.get("webSocketDebuggerUrl")
        ]
        target = next((p for p in flow_pages if "/project/" in p.get("url", "")), None)
        target = target or (flow_pages[0] if flow_pages else None)
        if target:
            value = await _evaluate(
                target["webSocketDebuggerUrl"],
                "performance.getEntriesByType('resource').map(x=>x.name).filter(x=>x.includes('gstatic.com/_/mss/')||x.includes('/_/js/'))",
                timeout=10,
            )
            if isinstance(value, list):
                urls = list(dict.fromkeys(str(item) for item in value if isinstance(item, str)))[:24]
    except Exception:
        urls = []

    discovered: set[str] = set()
    for url in urls:
        try:
            source = await asyncio.to_thread(_read_url, url)
        except Exception:
            continue
        discovered.update(_extract_models(source))

    _cache = (now, set(discovered))
    return discovered


async def image_capabilities(*, refresh: bool = False) -> dict[str, Any]:
    discovered = await discover_frontend_image_models(refresh=refresh)
    configured: dict[str, str] = {
        str(alias): str(model_id) for alias, model_id in config.IMAGE_MODELS.items()
    }
    aliases_by_id: dict[str, list[str]] = {}
    for alias, model_id in configured.items():
        aliases_by_id.setdefault(model_id, []).append(alias)

    fallback_models = set(fb.IMAGE_MODELS) | set(configured.values())
    models = []
    for model_id in sorted(discovered | fallback_models):
        models.append({
            "id": model_id,
            "label": _KNOWN_LABELS.get(model_id, model_id),
            "aliases": sorted(aliases_by_id.get(model_id, [])),
            "configured": model_id in configured.values(),
            "discovered": model_id in discovered,
        })

    default_id = fb.resolve_image_model(
        configured.get(config.DEFAULT_IMAGE_MODEL, config.DEFAULT_IMAGE_MODEL)
    )
    aspects = [
        {
            "ratio": ratio,
            "id": spec[0],
            "wire_value": spec[1],
            "observed_size": {"width": spec[2][0], "height": spec[2][1]},
        }
        for ratio, spec in fb.IMAGE_ASPECTS.items()
    ]
    return {
        "models": models,
        "default_model": default_id,
        "model_passthrough": True,
        "model_discovery": "live_flow_frontend_with_cached_fallback",
        "aspect_ratios": aspects,
        "count": {"min": 1, "max": 4, "default": 1},
        "upscale": {
            "original": "1K",
            "targets": [
                {"quality": "2K", "plan_gated": False},
                {"quality": "4K", "plan_gated": True},
            ],
        },
    }

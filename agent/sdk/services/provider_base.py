"""Media provider abstraction — FlowKit works with any generation backend.

A :class:`MediaProvider` executes one :class:`ProviderJob` and returns a
result dict in the same shape the rest of the pipeline already understands::

    {"data": {...}}   on success
    {"error": "..."}  on failure

Two provider flavours exist:

* **direct** (e.g. Google Flow) — submits to the backend and waits for the
  result inside the worker process.
* **delegated** (e.g. a Muse agent or any external AI agent) — the provider
  publishes the job to the provider-job queue; an external worker claims it
  via the HTTP API, renders, and posts the result back.

``OperationService`` never talks to a backend directly — it builds a
:class:`ProviderJob` (backend-agnostic inputs) plus backend-specific knobs in
``job.extra``, resolves the provider for the request, and calls
``provider.run(job)``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Job kinds ──────────────────────────────────────────────────────────────
KIND_IMAGE = "image"            # prompt (+refs) -> image  (scene / reference)
KIND_EDIT_IMAGE = "edit_image"  # source image + prompt -> edited image
KIND_VIDEO = "video"            # start image (+end) -> video  (i2v)
KIND_VIDEO_REFS = "video_refs"  # reference images -> video  (r2v)
KIND_UPSCALE = "upscale"        # video -> upscaled video
KIND_AUDIO = "audio"            # text (+voice hints) -> speech audio (TTS)

_ALL_KINDS = (KIND_IMAGE, KIND_EDIT_IMAGE, KIND_VIDEO, KIND_VIDEO_REFS,
              KIND_UPSCALE, KIND_AUDIO)


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a provider can do, plus its own throttling limits.

    Throttling is per-provider: the worker reads these instead of the old
    global MAX_CONCURRENT_REQUESTS / API_COOLDOWN.
    """

    generate_image: bool = True
    edit_image: bool = True
    generate_video_i2v: bool = True
    generate_video_r2v: bool = True
    upscale: bool = False
    generate_audio: bool = False
    max_concurrent: int = 5
    cooldown_s: float = 0.0

    def supports(self, kind: str) -> bool:
        return {
            KIND_IMAGE: self.generate_image,
            KIND_EDIT_IMAGE: self.edit_image,
            KIND_VIDEO: self.generate_video_i2v,
            KIND_VIDEO_REFS: self.generate_video_r2v,
            KIND_UPSCALE: self.upscale,
            KIND_AUDIO: self.generate_audio,
        }.get(kind, False)


@dataclass
class ProviderJob:
    """One unit of generation work, described backend-agnostically.

    ``extra`` carries backend-specific knobs the generic fields cannot
    express.  Convention for the built-in providers:

    * flow:      project_id, tier, aspect, character_media_ids,
                 source_media_id, start_media_id, end_media_id,
                 ref_media_ids, request_id, scene_id
    * assistant: scene_id, project_id, project_name, display_order,
                 reference_names, entity_name, entity_type, composition
    """

    job_id: str
    kind: str
    prompt: str = ""
    orientation: str = "VERTICAL"  # "VERTICAL" | "HORIZONTAL"
    source_url: Optional[str] = None      # edit_image input
    start_url: Optional[str] = None       # video start frame
    end_url: Optional[str] = None         # video end frame (chained)
    reference_urls: tuple = ()            # consistency references
    duration_s: Optional[float] = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in _ALL_KINDS:
            raise ValueError(f"Unknown provider job kind: {self.kind!r}")


class MediaProvider(ABC):
    """Abstract generation backend."""

    name: str = "base"
    display_name: str = "Base provider"
    capabilities: ProviderCapabilities = ProviderCapabilities()

    @abstractmethod
    async def run(self, job: ProviderJob) -> dict:
        """Execute one job. Returns {"data": ...} or {"error": ...}."""

    def is_available(self) -> bool:
        """Whether this provider can currently run jobs.

        Flow needs the Chrome extension connected; the assistant is
        always available (filesystem bridge, no credentials).
        """
        return True

    def check(self, job: ProviderJob) -> Optional[str]:
        """Return an error string if this provider cannot run the job."""
        if not self.capabilities.supports(job.kind):
            return (
                f"Provider '{self.name}' does not support "
                f"job kind '{job.kind}'"
            )
        return None

    def needs_media_id_registration(self) -> bool:
        """Whether generated outputs must be registered back to obtain a
        provider media id (Flow needs this; UUID-minting providers don't)."""
        return False

    async def register_existing_image(
        self, url: str, *, name: str = "", project_id: str = ""
    ) -> dict:
        """Turn an already-existing image URL into a provider media id.

        Used by the reference-image fast path ("image exists, just needs an
        id").  Providers that have no id concept may mint a UUID.
        """
        raise NotImplementedError(f"{self.name} has no register_existing_image")

"""Standalone provider registry.

The registry owns all registered :class:`MediaProvider` backends and is
shared between the SDK (``OperationService``) and the HTTP layer
(``/api/providers/status``), so provider discovery and health reporting do
not depend on having an ``OperationService`` instance around.

Built-ins:
    - ``flow`` — Google Flow via the Chrome extension + FlowClient.
      Only available when the extension is connected.
    - ``assistant`` — the local assistant (e.g. Pax/Muse) via the persistent
      provider-job queue (``provider_job`` table + ``/api/provider-jobs``).
      Always available, needs no Chrome.
    - ``muse2api`` — a muse2api gateway (muse.ai behind an OpenAI-compatible
      API) over HTTP. Available once ``MUSE2API_URL`` is set.

Extra backends (a Sora adapter, a local SDXL worker, …) can be registered
at startup and are then selectable per request through the ``provider``
field on requests / the ``DEFAULT_PROVIDER`` config.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent.config import DEFAULT_PROVIDER
from agent.sdk.services.assistant_provider import AssistantProvider
from agent.sdk.services.flow_provider import FlowProvider
from agent.sdk.services.muse2api_provider import Muse2APIProvider
from agent.sdk.services.provider_base import MediaProvider

if TYPE_CHECKING:
    from agent.services.flow_client import FlowClient

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Owns the set of available media providers."""

    def __init__(
        self,
        flow_client: "FlowClient | None" = None,
        extra: dict[str, MediaProvider] | None = None,
    ):
        providers: dict[str, MediaProvider] = {}
        if flow_client is not None:
            providers["flow"] = FlowProvider(flow_client)
        providers["assistant"] = AssistantProvider()
        providers["muse2api"] = Muse2APIProvider()
        if extra:
            providers.update(extra)
        self._providers = providers

    @property
    def providers(self) -> dict[str, MediaProvider]:
        return self._providers

    def names(self) -> list[str]:
        return list(self._providers)

    def get(self, name: str | None) -> MediaProvider | None:
        key = (name or "").strip().lower()
        return self._providers.get(key)

    def register(self, name: str, provider: MediaProvider) -> None:
        """Add or replace a provider backend."""
        self._providers[name.strip().lower()] = provider

    def resolve(self, name: str | None = None) -> MediaProvider:
        """Resolve a provider by name, falling back to the configured default."""
        key = (name or DEFAULT_PROVIDER).strip().lower()
        provider = self._providers.get(key)
        if provider is None:
            logger.warning(
                "Unknown provider '%s', falling back to default '%s'",
                key, DEFAULT_PROVIDER,
            )
            provider = self._providers.get(DEFAULT_PROVIDER)
        if provider is None:
            # Last resort: any provider at all.
            provider = next(iter(self._providers.values()))
        return provider

    def status(self) -> list[dict]:
        """Serializable status for every registered provider.

        Used by ``GET /api/providers/status``.
        """
        out = []
        for name, provider in self._providers.items():
            caps = provider.capabilities
            out.append({
                "name": name,
                "display_name": getattr(provider, "display_name", name),
                "available": provider.is_available(),
                "capabilities": {
                    "generate_image": caps.generate_image,
                    "edit_image": caps.edit_image,
                    "generate_video_i2v": caps.generate_video_i2v,
                    "generate_video_r2v": caps.generate_video_r2v,
                    "upscale": caps.upscale,
                    "max_concurrent": caps.max_concurrent,
                    "cooldown_s": caps.cooldown_s,
                },
            })
        return out
